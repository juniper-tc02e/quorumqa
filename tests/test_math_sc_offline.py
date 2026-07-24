"""Offline tests for benchmark/math_open_engine.py's W3 self-consistency
engine (solve_selfconsistency_math) -- no live API calls, no cost. Uses a
fake QwenClient matching the real client.chat_json return shape (an object
with .data / .usage), the same fake-client pattern
tests/test_math_open_engine_offline.py and tests/test_engine_offline.py
already use for this repo's offline suite.

Covers:
  (a) Clustering/margin: samples in different notations that are the same
      mathematical answer (per math_grade.grade) cluster together, and
      cluster_margin (top - runner-up) is computed correctly.
  (b) F4 early stop: a constructed all-agree sequence stops EXACTLY at the
      sample count where the lead becomes mathematically unassailable, not
      one sample earlier (verified two ways: samples_used equals the exact
      predicted count, AND the fake client is given exactly that many
      answers -- one extra draw would IndexError instead of silently
      passing). Disabling early_stop always consumes the full n.
  (c) Escalation path: when the final margin is below margin_threshold, the
      judge is called with one representative (answer, reasoning) per
      distinct cluster, and the judge's answer becomes final (mirrors
      solve_panel_math's escalation contract).
  (d) Tier/lens/temperature-schedule wiring: solver_model/solver_thinking
      pass through to every sample, all samples share BASELINE_LENS (self-
      consistency resamples one prompt, diversity comes from temperature),
      and successive samples cycle SC_TEMPERATURE_SCHEDULE.
"""

from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage

