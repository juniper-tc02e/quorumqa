"""Offline tests for benchmark/verify_tb1_flagship.py (TB-1).

Built BEFORE arm B fires, per docs/spec-trackb-flagship-comparison.md §10
build-items 1 and 5. Synthetic fixtures throughout -- no arm B/B'/C data exists
yet, so these prove the ANALYSIS is right, not that any result occurred.

Covers the three things the adversarial review said the first draft got wrong
and that this script now enforces in code rather than prose: the analysis-set
gate measured against the INTENDED 90, the Bonferroni-corrected secondary
threshold, and the compute-unmatched warning when arm C is absent.
"""

from __future__ import annotations

import json

import pytest

import benchmark.verify_tb1_flagship as tb1
from benchmark.verify_tb1_flagship import (
    INTENDED_N,
    MIN_ANALYSIS_SET,
    PRIMARY_ALPHA,
    SECONDARY_ALPHA,
    _paired,
    _sc_diagnostics,
    _sc_outcomes,
    verify,
)


def _engine_row(qid: str, gold: str, final: str) -> dict:
    return {
        "engine": {
            "item": {"question_id": qid, "correct_letter": gold},
            "final_letter": final,
            "correct": final == gold,
        }
    }


def _sc_row(qid: str, gold: str, letters) -> dict:
    return {
        "engine": {"item": {"question_id": qid, "correct_letter": gold}},
        "seat_answers": [{"seat_index": i, "letter": L} for i, L in enumerate(letters)],
    }


