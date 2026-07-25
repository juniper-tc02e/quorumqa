"""Offline tests pinning the unanimous-gate-headroom finding.

Guards two things that are easy to lose:
  1. The record shape. An earlier pass of this analysis keyed on `engine.judge`
     and `solver_answers[].letter`; the real field is `engine.verdict`. The wrong
     key yields ZERO escalations and reads as "no data" rather than as a bug, so
     a nonzero-count assertion is the only thing standing between us and a
     silent false null.
  2. The numbers quoted in `benchmark/results/unanimous_gate_headroom.md`.
"""

from __future__ import annotations

import pytest

from benchmark.analyze_judge_anchoring import collect


@pytest.fixture(scope="module")
def r():
    return collect()


def test_records_are_actually_found(r):
    """The silent-false-null guard -- see docstring."""
    assert r["escalations"] > 1000, (
        "found almost no escalations; the record shape probably changed "
        "(verdict/solver_answers keys) -- this reads as 'no effect' but is a bug"
    )
    assert r["unanimous_total"] > 1000


def test_judge_is_not_anchored_to_the_solver_slate(r):
    """Kills the AggLM none-of-the-above licence lever."""
    assert r["escalations"] == 1998
    assert r["off_slate"] == 203
    assert r["off_slate_correct"] == 169
    # Off-slate picks are right far more often than not: no licence needed.
    assert r["off_slate_correct"] / r["off_slate"] > 0.80
    # And on the all-solvers-wrong subset the Judge still recovers ~45%.
    assert r["gold_unoffered"] == 378
    assert r["gold_unoffered_recovered"] == 169


def test_unanimous_wrong_recovery_and_breakage(r):
    """The core asymmetry: ~48% recovered vs ~1% broken."""
    assert r["unanimous_wrong_escalations"] == 84
    assert r["unanimous_wrong_recovered"] == 40
    assert r["unanimous_right_escalations"] == 130
    assert r["unanimous_right_broken"] == 1

    recovery = r["unanimous_wrong_recovered"] / r["unanimous_wrong_escalations"]
    breakage = r["unanimous_right_broken"] / r["unanimous_right_escalations"]
    assert recovery == pytest.approx(0.476, abs=0.001)
    assert breakage == pytest.approx(0.0077, abs=0.001)
    # The load-bearing claim of the write-up.
    assert recovery / breakage > 50


def test_break_even_is_far_below_the_measured_wrong_rate(r):
    recovery = r["unanimous_wrong_recovered"] / r["unanimous_wrong_escalations"]
    breakage = r["unanimous_right_broken"] / r["unanimous_right_escalations"]
    break_even = breakage / (recovery + breakage)
    w = r["unanimous_total_wrong"] / r["unanimous_total"]

    assert break_even == pytest.approx(0.016, abs=0.002)
    assert w == pytest.approx(0.180, abs=0.002)
    assert w > break_even * 10, "the 11x-above-break-even claim"


def test_gate_recall_and_headroom(r):
    assert r["unanimous_total"] == 3660
    assert r["unanimous_total_wrong"] == 659
    assert r["unanimous_unescalated_wrong"] == 576
    recall = r["unanimous_wrong_escalations"] / r["unanimous_total_wrong"]
    assert recall == pytest.approx(0.127, abs=0.002)


def test_w_is_not_the_61_6_percent_figure(r):
    """Different denominators; conflating them was an explicit trap."""
    w = r["unanimous_total_wrong"] / r["unanimous_total"]
    assert w < 0.25, (
        "w is the wrong-rate among UNANIMOUS rows (~18%), not the unanimous "
        "share of WRONG rows (61.6%)"
    )


def test_supergpqa_converts_far_worse_than_gpqa(r):
    """The pooled 47.6% must never be quoted as a per-benchmark rate."""
    ds = r["by_dataset"]
    sg = ds["supergpqa"]
    assert sg["wrong"] == 21 and sg["recovered"] == 2
    sg_rate = sg["recovered"] / sg["wrong"]
    assert sg_rate < 0.15

    gpqa_default = ds["gpqa(default)"]
    assert gpqa_default["wrong"] == 49 and gpqa_default["recovered"] == 27
    gpqa_rate = gpqa_default["recovered"] / gpqa_default["wrong"]
    assert gpqa_rate > 0.50
    # The spread that makes the pooled figure misleading on its own.
    assert gpqa_rate / sg_rate > 4

    # Breakage is ~0 on every surface, which is why accuracy is positive
    # nearly everywhere and COST is the real constraint.
    total_right = sum(c.get("right", 0) for c in ds.values())
    total_broken = sum(c.get("broken", 0) for c in ds.values())
    assert total_right == 130
    assert total_broken == 1


def test_dataset_cells_sum_to_the_pooled_totals(r):
    """Internal consistency -- catches double counting across wrappers."""
    ds = r["by_dataset"]
    assert sum(c.get("wrong", 0) for c in ds.values()) == r[
        "unanimous_wrong_escalations"
    ]
    assert sum(c.get("recovered", 0) for c in ds.values()) == r[
        "unanimous_wrong_recovered"
    ]
    assert sum(c.get("right", 0) for c in ds.values()) == r[
        "unanimous_right_escalations"
    ]
