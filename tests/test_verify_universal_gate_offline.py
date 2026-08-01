"""Pins universal_gate's live seed-1001 result against its committed file.

The claim: escalating every unanimous GPQA panel (instead of the shipped
`if unanimous: return`) nets +9 items (78.9% -> 88.9%), one-sided exact McNemar
p=0.00195 -- clears the repo bar (net>=+5 at one seed, p<0.05) on its own.

Also pins the mechanism (every unanimous panel escalated, no split panel
double-escalated) and the honest report that the pre-registered prediction
(conversion BELOW the 47.6% pooled estimate) did not hold -- this run converted
at 75.0%, above it.
"""

from __future__ import annotations

import pytest

from benchmark.verify_universal_gate import verify


@pytest.fixture(scope="module")
def r():
    return verify()


def test_seed_1001_present(r):
    assert 1001 in r["per_seed"]


def test_mechanism_is_clean(r):
    """Every unanimous panel escalated; no split panel was double-counted."""
    s = r["per_seed"][1001]
    assert s["n"] == 90
    assert s["unanimous_count"] == 48
    assert s["unanimous_escalated"] == 48
    assert s["non_unanimous_escalated"] == 42
    assert s["mechanism_clean"] is True


def test_recovery_and_breakage(r):
    s = r["per_seed"][1001]
    assert s["unanimous_wrong"] == 12
    assert s["recovered"] == 9
    assert s["recovery_rate"] == pytest.approx(0.75, abs=1e-9)
    assert s["unanimous_right"] == 36
    assert s["broken"] == 0
    assert s["breakage_rate"] == pytest.approx(0.0, abs=1e-9)


def test_paired_accuracy_and_significance(r):
    s = r["per_seed"][1001]
    assert s["shipped_correct"] == 71
    assert s["gated_correct"] == 80
    assert s["b"] == 9
    assert s["c"] == 0
    assert s["net"] == 9
    assert s["p_one_sided"] == pytest.approx(0.00195, abs=1e-4)
    assert s["p_one_sided"] < 0.05


def test_clears_the_single_seed_bar(r):
    """net>=+5 at one seed with p<0.05 -- the repo's own bar, satisfied here
    without needing the pooled 2-of-3-seed branch."""
    s = r["per_seed"][1001]
    assert s["net"] >= 5
    assert s["p_one_sided"] < 0.05


def test_conversion_exceeded_the_pre_registered_prediction(r):
    """Honesty guard: the pre-registered prediction was that a wider gate
    would convert BELOW the 47.6% pooled estimate (selection bias in existing
    doubt-gates). It did not -- this seed converted at 75.0%, above it. A
    future edit must not quietly flip this back to 'as predicted'."""
    from benchmark.verify_universal_gate import PRIOR_POOLED_RECOVERY_PCT

    s = r["per_seed"][1001]
    recovery_pct = 100 * s["recovery_rate"]
    assert recovery_pct > PRIOR_POOLED_RECOVERY_PCT


# ---------------------------------------------------------------------------
# Pooled / 2-of-3 / kill logic, added 2026-08-01 for the pre-registered
# transfer replication at fresh seeds 2311 and 3407
# (docs/spec-sci1-and-knowledge-injection.md section 3.2). These tests must
# pass BOTH before those seeds land (partial read) and after, so the analysis
# is trustworthy mid-queue rather than only at the end.
# ---------------------------------------------------------------------------


def test_pooled_block_is_present_and_internally_consistent(r):
    p = r["pooled"]
    assert p["net"] == p["b"] - p["c"]
    assert p["b"] == sum(s["b"] for s in r["per_seed"].values())
    assert p["c"] == sum(s["c"] for s in r["per_seed"].values())
    assert p["n"] == sum(s["n"] for s in r["per_seed"].values())
    assert 0.0 <= p["p_one_sided"] <= 1.0


def test_pooling_sums_tables_rather_than_rejoining_items(r):
    """This repo's convention: pooled McNemar ADDS independent per-seed 2x2
    tables. Different seeds draw different item samples, so re-joining on
    question_id across seeds would be invalid."""
    from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

    p = r["pooled"]
    assert p["p_one_sided"] == pytest.approx(mcnemar_exact_one_sided(p["b"], p["c"]))


def test_bar_block_reports_both_branches(r):
    bar = r["bar"]
    assert set(bar) == {
        "single_seed_clears", "seeds_at_net_3_plus",
        "two_of_three_branch_clears", "clears",
    }
    # Seed 1001 (+9, p=0.00195) satisfies branch 1 on its own, whatever the
    # fresh seeds do.
    assert 1001 in bar["single_seed_clears"]
    assert bar["clears"] is True


def test_two_of_three_branch_needs_two_seeds_not_one(r):
    """Guards the arithmetic that matters most: one seed at net>=+3 must NOT
    be enough to call the 2-of-3 branch cleared, even with a tiny pooled p."""
    bar = r["bar"]
    if len(bar["seeds_at_net_3_plus"]) < 2:
        assert bar["two_of_three_branch_clears"] is False


def test_kill_clause_is_not_evaluable_until_both_fresh_seeds_exist(r):
    """A kill must never fire on absent data."""
    from benchmark.verify_universal_gate import FRESH_SEEDS

    kill = r["kill"]
    if len(kill["fresh_seeds_present"]) < len(FRESH_SEEDS):
        assert kill["killed"] is False


