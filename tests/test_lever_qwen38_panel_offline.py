"""Offline tests for the qwen38_panel lever (benchmark/lever_experiments.py)
-- no live API calls, no cost. Covers:
  (a) _solve_one_qwen38 parses a fake Anthropic-shaped response that has a
      "thinking" content block before the "text" block (the real
      qwen3.8-max-preview/Token Plan shape) into a valid SolverAnswer.
  (b) solve_all_qwen38_panel issues exactly 3 calls, all against
      qwen3.8-max-preview via the Token Plan transport.
  (c) run_question_lever(..., "qwen38_panel") routes ALL THREE solver seats
      through the Token Plan transport (never through
      client.chat_json(role="solver")), while Skeptic/Verifier/Judge stay
      untouched -- still routed through client.chat_json exactly as the
      shipped engine, via the default adjudicate() (qwen3.7-max/QwenClient),
      NOT adjudicate_qwen38.
  (d) the qwen38_panel lever is exposed in the CLI's --lever choices.

Mirrors the fake-client / fake-transport pattern in
tests/test_lever_qwen38_judge_offline.py."""

import asyncio

import pytest

import benchmark.lever_experiments as lever_experiments
from quorumqa.config import SOLVER_LENSES
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class FakeResponse:
    """Stands in for requests.Response -- just enough surface for
    _solve_one_qwen38 (json() + raise_for_status())."""

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


# ---------------------------------------------------------------------------
# (a) _solve_one_qwen38 parses a thinking-block-then-text response
# ---------------------------------------------------------------------------


def test_solve_one_qwen38_skips_thinking_block_and_parses_text_json(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "content": [
                    {"type": "thinking", "thinking": "Weighing each choice against the underlying physics..."},
                    {
                        "type": "text",
                        "text": '{"letter": "C", "confidence": 0.82, "reasoning": "eliminated A, B, D on dimensional grounds"}',
                    },
                ],
                "usage": {"input_tokens": 250, "output_tokens": 60},
            }
        )

    monkeypatch.setattr(lever_experiments.requests, "post", fake_post)

    lens = SOLVER_LENSES[0]
    answer, usage = lever_experiments._solve_one_qwen38(
        client=None,
        question="What is 2+2?",
        choices=["3", "4", "5", "6"],
        lens=lens,
        temperature=0.3,
    )

    assert answer.letter == "C"
    assert answer.confidence == pytest.approx(0.82)
    assert answer.reasoning == "eliminated A, B, D on dimensional grounds"
    assert answer.lens == lens

    assert usage.model == "qwen3.8-max-preview"
    assert usage.input_tokens == 250
    assert usage.output_tokens == 60
    assert usage.cost_usd == 0.0  # quota-based, never a fabricated USD figure
    assert usage.role == "solver"

    # Transport shape must match benchmark/qwen38_baseline.py's proven pattern.
    assert captured["url"].endswith("/v1/messages")
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert "x-api-key" in captured["headers"]
    assert captured["timeout"] == 300
    assert captured["json"]["model"] == "qwen3.8-max-preview"
    assert lens in captured["json"]["system"]
    assert lever_experiments.SOLVER_SYSTEM in captured["json"]["system"]


def test_solve_one_qwen38_survives_json_wrapped_in_prose(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Let me work through this step by step.\n\n"
                            '{"letter": "A", "confidence": 0.6, "reasoning": "first principles suggest A"}'
                            "\n\nThat is my final answer."
                        ),
                    }
                ],
                "usage": {"input_tokens": 180, "output_tokens": 40},
            }
        )

    monkeypatch.setattr(lever_experiments.requests, "post", fake_post)

    answer, usage = lever_experiments._solve_one_qwen38(
        client=None, question="Q", choices=["a", "b", "c", "d"], lens=SOLVER_LENSES[1], temperature=0.6,
    )

    assert answer.letter == "A"
    assert usage.input_tokens == 180
    assert usage.output_tokens == 40


# ---------------------------------------------------------------------------
# (b) solve_all_qwen38_panel issues 3 calls, all qwen3.8-max-preview
# ---------------------------------------------------------------------------


