"""Offline tests for the flagship_panel compute-matched control.

Covers solve_compute_matched_control (src/quorumqa/baseline.py) with a fake
client, and verify_compute_matched_control's pairing/McNemar logic against
fixture files. No API calls, no tokens.
"""

from __future__ import annotations

import asyncio
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


# --------------------------------------------------------------------------
# main()'s --retry-missing path -- added after seed 123's first live attempt
# dropped 75/90 items to QwenClient's fixed 300s per-call timeout (3
# sequential thinking=True flagship calls per item is far more timeout-prone
# than a single-call baseline). Mirrors qwen38_baseline.py's own resume path.
# --------------------------------------------------------------------------


@pytest.fixture
def fake_loader(monkeypatch):
    """Three fixed items (q1/q2/q3), all correct_letter='A'."""
    import benchmark.run_compute_matched_control as rcmc

    items = [
        GPQAItem(question_id=f"q{i}", question="Q?", choices=["c1", "c2", "c3", "c4"], correct_letter="A")
        for i in (1, 2, 3)
    ]
    monkeypatch.setitem(rcmc.DATASET_LOADERS, "fake_ds", lambda n, seed, skip: items)
    return items


def test_retry_missing_skips_already_done_and_appends(tmp_path, monkeypatch, fake_loader):
    import benchmark.run_compute_matched_control as rcmc

    out = tmp_path / "control.jsonl"
    # Pre-seed q1 as already done (wrong answer, on purpose, to prove it is
    # NOT re-run -- a fresh client would answer differently).
    out.write_text(json.dumps({
        "baseline": {"item": {"question_id": "q1", "correct_letter": "A"},
                      "answer_letter": "B", "correct": False, "calls": [], "latency_s": 0},
        "seed": 1,
    }) + "\n", encoding="utf-8")

    calls_by_qid = {"q1": [], "q2": [], "q3": []}

    def fake_solve(client, item):
        from quorumqa.baseline import BaselineResult
        calls_by_qid[item.question_id].append(1)
        letter = "A"  # every FRESH call answers correctly
        return BaselineResult(item=item, answer_letter=letter, correct=(letter == item.correct_letter),
                               calls=[], latency_s=0.0)

    monkeypatch.setattr(rcmc, "solve_compute_matched_control", fake_solve)
    asyncio.run(rcmc.main(1, 3, 2, out, True, "fake_ds", retry_missing=True))

    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 3
    by_qid = {r["baseline"]["item"]["question_id"]: r for r in rows}
    # q1 untouched -- still the pre-seeded wrong answer, never re-solved.
    assert by_qid["q1"]["baseline"]["answer_letter"] == "B"
    assert calls_by_qid["q1"] == []
    # q2/q3 freshly solved and correct.
    assert by_qid["q2"]["baseline"]["correct"] is True
    assert by_qid["q3"]["baseline"]["correct"] is True
    assert calls_by_qid["q2"] == [1]
    assert calls_by_qid["q3"] == [1]


def test_retry_missing_with_no_existing_file_runs_everything(tmp_path, monkeypatch, fake_loader):
    import benchmark.run_compute_matched_control as rcmc

    out = tmp_path / "control.jsonl"  # does not exist yet
    solved = []

    def fake_solve(client, item):
        from quorumqa.baseline import BaselineResult
        solved.append(item.question_id)
        return BaselineResult(item=item, answer_letter="A", correct=True, calls=[], latency_s=0.0)

    monkeypatch.setattr(rcmc, "solve_compute_matched_control", fake_solve)
    asyncio.run(rcmc.main(1, 3, 2, out, True, "fake_ds", retry_missing=True))

    assert sorted(solved) == ["q1", "q2", "q3"]
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 3


def test_without_retry_missing_always_reruns_everything(tmp_path, monkeypatch, fake_loader):
    """Default behaviour (no --retry-missing) must stay exactly as before:
    a fresh full run overwrites the file, regardless of what was there."""
    import benchmark.run_compute_matched_control as rcmc

    out = tmp_path / "control.jsonl"
    out.write_text(json.dumps({
        "baseline": {"item": {"question_id": "q1"}, "answer_letter": "B",
                      "correct": False, "calls": [], "latency_s": 0},
        "seed": 1,
    }) + "\n", encoding="utf-8")

    solved = []

    def fake_solve(client, item):
        from quorumqa.baseline import BaselineResult
        solved.append(item.question_id)
        return BaselineResult(item=item, answer_letter="A", correct=True, calls=[], latency_s=0.0)

    monkeypatch.setattr(rcmc, "solve_compute_matched_control", fake_solve)
    asyncio.run(rcmc.main(1, 3, 2, out, True, "fake_ds", retry_missing=False))

    assert sorted(solved) == ["q1", "q2", "q3"]  # q1 re-run despite pre-existing row
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 3
    assert all(r["baseline"]["correct"] for r in rows)  # old wrong row is gone


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
