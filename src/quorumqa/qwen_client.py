import json
import re
from dataclasses import dataclass

import requests

from quorumqa.config import TOKEN_PLAN_API_KEY, TOKEN_PLAN_BASE_URL
from quorumqa.schemas import CallUsage

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass
class JsonCallResult:
    data: dict
    usage: CallUsage


def _loads_tolerant(payload: str) -> dict | list:
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        if "Invalid \\escape" not in exc.msg:
            raise
        # GPQA answers are full of LaTeX (\Delta, \mu, \text{...}); models
        # faithfully reproduce it inside JSON strings, where a lone
        # backslash before anything but ["\\/bfnrtu] is illegal JSON.
        # Fix per RUN of backslashes (a char-by-char sub would turn \\\d
        # into a new invalid escape): an odd-length run followed by a
        # non-escape char gains one backslash, making the whole run
        # escaped-backslashes. Deterministic, lossless.
        def _fix_run(m: re.Match) -> str:
            run = m.group(0)
            nxt = m.string[m.end() : m.end() + 1]
            if len(run) % 2 == 1 and nxt not in '"\\/bfnrtu':
                return run + "\\"
            return run

        sanitized = re.sub(r"\\+", _fix_run, payload)
        return json.loads(sanitized)


def _extract_json(text: str) -> dict:
    fenced = _FENCE_RE.search(text)
    candidate = (fenced.group(1) if fenced else text).strip()
    # Output that IS an array (e.g. a bare claims list) must take the
    # array-wrap path first -- otherwise object-extraction would grab just
    # the first element of a single-item array.
    if candidate.startswith("["):
        parsed = _loads_tolerant(candidate[: candidate.rfind("]") + 1])
        if isinstance(parsed, list):
            return {"items": parsed}
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        return _loads_tolerant(candidate[start : end + 1])
    # Models sometimes answer a "list of claims" prompt with a bare JSON
    # array (e.g. '[]' when there is nothing to report) -- wrap it instead
    # of failing, callers read it via the "items" key.
    astart = candidate.find("[")
    aend = candidate.rfind("]")
    if astart != -1 and aend != -1 and aend > astart:
        parsed = _loads_tolerant(candidate[astart : aend + 1])
        if isinstance(parsed, list):
            return {"items": parsed}
    raise ValueError(f"No JSON object found in model output: {text[:300]!r}")


