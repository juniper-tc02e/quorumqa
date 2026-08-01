"""Offline tests for benchmark/analyze_unanimous_stability.py (META-2) --
synthetic fixtures, since no real META-2 data exists yet at the time this
analysis script was written (pre-registered before the live run, same
discipline as verify_aime_liveness_screen.py's own offline test suite).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.analyze_unanimous_stability import (
    COVERAGE_BAND_MIN,
    COVERAGE_GATE_MIN,
    CONTRAST_MIN_PP,
    analyze,
    is_correct,
    is_unanimous,
)

RESULTS = Path("benchmark/results")
_REAL_SEEDS = (909, 1313, 2027)
_REAL_CONTROL = [RESULTS / f"META2_control_supergpqa_seed{s}.jsonl" for s in _REAL_SEEDS]
_REAL_PERMUTED = [RESULTS / f"META2_permuted_panel_supergpqa_seed{s}.jsonl" for s in _REAL_SEEDS]


def _row(qid: str, escalated: bool, correct: bool) -> dict:
    return {
        "engine": {
            "item": {"question_id": qid},
            "escalated": escalated,
            "correct": correct,
        }
    }


def _write(path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_is_unanimous_and_is_correct_read_the_right_fields():
    row = _row("q1", escalated=False, correct=True)
    assert is_unanimous(row) is True
    assert is_correct(row) is True
    row2 = _row("q2", escalated=True, correct=False)
    assert is_unanimous(row2) is False
    assert is_correct(row2) is False


# ---------------------------------------------------------------------------
# Coverage gate
# ---------------------------------------------------------------------------


def test_coverage_gate_clears_at_or_above_10_percent(tmp_path):
    # 10 control-unanimous items, 1 flips (10.0% -- exactly at the floor).
    control = [_row(f"q{i}", escalated=False, correct=True) for i in range(10)]
    permuted = [_row(f"q{i}", escalated=(i == 0), correct=True) for i in range(10)]
    cpath, ppath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)

    r = analyze([str(cpath)], [str(ppath)])
    assert r["flip_rate_ab"] == pytest.approx(0.10)
    assert r["flip_rate_ab"] >= COVERAGE_GATE_MIN
    assert "CLEARS" in r["coverage_verdict"]


def test_coverage_gate_band_between_5_and_10_percent(tmp_path):
    # 20 unanimous items, 1 flips = 5.0% -- exactly at the band floor.
    control = [_row(f"q{i}", escalated=False, correct=True) for i in range(20)]
    permuted = [_row(f"q{i}", escalated=(i == 0), correct=True) for i in range(20)]
    cpath, ppath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)

    r = analyze([str(cpath)], [str(ppath)])
    assert r["flip_rate_ab"] == pytest.approx(0.05)
    assert COVERAGE_BAND_MIN <= r["flip_rate_ab"] < COVERAGE_GATE_MIN
    assert "BAND" in r["coverage_verdict"]


def test_coverage_gate_kills_below_5_percent(tmp_path):
    control = [_row(f"q{i}", escalated=False, correct=True) for i in range(100)]
    permuted = [_row(f"q{i}", escalated=(i == 0), correct=True) for i in range(100)]  # 1.0%
    cpath, ppath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)

    r = analyze([str(cpath)], [str(ppath)])
    assert r["flip_rate_ab"] < COVERAGE_BAND_MIN
    assert "KILL" in r["coverage_verdict"]


def test_raises_when_control_has_zero_unanimous_items(tmp_path):
    control = [_row("q1", escalated=True, correct=True)]  # not unanimous
    permuted = [_row("q1", escalated=True, correct=True)]
    cpath, ppath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)

    with pytest.raises(AssertionError, match="zero control-unanimous"):
        analyze([str(cpath)], [str(ppath)])


# ---------------------------------------------------------------------------
# Predictive contrast + Fisher exact
# ---------------------------------------------------------------------------


def test_contrast_clears_the_pre_registered_bar(tmp_path):
    # 10 unanimous-wrong items, 5 flip (50%); 10 unanimous-right, 0 flip (0%).
    # Contrast = 50pp >= 25pp, n_flipped=5... need >=8 flipped total, so scale up.
    wrong = [_row(f"w{i}", escalated=False, correct=False) for i in range(16)]
    right = [_row(f"r{i}", escalated=False, correct=True) for i in range(16)]
    control = wrong + right
    permuted = (
        [_row(f"w{i}", escalated=(i < 8), correct=False) for i in range(16)]  # 8/16 flip = 50%
        + [_row(f"r{i}", escalated=False, correct=True) for i in range(16)]     # 0/16 flip
    )
    cpath, ppath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)

    r = analyze([str(cpath)], [str(ppath)])
    assert r["n_unanimous_wrong"] == 16
    assert r["n_flipped_wrong"] == 8
    assert r["flip_rate_wrong"] == pytest.approx(0.5)
    assert r["flip_rate_right"] == pytest.approx(0.0)
    assert r["contrast_pp"] == pytest.approx(50.0)
    assert r["contrast_pp"] >= CONTRAST_MIN_PP
    assert r["fisher_p"] < 0.05
    assert r["contrast_clears_bar"] is True
    assert r["contrast_killed"] is False


def test_contrast_kill_clause_fires_on_small_gap(tmp_path):
    # Flip rates nearly identical between wrong and right -- gap < 10pt.
    wrong = [_row(f"w{i}", escalated=False, correct=False) for i in range(20)]
    right = [_row(f"r{i}", escalated=False, correct=True) for i in range(20)]
    control = wrong + right
    permuted = (
        [_row(f"w{i}", escalated=(i < 4), correct=False) for i in range(20)]  # 20%
        + [_row(f"r{i}", escalated=(i < 3), correct=True) for i in range(20)]  # 15%
    )
    cpath, ppath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)

    r = analyze([str(cpath)], [str(ppath)])
    assert r["contrast_pp"] == pytest.approx(5.0, abs=0.01)
    assert r["contrast_killed"] is True
    assert r["contrast_clears_bar"] is False


def test_contrast_requires_minimum_flipped_count(tmp_path):
    # 100pp gap but only 2 flipped total -- must NOT clear (n_flipped < 8).
    wrong = [_row(f"w{i}", escalated=False, correct=False) for i in range(2)]
    right = [_row(f"r{i}", escalated=False, correct=True) for i in range(20)]
    control = wrong + right
    permuted = (
        [_row(f"w{i}", escalated=True, correct=False) for i in range(2)]  # both flip
        + [_row(f"r{i}", escalated=False, correct=True) for i in range(20)]  # none flip
    )
    cpath, ppath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)

    r = analyze([str(cpath)], [str(ppath)])
    assert r["n_flipped_wrong"] + r["n_flipped_right"] == 2
    assert r["contrast_pp"] == pytest.approx(100.0)
    assert r["contrast_clears_bar"] is False  # blocked by the min-flipped clause


# ---------------------------------------------------------------------------
# Mechanism decomposition (arm C)
# ---------------------------------------------------------------------------


def test_mechanism_without_arm_c_is_labelled_resample_or_permute(tmp_path):
    control = [_row(f"q{i}", escalated=False, correct=True) for i in range(10)]
    permuted = [_row(f"q{i}", escalated=(i == 0), correct=True) for i in range(10)]
    cpath, ppath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)

    r = analyze([str(cpath)], [str(ppath)])
    assert r["flip_rate_c"] is None
    assert "resample-or-permute" in r["mechanism_verdict"]


def test_mechanism_with_arm_c_decomposes_permutation_specific_component(tmp_path):
    control = [_row(f"q{i}", escalated=False, correct=True) for i in range(20)]
    permuted = [_row(f"q{i}", escalated=(i < 6), correct=True) for i in range(20)]   # 30% flip
    resample = [_row(f"q{i}", escalated=(i < 2), correct=True) for i in range(20)]   # 10% flip
    cpath, ppath, rpath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl", tmp_path / "resample.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)
    _write(rpath, resample)

    r = analyze([str(cpath)], [str(ppath)], [str(rpath)])
    assert r["flip_rate_ab"] == pytest.approx(0.30)
    assert r["flip_rate_c"] == pytest.approx(0.10)
    assert r["permutation_specific_pp"] == pytest.approx(20.0)
    assert r["mechanism_verdict"] == "permutation instability"


def test_mechanism_negative_component_reads_as_not_distinguishable(tmp_path):
    # Resampling alone flips MORE than permutation -- the permutation-
    # specific component is negative, so the claim cannot be "permutation
    # instability".
    control = [_row(f"q{i}", escalated=False, correct=True) for i in range(20)]
    permuted = [_row(f"q{i}", escalated=(i < 2), correct=True) for i in range(20)]   # 10%
    resample = [_row(f"q{i}", escalated=(i < 6), correct=True) for i in range(20)]   # 30%
    cpath, ppath, rpath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl", tmp_path / "resample.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)
    _write(rpath, resample)

    r = analyze([str(cpath)], [str(ppath)], [str(rpath)])
    assert r["permutation_specific_pp"] == pytest.approx(-20.0)
    assert "not distinguishable" in r["mechanism_verdict"]


# ---------------------------------------------------------------------------
# Accuracy side-comparison (B vs A)
# ---------------------------------------------------------------------------


def test_accuracy_side_comparison_matches_standard_mcnemar_bar(tmp_path):
    # 6 items where permuted gains, 0 losses -- net=+6, p=0.5**6=0.015625 < 0.05.
    control = [_row(f"q{i}", escalated=False, correct=False) for i in range(6)]
    permuted = [_row(f"q{i}", escalated=False, correct=True) for i in range(6)]
    cpath, ppath = tmp_path / "control.jsonl", tmp_path / "permuted.jsonl"
    _write(cpath, control)
    _write(ppath, permuted)

    r = analyze([str(cpath)], [str(ppath)])
    assert r["accuracy_b_gain"] == 6
    assert r["accuracy_c_loss"] == 0
    assert r["accuracy_net"] == 6
    assert r["accuracy_p_one_sided"] == pytest.approx(0.015625, abs=1e-6)
    assert r["accuracy_bar_clears"] is True


# ---------------------------------------------------------------------------
# Multi-file pooling (across seeds)
# ---------------------------------------------------------------------------


def test_pools_multiple_files_per_arm(tmp_path):
    control1 = [_row(f"s1-q{i}", escalated=False, correct=True) for i in range(5)]
    control2 = [_row(f"s2-q{i}", escalated=False, correct=True) for i in range(5)]
    permuted1 = [_row(f"s1-q{i}", escalated=(i == 0), correct=True) for i in range(5)]
    permuted2 = [_row(f"s2-q{i}", escalated=(i == 0), correct=True) for i in range(5)]
    c1, c2 = tmp_path / "c1.jsonl", tmp_path / "c2.jsonl"
    p1, p2 = tmp_path / "p1.jsonl", tmp_path / "p2.jsonl"
    _write(c1, control1)
    _write(c2, control2)
    _write(p1, permuted1)
    _write(p2, permuted2)

    r = analyze([str(c1), str(c2)], [str(p1), str(p2)])
    assert r["n_unanimous_control"] == 10
    assert r["n_flipped_ab"] == 2


# ---------------------------------------------------------------------------
# Pin against the real committed 3-seed run (raw pools gitignored -- only
# present on the machine that ran it). See
# benchmark/results/meta2_permutation_instability_findings.md: KILL, pooled
# contrast +7.1pp / p=0.4552, both disjuncts of the kill clause fire
# independently.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not all(p.exists() for p in _REAL_CONTROL + _REAL_PERMUTED),
    reason="META-2 raw result files are gitignored and only present on the machine that ran it live.",
)
def test_real_pooled_3seed_result_matches_the_committed_findings():
    r = analyze([str(p) for p in _REAL_CONTROL], [str(p) for p in _REAL_PERMUTED])

    assert r["n_unanimous_control"] == 139
    assert r["n_flipped_ab"] == 59
    assert r["flip_rate_ab"] == pytest.approx(0.4244604316546763, abs=1e-9)
    assert "CLEARS" in r["coverage_verdict"]

    assert r["n_unanimous_wrong"] == 40
    assert r["n_unanimous_right"] == 99
    assert r["n_flipped_wrong"] == 19
    assert r["n_flipped_right"] == 40
    assert r["contrast_pp"] == pytest.approx(7.095959595959594, abs=1e-9)
    assert r["fisher_p"] == pytest.approx(0.4552, abs=1e-3)

    assert r["contrast_clears_bar"] is False
    assert r["contrast_killed"] is True  # both disjuncts fire: gap<10pt AND p>0.2
    assert r["contrast_pp"] < 10.0
    assert r["fisher_p"] > 0.2

    assert r["accuracy_net"] == 7
    assert r["accuracy_bar_clears"] is False