def _write(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ---------------------------------------------------------------------------
# Arm C vote recomputation -- the pre-registered rules
# ---------------------------------------------------------------------------


def test_sc_majority_picks_the_modal_letter():
    out = _sc_outcomes([_sc_row("q1", "A", ["A", "A", "B", "A", "C"])])
    assert out["q1"] is True


def test_sc_tie_resolves_to_lowest_seat_index_not_confidence():
    """S7 killed confidence-based selection out-of-sample; the tie-break is
    positional by design. Here B and A tie 2-2 with B first, so B wins and the
    gold answer A is NOT credited."""
    out = _sc_outcomes([_sc_row("q1", "A", ["B", "B", "A", "A"])])
    assert out["q1"] is False
    # Same votes, A first -> A wins.
    out2 = _sc_outcomes([_sc_row("q1", "A", ["A", "A", "B", "B"])])
    assert out2["q1"] is True


def test_sc_empty_seats_are_dropped_before_the_majority():
    """An empty letter is not a vote -- but it must not silently sink the item."""
    out = _sc_outcomes([_sc_row("q1", "A", ["A", "", "A", "", "B"])])
    assert out["q1"] is True


def test_sc_all_unparsed_counts_wrong_never_dropped():
    """The survivorship guard. Dropping these would bias the arm toward easy
    items, which is exactly what voided an earlier AIME run."""
    out = _sc_outcomes([_sc_row("q1", "A", ["", "", "", "", ""])])
    assert out == {"q1": False}
    assert "q1" in out, "the item must remain in the analysis set"


# ---------------------------------------------------------------------------
# Paired arithmetic
# ---------------------------------------------------------------------------


def test_paired_counts_gains_and_losses_from_arm_a_perspective():
    a = {"q1": True, "q2": False, "q3": True, "q4": False}
    b = {"q1": False, "q2": True, "q3": True, "q4": False}
    r = _paired(a, b, ["q1", "q2", "q3", "q4"])
    assert (r["b"], r["c"]) == (1, 1)
    assert r["net"] == 0
    assert r["a_correct"] == 2 and r["other_correct"] == 2


# ---------------------------------------------------------------------------
# The Bonferroni consequence the spec registers explicitly
# ---------------------------------------------------------------------------


def test_secondary_alpha_is_bonferroni_over_three_seeds():
    assert SECONDARY_ALPHA == pytest.approx(0.05 / 3, abs=1e-9)


def test_b5_c0_no_longer_passes_the_secondary_branch():
    """The registered consequence of the multiplicity correction: net +5 with
    zero losses (p=0.03125) CLEARED the old uncorrected branch and must NOT
    clear the corrected one. Net +6 with zero losses does."""
    from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

    assert mcnemar_exact_one_sided(5, 0) == pytest.approx(0.03125)
    assert mcnemar_exact_one_sided(5, 0) > SECONDARY_ALPHA      # fails now
    assert mcnemar_exact_one_sided(5, 0) < PRIMARY_ALPHA        # would have passed before
    assert mcnemar_exact_one_sided(6, 0) < SECONDARY_ALPHA      # the new threshold
    # b=7,c=1 (net +6) also fails -- flagged in the spec so it is not a surprise.
    assert mcnemar_exact_one_sided(7, 1) > SECONDARY_ALPHA


# ---------------------------------------------------------------------------
# Analysis-set gate, measured against the INTENDED n
# ---------------------------------------------------------------------------


def test_gate_threshold_is_ninety_percent_of_the_intended_n():
    assert INTENDED_N == 90
    assert MIN_ANALYSIS_SET == 81


def test_gate_voids_a_seed_whose_intersection_is_too_small(tmp_path, monkeypatch):
    """The defect this guards: per-arm drop gates can each pass while the
    INTERSECTION collapses, because different arms drop different items."""
    monkeypatch.setattr(tb1, "RESULTS", tmp_path)
    ids = [f"q{i}" for i in range(90)]
    _write(tmp_path / "lever_universal_gate_gpqa_seed1001.jsonl",
           [_engine_row(q, "A", "A") for q in ids])
    # Arm B drops 15 -> intersection 75 < 81, even though 75/90 is under a
    # naive 10% per-arm gate only if measured against the wrong denominator.
    _write(tmp_path / "TB1_flagship1x_gpqa_seed1001.jsonl",
           [_engine_row(q, "A", "A") for q in ids[:75]])

    r = verify()
    s = r["per_seed"][1001]
    assert s["analysis_set_size"] == 75
    assert s["gate_ok"] is False
    assert s["dropped_vs_intended"] == 15


def test_gate_passes_at_exactly_the_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(tb1, "RESULTS", tmp_path)
    ids = [f"q{i}" for i in range(90)]
    _write(tmp_path / "lever_universal_gate_gpqa_seed1001.jsonl",
           [_engine_row(q, "A", "A") for q in ids])
    _write(tmp_path / "TB1_flagship1x_gpqa_seed1001.jsonl",
           [_engine_row(q, "A", "A") for q in ids[:81]])

    assert verify()["per_seed"][1001]["gate_ok"] is True


# ---------------------------------------------------------------------------
# Both comparisons must land on the SAME analysis set
# ---------------------------------------------------------------------------


def test_arm_a_accuracy_is_identical_across_both_comparisons(tmp_path, monkeypatch):
    """The spec requires A-vs-B and A-vs-C be shown together; if they ran on
    different item sets, arm A would have two different accuracies and the
    tables would not be comparable."""
    monkeypatch.setattr(tb1, "RESULTS", tmp_path)
    ids = [f"q{i}" for i in range(90)]
    _write(tmp_path / "lever_universal_gate_gpqa_seed1001.jsonl",
           [_engine_row(q, "A", "A" if i % 10 else "B") for i, q in enumerate(ids)])
    _write(tmp_path / "TB1_flagship1x_gpqa_seed1001.jsonl",
           [_engine_row(q, "A", "A") for q in ids[:86]])
    _write(tmp_path / "TB1_flagship_sc5_gpqa_seed1001.jsonl",
           [_sc_row(q, "A", ["A"] * 5) for q in ids[:84]])

    s = verify()["per_seed"][1001]
    assert s["analysis_set_size"] == 84  # the three-way intersection
    assert s["comparisons"]["B"]["a_correct"] == s["comparisons"]["C"]["a_correct"]
    assert s["comparisons"]["B"]["n"] == s["comparisons"]["C"]["n"] == 84


# ---------------------------------------------------------------------------
# The compute-unmatched warning, enforced in code rather than prose
# ---------------------------------------------------------------------------


def test_arm_c_absence_is_reported_as_a_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(tb1, "RESULTS", tmp_path)
    ids = [f"q{i}" for i in range(90)]
    _write(tmp_path / "lever_universal_gate_gpqa_seed1001.jsonl",
           [_engine_row(q, "A", "A") for q in ids])
    _write(tmp_path / "TB1_flagship1x_gpqa_seed1001.jsonl",
           [_engine_row(q, "A", "A") for q in ids])

    r = verify()
    assert r["arm_c_run"] is False


def test_arm_c_presence_clears_the_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(tb1, "RESULTS", tmp_path)
    ids = [f"q{i}" for i in range(90)]
    _write(tmp_path / "lever_universal_gate_gpqa_seed1001.jsonl",
           [_engine_row(q, "A", "A") for q in ids])
    _write(tmp_path / "TB1_flagship_sc5_gpqa_seed1001.jsonl",
           [_sc_row(q, "A", ["A"] * 5) for q in ids])

    assert verify()["arm_c_run"] is True


# ---------------------------------------------------------------------------
# Arm C diversity diagnostics -- kill clause 4
# ---------------------------------------------------------------------------


def test_sc_diagnostics_detect_a_degenerate_control(tmp_path, monkeypatch):
    """A control whose 5 samples are identical is defeated by construction:
    it costs 5x and cannot outvote itself. Agreement must read 1.0 so this is
    visible rather than silently producing a flattering null."""
    monkeypatch.setattr(tb1, "RESULTS", tmp_path)
    _write(tmp_path / "TB1_flagship_sc5_gpqa_seed1001.jsonl",
           [_sc_row(f"q{i}", "A", ["A"] * 5) for i in range(20)])

    d = _sc_diagnostics(1001)
    assert d["mean_pairwise_agreement"] == pytest.approx(1.0)
    assert d["mean_per_sample_accuracy"] == pytest.approx(1.0)


def test_sc_diagnostics_show_diversity_when_samples_differ(tmp_path, monkeypatch):
    monkeypatch.setattr(tb1, "RESULTS", tmp_path)
    _write(tmp_path / "TB1_flagship_sc5_gpqa_seed1001.jsonl",
           [_sc_row(f"q{i}", "A", ["A", "B", "A", "C", "A"]) for i in range(20)])

    d = _sc_diagnostics(1001)
    assert d["mean_pairwise_agreement"] < 0.5
    assert d["mean_per_sample_accuracy"] == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Pooled = primary
# ---------------------------------------------------------------------------


def test_pooled_is_the_primary_test_and_sums_per_seed_tables(tmp_path, monkeypatch):
    monkeypatch.setattr(tb1, "RESULTS", tmp_path)
    for seed in (1001, 2311, 3407):
        ids = [f"s{seed}q{i}" for i in range(90)]
        # Arm A right everywhere; arm B wrong on 3 items per seed -> b=3,c=0.
        _write(tmp_path / f"lever_universal_gate_gpqa_seed{seed}.jsonl",
               [_engine_row(q, "A", "A") for q in ids])
        _write(tmp_path / f"TB1_flagship1x_gpqa_seed{seed}.jsonl",
               [_engine_row(q, "A", "B" if i < 3 else "A") for i, q in enumerate(ids)])

    p = verify()["pooled"]["B"]
    assert p["b"] == 9 and p["c"] == 0
    assert p["net"] == 9
    assert p["n"] == 270
    assert sorted(p["seeds"]) == [1001, 2311, 3407]
    assert p["primary_clears"] is True


# ---------------------------------------------------------------------------
# The real committed TB-1 arm B result. Raw .jsonl are gitignored, so these
# skip where the run did not happen.
# See benchmark/results/tb1_flagship_comparison_result.md -- a NULL:
# the scaffolded flagship does not beat the solo flagship.
# ---------------------------------------------------------------------------

from pathlib import Path as _Path

_REAL = [
    _Path("benchmark/results") / f"{stem}_gpqa_seed{s}.jsonl"
    for s in (1001, 2311, 3407)
    for stem in ("lever_universal_gate", "TB1_flagship1x")
]

_real_present = pytest.mark.skipif(
    not all(p.exists() for p in _REAL),
    reason="TB-1 arm A/B raw runs are gitignored; present only where the queue ran",
)


@_real_present
def test_real_tb1_arm_b_is_a_null():
    """The headline: pooled net +1 over 265 items, p=0.50. If a future change
    turns this into a win, something broke -- investigate before celebrating."""
    r = verify()
    p = r["pooled"]["B"]
    assert p["b"] == 8
    assert p["c"] == 7
    assert p["net"] == 1
    assert p["n"] == 265
    assert p["p_one_sided"] == pytest.approx(0.5, abs=1e-6)
    assert p["primary_clears"] is False


@_real_present
def test_real_tb1_every_seed_gate_passed():
    """All three seeds cleared |S| >= 81, so the null is not an artifact of a
    collapsed analysis set."""
    r = verify()
    sizes = {seed: s["analysis_set_size"] for seed, s in r["per_seed"].items()}
    assert sizes == {1001: 88, 2311: 88, 3407: 89}
    assert all(s["gate_ok"] for s in r["per_seed"].values())


@_real_present
def test_real_tb1_no_seed_clears_the_secondary_branch():
    r = verify()
    for seed, s in r["per_seed"].items():
        cmp_ = s["comparisons"]["B"]
        assert cmp_["p_one_sided"] > SECONDARY_ALPHA, f"seed {seed} unexpectedly clears"


@_real_present
def test_real_tb1_accuracy_difference_is_under_one_point():
    """238/265 vs 237/265 = +0.38pp. The architecture matches a single flagship
    call; it does not beat it."""
    r = verify()
    total_a = sum(s["comparisons"]["B"]["a_correct"] for s in r["per_seed"].values())
    total_b = sum(s["comparisons"]["B"]["other_correct"] for s in r["per_seed"].values())
    n = sum(s["comparisons"]["B"]["n"] for s in r["per_seed"].values())
    assert (total_a, total_b, n) == (238, 237, 265)
    assert abs(total_a - total_b) / n < 0.01


@_real_present
def test_arm_c_remains_unrun_by_design():
    """Arm C was CANCELLED, not deferred: its pre-registered purpose was to
    attribute a WIN, and there is no win. If C files ever appear, the result
    doc's section 5 needs revisiting rather than silently absorbing them."""
    assert verify()["arm_c_run"] is False