from benchmark.load_math_open import MathItem
from benchmark.math_grade import grade
from benchmark.math_open_engine import (
    BASELINE_LENS,
    SC_TEMPERATURE_SCHEDULE,
    solve_selfconsistency_math,
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


class FakeSCClient:
    """Feeds solve_selfconsistency_math a pre-scripted SEQUENCE of solver
    answers (consumed in call order, one per sample) plus a fixed judge
    response for the escalation path. Supplying exactly as many answers as
    a test expects samples to be drawn is itself an assertion: an
    unexpected extra draw raises IndexError instead of silently passing."""

    def __init__(self, answers: list[str], judge_answer: str | None = None, judge_reasoning: str = "judged"):
        self._answers = list(answers)
        self._judge_answer = judge_answer
        self._judge_reasoning = judge_reasoning
        self.solver_calls: list[dict] = []
        self.judge_calls = 0

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        if role == "solver":
            idx = len(self.solver_calls)
            self.solver_calls.append(dict(model=model, system=system, temperature=temperature, thinking=thinking))
            answer = self._answers[idx]  # IndexError if more draws happen than scripted
            return JsonCallResult(
                data={"reasoning": f"reasoning for sample {idx}", "answer": answer}, usage=_usage("solver")
            )
        if role == "judge":
            self.judge_calls += 1
            if self._judge_answer is None:
                raise AssertionError("judge_math was called but no judge_answer was configured")
            return JsonCallResult(data={"reasoning": self._judge_reasoning, "answer": self._judge_answer}, usage=_usage("judge"))
        raise AssertionError(f"unexpected role {role!r}")


# ---------------------------------------------------------------------------
# (a) Clustering / margin
# ---------------------------------------------------------------------------


def test_sc_clusters_by_grade_equivalence_and_computes_margin():
    # 3 samples equivalent to 1/2 (two different notations), then two
    # genuinely different wrong answers.
    client = FakeSCClient(answers=[r"\boxed{\frac{1}{2}}", r"\boxed{0.5}", r"\boxed{0.5}", r"\boxed{7}", r"\boxed{9}"])
    item = _item(gold_answer=r"\frac{1}{2}")

    result = solve_selfconsistency_math(client, item, n=5, margin_threshold=2, early_stop=False)

    assert result["samples_used"] == 5
    sizes = sorted((c["size"] for c in result["clusters"]), reverse=True)
    assert sizes == [3, 1, 1]
    assert result["margin"] == 2  # 3 - 1
    assert result["escalated"] is False
    assert client.judge_calls == 0
    assert grade(result["final_answer"], "0.5")
    assert result["correct"] is True
    assert len(result["calls"]) == 5


def test_sc_all_agree_gives_full_margin_and_single_cluster():
    client = FakeSCClient(answers=[r"\boxed{9}"] * 5)
    item = _item(gold_answer="9")

    result = solve_selfconsistency_math(client, item, n=5, margin_threshold=2, early_stop=False)

    assert result["clusters"] == [{"size": 5, "representative_answer": "9"}]
    assert result["margin"] == 5
    assert result["escalated"] is False
    assert result["correct"] is True


# ---------------------------------------------------------------------------
# (b) F4 early stop
# ---------------------------------------------------------------------------


def test_sc_early_stop_stops_exactly_when_lead_unassailable_never_earlier():
    # All samples agree -> after k identical draws, lead = k (runner-up=0).
    # n=9, margin_threshold=2: stop condition is lead > remaining + 1, i.e.
    # k > (9-k) + 1  <=>  2k > 10  <=>  k > 5  <=>  k >= 6.
    # At k=5: lead=5, remaining=4 -> 5 > 4+1=5 is FALSE -> must NOT stop.
    # At k=6: lead=6, remaining=3 -> 6 > 3+1=4 is TRUE -> must stop.
    # Only 6 answers are scripted -- a 7th draw would IndexError, so this
    # also proves it never draws MORE than necessary.
    client = FakeSCClient(answers=[r"\boxed{5}"] * 6)
    item = _item(gold_answer="5")

    result = solve_selfconsistency_math(client, item, n=9, margin_threshold=2, early_stop=True)

    assert result["samples_used"] == 6
    assert len(client.solver_calls) == 6
    assert result["margin"] == 6
    assert result["escalated"] is False
    assert result["correct"] is True


def test_sc_early_stop_disabled_always_uses_all_n_samples():
    # Same all-agree sequence as above, but early_stop=False -- must draw
    # the full 9 even though the lead became unassailable at sample 6.
    client = FakeSCClient(answers=[r"\boxed{5}"] * 9)
    item = _item(gold_answer="5")

    result = solve_selfconsistency_math(client, item, n=9, margin_threshold=2, early_stop=False)

    assert result["samples_used"] == 9
    assert len(client.solver_calls) == 9
    assert result["margin"] == 9


def test_sc_early_stop_never_fires_when_margin_stays_contested():
    # A 2/2/1 split (see the escalation test below) never reaches an
    # unassailable lead before the last draw -- early_stop=True must still
    # consume the full n rather than stopping prematurely.
    client = FakeSCClient(answers=[r"\boxed{1}", r"\boxed{1}", r"\boxed{2}", r"\boxed{2}", r"\boxed{3}"], judge_answer=r"\boxed{2}")
    item = _item(gold_answer="2")

    result = solve_selfconsistency_math(client, item, n=5, margin_threshold=2, early_stop=True)

    assert result["samples_used"] == 5
    assert len(client.solver_calls) == 5


# ---------------------------------------------------------------------------
# (c) Escalation path
# ---------------------------------------------------------------------------


def test_sc_escalates_when_margin_below_threshold_and_judge_answer_is_final():
    client = FakeSCClient(
        answers=[r"\boxed{1}", r"\boxed{1}", r"\boxed{2}", r"\boxed{2}", r"\boxed{3}"],
        judge_answer=r"\boxed{2}",
        judge_reasoning="re-derived from scratch, 2 is correct",
    )
    item = _item(gold_answer="2")

    result = solve_selfconsistency_math(client, item, n=5, margin_threshold=2)

    assert result["samples_used"] == 5
    assert result["margin"] == 0  # two clusters of size 2 tie for the lead
    assert result["escalated"] is True
    assert client.judge_calls == 1
    assert result["final_answer"] == "2"
    assert result["correct"] is True
    assert result["judge_reasoning"] == "re-derived from scratch, 2 is correct"
    assert len(result["calls"]) == 6  # 5 solver samples + 1 judge
    sizes = sorted((c["size"] for c in result["clusters"]), reverse=True)
    assert sizes == [2, 2, 1]
    # judge_math must have been called with one distinct representative
    # per cluster (3 clusters here), not all 5 raw samples.
    reps = {c["representative_answer"] for c in result["clusters"]}
    assert reps == {"1", "2", "3"}


def test_sc_escalation_when_judge_is_wrong_scores_incorrect():
    client = FakeSCClient(
        answers=[r"\boxed{1}", r"\boxed{1}", r"\boxed{2}", r"\boxed{2}"],
        judge_answer=r"\boxed{100}",
    )
    item = _item(gold_answer="2")

    result = solve_selfconsistency_math(client, item, n=4, margin_threshold=2)

    assert result["escalated"] is True
    assert result["final_answer"] == "100"
    assert result["correct"] is False


def test_sc_margin_meeting_threshold_exactly_does_not_escalate():
    # margin_threshold=2, margin==2 -> escalated must be False ('>=', not
    # strictly '>').
    client = FakeSCClient(answers=[r"\boxed{4}", r"\boxed{4}", r"\boxed{4}", r"\boxed{9}"])
    item = _item(gold_answer="4")

    result = solve_selfconsistency_math(client, item, n=4, margin_threshold=2, early_stop=False)

    assert result["margin"] == 2
    assert result["escalated"] is False
    assert client.judge_calls == 0


# ---------------------------------------------------------------------------
# (d) Tier / lens / temperature-schedule wiring
# ---------------------------------------------------------------------------


def test_sc_uses_temperature_schedule_cycling_and_shared_baseline_lens():
    client = FakeSCClient(answers=[r"\boxed{5}"] * 7)
    item = _item(gold_answer="5")

    solve_selfconsistency_math(client, item, n=7, margin_threshold=2, early_stop=False)

    expected_temps = [SC_TEMPERATURE_SCHEDULE[i % len(SC_TEMPERATURE_SCHEDULE)] for i in range(7)]
    assert [c["temperature"] for c in client.solver_calls] == expected_temps
    # Every sample uses the SAME lens (self-consistency resamples one
    # prompt) -- unlike the panel's 3 DISTINCT lenses.
    assert all(BASELINE_LENS in c["system"] for c in client.solver_calls)


def test_sc_solver_model_and_thinking_pass_through_every_sample():
    from quorumqa.config import MECHANICAL_MODEL

    client = FakeSCClient(answers=[r"\boxed{5}"] * 3)
    item = _item(gold_answer="5")

    result = solve_selfconsistency_math(
        client, item, n=3, margin_threshold=2, solver_model=MECHANICAL_MODEL, solver_thinking=False, early_stop=False
    )

    assert all(c["model"] == MECHANICAL_MODEL for c in client.solver_calls)
    assert all(c["thinking"] is False for c in client.solver_calls)
    assert result["solver_model"] == MECHANICAL_MODEL


def test_sc_default_tier_is_flagship_thinking_true():
    from quorumqa.config import ORCHESTRATOR_MODEL

    client = FakeSCClient(answers=[r"\boxed{5}"] * 3)
    item = _item(gold_answer="5")

    result = solve_selfconsistency_math(client, item, n=3, margin_threshold=2, early_stop=False)

    assert all(c["model"] == ORCHESTRATOR_MODEL for c in client.solver_calls)
    assert all(c["thinking"] is True for c in client.solver_calls)
    assert result["solver_model"] == ORCHESTRATOR_MODEL


def test_sc_output_row_shape():
    client = FakeSCClient(answers=[r"\boxed{5}"] * 3)
    item = _item(gold_answer="5", question_id="q_shape")

    result = solve_selfconsistency_math(client, item, n=3, margin_threshold=2, early_stop=False)

    assert result["question_id"] == "q_shape"
    assert result["gold_answer"] == "5"
    assert result["n_requested"] == 3
    assert set(result.keys()) >= {
        "question_id", "gold_answer", "final_answer", "correct", "escalated",
        "n_requested", "samples_used", "clusters", "margin", "calls",
    }