def test_verify_runs_with_seeds_missing_from_disk(r):
    """The queue fires seeds sequentially; this analysis has to stay runnable
    between runs rather than crashing on a missing file."""
    from benchmark.verify_universal_gate import SEEDS

    assert len(r["per_seed"]) >= 1
    assert set(r["per_seed"]).issubset(set(SEEDS))


# ---------------------------------------------------------------------------
# The completed 3-seed result and its compute-matched attribution.
# See benchmark/results/universal_gate_3seed_result.md.
# Raw .jsonl are gitignored, so these skip on a machine that has not run them.
# ---------------------------------------------------------------------------

import json as _json
from pathlib import Path as _Path

_RES = _Path("benchmark/results")
_UG = [_RES / f"lever_universal_gate_gpqa_seed{s}.jsonl" for s in (1001, 2311, 3407)]
_CM = _RES / "KI1BC_compute_matched_n9_gpqa_seed2311.jsonl"

_all_seeds = pytest.mark.skipif(
    not all(p.exists() for p in _UG),
    reason="universal_gate raw runs are gitignored; present only where the queue ran",
)


@_all_seeds
def test_three_seed_pooled_result(r):
    p = r["pooled"]
    assert sorted(r["per_seed"]) == [1001, 2311, 3407]
    assert p["b"] == 25
    assert p["c"] == 0, "a single loss would change the claim materially"
    assert p["net"] == 25
    assert p["p_one_sided"] == pytest.approx(2 ** -25, rel=1e-6)


@_all_seeds
def test_every_seed_clears_the_single_seed_bar_independently(r):
    """Stronger than the 2-of-3 branch that was the pre-registered target."""
    for seed, s in r["per_seed"].items():
        assert s["net"] >= 5, f"seed {seed} net={s['net']}"
        assert s["p_one_sided"] < 0.05, f"seed {seed} p={s['p_one_sided']}"
    assert set(r["bar"]["single_seed_clears"]) == {1001, 2311, 3407}
    assert r["bar"]["two_of_three_branch_clears"] is True


@_all_seeds
def test_per_seed_nets_are_not_transposed(r):
    """Guards a real error made while writing the result up: seeds 2311 and
    3407 were swapped in the first draft of the table."""
    assert r["per_seed"][1001]["net"] == 9
    assert r["per_seed"][2311]["net"] == 11
    assert r["per_seed"][3407]["net"] == 5
    assert r["per_seed"][2311]["gated_accuracy"] == pytest.approx(80 / 89, abs=1e-3)


@_all_seeds
def test_zero_breakage_across_all_seeds(r):
    total_right = sum(s["unanimous_right"] for s in r["per_seed"].values())
    total_broken = sum(s["broken"] for s in r["per_seed"].values())
    total_wrong = sum(s["unanimous_wrong"] for s in r["per_seed"].values())
    total_recovered = sum(s["recovered"] for s in r["per_seed"].values())
    assert total_broken == 0
    assert (total_right, total_wrong, total_recovered) == (118, 38, 25)


@_all_seeds
def test_kill_clause_did_not_fire(r):
    assert r["kill"]["fresh_seeds_present"] == [2311, 3407]
    assert r["kill"]["killed"] is False


@pytest.mark.skipif(
    not (_CM.exists() and _UG[1].exists()),
    reason="compute-matched control raw run is gitignored",
)
def test_compute_matched_control_does_not_explain_the_gain():
    """The attribution guard that retracted the LAST headline. If N=9 cheap
    votes matched universal_gate at equal tokens, the mechanism claim would be
    retracted. It does not -- it loses to the shipped 3-seat panel."""
    from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

    def load(p):
        return [_json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

    ug = {r["engine"]["item"]["question_id"]: r["engine"] for r in load(_UG[1])}
    cm = {r["engine"]["item"]["question_id"]: r["engine"] for r in load(_CM)}
    shared = sorted(set(ug) & set(cm))
    assert len(shared) == 89

    def ok(e):
        return e["final_letter"] == e["item"]["correct_letter"]

    b = sum(1 for q in shared if ok(ug[q]) and not ok(cm[q]))
    c = sum(1 for q in shared if ok(cm[q]) and not ok(ug[q]))
    assert (b, c) == (24, 2)
    assert b - c == 22
    assert mcnemar_exact_one_sided(b, c) < 0.001


@pytest.mark.skipif(not _CM.exists(), reason="compute-matched control raw run is gitignored")
def test_scaling_cheap_votes_within_the_control_arm_is_flat():
    """Answers the obvious objection to the control (its seats are weaker, so
    maybe votes DO scale). Within the arm, N=3 -> N=9 nets exactly zero, which
    also replicates panel_scaling_n15_seed19.md's flat-N finding on GPQA."""
    from collections import Counter

    from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

    rows = [_json.loads(l) for l in open(_CM, encoding="utf-8") if l.strip()]
    assert all(len(r["seat_answers"]) == 9 for r in rows)

    def at(n):
        return {
            r["engine"]["item"]["question_id"]:
                Counter(s["letter"] for s in r["seat_answers"][:n]).most_common(1)[0][0]
                == r["engine"]["item"]["correct_letter"]
            for r in rows
        }

    n3, n9 = at(3), at(9)
    b = sum(1 for q in n9 if n9[q] and not n3[q])
    c = sum(1 for q in n9 if n3[q] and not n9[q])
    assert b - c == 0, "more cheap votes suddenly help -- the attribution argument needs revisiting"
    assert mcnemar_exact_one_sided(b, c) > 0.05
