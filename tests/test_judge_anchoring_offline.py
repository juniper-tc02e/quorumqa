"""Offline tests pinning the unanimous-gate-headroom finding.

Guards two things that are easy to lose:
  1. The record shape. An earlier pass of this analysis keyed on `engine.judge`
     and `solver_answers[].letter`; the real field is `engine.verdict`. The wrong
     key yields ZERO escalations and reads as "no data" rather than as a bug, so
     a nonzero-count assertion is the only thing standing between us and a
     silent false null.
  2. The numbers quoted in `benchmark/results/unanimous_gate_headroom.md`.

Pins updated 2026-07-30 after `lever_universal_gate_gpqa_seed1001.jsonl` (90
rows, 48 unanimous panels: 12 wrong, 36 right) was committed -- this script
globs every result file, so a legitimately new committed run shifts every
pooled number here. Each new value below was verified to shift by EXACTLY that
run's own contribution (e.g. unanimous_wrong_escalations 84->96 is +12, not an
unrelated drift) before being pinned -- see the commit that added this comment
for the arithmetic.

Pins updated again 2026-07-31 after the Tier D odd-N harvest
(`lever_diversified_panel_supergpqa_seed19.jsonl`,
`lever_cycled_panel_supergpqa_seed19.jsonl`, both `--no-tribunal`) was
committed. Neither run can ever escalate, so they shift ONLY the raw
unanimous-panel counts, not any escalation-derived figure: 8+22=30 new
unanimous panels (verified directly against each file's own `unanimous` field
before pinning), of which 10 were wrong -- unanimous_total 3708->3738,
unanimous_total_wrong 671->681, unanimous_unescalated_wrong 576->586. Every
escalation-side number (escalations, off_slate, unanimous_wrong_escalations,
unanimous_wrong_recovered, unanimous_right_escalations,
unanimous_right_broken, by_dataset) is unchanged, exactly as expected for a
no-tribunal run.
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
    assert r["escalations"] == 2088
    assert r["off_slate"] == 216
    assert r["off_slate_correct"] == 180
    # Off-slate picks are right far more often than not: no licence needed.
    assert r["off_slate_correct"] / r["off_slate"] > 0.80
    # And on the all-solvers-wrong subset the Judge still recovers ~45%.
    assert r["gold_unoffered"] == 398
    assert r["gold_unoffered_recovered"] == 180


def test_unanimous_wrong_recovery_and_breakage(r):
    """The core asymmetry: recovered vs broken. Both moved in universal_gate's
    favor after its live run was committed (49/96 recovery, still ~1% broken)."""
    assert r["unanimous_wrong_escalations"] == 96
    assert r["unanimous_wrong_recovered"] == 49
    assert r["unanimous_right_escalations"] == 166
    assert r["unanimous_right_broken"] == 1

    recovery = r["unanimous_wrong_recovered"] / r["unanimous_wrong_escalations"]
    breakage = r["unanimous_right_broken"] / r["unanimous_right_escalations"]
    assert recovery == pytest.approx(0.510, abs=0.001)
    assert breakage == pytest.approx(0.0060, abs=0.001)
    # The load-bearing claim of the write-up.
    assert recovery / breakage > 50


def test_break_even_is_far_below_the_measured_wrong_rate(r):
    recovery = r["unanimous_wrong_recovered"] / r["unanimous_wrong_escalations"]
    breakage = r["unanimous_right_broken"] / r["unanimous_right_escalations"]
    break_even = breakage / (recovery + breakage)
    w = r["unanimous_total_wrong"] / r["unanimous_total"]

    assert break_even == pytest.approx(0.0117, abs=0.002)
    assert w == pytest.approx(0.181, abs=0.002)
    assert w > break_even * 10, "the >10x-above-break-even claim"


def test_gate_recall_and_headroom(r):
    assert r["unanimous_total"] == 3738
    assert r["unanimous_total_wrong"] == 681
    assert r["unanimous_unescalated_wrong"] == 586
    recall = r["unanimous_wrong_escalations"] / r["unanimous_total_wrong"]
    assert recall == pytest.approx(0.141, abs=0.002)


def test_w_is_not_the_61_6_percent_figure(r):
    """Different denominators; conflating them was an explicit trap."""
    w = r["unanimous_total_wrong"] / r["unanimous_total"]
    assert w < 0.25, (
        "w is the wrong-rate among UNANIMOUS rows (~18%), not the unanimous "
        "share of WRONG rows (61.6%)"
    )


def test_supergpqa_converts_far_worse_than_gpqa(r):
    """The pooled rate must never be quoted as a per-benchmark rate."""
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

    # dataset="gpqa" (explicit --dataset flag, e.g. universal_gate seed 1001)
    # is a THIRD bucket distinct from gpqa(default) -- and now the strongest:
    # universal_gate's own 12 wrong / 9 recovered = 75.0% landed here.
    gpqa_explicit = ds["gpqa"]
    assert gpqa_explicit["wrong"] == 24 and gpqa_explicit["recovered"] == 18
    assert gpqa_explicit["recovered"] / gpqa_explicit["wrong"] == pytest.approx(0.75, abs=0.001)

    # Breakage is ~0 on every surface, which is why accuracy is positive
    # nearly everywhere and COST is the real constraint.
    total_right = sum(c.get("right", 0) for c in ds.values())
    total_broken = sum(c.get("broken", 0) for c in ds.values())
    assert total_right == 166
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
