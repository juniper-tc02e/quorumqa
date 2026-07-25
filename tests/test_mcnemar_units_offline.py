"""The +5 bar is in ITEMS, not percentage points.

Two distinct traps are pinned here.

TRAP 1 -- the qualifier. "+5 net clears p<0.05" is true only with ZERO losses.
The repo's own mcnemar_exact_one_sided docstring says "with zero losses"; the
public summary in docs/FINDINGS.md dropped that qualifier until 2026-07-26. A
net of +5 made of 10 gains and 5 losses is p=0.151, not p=0.031.

TRAP 2 -- the units. MCNEMAR_MIN_NET is 5 items. Comparing it directly against a
percentage-point delta is only valid at n=100, and is too PERMISSIVE at every
smaller n. Every benchmark in figure_claims_ledger.csv has n<100 (bar one row at
n=451), so the old pp-proxy rule was permissive everywhere it mattered. The fix
classifies on real item counts; these tests pin that it is also a no-op on
current data, so it closed a latent trap without restating any published claim.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided
from benchmark.figure_data import MCNEMAR_MIN_NET, NOISE_FLOOR_PP
from benchmark.make_figures_progress import _to_float_or_none, fill_category

LEDGER = Path(__file__).resolve().parents[1] / "benchmark" / "results" / "figure_claims_ledger.csv"


def _rows() -> list[dict]:
    with LEDGER.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _seed_count(row: dict) -> int:
    raw = (row.get("seeds") or "").replace(";", ",")
    return len([s for s in raw.split(",") if s.strip()])


# --------------------------------------------------------------------------
# TRAP 1: the zero-losses qualifier
# --------------------------------------------------------------------------

def test_plus_five_only_clears_with_zero_losses():
    assert mcnemar_exact_one_sided(5, 0) == pytest.approx(0.03125)
    assert mcnemar_exact_one_sided(5, 0) < 0.05
    # Same net of +5, but with losses -- nowhere near significant.
    for b, c in [(8, 3), (9, 4), (10, 5), (12, 7)]:
        assert b - c == 5
        assert mcnemar_exact_one_sided(b, c) > 0.10, f"b={b} c={c}"


def test_required_net_grows_with_discordant_volume():
    """At 10 discordant pairs you need +8, not +5."""

    def min_net(n: int) -> int:
        for b in range(n + 1):
            c = n - b
            if b - c > 0 and mcnemar_exact_one_sided(b, c) < 0.05:
                return b - c
        return 10**9

    assert min_net(5) == 5
    assert min_net(10) == 8
    assert min_net(20) == 10
    # Monotone non-decreasing in n over this range.
    nets = [min_net(n) for n in (5, 8, 10, 12, 16, 20, 24)]
    assert nets == sorted(nets)


# --------------------------------------------------------------------------
# TRAP 2: items vs percentage points
# --------------------------------------------------------------------------

def test_five_items_is_not_five_pp_except_at_n_100():
    assert 5 / 100 * 100 == pytest.approx(5.0)
    # Smaller n => 5 items is MORE than 5pp, so a 5pp line is permissive.
    for n in (50, 60, 88, 90):
        assert 5 / n * 100 > 5.0
    assert 5 / 50 * 100 == pytest.approx(10.0)


def test_every_ledger_benchmark_is_below_n_100():
    """Why the old proxy was permissive everywhere it mattered."""
    ns = [
        n for n in (_to_float_or_none(r.get("n_common_items")) for r in _rows())
        if n
    ]
    assert ns, "ledger has no n_common_items values"
    assert sum(1 for n in ns if n < 100) >= len(ns) - 1


def test_fill_category_uses_items_not_pp():
    """+6pp on n=50 is 3 items -- below the bar, so not solid."""
    assert fill_category(3, 6.0, False, "printed_mean", 50) == "half"
    # The same +6pp on n=100 is 6 items, which does clear it.
    assert fill_category(3, 6.0, False, "printed_mean", 100) == "solid"
    # And 5 items exactly at n=90 needs ~5.56pp.
    assert fill_category(3, 5.0, False, "printed_mean", 90) == "half"
    assert fill_category(3, 5.6, False, "printed_mean", 90) == "solid"


def test_unknown_n_can_never_claim_solid():
    for pp in (5.0, 20.0, 99.0):
        assert fill_category(3, pp, False, "printed_mean", None) != "solid"


def test_noise_band_and_contamination_still_dominate():
    assert fill_category(3, 1.0, False, "printed_mean", 90) == "hollow"
    assert fill_category(3, 50.0, True, "printed_mean", 90) == "hollow"
    assert fill_category(1, 50.0, False, "printed_mean", 90) == "hollow"


def test_flagship_row_is_solid_because_it_now_carries_a_real_p_value():
    """The one intended classification change, and why it is not a regression.

    flagship_panel/SuperGPQA-hard used to render "half" only because its
    net_discordant_items and mcnemar_p cells were EMPTY -- the claim was
    validated but its statistic had never been computed. Filling in the real
    pooled test (net +10, p=0.0032, verified by
    benchmark/verify_flagship_claim.py) promotes it to "solid". That is the
    figure becoming more accurate, not looser: the promotion is driven by a
    measured p<0.05, not by the pp proxy.
    """
    row = next(
        r for r in _rows()
        if r["config"] == "flagship_panel" and r["benchmark_label"] == "SuperGPQA-hard"
    )
    assert row["net_discordant_items"] == "+10"
    assert row["mcnemar_p"] == "0.0032"
    assert fill_category(
        3, 4.1, False, "printed_mean",
        _to_float_or_none(row["n_common_items"]),
        _to_float_or_none(row["net_discordant_items"]),
        _to_float_or_none(row["mcnemar_p"]),
    ) == "solid"
    # Without the statistic it would have stayed "half" -- the old behaviour.
    assert fill_category(3, 4.1, False, "printed_mean", None, None, None) == "half"


def test_a_real_p_value_cannot_rescue_a_sub_bar_net():
    """p<0.05 alone is not enough; net magnitude remains a necessary screen."""
    assert fill_category(3, 4.1, False, "printed_mean", 241, 3, 0.01) == "half"
    assert fill_category(3, 4.1, False, "printed_mean", 241, 10, 0.20) == "half"


def test_units_fix_is_a_no_op_on_rows_without_a_recorded_statistic():
    """Closed a latent trap; restated no published claim.

    Scoped to rows whose net/p cells are empty -- i.e. every row as the ledger
    stood before the flagship statistic was computed. The one row that now
    carries a real p-value is covered by the test above.
    """

    def old_rule(seeds, delta_pp, contaminated, provenance):
        if delta_pp is None:
            return "hollow"
        if contaminated:
            return "hollow"
        magnitude = abs(delta_pp)
        if seeds <= 1 or magnitude < NOISE_FLOOR_PP:
            category = "hollow"
        elif seeds >= 3 and magnitude >= MCNEMAR_MIN_NET:
            category = "solid"
        else:
            category = "half"
        if provenance == "computed_matched_approx" and category == "solid":
            category = "half"
        return category

    provenances = (
        "printed_mean",
        "printed_per_seed_centroid",
        "computed_matched_approx",
        "computed_vs_flat_reference",
        "unresolved",
    )
    compared = 0
    for row in _rows():
        if _to_float_or_none(row.get("mcnemar_p")) is not None:
            continue  # covered by the flagship-promotion test instead
        seeds = _seed_count(row)
        pp = _to_float_or_none(row.get("mean_delta_pp"))
        n = _to_float_or_none(row.get("n_common_items"))
        contaminated = str(row.get("contaminated", "")).strip().lower() in (
            "1", "true", "yes",
        )
        for prov in provenances:
            compared += 1
            assert old_rule(seeds, pp, contaminated, prov) == fill_category(
                seeds, pp, contaminated, prov, n
            ), f"{row.get('benchmark_label')} / {row.get('config')} / {prov}"
    assert compared > 100


def test_to_float_or_none_tolerates_blank_cells():
    """The strict _to_float raises on '' -- that crash was introduced and fixed."""
    assert _to_float_or_none("") is None
    assert _to_float_or_none(None) is None
    assert _to_float_or_none("NR") is None
    assert _to_float_or_none(" 90 ") == pytest.approx(90.0)
    assert _to_float_or_none("+4.1") == pytest.approx(4.1)
    assert _to_float_or_none("−6.0") == pytest.approx(-6.0)
