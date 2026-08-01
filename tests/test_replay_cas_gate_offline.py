"""Offline tests for benchmark/replay_cas_gate_on_wrong_pool.py (KI-0R).

No API calls: the one paid call (cas_gate_check) is monkeypatched, and
sympy_check runs locally for free anyway. Covers the pooling/dedup scoping,
the p_check / y_detect / product arithmetic, the Wilson interval, and the
gate_would_fire rule matching lever_experiments' own escalation condition.
"""

from __future__ import annotations

import asyncio

import pytest

import benchmark.replay_cas_gate_on_wrong_pool as ki0r
from benchmark.replay_cas_gate_on_wrong_pool import (
    GATE_THRESHOLD,
    _replay_one,
    _to_solver_answers,
    _unanimous,
    _wilson,
    inventory_both_pools,
    summarize,
)


def _engine(letters, correct: bool) -> dict:
    return {
        "item": {"question_id": "q1", "question": "Q", "choices": ["a", "b", "c", "d"]},
        "solver_answers": [
            {"letter": L, "lens": f"lens{i}", "confidence": 0.9, "reasoning": "r"}
            for i, L in enumerate(letters)
        ],
        "plurality_letter": letters[0],
        "correct": correct,
    }


# ---------------------------------------------------------------------------
# Unanimity predicate -- must agree with classify_pool_checkability's scoping
# ---------------------------------------------------------------------------


def test_unanimous_true_only_when_all_three_agree():
    assert _unanimous(_engine(["A", "A", "A"], True)) is True
    assert _unanimous(_engine(["A", "A", "B"], True)) is False


def test_non_three_seat_rows_are_skipped():
    """Guards against a differently-shaped lever (e.g. `five`) leaking in."""
    assert _unanimous(_engine(["A", "A"], True)) is False
    assert _unanimous(_engine(["A"] * 5, True)) is False


def test_blank_letters_never_count_as_unanimous():
    assert _unanimous(_engine(["", "", ""], True)) is False


# ---------------------------------------------------------------------------
# SolverAnswer reconstruction -- cas_gate_check reads .lens/.reasoning
# ---------------------------------------------------------------------------


def test_to_solver_answers_rebuilds_attribute_access():
    raw = _engine(["A", "A", "A"], False)["solver_answers"]
    objs = _to_solver_answers(raw)
    assert len(objs) == 3
    assert objs[0].lens == "lens0"
    assert objs[0].reasoning == "r"
    assert objs[0].letter == "A"


# ---------------------------------------------------------------------------
# Summary arithmetic
# ---------------------------------------------------------------------------


def _row(checkable: bool, status: str, tokens: int = 100) -> dict:
    return {
        "question_id": "q", "checkable": checkable, "relation": "1=1",
        "candidate": "1", "status": status, "detail": "",
        "gate_would_fire": status == "fail", "tokens": tokens,
    }


def test_summarize_computes_p_check_y_detect_and_product():
    rows = [
        _row(True, "fail"),          # parseable, gate fires
        _row(True, "fail"),          # parseable, gate fires
        _row(True, "pass"),          # parseable, no fire
        _row(True, "unparseable"),   # checkable but NOT parseable
        _row(False, "not_checkable"),
    ]
    s = summarize(rows, n_attempted=5)
    assert s["n_completed"] == 5
    assert s["n_checkable"] == 4
    assert s["n_parseable"] == 3      # unparseable excluded
    assert s["n_unparseable"] == 1
    assert s["n_gate_fires"] == 2
    assert s["p_check"] == pytest.approx(3 / 5)
    assert s["y_detect"] == pytest.approx(2 / 3)
    assert s["product"] == pytest.approx(2 / 5)


def test_product_is_the_quantity_the_gate_tests():
    """product must equal gate_fires/n directly, not p_check*y_detect computed
    separately -- rounding two ratios then multiplying drifts."""
    rows = [_row(True, "fail")] * 7 + [_row(True, "pass")] * 11 + [_row(False, "not_checkable")] * 13
    s = summarize(rows, n_attempted=31)
    assert s["product"] == pytest.approx(7 / 31)
    assert s["p_check"] * s["y_detect"] == pytest.approx(s["product"])


def test_summarize_reports_drops_rather_than_hiding_them():
    s = summarize([_row(True, "fail")], n_attempted=10)
    assert s["n_completed"] == 1
    assert s["n_dropped"] == 9


def test_summarize_handles_an_all_unparseable_pool():
    """The expected-outcome case: the model emits relations, none parse.
    y_detect must be None (undefined), not 0-divided."""
    rows = [_row(True, "unparseable")] * 5
    s = summarize(rows, n_attempted=5)
    assert s["n_parseable"] == 0
    assert s["y_detect"] is None
    assert s["product"] == 0.0


# ---------------------------------------------------------------------------
# Wilson interval -- correct at the near-zero rates this replay expects
# ---------------------------------------------------------------------------


def test_wilson_zero_successes_has_zero_lower_bound_and_nonzero_upper():
    lo, hi = _wilson(0, 110)
    assert lo == 0.0
    assert 0.0 < hi < 0.05
    # A normal approximation would give [0, 0] here -- the whole reason for Wilson.