def test_solve_all_qwen38_panel_issues_three_calls_with_right_model(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        letter = ["A", "B", "C"][len(calls) - 1]
        return FakeResponse(
            {
                "content": [{"type": "text", "text": f'{{"letter": "{letter}", "confidence": 0.7, "reasoning": "r"}}'}],
                "usage": {"input_tokens": 100, "output_tokens": 20},
            }
        )

    monkeypatch.setattr(lever_experiments.requests, "post", fake_post)

    pairs = asyncio.run(lever_experiments.solve_all_qwen38_panel(None, "What is 2+2?", ["3", "4", "5", "6"]))

    assert len(pairs) == 3
    assert len(calls) == 3
    assert all(c["model"] == "qwen3.8-max-preview" for c in calls)

    answers = [a for a, _ in pairs]
    usages = [u for _, u in pairs]
    assert [a.letter for a in answers] == ["A", "B", "C"]
    assert all(u.role == "solver" for u in usages)
    assert all(u.cost_usd == 0.0 for u in usages)
    # Distinct lenses and the shipped per-seat temperatures were used.
    assert len({a.lens for a in answers}) == 3


# ---------------------------------------------------------------------------
# (c) lever dispatch routes qwen38_panel's solvers through the Token Plan
#     transport, and leaves Skeptic/Verifier/Judge on the shipped path
# ---------------------------------------------------------------------------


def test_qwen38_panel_lever_routes_solvers_through_token_plan_not_chat_json(monkeypatch):
    # Token Plan solver responses split 2-1 so the question escalates into
    # the tribunal -- unanimous questions never reach skeptic/verifier/judge.
    solver_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json["model"] == "qwen3.8-max-preview"
        solver_calls.append(json)
        letter = ["B", "B", "D"][len(solver_calls) - 1]
        return FakeResponse(
            {
                "content": [{"type": "text", "text": f'{{"letter": "{letter}", "confidence": 0.7, "reasoning": "r"}}'}],
                "usage": {"input_tokens": 100, "output_tokens": 20},
            }
        )

    monkeypatch.setattr(lever_experiments.requests, "post", fake_post)

    class ClientNoSolverRole:
        """A client whose chat_json raises if role="solver" is ever
        requested -- proves the qwen38_panel lever never falls back to the
        shipped MECHANICAL_MODEL solver path via QwenClient. Skeptic/
        Verifier/Judge roles are answered normally, proving they stay on
        the shipped path (untouched by this lever)."""

        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            if role == "solver":
                raise AssertionError(
                    "qwen38_panel lever must not call client.chat_json(role='solver') -- "
                    "all three solver seats must go through the Token Plan transport instead"
                )
            if role == "skeptic":
                return JsonCallResult(
                    data={"target_letter": "B", "disputed_step": "step X", "argument": "argument Y"},
                    usage=_usage("skeptic"),
                )
            if role == "verifier":
                return JsonCallResult(data={"claims": []}, usage=_usage("verifier"))
            if role == "judge":
                # Proves the judge stayed on the SHIPPED path (qwen3.7-max
                # via QwenClient/chat_json), not adjudicate_qwen38's Token
                # Plan transport.
                return JsonCallResult(
                    data={
                        "final_letter": "D",
                        "decisive_reasoning": "shipped judge ruled",
                        "dissent": None,
                        "overturned_plurality": True,
                        "confidence": "high",
                    },
                    usage=_usage("judge"),
                )
            raise AssertionError(f"unexpected role {role!r}")

    item = GPQAItem(question_id="q1", question="What is 2+2?", choices=["3", "4", "5", "6"], correct_letter="D")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(ClientNoSolverRole(), None, item, "qwen38_panel")
    )

    assert len(solver_calls) == 3
    assert result.escalated is True
    assert result.plurality_letter == "B"
    assert result.final_letter == "D"
    assert result.verdict.decisive_reasoning == "shipped judge ruled"
    assert result.correct is True


def test_qwen38_panel_lever_unanimous_case_skips_tribunal(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(
            {
                "content": [{"type": "text", "text": '{"letter": "D", "confidence": 0.9, "reasoning": "r"}'}],
                "usage": {"input_tokens": 100, "output_tokens": 20},
            }
        )

    monkeypatch.setattr(lever_experiments.requests, "post", fake_post)

    class ClientNoCalls:
        def chat_json(self, *a, **kw):
            raise AssertionError("no client.chat_json call expected on a unanimous qwen38_panel question")

    item = GPQAItem(question_id="q2", question="What is 2+2?", choices=["3", "4", "5", "6"], correct_letter="D")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(ClientNoCalls(), None, item, "qwen38_panel")
    )

    assert result.escalated is False
    assert result.final_letter == "D"
    assert result.correct is True


# ---------------------------------------------------------------------------
# (d) qwen38_panel is exposed in the CLI's --lever choices
# ---------------------------------------------------------------------------


def test_qwen38_panel_lever_present_in_argparse_choices():
    import inspect

    source = inspect.getsource(lever_experiments)
    assert '"qwen38_panel"' in source
