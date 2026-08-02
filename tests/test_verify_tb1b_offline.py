"""Offline tests for benchmark/verify_tb1b_supergpqa.py.

Written BEFORE the screen's result is read, per docs/spec-tb1b-supergpqa.md.
Synthetic fixtures throughout: these prove the ANALYSIS is right, not that any
particular result occurred.

The property that matters most here is that the PRIMARY claim (vs a flagship
call) and the SECONDARY claim (vs the shipped escalate-on-split rule) never
get conflated -- reporting the latter as the former is precisely how
universal_gate's GPQA +25 came to read as a flagship win when it was a
cheap-panel win.
"""

from __future__ import annotations

import json

import pytest

import benchmark.verify_tb1b_supergpqa as tb1b
from benchmark.verify_tb1b_supergpqa import (
    INTENDED_N,
    MIN_ANALYSIS_SET,
    MIN_NET,
    SCREEN_KILL_MAX_NET,
    SCREEN_SEED,
    verify,
)


def _ug_row(qid, gold, letters, final):
    """A universal_gate row: 3 solver letters, a final letter after the tribunal."""
    return {
        "engine": {
            "item": {"question_id": qid, "correct_letter": gold},
            "solver_answers": [{"letter": L} for L in letters],
            "plurality_letter": letters[0],
            "final_letter": final,
            "correct": final == gold,
            "escalated": True,
            "calls": [{"input_tokens": 5000, "output_tokens": 5000}],
        }
    }


def _bl_row(qid, gold, answer):
    return {"baseline": {"item": {"question_id": qid, "correct_letter": gold},
                         "correct": answer == gold,
                         "calls": [{"input_tokens": 1500, "output_tokens": 1500}]}}


