import json
import re
from dataclasses import dataclass

from openai import OpenAI

from quorumqa.config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL
from quorumqa.cost_tracker import price_call
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
        # Escape those backslashes and retry -- deterministic, lossless.
        sanitized = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", payload)
        return json.loads(sanitized)


def _extract_json(text: str) -> dict:
    fenced = _FENCE_RE.search(text)
    candidate = fenced.group(1) if fenced else text
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
    """Thin wrapper around the DashScope OpenAI-compatible endpoint.

    Kept deliberately independent of any specific structured-output feature
    (response_format json_schema support varies by compatible-mode model) --
    every JSON call asks for JSON in the prompt and parses defensively, so it
    works the same way regardless of what the currently deployed model
    actually honors.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._client = OpenAI(
            api_key=api_key or DASHSCOPE_API_KEY,
            base_url=base_url or DASHSCOPE_BASE_URL,
        )

    def chat(self, model: str, messages: list[dict], role: str, temperature: float = 0.4, max_tokens: int = 1024, thinking: bool = True) -> tuple[str, CallUsage]:
        # Qwen3 hybrid models think by default, billing reasoning tokens as
        # output. Cheap fast-voter roles (solvers/skeptic/verifier) disable
        # it -- three thinking "cheap" calls otherwise cost more than one
        # flagship call, inverting the engine's whole economic premise.
        extra_body = {} if thinking else {"enable_thinking": False}
        resp = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body,
        )
        content = resp.choices[0].message.content or ""
        usage = price_call(
            model=model,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
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
    ) -> JsonCallResult:
        messages = [
            {"role": "system", "content": system + "\n\nRespond with ONLY a single valid JSON object. No markdown, no commentary before or after."},
            {"role": "user", "content": user},
        ]
        last_error: Exception | None = None
        spent_input = spent_output = 0
        spent_cost = 0.0
        for attempt in range(retries + 1):
            content, usage = self.chat(model, messages, role=role, temperature=temperature, max_tokens=max_tokens, thinking=thinking)
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
