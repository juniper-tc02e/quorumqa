"""Pins the S7 ship-gate live run (SuperGPQA-hard, seeds 411/523/631) against
its committed log/JSON and against the raw pool files themselves. No API
calls, no tokens -- pure JSONL/dict mining via benchmark/score_selectors.py's
own `load_pool` / `score_pool` / `selector_report` / `ship_gate_verdict`
(imported, not reimplemented), matching this repo's existing offline-test
convention (see test_score_selectors_offline.py, test_verify_universal_gate_offline.py).

The claim being pinned: `max_single_confidence` -- the strongest S1 in-sample
candidate (net +76 on SuperGPQA-hard, the single strongest net in the whole
audit) -- reverses sign on held-out data: pooled net=-4, p=0.7796,
DO NOT SHIP. `confidence_weighted`, the other S1 shippable candidate, also
fails (net=+3 < required +5, discordant=11 < required 12). Both consumed-seed
markers exist and are correctly attributed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.score_selectors import (
    assert_seeds_not_burned,
    load_pool,
    score_pool,
    selector_report,
    ship_gate_verdict,
)

RESULTS_DIR = Path("benchmark/results")
POOL_PATHS = {
    411: RESULTS_DIR / "pool_supergpqa_cheap_k8_seed411.jsonl",
    523: RESULTS_DIR / "pool_supergpqa_cheap_k8_seed523.jsonl",
    631: RESULTS_DIR / "pool_supergpqa_cheap_k8_seed631.jsonl",
}
VERDICT_JSON_PATH = RESULTS_DIR / "s7_ship_gate_max_single_confidence.json"
CONSUMED_SEED_PATHS = {
    411: RESULTS_DIR / "s7_shipgate_consumed_seed411.jsonl",
    523: RESULTS_DIR / "s7_shipgate_consumed_seed523.jsonl",
    631: RESULTS_DIR / "s7_shipgate_consumed_seed631.jsonl",
}

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in POOL_PATHS.values()),
    reason="S7 raw pool files are gitignored (benchmark/results/*.jsonl) and only present on the machine that ran S7 live.",
)

EXPECTED_PER_SEED_BC = {
    "max_single_confidence": {411: (6, 7), 523: (5, 4), 631: (8, 12)},
    "confidence_weighted": {411: (2, 2), 523: (1, 1), 631: (4, 1)},
}
EXPECTED_PLURALITY_ACC_PCT = {411: 57.78, 523: 61.11, 631: 65.56}
EXPECTED_ORACLE_COV_PCT = {411: 76.67, 523: 80.00, 631: 85.56}


@pytest.fixture(scope="module")
def scored_by_seed():
    """Fresh score_pool(k=8) per seed, straight from the raw pool files."""
    out = {}
    for seed, path in POOL_PATHS.items():
        rows = load_pool(path)
        assert len(rows) == 90, f"seed {seed}: expected 90 rows, got {len(rows)}"
        out[seed] = score_pool(rows, k=8)
    return out


@pytest.fixture(scope="module")
def committed_verdict_json():
    return json.loads(VERDICT_JSON_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Per-seed arithmetic, recomputed fresh from the raw pools
# ---------------------------------------------------------------------------


def test_pool_inventory_is_90_items_each(scored_by_seed):
    for seed, scored in scored_by_seed.items():
        assert scored["n_items"] == 90


@pytest.mark.parametrize("seed", [411, 523, 631])
def test_plurality_accuracy_and_oracle_coverage_match(seed, scored_by_seed):
    scored = scored_by_seed[seed]
    assert round(scored["plurality_accuracy"] * 100, 2) == pytest.approx(EXPECTED_PLURALITY_ACC_PCT[seed], abs=0.01)
    assert round(scored["oracle_coverage"] * 100, 2) == pytest.approx(EXPECTED_ORACLE_COV_PCT[seed], abs=0.01)


@pytest.mark.parametrize("selector", ["max_single_confidence", "confidence_weighted"])
@pytest.mark.parametrize("seed", [411, 523, 631])
def test_per_seed_bc_matches_log(selector, seed, scored_by_seed):
    rep = selector_report(scored_by_seed[seed]["per_item"], selector)
    exp_b, exp_c = EXPECTED_PER_SEED_BC[selector][seed]
    assert (rep["b"], rep["c"]) == (exp_b, exp_c)
    assert rep["net"] == exp_b - exp_c


# ---------------------------------------------------------------------------
# Pooled ship-gate verdict for max_single_confidence -- the headline pin
# ---------------------------------------------------------------------------


def test_pooled_bc_net_p_for_max_single_confidence(scored_by_seed):
    reports = [
        {
            "seed": seed,
            "b": selector_report(scored_by_seed[seed]["per_item"], "max_single_confidence")["b"],
            "c": selector_report(scored_by_seed[seed]["per_item"], "max_single_confidence")["c"],
            "n_items": scored_by_seed[seed]["n_items"],
        }
        for seed in (411, 523, 631)
    ]
    verdict, reasons, stats = ship_gate_verdict("max_single_confidence", "SuperGPQA-hard", reports)

    assert stats["pooled_b"] == 19
    assert stats["pooled_c"] == 23
    assert stats["pooled_net"] == -4
    assert stats["pooled_discordant"] == 42
    assert stats["pooled_p"] == pytest.approx(0.7796, abs=1e-4)
    assert stats["pooled_n"] == 270


def test_verdict_is_do_not_ship_for_max_single_confidence(scored_by_seed):
    reports = [
        {
            "seed": seed,
            "b": selector_report(scored_by_seed[seed]["per_item"], "max_single_confidence")["b"],
            "c": selector_report(scored_by_seed[seed]["per_item"], "max_single_confidence")["c"],
            "n_items": scored_by_seed[seed]["n_items"],
        }
        for seed in (411, 523, 631)
    ]
    verdict, reasons, stats = ship_gate_verdict("max_single_confidence", "SuperGPQA-hard", reports)

    assert verdict == "DO NOT SHIP"
    # Four independent failing clauses, per the committed log.
    assert any("net=-4" in r and "required +5" in r for r in reasons)
    assert any("0.7796" in r and "not < 0.05" in r for r in reasons)
    assert any("outside 50%" in r for r in reasons)
    assert any("negative net on seed(s) [411, 631]" in r for r in reasons)


def test_confidence_weighted_also_fails_the_gate(scored_by_seed):
    reports = [
        {
            "seed": seed,
            "b": selector_report(scored_by_seed[seed]["per_item"], "confidence_weighted")["b"],
            "c": selector_report(scored_by_seed[seed]["per_item"], "confidence_weighted")["c"],
            "n_items": scored_by_seed[seed]["n_items"],
        }
        for seed in (411, 523, 631)
    ]
    verdict, reasons, stats = ship_gate_verdict("confidence_weighted", "SuperGPQA-hard", reports)

    assert stats["pooled_b"] == 7
    assert stats["pooled_c"] == 4
    assert stats["pooled_net"] == 3
    assert stats["pooled_discordant"] == 11
    assert verdict == "DO NOT SHIP"
    assert any("net=+3" in r and "required +5" in r for r in reasons)
    assert any("discordant" in r for r in reasons)


# ---------------------------------------------------------------------------
# Recomputed numbers must match the already-committed log/JSON exactly --
# this test file is an independent check, not a duplicate of the run.
# ---------------------------------------------------------------------------


def test_recomputed_verdict_matches_committed_json(scored_by_seed, committed_verdict_json):
    reports = [
        {
            "seed": seed,
            "b": selector_report(scored_by_seed[seed]["per_item"], "max_single_confidence")["b"],
            "c": selector_report(scored_by_seed[seed]["per_item"], "max_single_confidence")["c"],
            "n_items": scored_by_seed[seed]["n_items"],
        }
        for seed in (411, 523, 631)
    ]
    verdict, reasons, stats = ship_gate_verdict("max_single_confidence", "SuperGPQA-hard", reports)

    committed = committed_verdict_json["ship_gate"]
    assert verdict == committed["verdict"]
    assert stats["pooled_b"] == committed["pooled_b"]
    assert stats["pooled_c"] == committed["pooled_c"]
    assert stats["pooled_net"] == committed["pooled_net"]
    assert stats["pooled_discordant"] == committed["pooled_discordant"]
    assert stats["pooled_p"] == pytest.approx(committed["pooled_p"], abs=1e-9)
    assert reasons == committed["reasons"]


# ---------------------------------------------------------------------------
# Burn-guard: the three held-out seeds must now be consumed
# ---------------------------------------------------------------------------


def test_consumed_seed_marker_files_exist_and_reference_correct_seeds():
    for seed, path in CONSUMED_SEED_PATHS.items():
        assert path.exists(), f"missing consumption marker for seed {seed}: {path}"
        line = path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        assert record["seed"] == seed
        assert record["selector"] == "max_single_confidence"
        assert record["benchmark"] == "SuperGPQA-hard"
        assert record["verdict"] == "DO NOT SHIP"


def test_all_three_seeds_are_now_burned():
    with pytest.raises(ValueError, match=r"burned"):
        assert_seeds_not_burned([411, 523, 631], results_dir=RESULTS_DIR)
