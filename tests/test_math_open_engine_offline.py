"""Offline tests for benchmark/math_open_engine.py -- no live API calls, no
cost. Uses a fake QwenClient (matching the real client.chat_json return
shape: an object with .data (parsed dict) and .usage), keyed off `role` and
(for the panel) the lens embedded in the `system` prompt -- the same
fake-client pattern tests/test_engine_offline.py and
tests/test_lever_qwen38_panel_offline.py already use for this repo's
offline suite.

Covers:
  (a) extract_boxed -- last \\boxed{} occurrence, brace-matched (including
      nested braces), and the non-\\boxed fallback path.
  (b) Plurality clustering: 2 of 3 solvers agree (even in different
      notation) -> not escalated, that (equivalence class of) answer wins.
  (c) Split -> escalation: 3 mutually different answers -> escalated=True,
      the judge is called, and the judge's boxed answer becomes final.
  (d) Grading integration: a panel result whose final answer is a different
      notation of the gold answer is scored correct via
      benchmark.math_grade.grade.
  (e) Baseline: solve_single_math returns correct=True when the single
      answer matches gold in different notation.
"""

import pytest

from quorumqa.config import SOLVER_TEMPERATURES
from quorumqa.engine.solver import _lenses_for
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage

from benchmark.load_math_open import MathItem
from benchmark.math_grade import grade
from benchmark.math_open_engine import (
    BASELINE_LENS,
    extract_boxed,
    solve_one_math,
    solve_panel_math,
    solve_single_math,
)


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


def _item(gold_answer: str, question_id: str = "q1") -> MathItem:
    return MathItem(
        question_id=question_id,
        problem="What is the answer?",
        gold_answer=gold_answer,
        subject="Algebra",
        level=5,
    )


# ---------------------------------------------------------------------------
# (a) extract_boxed
# ---------------------------------------------------------------------------


def test_extract_boxed_pulls_last_occurrence_brace_matched():
    text = r"First I try \boxed{42} but on review the answer is \boxed{\frac{1}{2}}."
    assert extract_boxed(text) == r"\frac{1}{2}"


def test_extract_boxed_handles_deeply_nested_braces():
    text = r"So the final result is \boxed{\sqrt{\frac{a}{b+1}}} and nothing else."
    assert extract_boxed(text) == r"\sqrt{\frac{a}{b+1}}"


def test_extract_boxed_single_occurrence():
    assert extract_boxed(r"Therefore \boxed{17}.") == "17"


def test_extract_boxed_falls_back_to_last_nonempty_line_when_no_boxed():
    text = "Step 1: simplify the expression\nStep 2: solve for x\n\nThe final answer is 17"
    assert extract_boxed(text) == "The final answer is 17"


def test_extract_boxed_empty_string_returns_empty():
    assert extract_boxed("") == ""
    assert extract_boxed("   \n  ") == ""


# ---------------------------------------------------------------------------
# solve_one_math: JSON contract / call shape
# ---------------------------------------------------------------------------


class _SingleAnswerClient:
    """Always returns the same canned solver/judge answer -- for baseline
    tests and for asserting the call shape solve_one_math sends."""

    def __init__(self, answer: str, reasoning: str = "because algebra", role: str = "solver"):
        self.answer = answer
        self.reasoning = reasoning
        self.role = role
        self.calls: list[dict] = []

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append(dict(model=model, system=system, user=user, role=role, temperature=temperature, thinking=thinking))
        if role != self.role:
            raise AssertionError(f"unexpected role {role!r}, expected {self.role!r}")
        return JsonCallResult(data={"reasoning": self.reasoning, "answer": self.answer}, usage=_usage(role))


def test_solve_one_math_calls_flagship_thinking_true_and_extracts_boxed():
    client = _SingleAnswerClient(answer=r"\boxed{7}", reasoning="7 follows from the algebra")
    answer, reasoning, usage = solve_one_math(client, "What is 3+4?", BASELINE_LENS, temperature=0.3)

    assert answer == "7"
    assert reasoning == "7 follows from the algebra"
    assert usage.role == "solver"

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == "qwen3.7-max"
    assert call["thinking"] is True
    assert BASELINE_LENS in call["system"]


def test_solve_one_math_falls_back_to_reasoning_when_answer_field_has_no_boxed():
    client = _SingleAnswerClient(answer="7", reasoning="working... the final answer is \\boxed{7}")
    answer, _, _ = solve_one_math(client, "problem", BASELINE_LENS)
    # answer field itself has no \boxed{}, so extract_boxed(raw_answer) falls
    # back to its own last-non-empty-line rule -- "7" IS non-empty, so it
    # wins outright without ever consulting reasoning.
    assert answer == "7"


