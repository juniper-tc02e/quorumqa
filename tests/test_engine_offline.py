"""Exercises the full orchestration logic (split-detection, conditional
escalation, false-escalation flagging) against a fake QwenClient/tool
session -- no live API calls, no cost, safe to run before touching real
Qwen Cloud credits."""

import pytest

from quorumqa.config import SOLVER_LENSES
from quorumqa.engine.orchestrator import run_question
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class FakeToolSession:
    async def call(self, tool_name, arguments):
        if tool_name == "lookup_constant":
            return {"found": True, "name": arguments.get("name"), "value": 3.14159}
        return {"ok": True, "value": 1.0}


class FakeQwenClient:
    def __init__(self, solver_letters, skeptic_target, verifier_claims, judge_verdict):
        self._solver_letters = solver_letters
        self._skeptic_target = skeptic_target
        self._verifier_claims = verifier_claims
        self._judge_verdict = judge_verdict
        self._verifier_call_count = 0

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        if role == "solver":
            lens = next(l for l in SOLVER_LENSES if l in system)
            return JsonCallResult(
                data={"letter": self._solver_letters[lens], "confidence": 0.7, "reasoning": "because"},
                usage=_usage("solver"),
            )
        if role == "skeptic":
            return JsonCallResult(
                data={"target_letter": self._skeptic_target, "disputed_step": "step X", "argument": "argument Y"},
                usage=_usage("skeptic"),
            )
        if role == "verifier":
            self._verifier_call_count += 1
            if self._verifier_call_count == 1:
                return JsonCallResult(data={"claims": self._verifier_claims}, usage=_usage("verifier"))
            findings = [
                {"claim": c["claim"], "supports_claim": True, "explanation": "checked"} for c in self._verifier_claims
            ]
            return JsonCallResult(data={"findings": findings}, usage=_usage("verifier"))
        if role == "judge":
            return JsonCallResult(data=self._judge_verdict, usage=_usage("judge"))
        raise AssertionError(f"unexpected role {role!r}")


def _item(correct_letter: str, question_id: str = "q") -> GPQAItem:
    return GPQAItem(question_id=question_id, question="What is 2+2?", choices=["3", "4", "5", "6"], correct_letter=correct_letter)


@pytest.mark.asyncio
async def test_unanimous_skips_escalation_entirely():
    letters = {lens: "B" for lens in SOLVER_LENSES}
    client = FakeQwenClient(letters, skeptic_target="B", verifier_claims=[], judge_verdict={})

    result = await run_question(client, FakeToolSession(), _item(correct_letter="B"))

    assert result.escalated is False
    assert result.final_letter == "B"
    assert result.correct is True
    assert result.skeptic_rebuttal is None
    assert result.verdict is None
    assert len(result.calls) == 3  # solvers only -- no skeptic/verifier/judge cost


@pytest.mark.asyncio
async def test_split_escalates_and_judge_can_correctly_overturn_plurality():
    lenses = SOLVER_LENSES
    letters = {lenses[0]: "B", lenses[1]: "B", lenses[2]: "D"}
    client = FakeQwenClient(
        letters,
        skeptic_target="B",
        verifier_claims=[{"claim": "2+2=4", "tool": "safe_calculate", "arguments": {"expression": "2+2"}}],
        judge_verdict={
            "final_letter": "D",
            "decisive_reasoning": "the minority solver's derivation held up under the skeptic's challenge",
            "dissent": None,
            "overturned_plurality": True,
            "confidence": "high",
        },
    )

    result = await run_question(client, FakeToolSession(), _item(correct_letter="D"))

    assert result.escalated is True
    assert result.plurality_letter == "B"
    assert result.final_letter == "D"
    assert result.correct is True  # judge overturned a wrong plurality to the right answer
    assert result.false_escalation is False
    assert len(result.verifier_findings) == 1
    assert len(result.calls) == 3 + 1 + 2 + 1  # solvers + skeptic + verifier(extract+finalize) + judge


@pytest.mark.asyncio
async def test_false_escalation_flagged_when_judge_just_reconfirms_plurality():
    lenses = SOLVER_LENSES
    letters = {lenses[0]: "B", lenses[1]: "B", lenses[2]: "D"}
    client = FakeQwenClient(
        letters,
        skeptic_target="B",
        verifier_claims=[],
        judge_verdict={
            "final_letter": "B",
            "decisive_reasoning": "the skeptic's rebuttal did not hold up",
            "dissent": "minority solver still disagrees",
            "overturned_plurality": False,
            "confidence": "medium",
        },
    )

    result = await run_question(client, FakeToolSession(), _item(correct_letter="B"))

    assert result.escalated is True
    assert result.final_letter == "B"
    assert result.correct is True
    assert result.false_escalation is True  # paid for Skeptic/Verifier/Judge and got nothing new
    assert len(result.calls) == 3 + 1 + 1 + 1  # solvers + skeptic + verifier(extract only, no claims) + judge
