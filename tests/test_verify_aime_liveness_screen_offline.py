"""Offline tests for benchmark/verify_aime_liveness_screen.py -- validates the
MATH-1 bar/kill/contamination LOGIC against synthetic fixtures, since no real
AIME seed-101 data exists yet at the time this analysis script was written
(pre-registered before the live run, matching this repo's own discipline of
reviewing analysis logic before trusting its verdict -- see
benchmark/results/s7_harness_adversarial_review.md for the same posture
applied to a different harness).

Once the live run lands, a SEPARATE pin test (matching
tests/test_s7_live_result_offline.py's pattern) should pin verify()'s output
against the real committed seed101 files -- this file only proves the
analysis is correct, not that any particular result occurred.
"""

from __future__ import annotations

import json

import pytest

from benchmark.verify_aime_liveness_screen import (
    BAR_MAX_FLAGSHIP_ACC,
    BAR_MIN_NET,
    CONTAMINATION_MIN_YEAR_GAP,
    KILL_CHEAP_ACC,
    KILL_FLAGSHIP_ACC,
    verify,
)


def _row(qid: str, correct: bool) -> dict:
    return {"question_id": qid, "correct": correct}


def _write(path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _ids(prefix: str, n: int) -> list[str]:
    return [f"{prefix}-{i}" for i in range(n)]


def _write_pair(tmp_path, baseline_correct: dict, cheap_correct: dict):
    """baseline_correct / cheap_correct: {question_id: bool} for all 60 ids."""
    _write(tmp_path / "aime_open_baseline_seed101.jsonl", [_row(q, c) for q, c in baseline_correct.items()])
    _write(tmp_path / "aime_open_sc_cheap_seed101.jsonl", [_row(q, c) for q, c in cheap_correct.items()])


def _all_60_ids():
    return _ids("aime2024", 30) + _ids("aime2025", 30)


# ---------------------------------------------------------------------------
# Admissibility
# ---------------------------------------------------------------------------


def test_inadmissible_on_row_count_mismatch(tmp_path):
    ids = _all_60_ids()
    baseline = {q: True for q in ids}
    cheap = {q: True for q in ids[:59]}  # one dropped
    _write_pair(tmp_path, baseline, cheap)

    with pytest.raises(AssertionError, match="INADMISSIBLE"):
        verify(results_dir=tmp_path)


def test_inadmissible_on_partial_id_overlap(tmp_path):
    # 60/60 rows in EACH arm, but they don't refer to the same 60 items --
    # the row-count check alone would miss this.
    ids = _all_60_ids()
    baseline = {q: True for q in ids}
    cheap_ids = ids[:59] + ["aime2024-decoy"]
    cheap = {q: True for q in cheap_ids}
    _write_pair(tmp_path, baseline, cheap)

    with pytest.raises(AssertionError, match="INADMISSIBLE"):
        verify(results_dir=tmp_path)


# ---------------------------------------------------------------------------
# Bar / kill / verdict branches
# ---------------------------------------------------------------------------


def test_alive_when_net_and_headroom_conditions_both_hold(tmp_path):
    ids = _all_60_ids()
    # flagship correct on 40/60 (66.7%, well under the 85% kill/bar ceiling);
    # cheap wrong on exactly those items it needs to be wrong on to produce
    # net=+12 with zero reverse discordance -- b=12, c=0.
    baseline = {q: True for q in ids[:40]}
    baseline.update({q: False for q in ids[40:]})
    cheap = dict(baseline)  # start concordant everywhere
    # Flip 12 of the flagship-correct items to cheap-wrong -> b=12, c=0.
    for q in ids[:12]:
        cheap[q] = False
    _write_pair(tmp_path, baseline, cheap)

    r = verify(results_dir=tmp_path)
    assert r["b"] == 12
    assert r["c"] == 0
    assert r["net"] == 12
    assert r["net"] >= BAR_MIN_NET
    assert r["baseline_acc"] == pytest.approx(40 / 60)
    assert r["baseline_acc"] <= BAR_MAX_FLAGSHIP_ACC
    assert not r["killed"]
    assert r["bar_cleared"]
    assert r["verdict"] == "ALIVE"


def test_neither_when_net_too_small(tmp_path):
    ids = _all_60_ids()
    baseline = {q: True for q in ids[:40]}
    baseline.update({q: False for q in ids[40:]})
    cheap = dict(baseline)
    for q in ids[:3]:  # only net=+3, below the +10 bar
        cheap[q] = False
    _write_pair(tmp_path, baseline, cheap)

    r = verify(results_dir=tmp_path)
    assert r["net"] == 3
    assert not r["bar_cleared"]
    assert not r["killed"]
    assert r["verdict"].startswith("NEITHER")
    assert any("required +10" in reason for reason in r["bar_reasons"])


def test_kill_dominates_even_when_net_would_clear_the_bar(tmp_path):
    # Cheap accuracy >=90% (saturated) -- KILL must fire even if net looks
    # like it clears the bar, since kill is checked unconditionally and
    # dominates (spec: "KILL DOMINATES BAR").
    #
    # NOTE: with the CORRECTED net-based bar, cheap_acc>=90% and bar_cleared
    # are provably mutually exclusive whenever baseline_acc<=85% -- this is
    # exactly why the fix works (spec: "The directional bar plus this
    # precedence rule removes the undefined state"). Proof: cheap_correct =
    # (baseline_correct - b) + c; bar_cleared needs net=b-c>=10 i.e. c<=b-10,
    # so cheap_correct <= baseline_correct - 10 <= 51-10 = 41 (68.3%) when
    # baseline_acc<=85% (51/60) -- nowhere near the 90% (54/60) kill
    # threshold. So this test cannot construct "bar_cleared AND killed" (it
    # is mathematically unreachable); it instead proves KILL still reports
    # as the final verdict even though net independently comes out negative
    # here (kill is checked and reported without needing bar_cleared to be
    # true at all -- there is no ambiguous state for it to dominate).
    ids = _all_60_ids()
    baseline = {q: True for q in ids[:40]}  # 66.7%, well under both ceilings
    baseline.update({q: False for q in ids[40:]})
    cheap = {q: True for q in ids[:40]}  # concordant-right on all 40
    cheap.update({q: True for q in ids[40:54]})  # + 14 of the baseline-wrong items right too
    cheap.update({q: False for q in ids[54:]})  # remaining 6 concordant-wrong
    _write_pair(tmp_path, baseline, cheap)

    r = verify(results_dir=tmp_path)
    assert r["cheap_acc"] == pytest.approx(54 / 60)
    assert r["cheap_acc"] >= KILL_CHEAP_ACC
    assert r["killed"]
    assert r["verdict"] == "KILL"
    assert any("cheap accuracy" in reason for reason in r["kill_reasons"])
    # And bar_cleared is indeed false here -- confirming the two conditions
    # never overlap under the corrected bar, not just that kill wins a race.
    assert not r["bar_cleared"]


def test_kill_on_flagship_saturation_no_headroom(tmp_path):
    ids = _all_60_ids()
    baseline = {q: True for q in ids[:58]}  # 58/60 = 96.7% >= 95% kill threshold
    baseline.update({q: False for q in ids[58:]})
    cheap = {q: False for q in ids}
    _write_pair(tmp_path, baseline, cheap)

    r = verify(results_dir=tmp_path)
    assert r["baseline_acc"] >= KILL_FLAGSHIP_ACC
    assert r["killed"]
    assert r["verdict"] == "KILL"
    assert any("flagship accuracy" in reason for reason in r["kill_reasons"])


# ---------------------------------------------------------------------------
# Contamination flag
# ---------------------------------------------------------------------------


def test_contamination_flag_raised_on_large_year_gap(tmp_path):
    ids2024 = _ids("aime2024", 30)
    ids2025 = _ids("aime2025", 30)
    baseline = {q: False for q in ids2024 + ids2025}
    # cheap: memorised on 2024 (25/30 correct), weak on 2025 (5/30) -- gap=20.
    cheap = {q: (i < 25) for i, q in enumerate(ids2024)}
    cheap.update({q: (i < 5) for i, q in enumerate(ids2025)})
    _write_pair(tmp_path, baseline, cheap)

    r = verify(results_dir=tmp_path)
    assert r["by_year"]["2024"]["cheap_correct"] == 25
    assert r["by_year"]["2025"]["cheap_correct"] == 5
    assert r["year_gap_cheap_correct"] == 20
    assert r["year_gap_cheap_correct"] >= CONTAMINATION_MIN_YEAR_GAP
    assert r["contamination_flag"] is True


def test_contamination_flag_not_raised_when_years_are_close(tmp_path):
    ids2024 = _ids("aime2024", 30)
    ids2025 = _ids("aime2025", 30)
    baseline = {q: False for q in ids2024 + ids2025}
    cheap = {q: (i < 10) for i, q in enumerate(ids2024)}
    cheap.update({q: (i < 8) for i, q in enumerate(ids2025)})  # gap=2
    _write_pair(tmp_path, baseline, cheap)

    r = verify(results_dir=tmp_path)
    assert r["year_gap_cheap_correct"] == 2
    assert r["contamination_flag"] is False