# ---------------------------------------------------------------------------
# (e) Baseline: different-notation match still grades correct
# ---------------------------------------------------------------------------


def test_solve_single_math_correct_true_on_different_notation_match():
    client = _SingleAnswerClient(answer=r"\boxed{0.5}", reasoning="half")
    item = _item(gold_answer=r"\frac{1}{2}")

    result = solve_single_math(client, item)

    assert result["question_id"] == "q1"
    assert result["final_answer"] == "0.5"
    assert result["correct"] is True  # grade(\frac{1}{2}, 0.5) is True
    assert len(result["calls"]) == 1
    assert result["calls"][0]["role"] == "solver"


def test_solve_single_math_correct_false_on_genuine_mismatch():
    client = _SingleAnswerClient(answer=r"\boxed{8}", reasoning="wrong path")
    item = _item(gold_answer="7")

    result = solve_single_math(client, item)

    assert result["final_answer"] == "8"
    assert result["correct"] is False


# ---------------------------------------------------------------------------
# Fake panel client -- keyed by lens embedded in the system prompt (same
# pattern tests/test_engine_offline.py's FakeQwenClient uses for solver
# seats), plus a fixed judge response for escalation cases.
# ---------------------------------------------------------------------------


class FakePanelClient:
    def __init__(self, answers_by_lens: dict[str, str], judge_answer: str | None = None, judge_reasoning: str = "judged"):
        self._answers_by_lens = answers_by_lens
        self._judge_answer = judge_answer
        self._judge_reasoning = judge_reasoning
        self.judge_calls = 0
        self.solver_calls = 0

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        if role == "solver":
            self.solver_calls += 1
            lens = next(l for l in self._answers_by_lens if l in system)
            answer = self._answers_by_lens[lens]
            return JsonCallResult(data={"reasoning": f"solving via lens {lens!r}", "answer": answer}, usage=_usage("solver"))
        if role == "judge":
            self.judge_calls += 1
            if self._judge_answer is None:
                raise AssertionError("judge_math was called but no judge_answer was configured")
            return JsonCallResult(data={"reasoning": self._judge_reasoning, "answer": self._judge_answer}, usage=_usage("judge"))
        raise AssertionError(f"unexpected role {role!r}")


def _answers_by_lens(answers: list[str]) -> dict[str, str]:
    lenses = _lenses_for(3)
    assert len(answers) == 3
    return dict(zip(lenses, answers))


# ---------------------------------------------------------------------------
# (b) Plurality clustering: 2 of 3 agree (different notation) -> not escalated
# ---------------------------------------------------------------------------


def test_panel_two_agree_in_different_notation_wins_without_escalation():
    # lens0 -> "\frac{1}{2}", lens1 -> "0.5" (equivalent, different notation),
    # lens2 -> "7" (genuinely different).
    client = FakePanelClient(_answers_by_lens([r"\boxed{\frac{1}{2}}", r"\boxed{0.5}", r"\boxed{7}"]))
    item = _item(gold_answer=r"\frac{1}{2}")

    result = solve_panel_math(client, item)

    assert result["escalated"] is False
    assert client.judge_calls == 0
    assert client.solver_calls == 3
    # The winning answer must be grade-equivalent to both "\frac{1}{2}" and
    # "0.5" -- which literal string wins is an implementation detail.
    assert grade(result["final_answer"], r"\frac{1}{2}")
    assert grade(result["final_answer"], "0.5")
    assert result["correct"] is True
    assert len(result["calls"]) == 3
    assert result["judge_reasoning"] is None


def test_panel_all_three_agree_wins_without_escalation():
    client = FakePanelClient(_answers_by_lens([r"\boxed{9}", r"\boxed{9}", r"\boxed{9}"]))
    item = _item(gold_answer="9")

    result = solve_panel_math(client, item)

    assert result["escalated"] is False
    assert client.judge_calls == 0
    assert result["final_answer"] == "9"
    assert result["correct"] is True


# ---------------------------------------------------------------------------
# (c) Split -> escalation: 3 mutually different answers -> judge decides
# ---------------------------------------------------------------------------


