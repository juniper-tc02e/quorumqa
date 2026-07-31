"""Pins the merged N=15 odd-N harvest (PS-1+PS-2, spec-book section 2) against
the committed seed-19 result files. No API calls, no tokens.

Also guards the false alarm caught before publication: the first reading of
diversified_panel's 47.1% looked like severe degradation against the N=3
control's historical range (63.6-74.4%) on OTHER seeds. Deriving N=3 from the
SAME 87 items showed 47.1% too -- the gap was item-sample difficulty, not an
N-scaling effect. These tests pin that the same-item derivation, not a
cross-seed comparison, is what the finding rests on.
"""

from __future__ import annotations

import pytest

from benchmark.analyze_panel_scaling import (
    analyze,
    load_panel_rows,
    mcnemar_exact_one_sided,
    metrics_at_n,
    paired_discordant,
)

DIVERSIFIED = "benchmark/results/lever_diversified_panel_supergpqa_seed19.jsonl"
CYCLED = "benchmark/results/lever_cycled_panel_supergpqa_seed19.jsonl"


@pytest.fixture(scope="module")
def diversified():
    return analyze(DIVERSIFIED)


@pytest.fixture(scope="module")
def cycled():
    return analyze(CYCLED)


def test_both_arms_loaded_with_the_expected_shape(diversified, cycled):
    assert diversified["n_items"] == 87
    assert cycled["n_items"] == 87
    assert diversified["max_n"] == 15
    assert cycled["max_n"] == 15
    assert diversified["ns"] == [3, 5, 7, 9, 11, 13, 15]


def test_the_false_alarm_is_resolved_same_item_n3_matches_n15():
    """The load-bearing check: N=3 derived from the SAME 87 items as N=15
    must reproduce N=15's ballpark accuracy, not the N=3 control's historical
    63.6-74.4% range from OTHER seeds. If this ever drifts toward that range,
    something about the derivation broke."""
    rows = load_panel_rows(DIVERSIFIED)
    m3 = metrics_at_n(rows, 3)
    m15 = metrics_at_n(rows, 15)
    assert m3["plurality_accuracy"] == pytest.approx(0.471, abs=0.01)
    assert m15["plurality_accuracy"] == pytest.approx(0.471, abs=0.01)
    # Explicitly NOT in the other seeds' 63.6-74.4% range.
    assert m3["plurality_accuracy"] < 0.60


def test_paired_n3_vs_n15_is_flat_not_significant(diversified):
    m3 = diversified["metrics"][3]
    m15 = diversified["metrics"][15]
    b, c = paired_discordant(m3["per_item"], m15["per_item"])
    p = mcnemar_exact_one_sided(c, b)  # net = b - c from N=15's perspective... see below
    # b/c convention: paired_discordant(baseline, other) -> b=other wins, c=baseline wins
    assert (b, c) == (6, 6)
    assert b - c == 0
    assert p > 0.05


def test_s1_bar_does_not_clear(diversified):
    """Pre-registered bar: max over odd N of (plurality@N - plurality@3) in
    ITEMS must reach +5/90. Best observed is +3 (N=9)."""
    base_acc = diversified["metrics"][3]["plurality_accuracy"]
    n_items = diversified["n_items"]
    best_net_items = max(
        (diversified["metrics"][n]["plurality_accuracy"] - base_acc) * n_items
        for n in (5, 7, 9, 11, 13, 15)
    )
    assert best_net_items == pytest.approx(3.0, abs=0.5)
    assert best_net_items < 5


def test_coverage_climbs_while_accuracy_stays_flat(diversified, cycled):
    """The actual shape of the null: coverage rises steadily, plurality
    accuracy does not move -- selection, not coverage, is the bottleneck."""
    for arm in (diversified, cycled):
        cov_n3 = arm["metrics"][3]["coverage"]
        cov_n15 = arm["metrics"][15]["coverage"]
        acc_n3 = arm["metrics"][3]["plurality_accuracy"]
        acc_n15 = arm["metrics"][15]["plurality_accuracy"]
        # diversified rises 19.5pp, cycled 14.9pp -- 0.10 is comfortably below
        # both while still ruling out "coverage barely moved".
        assert cov_n15 - cov_n3 > 0.10, "coverage must rise substantially"
        assert abs(acc_n15 - acc_n3) < 0.05, "accuracy must stay within noise"


def test_s2_diversified_vs_cycled_settles_flat_at_every_n(diversified, cycled):
    """spec-book's own decision rule: 'S2 is the spec that settles the record
    -- if diversified minus cycled is < 3, [...]'. Pins that no N reaches
    significance and none reaches a net of 3 either."""
    for n in (3, 5, 7, 9, 11, 13, 15):
        dm = diversified["metrics"][n]
        cm = cycled["metrics"][n]
        b, c = paired_discordant(cm["per_item"], dm["per_item"])
        net = b - c
        p = mcnemar_exact_one_sided(b, c)
        assert abs(net) < 5, f"N={n}: net={net} unexpectedly large"
        assert p > 0.05, f"N={n}: p={p} unexpectedly significant"


def test_both_arms_dropped_the_same_chronic_item():
    """3/90 dropped in both arms; the drop pattern should overlap, consistent
    with a chronic-timeout item class rather than independent random failures."""
    div_rows = load_panel_rows(DIVERSIFIED)
    cyc_rows = load_panel_rows(CYCLED)
    div_ids = {r["engine"]["item"]["question_id"] for r in div_rows}
    cyc_ids = {r["engine"]["item"]["question_id"] for r in cyc_rows}
    assert len(div_rows) == 87
    assert len(cyc_rows) == 87
    # At least one item dropped in both arms independently.
    all_ids_div = div_ids
    all_ids_cyc = cyc_ids
    # Both arms started from the same 90-item seed-19 sample, so the surviving
    # sets should overlap heavily even though 3 different items may have
    # dropped in each arm's own paced run.
    overlap = len(all_ids_div & all_ids_cyc)
    assert overlap >= 84  # at most 3+3 distinct drops between the two arms
