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

Pins updated again 2026-08-01 after META-2's 6 result files (control +
permuted_panel at seeds 909/1313/2027) were committed. Unlike Tier D, these
DO use the real tribunal (control/permuted_panel have no gate logic that
force-escalates a unanimous vote, but genuine 2-1 splits still escalate
normally), so this shift touches BOTH sides: +262 new unanimous rows
(verified directly: 43+44+46+38+53+38=262 across the six files) ->
unanimous_total 3738->4000, unanimous_total_wrong 681->753,
unanimous_unescalated_wrong 586->658; AND +268 new escalations (2088->2356,
all from genuine splits, not unanimity-gated) -> off_slate 216->245,
off_slate_correct 180->203, gold_unoffered 398->448,
gold_unoffered_recovered 180->203. unanimous_wrong_escalations (96),
unanimous_wrong_recovered (49), unanimous_right_escalations (166),
unanimous_right_broken (1), and by_dataset are ALL unchanged -- every one of
META-2's escalations came from a split, never from a unanimous panel hitting
a gate, so none of them land in the unanimous_*_escalations buckets.

RESTRUCTURED 2026-08-03, on the fifth re-pin, because four re-pins is a
design telling you something.

The trigger was TB-1B's seed-7 file. Every shift checked out exactly
(escalations +89, unanimous_total +47, unanimous_wrong_escalations +18,
recovered +8, unanimous_right_escalations +29, broken +2 -- all equal to that
one file's own contribution, no unrelated drift). But verifying the fifth
re-pin surfaced something the previous four had hidden: **the doc these pins
claim to guard was never moving with them.** `unanimous_gate_headroom.md`
publishes 3,660 unanimous panels; the pins went 3708 -> 3738 -> 4000 -> 4130.
Each re-pin was performed carefully and each one widened the gap to the
published number, because the pins track a growing glob of `results/*.jsonl`
and the doc is a dated snapshot that cannot.

So the assertions are now split by what they actually are:

  STRUCTURAL -- true of any corpus, and the real content of the finding.
  Ratios, inequalities and internal consistency. These never need re-pinning
  and they are what the write-up's argument rests on.

  SNAPSHOT -- exact pooled counts, valid only for one corpus. Collected into
  a single CORPUS_SNAPSHOT dict stamped with its date and file count, so
  re-pinning is one obvious edit rather than numbers scattered through six
  tests, and so a reader can see at a glance that these are a point-in-time
  measurement rather than a claim.

The file count is pinned too. Previously a new run shifted the totals with no
independent signal that the corpus itself had changed, which is exactly what
made the doc drift invisible.
"""

from __future__ import annotations

import pytest

from benchmark.analyze_judge_anchoring import collect, corpus_size

#: Exact pooled values for ONE corpus. Not claims -- a measurement of a file
#: set. When a new result file lands these all move, and the correct response
#: is to verify each delta equals the new file's own contribution (see the
#: 2026-08-03 entry above for the arithmetic) and then update this block.
CORPUS_SNAPSHOT = {
    "as_of": "2026-08-03",
    "n_result_files": 105,
    "last_added": "TB1_flagship_sc5_gpqa_seed1001.jsonl",
    "escalations": 2624,
    "off_slate": 286,
    "off_slate_correct": 235,
    "gold_unoffered": 508,
    "gold_unoffered_recovered": 235,
    "unanimous_wrong_escalations": 140,
    "unanimous_wrong_recovered": 73,
    "unanimous_right_escalations": 278,
    "unanimous_right_broken": 3,
    "unanimous_total": 4256,
    "unanimous_total_wrong": 803,
    "unanimous_unescalated_wrong": 664,
}


@pytest.fixture(scope="module")
def r():
    return collect()


# ---------------------------------------------------------------------------
# SNAPSHOT -- exact counts, valid for one corpus only
# ---------------------------------------------------------------------------


def test_the_corpus_is_the_one_the_snapshot_was_taken_over():
    """Fails FIRST when a new result file lands, so the cause of every other
    snapshot failure is named rather than inferred."""
    n = corpus_size()
    assert n == CORPUS_SNAPSHOT["n_result_files"], (
        f"corpus is now {n} files, snapshot was taken over "
        f"{CORPUS_SNAPSHOT['n_result_files']} (as of {CORPUS_SNAPSHOT['as_of']}). "
        f"Every pooled count below will differ. Verify each delta equals the new "
        f"file's own contribution, then update CORPUS_SNAPSHOT."
    )


@pytest.mark.parametrize("key", [
    "escalations", "off_slate", "off_slate_correct", "gold_unoffered",
    "gold_unoffered_recovered", "unanimous_wrong_escalations",
    "unanimous_wrong_recovered", "unanimous_right_escalations",
    "unanimous_right_broken", "unanimous_total", "unanimous_total_wrong",
    "unanimous_unescalated_wrong",
])
def test_pooled_counts_match_the_snapshot(r, key):
    assert r[key] == CORPUS_SNAPSHOT[key], (
        f"{key}: {r[key]} vs snapshot {CORPUS_SNAPSHOT[key]} "
        f"({CORPUS_SNAPSHOT['as_of']}, {CORPUS_SNAPSHOT['n_result_files']} files)"
    )


def test_records_are_actually_found(r):
    """The silent-false-null guard -- see docstring."""
    assert r["escalations"] > 1000, (
        "found almost no escalations; the record shape probably changed "
        "(verdict/solver_answers keys) -- this reads as 'no effect' but is a bug"
    )
    assert r["unanimous_total"] > 1000


# ---------------------------------------------------------------------------
# STRUCTURAL -- the actual finding. True of any corpus; never needs re-pinning.
# ---------------------------------------------------------------------------


def test_judge_is_not_anchored_to_the_solver_slate(r):
    """Kills the AggLM none-of-the-above licence lever.

    The claim is that the Judge already picks off-slate when it should, so
    granting it an explicit licence buys nothing. That is a statement about
    RATES, not counts -- an off-slate accuracy of 82% means the same thing
    whether it is measured over 272 picks or 286.
    """
    assert r["off_slate"] > 100, "too few off-slate picks to say anything"
    assert r["off_slate_correct"] / r["off_slate"] > 0.80, (
        "off-slate picks are right far more often than not: no licence needed"
    )
    # On the all-solvers-wrong subset the Judge still recovers a large share.
    assert r["gold_unoffered"] > 100
    assert r["gold_unoffered_recovered"] / r["gold_unoffered"] > 0.40


def test_unanimous_wrong_recovery_and_breakage(r):
    """The core asymmetry: escalating a unanimous panel recovers wrong answers
    far more often than it breaks right ones.

    Pinned as a RATIO because that is the load-bearing claim. The absolute
    counts moved four times without the claim changing at all.
    """
    recovery = r["unanimous_wrong_recovered"] / r["unanimous_wrong_escalations"]
    breakage = r["unanimous_right_broken"] / r["unanimous_right_escalations"]

    assert recovery > 0.45, "recovery on unanimous-wrong escalations"
    assert breakage < 0.05, "breakage on unanimous-right escalations"
    assert recovery / breakage > 20, (
        "the write-up's load-bearing asymmetry. Threshold is 20x, not the "
        "measured value: TB-1B's seed 7 took breakage from 1/249 to 3/278 and "
        "the ratio from 133x to 48x. Both support the claim; pinning the "
        "measured figure would have failed on data that agrees with it."
    )


def test_break_even_is_far_below_the_measured_wrong_rate(r):
    """Escalating everything pays as long as the unanimous-wrong rate exceeds
    the break-even point. It does, by a wide margin."""
    recovery = r["unanimous_wrong_recovered"] / r["unanimous_wrong_escalations"]
    breakage = r["unanimous_right_broken"] / r["unanimous_right_escalations"]
    break_even = breakage / (recovery + breakage)
    w = r["unanimous_total_wrong"] / r["unanimous_total"]

    assert break_even < 0.05
    assert 0.15 < w < 0.25, "the unanimous-wrong rate sits near 19%"
    assert w > break_even * 5, "the comfortably-above-break-even claim"


def test_gate_recall_is_low_which_is_the_whole_finding(r):
    """The shipped gate escalates only a small fraction of the unanimous-wrong
    items it would need to. That headroom is the finding; its exact size is a
    snapshot and lives in CORPUS_SNAPSHOT."""
    recall = r["unanimous_wrong_escalations"] / r["unanimous_total_wrong"]
    assert recall < 0.25, (
        "if gate recall ever climbs above 25% the headroom argument needs "
        "rewriting, not re-pinning"
    )
    assert r["unanimous_unescalated_wrong"] > r["unanimous_wrong_escalations"], (
        "most unanimous-wrong items are still never escalated"
    )


def test_w_is_not_the_61_6_percent_figure(r):
    """Different denominators; conflating them was an explicit trap."""
    w = r["unanimous_total_wrong"] / r["unanimous_total"]
    assert w < 0.25, (
        "w is the wrong-rate among UNANIMOUS rows (~18%), not the unanimous "
        "share of WRONG rows (61.6%)"
    )


def test_supergpqa_converts_far_worse_than_gpqa(r):
    """The pooled rate must never be quoted as a per-benchmark rate.

    This spread is the reason the pooled recovery figure is misleading on its
    own, and it is the same conclusion TB-1B reached independently: escalating
    everything converts well on GPQA and poorly on SuperGPQA-hard.
    """
    ds = r["by_dataset"]
    sg_rate = ds["supergpqa"]["recovered"] / ds["supergpqa"]["wrong"]
    gpqa_rate = ds["gpqa(default)"]["recovered"] / ds["gpqa(default)"]["wrong"]

    assert sg_rate < 0.35, "SuperGPQA converts poorly"
    assert gpqa_rate > 0.50, "GPQA converts well"
    assert gpqa_rate / sg_rate > 2, "the spread that makes pooling misleading"

    # dataset="gpqa" (explicit --dataset flag) is a THIRD bucket distinct from
    # gpqa(default), and it is where all three universal_gate seeds land.
    gpqa_explicit = ds["gpqa"]
    assert gpqa_explicit["recovered"] / gpqa_explicit["wrong"] > 0.50

    # Breakage stays near zero on every surface, which is why accuracy is
    # positive nearly everywhere and COST is the real constraint.
    total_right = sum(c.get("right", 0) for c in ds.values())
    total_broken = sum(c.get("broken", 0) for c in ds.values())
    assert total_broken / total_right < 0.05, (
        "breakage must stay negligible; if it does not, the 'escalate "
        "everything is safe' claim fails and needs rewriting"
    )


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