def test_wilson_brackets_the_point_estimate():
    lo, hi = _wilson(5, 110)
    assert lo < 5 / 110 < hi


def test_wilson_empty_pool_is_safe():
    assert _wilson(0, 0) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# _replay_one: the gate rule, and that sympy runs only on a checkable relation
# ---------------------------------------------------------------------------


def _fake_cas(result):
    """Returns a cas_gate_check stand-in yielding a fixed triple."""
    class _U:
        input_tokens, output_tokens = 50, 50

    def fake(client, question, choices, solver_answers, plurality_letter):
        checkable, relation, candidate = result
        return checkable, relation, candidate, _U()
    return fake


def _rec():
    e = _engine(["A", "A", "A"], False)
    return {
        "question_id": "q1", "question": "Q", "choices": e["item"]["choices"],
        "solver_answers": e["solver_answers"], "plurality_letter": "A", "source": "f.jsonl",
    }


def test_replay_fires_the_gate_only_on_a_failing_sympy_check(monkeypatch):
    # A relation that is arithmetically FALSE -> sympy 'fail' -> gate fires.
    monkeypatch.setattr(ki0r, "cas_gate_check", _fake_cas((True, "2 + 2 = 5", "5")))
    out = asyncio.run(_replay_one(None, _rec(), asyncio.Semaphore(1)))
    assert out["status"] == "fail"
    assert out["gate_would_fire"] is True


def test_replay_does_not_fire_when_the_model_writes_a_self_consistent_check(monkeypatch):
    """The structural failure mode the whole script exists to measure: a model
    reconstructing its own chain writes an equation that PASSES, so a wrong
    answer never escalates."""
    monkeypatch.setattr(ki0r, "cas_gate_check", _fake_cas((True, "2 + 2 = 4", "4")))
    out = asyncio.run(_replay_one(None, _rec(), asyncio.Semaphore(1)))
    assert out["status"] == "pass"
    assert out["gate_would_fire"] is False


def test_replay_skips_sympy_entirely_when_not_checkable(monkeypatch):
    monkeypatch.setattr(ki0r, "cas_gate_check", _fake_cas((False, "", "")))
    out = asyncio.run(_replay_one(None, _rec(), asyncio.Semaphore(1)))
    assert out["status"] == "not_checkable"
    assert out["gate_would_fire"] is False


def test_replay_marks_unparseable_relations_without_firing(monkeypatch):
    monkeypatch.setattr(ki0r, "cas_gate_check", _fake_cas((True, "c3 point group", "c3")))
    out = asyncio.run(_replay_one(None, _rec(), asyncio.Semaphore(1)))
    assert out["status"] == "unparseable"
    assert out["gate_would_fire"] is False


def test_replay_returns_none_after_exhausting_retries(monkeypatch):
    def always_raises(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(ki0r, "cas_gate_check", always_raises)

    async def run():
        return await _replay_one(None, _rec(), asyncio.Semaphore(1), sleep_fn=lambda s: asyncio.sleep(0))
    assert asyncio.run(run()) is None


# ---------------------------------------------------------------------------
# Real-pool scoping -- pins the committed pool sizes
# ---------------------------------------------------------------------------


def test_real_pools_reproduce_the_committed_gpqa_size():
    """GPQA's unanimous-wrong pool is 34 in benchmark/results/pool_checkability.md
    and must stay 34 here -- identical scoping (control-lever only, deduped).

    SuperGPQA is deliberately NOT pinned: this session's own META-2 control runs
    (seeds 909/1313/2027) legitimately grew it 110 -> 151, verified attributable
    (17+12+12 = 41 new unique items). Pinning it would break on every future
    control run, which is data growth rather than a defect.
    """
    pools = inventory_both_pools(["gpqa", "supergpqa"])
    assert len(pools["gpqa"]["wrong"]) == 34
    assert len(pools["supergpqa"]["wrong"]) >= 110
    # Both buckets must be populated or the specificity arm is silently empty.
    assert len(pools["gpqa"]["right"]) > 0
    assert len(pools["supergpqa"]["right"]) > 0


def test_pools_are_disjoint_between_wrong_and_right():
    """An item cannot be both; overlap would mean the correct field is being
    read inconsistently across files."""
    pools = inventory_both_pools(["gpqa", "supergpqa"])
    for ds in ("gpqa", "supergpqa"):
        assert not (set(pools[ds]["wrong"]) & set(pools[ds]["right"]))


def test_pool_records_carry_what_cas_gate_check_needs():
    pools = inventory_both_pools(["gpqa"])
    rec = next(iter(pools["gpqa"]["wrong"].values()))
    assert rec["question"] and rec["choices"]
    assert len(rec["solver_answers"]) == 3
    assert rec["plurality_letter"]
    # Must round-trip into real SolverAnswer objects, not just dicts.
    objs = _to_solver_answers(rec["solver_answers"])
    assert all(o.reasoning is not None for o in objs)


def test_gate_threshold_matches_the_pre_registered_value():
    """5 / (33.8 * 0.476) = 0.311 -- changing this silently would move the
    kill clause after the fact."""
    assert GATE_THRESHOLD == pytest.approx(0.311, abs=0.001)
    assert 5 / (33.8 * 0.476) == pytest.approx(GATE_THRESHOLD, abs=0.002)
