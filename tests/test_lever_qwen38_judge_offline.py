"""Offline tests for the qwen38_judge lever (benchmark/lever_experiments.py)
-- no live API calls, no cost. Covers:
  (a) adjudicate_qwen38 parses a fake Anthropic-shaped response that has a
      "thinking" content block before the "text" block (the real
      qwen3.8-max-preview/Token Plan shape).
  (b) adjudicate_qwen38 survives JSON wrapped in prose, not just bare JSON.
  (c) run_question_lever(..., "qwen38_judge") routes an escalated question's
      judge call through adjudicate_qwen38 (the Token Plan transport), NOT
      through the shipped client.chat_json(role="judge") path.

Mirrors the fake-client pattern in tests/test_engine_offline.py and the
requests.post-shaped fake response in benchmark/qwen38_baseline.py."""

import asyncio

import pytest

import benchmark.lever_experiments as lever_experiments
from quorumqa.config import SOLVER_LENSES
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem, SkepticRebuttal, SolverAnswer


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


def _solver_answer(letter: str) -> SolverAnswer:
    return SolverAnswer(letter=letter, confidence=0.7, reasoning="because", lens=SOLVER_LENSES[0])


class FakeResponse:
    """Stands in for requests.Response -- just enough surface for
    adjudicate_qwen38 (json() + raise_for_status())."""

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


# ---------------------------------------------------------------------------
# (a) thinking block before the text block
# ---------------------------------------------------------------------------


def test_adjudicate_qwen38_skips_thinking_block_and_parses_text_json(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "content": [
                    {"type": "thinking", "thinking": "Let me weigh the arguments carefully..."},
                    {
                        "type": "text",
                        "text": (
                            '{"final_letter": "D", "decisive_reasoning": "the minority '
                            'solver held up under scrutiny", "dissent": null, '
                            '"overturned_plurality": true, "confidence": "high"}'
                        ),
                    },
                ],
                "usage": {"input_tokens": 500, "output_tokens": 120},
            }
        )

    monkeypatch.setattr(lever_experiments.requests, "post", fake_post)

    verdict, usage = lever_experiments.adjudicate_qwen38(
        client=None,
        question="What is 2+2?",
        choices=["3", "4", "5", "6"],
        solver_answers=[_solver_answer("B"), _solver_answer("B"), _solver_answer("D")],
        skeptic_rebuttal=SkepticRebuttal(target_letter="B", disputed_step="step X", argument="argument Y"),
        verifier_findings=[],
    )

    assert verdict.final_letter == "D"
    assert verdict.overturned_plurality is True
    assert verdict.confidence == "high"
    assert verdict.dissent is None

    assert usage.model == "qwen3.8-max-preview"
    assert usage.input_tokens == 500
    assert usage.output_tokens == 120
    assert usage.cost_usd == 0.0  # quota-based, never a fabricated USD figure
    assert usage.role == "judge"

    # Transport shape must match benchmark/qwen38_baseline.py's proven pattern.
    assert captured["url"].endswith("/v1/messages")
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert "x-api-key" in captured["headers"]
    assert captured["timeout"] == 300
    assert captured["json"]["model"] == "qwen3.8-max-preview"
    assert captured["json"]["system"] == lever_experiments.JUDGE_SYSTEM


# ---------------------------------------------------------------------------
# (b) JSON wrapped in prose
# ---------------------------------------------------------------------------


def test_adjudicate_qwen38_survives_json_wrapped_in_prose(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Based on my analysis of the transcript, here is my ruling:\n\n"
                            '{"final_letter": "B", "decisive_reasoning": "plurality reasoning '
                            'was never actually refuted", "dissent": "minority solver still '
                            'disagrees", "overturned_plurality": false, "confidence": "medium"}'
                            "\n\nThat concludes my assessment."
                        ),
                    }
                ],
                "usage": {"input_tokens": 300, "output_tokens": 80},
            }
        )

    monkeypatch.setattr(lever_experiments.requests, "post", fake_post)

    verdict, usage = lever_experiments.adjudicate_qwen38(
        client=None,
        question="Q",
        choices=["a", "b", "c", "d"],
        solver_answers=[_solver_answer("B")],
        skeptic_rebuttal=SkepticRebuttal(target_letter="B", disputed_step="s", argument="a"),
        verifier_findings=[],
    )

    assert verdict.final_letter == "B"
    assert verdict.dissent == "minority solver still disagrees"
    assert verdict.overturned_plurality is False
    assert usage.input_tokens == 300
    assert usage.output_tokens == 80


# ---------------------------------------------------------------------------
# (c) lever dispatch routes qwen38_judge to adjudicate_qwen38
# ---------------------------------------------------------------------------


def test_qwen38_judge_lever_routes_escalation_through_token_plan_judge(monkeypatch):
    # Solver panel splits 2-1 so the question escalates into the tribunal --
    # unanimous questions never reach the judge at all, qwen38_judge or not.
    lenses = SOLVER_LENSES
    letters = {lenses[0]: "B", lenses[1]: "B", lenses[2]: "D"}

    class ClientNoJudgeRole:
        """A client whose chat_json raises if role="judge" is ever requested
        -- proves the qwen38_judge lever never falls back to the shipped
        DashScope/qwen3.7-max judge path via QwenClient."""

        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            if role == "solver":
                lens = next(l for l in SOLVER_LENSES if l in system)
                return JsonCallResult(
                    data={"letter": letters[lens], "confidence": 0.7, "reasoning": "because"},
                    usage=_usage("solver"),
                )
            if role == "skeptic":
                return JsonCallResult(
                    data={"target_letter": "B", "disputed_step": "step X", "argument": "argument Y"},
                    usage=_usage("skeptic"),
                )
            if role == "verifier":
                return JsonCallResult(data={"claims": []}, usage=_usage("verifier"))
            if role == "judge":
                raise AssertionError(
                    "qwen38_judge lever must not call client.chat_json(role='judge') -- "
                    "the judge call must go through the Token Plan transport instead"
                )
            raise AssertionError(f"unexpected role {role!r}")

    def fake_post(url, headers=None, json=None, timeout=None):
        assert json["model"] == "qwen3.8-max-preview"
        return FakeResponse(
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"final_letter": "D", "decisive_reasoning": "token plan judge ruled", '
                            '"dissent": null, "overturned_plurality": true, "confidence": "high"}'
                        ),
                    }
                ],
                "usage": {"input_tokens": 400, "output_tokens": 90},
            }
        )

    monkeypatch.setattr(lever_experiments.requests, "post", fake_post)

    item = GPQAItem(question_id="q1", question="What is 2+2?", choices=["3", "4", "5", "6"], correct_letter="D")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(ClientNoJudgeRole(), None, item, "qwen38_judge")
    )

    assert result.escalated is True
    assert result.plurality_letter == "B"
    assert result.final_letter == "D"
    assert result.verdict.decisive_reasoning == "token plan judge ruled"
    assert result.correct is True


def test_qwen38_judge_lever_present_in_argparse_choices():
    # Regression guard: the CLI must actually expose the lever, not just the
    # underlying functions.
    import benchmark.lever_experiments as mod
    import inspect

    source = inspect.getsource(mod)
    assert '"qwen38_judge"' in source