def test_panel_three_way_split_escalates_and_judge_answer_becomes_final():
    client = FakePanelClient(
        _answers_by_lens([r"\boxed{7}", r"\boxed{8}", r"\boxed{9}"]),
        judge_answer=r"\boxed{8}",
        judge_reasoning="re-derived from scratch, 8 is correct",
    )
    item = _item(gold_answer="8", question_id="q_split")

    result = solve_panel_math(client, item)

    assert result["escalated"] is True
    assert client.judge_calls == 1
    assert client.solver_calls == 3
    assert result["final_answer"] == "8"
    assert result["correct"] is True
    assert result["judge_reasoning"] == "re-derived from scratch, 8 is correct"
    assert len(result["calls"]) == 4  # 3 solvers + 1 judge
    assert len(result["solver_answers"]) == 3
    assert {sa["answer"] for sa in result["solver_answers"]} == {"7", "8", "9"}
    # Distinct lenses and the shipped per-seat temperatures were used.
    assert {sa["lens"] for sa in result["solver_answers"]} == set(_lenses_for(3))
    assert [sa["temperature"] for sa in result["solver_answers"]] == SOLVER_TEMPERATURES


def test_panel_escalation_when_judge_is_wrong_scores_incorrect():
    client = FakePanelClient(
        _answers_by_lens([r"\boxed{7}", r"\boxed{8}", r"\boxed{9}"]),
        judge_answer=r"\boxed{100}",
    )
    item = _item(gold_answer="8")

    result = solve_panel_math(client, item)

    assert result["escalated"] is True
    assert result["final_answer"] == "100"
    assert result["correct"] is False


# ---------------------------------------------------------------------------
# (d) Grading integration: different-notation final answer still scores
#     correct via benchmark.math_grade.grade (radical vs simplified radical)
# ---------------------------------------------------------------------------


def test_panel_grades_correct_on_different_notation_against_gold():
    # Two solvers agree on "2\sqrt{5}", one is way off -- gold is stated in
    # the OTHER equivalent notation, "\sqrt{20}".
    client = FakePanelClient(_answers_by_lens([r"\boxed{2\sqrt{5}}", r"\boxed{2\sqrt{5}}", r"\boxed{0}"]))
    item = _item(gold_answer=r"\sqrt{20}")

    result = solve_panel_math(client, item)

    assert result["escalated"] is False
    assert result["final_answer"] == r"2\sqrt{5}"
    assert grade(item.gold_answer, result["final_answer"]) is True
    assert result["correct"] is True


def test_panel_cheap_tier_uses_flash_solvers_but_flagship_judge():
    # The shipped-engine tier: cheap flash solvers, flagship judge on split.
    from quorumqa.config import MECHANICAL_MODEL, ORCHESTRATOR_MODEL

    class _TierRecordingClient:
        def __init__(self):
            self.solver_models = []
            self.judge_models = []

        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            if role == "solver":
                self.solver_models.append(model)
                # 3-way split so the judge is exercised too
                lens = next(l for l in _lenses_for(3) if l in system)
                ans = {_lenses_for(3)[0]: r"\boxed{1}", _lenses_for(3)[1]: r"\boxed{2}", _lenses_for(3)[2]: r"\boxed{3}"}[lens]
                return JsonCallResult(data={"reasoning": "r", "answer": ans}, usage=_usage("solver"))
            if role == "judge":
                self.judge_models.append(model)
                return JsonCallResult(data={"reasoning": "j", "answer": r"\boxed{2}"}, usage=_usage("judge"))
            raise AssertionError(role)

    client = _TierRecordingClient()
    result = solve_panel_math(client, _item(gold_answer="2"), solver_model=MECHANICAL_MODEL)

    assert client.solver_models == [MECHANICAL_MODEL] * 3   # cheap solvers
    assert client.judge_models == [ORCHESTRATOR_MODEL]      # flagship judge (escalation)
    assert result["solver_model"] == MECHANICAL_MODEL
    assert result["escalated"] is True
    assert result["correct"] is True


def test_panel_default_tier_is_flagship_unchanged():
    # Byte-compatible default: no solver_model arg -> flagship solvers.
    from quorumqa.config import ORCHESTRATOR_MODEL

    seen = []

    class _C:
        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            seen.append((role, model))
            return JsonCallResult(data={"reasoning": "r", "answer": r"\boxed{5}"}, usage=_usage(role))

    result = solve_panel_math(_C(), _item(gold_answer="5"))
    assert all(m == ORCHESTRATOR_MODEL for r, m in seen if r == "solver")
    assert result["solver_model"] == ORCHESTRATOR_MODEL


def test_panel_all_mutually_different_but_none_match_gold():
    client = FakePanelClient(
        _answers_by_lens([r"\boxed{1}", r"\boxed{2}", r"\boxed{3}"]),
        judge_answer=r"\boxed{4}",
    )
    item = _item(gold_answer="5")

    result = solve_panel_math(client, item)

    assert result["escalated"] is True
    assert result["correct"] is False