class QwenClient:
    """Thin wrapper around the Token Plan's Anthropic-Messages-API-compatible
    endpoint (migrated from the pay-as-you-go DashScope OpenAI-compatible
    endpoint 2026-07-21 -- see config.py's TOKEN_PLAN_* constants for why the
    two are not interchangeable).

    Kept deliberately independent of any specific structured-output feature
    -- every JSON call asks for JSON in the prompt and parses defensively, so
    it works the same way regardless of what the currently deployed model
    actually honors. The public chat()/chat_json() signatures are unchanged
    from the pre-migration client, so solver.py/skeptic.py/verifier.py/
    judge.py/baseline.py needed zero changes -- none of them touch API-shape
    details, tool-calling included (the Verifier's "tool calls" are plain
    JSON-mode prompting plus a direct Python call to the real MCP server,
    never the model API's native tool-use protocol either).
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._api_key = api_key or TOKEN_PLAN_API_KEY
        self._messages_url = (base_url or TOKEN_PLAN_BASE_URL).rstrip("/") + "/v1/messages"

    def chat(
        self,
        model: str,
        messages: list[dict],
        role: str,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        thinking: bool = True,
        seed: int | None = None,
        thinking_budget: int | None = None,
    ) -> tuple[str, CallUsage]:
        # Anthropic Messages API takes system as a top-level field, not a
        # "system"-role entry in messages -- split it out here so every
        # caller (chat_json below) can keep building messages the OpenAI way.
        system = None
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system = (system + "\n\n" + m["content"]) if system else m["content"]
            else:
                chat_messages.append(m)

        body = {"model": model, "max_tokens": max_tokens, "temperature": temperature, "messages": chat_messages}
        if system:
            body["system"] = system
        # Qwen3 hybrid models think by default, billing reasoning tokens as
        # output. Cheap fast-voter roles (solvers/skeptic/verifier) disable
        # it via the real Anthropic-style {"type": "disabled"} shape (the
        # DashScope-style enable_thinking:false flag this client used to
        # send is silently ignored here -- verified live, the response still
        # came back with a thinking block) -- three thinking "cheap" calls
        # otherwise cost more than one flagship call, inverting the engine's
        # whole economic premise.
        if not thinking:
            body["thinking"] = {"type": "disabled"}
        elif thinking_budget is not None:
            # F6 rigor wiring (docs/same-provider-scaling-research.md F6):
            # a DashScope-compatible "budget_tokens" knob layered on top of
            # the real Anthropic-style enabled/disabled thinking shape --
            # ENDPOINT-DEPENDENT (the Token Plan's Anthropic-Messages-API-
            # compatible endpoint accepts it; a strictly spec-following
            # Anthropic endpoint would ignore the extra field). Only sent
            # when thinking=True (a budget on a disabled thinking block is
            # meaningless) and only when the caller explicitly asks for it
            # -- thinking_budget=None (the default) leaves the body exactly
            # as before this param existed. Unknown/unsupported params are
            # safely ignored server-side, per this endpoint's observed
            # behavior (see the enable_thinking:false note above).
            body["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
        # else: thinking=True, thinking_budget=None -- no "thinking" key at
        # all, BYTE-IDENTICAL to the body sent before thinking_budget
        # existed (the model's own default thinking behavior applies).

        if seed is not None:
            # Same F6 rigor wiring, same endpoint-dependent caveat: a
            # DashScope-compatible reproducibility knob, sent only when the
            # caller explicitly opts in (default None -> body unchanged).
            body["seed"] = seed

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        # 300s, not the original 120s: live-measured 2026-07-21, flagship
        # thinking=True calls on genuinely hard questions (chem_flagship_gate
        # lever) regularly exceeded 120s and were dropped -- and ALL 14 drops
        # in that run were the exact subject the lever targets (Organic
        # Chemistry), which would silently bias any accuracy figure computed
        # from the survivors toward the easier, faster-answered questions.
        resp = requests.post(self._messages_url, headers=headers, json=body, timeout=300)
        resp.raise_for_status()
        data = resp.json()

        content = "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage_raw = data.get("usage", {})
        usage = CallUsage(
            model=model,
            input_tokens=usage_raw.get("input_tokens", 0) or 0,
            output_tokens=usage_raw.get("output_tokens", 0) or 0,
            # Token Plan bills via Credits against a subscription's 5-hour/
            # 7-day sliding quota, not per-token USD -- there is no published
            # $/token rate to convert against, so there is no honest cost_usd
            # figure to report here. Left at 0.0 rather than a fabricated
            # number; input_tokens/output_tokens above are the real signal
            # for anything comparing efficiency across calls made through
            # this client.
            cost_usd=0.0,
            role=role,
        )
        return content, usage

    def chat_json(
        self,
        model: str,
        system: str,
        user: str,
        role: str,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        retries: int = 1,
        thinking: bool = True,
        seed: int | None = None,
        thinking_budget: int | None = None,
    ) -> JsonCallResult:
        messages = [
            {"role": "system", "content": system + "\n\nRespond with ONLY a single valid JSON object. No markdown, no commentary before or after."},
            {"role": "user", "content": user},
        ]
        last_error: Exception | None = None
        spent_input = spent_output = 0
        spent_cost = 0.0
        for attempt in range(retries + 1):
            content, usage = self.chat(
                model, messages, role=role, temperature=temperature, max_tokens=max_tokens, thinking=thinking,
                seed=seed, thinking_budget=thinking_budget,
            )
            spent_input += usage.input_tokens
            spent_output += usage.output_tokens
            spent_cost += usage.cost_usd
            try:
                data = _extract_json(content)
                total_usage = CallUsage(
                    model=model, input_tokens=spent_input, output_tokens=spent_output,
                    cost_usd=round(spent_cost, 8), role=role,
                )
                return JsonCallResult(data=data, usage=total_usage)
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "That was not valid JSON (it may have been cut off). Respond again with ONLY the complete JSON object, keeping every string value under 50 words."})
        raise ValueError(f"Model {model} failed to return parseable JSON after {retries + 1} attempts: {last_error}")