def _write(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _setup(tmp_path, monkeypatch, seed, ug_rows, bl_rows):
    monkeypatch.setattr(tb1b, "RESULTS", tmp_path)
    _write(tmp_path / f"TB1B_universal_gate_supergpqa_seed{seed}.jsonl", ug_rows)
    _write(tmp_path / f"lever_baseline_supergpqa_seed{seed}.jsonl", bl_rows)


# ---------------------------------------------------------------------------
# The two claims must not be conflated
# ---------------------------------------------------------------------------


def test_primary_and_secondary_are_computed_independently(tmp_path, monkeypatch):
    """Construct a case where universal_gate BEATS the shipped rule handsomely
    but only TIES the flagship. The secondary must show the win; the primary
    must show the tie. That divergence is the whole point of the spec."""
    ug, bl = [], []
    for i in range(90):
        qid = f"q{i}"
        if i < 20:
            # Unanimous-WRONG that the tribunal recovers: shipped rule loses
            # this item, universal_gate wins it. Flagship also gets it right.
            ug.append(_ug_row(qid, "A", ["B", "B", "B"], "A"))
            bl.append(_bl_row(qid, "A", "A"))
        else:
            ug.append(_ug_row(qid, "A", ["A", "A", "A"], "A"))
            bl.append(_bl_row(qid, "A", "A"))
    _setup(tmp_path, monkeypatch, 7, ug, bl)

    s = verify()["per_seed"][7]
    assert s["vs_shipped_rule"]["net"] == 20, "should beat the shipped rule by 20"
    assert s["vs_flagship"]["net"] == 0, "should merely TIE the flagship"
    assert s["recovered"] == 20 and s["broken"] == 0


def test_a_win_over_the_shipped_rule_does_not_clear_the_primary(tmp_path, monkeypatch):
    ug, bl = [], []
    for i in range(90):
        qid = f"q{i}"
        ug.append(_ug_row(qid, "A", ["B", "B", "B"], "A") if i < 30
                  else _ug_row(qid, "A", ["A", "A", "A"], "A"))
        bl.append(_bl_row(qid, "A", "A"))
    _setup(tmp_path, monkeypatch, 7, ug, bl)

    r = verify()
    assert r["pooled_vs_shipped_rule"]["net"] == 30
    assert r["pooled_vs_flagship"]["clears"] is False


# ---------------------------------------------------------------------------
# Primary bar
# ---------------------------------------------------------------------------


def test_primary_clears_on_a_real_win(tmp_path, monkeypatch):
    ug, bl = [], []
    for i in range(90):
        qid = f"q{i}"
        ug.append(_ug_row(qid, "A", ["A", "A", "A"], "A"))
        # Flagship misses 6 items that universal_gate gets -> b=6, c=0.
        bl.append(_bl_row(qid, "A", "B" if i < 6 else "A"))
    _setup(tmp_path, monkeypatch, 7, ug, bl)

    p = verify()["pooled_vs_flagship"]
    assert (p["b"], p["c"], p["net"]) == (6, 0, 6)
    assert p["net"] >= MIN_NET
    assert p["p_one_sided"] < 0.05
    assert p["clears"] is True


def test_primary_requires_both_net_and_significance(tmp_path, monkeypatch):
    """net +5 with losses does not clear: b=8 c=3 is net +5 but p>0.05."""
    ug, bl = [], []
    for i in range(90):
        qid = f"q{i}"
        if i < 8:
            ug.append(_ug_row(qid, "A", ["A", "A", "A"], "A")); bl.append(_bl_row(qid, "A", "B"))
        elif i < 11:
            ug.append(_ug_row(qid, "A", ["B", "B", "B"], "B")); bl.append(_bl_row(qid, "A", "A"))
        else:
            ug.append(_ug_row(qid, "A", ["A", "A", "A"], "A")); bl.append(_bl_row(qid, "A", "A"))
    _setup(tmp_path, monkeypatch, 7, ug, bl)

    p = verify()["pooled_vs_flagship"]
    assert p["net"] == 5
    assert p["p_one_sided"] > 0.05
    assert p["clears"] is False


# ---------------------------------------------------------------------------
# Screen kill
# ---------------------------------------------------------------------------


def test_screen_kill_fires_on_a_non_positive_net(tmp_path, monkeypatch):
    ug, bl = [], []
    for i in range(90):
        qid = f"q{i}"
        ug.append(_ug_row(qid, "A", ["A", "A", "A"], "A"))
        bl.append(_bl_row(qid, "A", "A"))
    _setup(tmp_path, monkeypatch, SCREEN_SEED, ug, bl)

    r = verify()
    assert r["per_seed"][SCREEN_SEED]["vs_flagship"]["net"] == 0
    assert 0 <= SCREEN_KILL_MAX_NET
    assert r["screen_killed"] is True


def test_screen_kill_does_not_fire_on_a_positive_net(tmp_path, monkeypatch):
    ug, bl = [], []
    for i in range(90):
        qid = f"q{i}"
        ug.append(_ug_row(qid, "A", ["A", "A", "A"], "A"))
        bl.append(_bl_row(qid, "A", "B" if i < 3 else "A"))
    _setup(tmp_path, monkeypatch, SCREEN_SEED, ug, bl)

    assert verify()["screen_killed"] is False


# ---------------------------------------------------------------------------
# Analysis-set gate and cost kill
# ---------------------------------------------------------------------------


def test_gate_measures_against_the_intended_n_not_the_arm_row_count(tmp_path, monkeypatch):
    """Both arms could each look complete while their INTERSECTION collapses."""
    ug = [_ug_row(f"q{i}", "A", ["A", "A", "A"], "A") for i in range(90)]
    bl = [_bl_row(f"q{i}", "A", "A") for i in range(70)]
    _setup(tmp_path, monkeypatch, 7, ug, bl)

    s = verify()["per_seed"][7]
    assert s["n_shared"] == 70
    assert s["gate_ok"] is False
    assert s["dropped_vs_intended"] == INTENDED_N - 70
    assert MIN_ANALYSIS_SET == 81


def test_cost_kill_fires_when_expensive_and_not_winning(tmp_path, monkeypatch):
    """universal_gate measured 13,541 tok/item on GPQA and the spec budgets
    ~15,000 on SuperGPQA, against the flagship's measured 2,969 -- ~5x. With
    net under the bar that is 'dominated', the same wording GPQA's result got.

    (An earlier version of this test used the 10,000 tok/item the generic row
    helper produces, which is only 3.37x -- the fixture was unrealistic, not
    the threshold. Using a real lever cost here keeps the test honest about
    what it is checking.)
    """
    ug = [_ug_row(f"q{i}", "A", ["A", "A", "A"], "A") for i in range(90)]
    for row in ug:
        row["engine"]["calls"] = [{"input_tokens": 7500, "output_tokens": 7500}]
    bl = [_bl_row(f"q{i}", "A", "A") for i in range(90)]
    _setup(tmp_path, monkeypatch, 7, ug, bl)

    cost = verify()["cost"]
    assert cost["tokens_per_item"] == pytest.approx(15000)
    assert cost["ratio"] > 4.0
    assert cost["cost_killed"] is True


def test_cost_kill_does_not_fire_when_the_arm_actually_wins(tmp_path, monkeypatch):
    """Expensive is only 'dominated' if it also fails to clear the bar."""
    ug = [_ug_row(f"q{i}", "A", ["A", "A", "A"], "A") for i in range(90)]
    for row in ug:
        row["engine"]["calls"] = [{"input_tokens": 7500, "output_tokens": 7500}]
    bl = [_bl_row(f"q{i}", "A", "B" if i < 8 else "A") for i in range(90)]
    _setup(tmp_path, monkeypatch, 7, ug, bl)

    r = verify()
    assert r["cost"]["ratio"] > 4.0
    assert r["pooled_vs_flagship"]["net"] >= MIN_NET
    assert r["cost"]["cost_killed"] is False


def test_no_files_is_reported_not_crashed(tmp_path, monkeypatch):
    monkeypatch.setattr(tb1b, "RESULTS", tmp_path)
    r = verify()
    assert r["per_seed"] == {}
    assert r["screen_killed"] is False
