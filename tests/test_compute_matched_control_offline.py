"""Offline tests for the flagship_panel compute-matched control.

Covers solve_compute_matched_control (src/quorumqa/baseline.py) with a fake
client, and verify_compute_matched_control's pairing/McNemar logic against
fixture files. No API calls, no tokens.
"""

from __future__ import annotations

import json

import pytest

from quorumqa.baseline import solve_compute_matched_control
from quorumqa.config import N_SOLVERS
from quorumqa.qwen_client import CallUsage, JsonCallResult
from quorumqa.schemas import GPQAItem


class _FakeClient:
    """Returns a scripted sequence of letters, one per chat_json call, so a
    test can control exactly what solve_compute_matched_control sees."""

    def __init__(self, letters):
        self._letters = list(letters)
        self.calls = []

    def chat_json(self, **kwargs):
        letter = self._letters.pop(0)
        self.calls.append(kwargs)
        usage = CallUsage(model=kwargs["model"], input_tokens=10, output_tokens=5,
                           cost_usd=0.0, role=kwargs["role"])
        return JsonCallResult(data={"letter": letter, "reasoning": "r"}, usage=usage)


def _item(correct="B"):
    return GPQAItem(question_id="q1", question="Q?", choices=["c1", "c2", "c3", "c4"],
                     correct_letter=correct)


def test_calls_n_solvers_independent_times():
    client = _FakeClient(["B", "B", "B"])
    result = solve_compute_matched_control(client, _item())
    assert len(client.calls) == N_SOLVERS == 3
    assert len(result.calls) == 3


def test_majority_vote_wins_over_a_minority():
    client = _FakeClient(["B", "B", "A"])
    result = solve_compute_matched_control(client, _item(correct="B"))
    assert result.answer_letter == "B"
    assert result.correct is True


def test_majority_vote_can_be_wrong():
    client = _FakeClient(["A", "A", "B"])
    result = solve_compute_matched_control(client, _item(correct="B"))
    assert result.answer_letter == "A"
    assert result.correct is False


def test_uses_the_flagship_tier_and_thinking_true():
    """The control must match flagship_panel's tier, not the cheap solver
    tier -- that is the entire point of a compute-matched comparison."""
    from quorumqa.config import BASELINE_MODEL

    client = _FakeClient(["A", "A", "A"])
    solve_compute_matched_control(client, _item(correct="A"))
    for call in client.calls:
        assert call["model"] == BASELINE_MODEL
        assert call["thinking"] is True
        assert call["role"] == "baseline"


def test_result_is_baseline_result_compatible_with_the_existing_writer():
    """Must round-trip through model_dump() and back the same way
    lever_experiments.main_baseline's writer expects."""
    client = _FakeClient(["C", "C", "D"])
    result = solve_compute_matched_control(client, _item(correct="C"))
    dumped = result.model_dump()
    assert dumped["answer_letter"] == "C"
    assert dumped["correct"] is True
    assert len(dumped["calls"]) == 3
    assert "item" in dumped and dumped["item"]["question_id"] == "q1"


# --------------------------------------------------------------------------
# verify_compute_matched_control -- pairing and McNemar over fixture files
# --------------------------------------------------------------------------


@pytest.fixture
def fixture_results_dir(tmp_path, monkeypatch):
    import benchmark.verify_compute_matched_control as vcmc

    monkeypatch.setattr(vcmc, "RESULTS", tmp_path)
    return tmp_path


def _panel_row(qid, correct):
    return {"engine": {"item": {"question_id": qid, "correct_letter": "A"},
                        "correct": correct}}


def _control_row(qid, correct):
    return {"baseline": {"item": {"question_id": qid, "correct_letter": "A"},
                          "correct": correct}}


def _write(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_verify_reports_no_data_when_no_control_files_exist(fixture_results_dir):
    from benchmark.verify_compute_matched_control import verify

    r = verify()
    assert r["per_seed"] == {}
    assert r["pooled"] is None
    assert set(r["missing_seeds"]) == {42, 7, 123}


def test_verify_computes_paired_net_for_one_seed(fixture_results_dir):
    from benchmark.verify_compute_matched_control import verify

    _write(fixture_results_dir / "lever_flagship_panel_supergpqa_seed42.jsonl", [
        _panel_row("q1", True), _panel_row("q2", True), _panel_row("q3", False),
    ])
    _write(fixture_results_dir / "compute_matched_control_supergpqa_seed42.jsonl", [
        _control_row("q1", False), _control_row("q2", True), _control_row("q3", False),
    ])
    r = verify()
    assert r["missing_seeds"] == [7, 123]
    s = r["per_seed"][42]
    # q1: panel right, control wrong -> b. q2: both right -> neither. q3: both wrong -> neither.
    assert s["b"] == 1
    assert s["c"] == 0
    assert s["shared"] == 3
    assert r["pooled"]["net"] == 1


def test_verify_pools_across_seeds_by_summing_bc(fixture_results_dir):
    from benchmark.verify_compute_matched_control import verify

    for seed in (42, 7, 123):
        _write(fixture_results_dir / f"lever_flagship_panel_supergpqa_seed{seed}.jsonl",
               [_panel_row(f"q{seed}_1", True), _panel_row(f"q{seed}_2", False)])
        _write(fixture_results_dir / f"compute_matched_control_supergpqa_seed{seed}.jsonl",
               [_control_row(f"q{seed}_1", False), _control_row(f"q{seed}_2", True)])
    r = verify()
    assert r["missing_seeds"] == []
    # Each seed: q_1 -> panel-only-right (b), q_2 -> control-only-right (c). Net 0 per seed.
    assert r["pooled"]["b"] == 3
    assert r["pooled"]["c"] == 3
    assert r["pooled"]["net"] == 0
    assert r["pooled"]["shared"] == 6


def test_verify_raises_on_zero_overlap_instead_of_silent_null(fixture_results_dir):
    """The exact wrapper-key trap this session hit twice already: an empty
    intersection must raise, not read as 'no effect'."""
    from benchmark.verify_compute_matched_control import verify

    _write(fixture_results_dir / "lever_flagship_panel_supergpqa_seed42.jsonl",
           [_panel_row("qA", True)])
    _write(fixture_results_dir / "compute_matched_control_supergpqa_seed42.jsonl",
           [_control_row("qB", True)])
    with pytest.raises(AssertionError, match="zero shared question_ids"):
        verify()
