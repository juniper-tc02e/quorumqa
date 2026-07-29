"""Pins chem_thinking_gate's corrected, now-3-seed claim to its paired statistic.

Prior state: "+4.4" was one matched seed (314), p=0.145, did not clear the bar
(corrected 2026-07-26). Tier G of the approved week-1 queue ran the two missing
matched baselines (seeds 217, 471) to complete the comparison. These tests pin
the result so it breaks loudly if the underlying files ever change.
"""

from __future__ import annotations

import pytest

from benchmark.verify_chemistry_claim import ARMS, verify


@pytest.fixture(scope="module")
def r():
    return verify()


def test_all_three_seeds_present(r):
    assert set(r["per_seed"]) == {217, 314, 471} == set(ARMS)


def test_shared_counts_are_nonzero(r):
    for seed, s in r["per_seed"].items():
        assert s["shared"] > 50, f"seed {seed} shared only {s['shared']} items"


def test_per_seed_discordant_counts(r):
    assert (r["per_seed"][217]["b"], r["per_seed"][217]["c"]) == (9, 0)
    assert (r["per_seed"][314]["b"], r["per_seed"][314]["c"]) == (6, 2)
    assert (r["per_seed"][471]["b"], r["per_seed"][471]["c"]) == (1, 2)


def test_seed_314_matches_the_previously_published_single_seed_figure(r):
    """The pre-existing correction (commit 019d9da) must still reproduce."""
    s = r["per_seed"][314]
    assert s["net"] == 4
    assert s["delta_pp"] == pytest.approx(4.60, abs=0.05)
    assert s["p_one_sided"] == pytest.approx(0.1445, abs=1e-3)


def test_seed_471_is_slightly_negative(r):
    """Honesty guard: the pooled win must not hide seed 471's loss."""
    s = r["per_seed"][471]
    assert s["net"] < 0
    assert s["b"] < s["c"]


def test_seed_217_alone_clears_the_bar(r):
    s = r["per_seed"][217]
    assert s["net"] >= 5
    assert s["p_one_sided"] < 0.05


def test_pooled_statistic(r):
    p = r["pooled"]
    assert p["shared"] == 259
    assert (p["b"], p["c"]) == (16, 4)
    assert p["net"] == 12
    assert p["delta_pp"] == pytest.approx(4.63, abs=0.02)
    assert p["p_one_sided"] == pytest.approx(0.00591, abs=1e-5)
    assert p["p_one_sided"] < 0.05


def test_bar_is_now_cleared_by_both_branches(r):
    """The claim upgrade this Tier G run produced: from 'does not clear' to
    'clears both branches'."""
    per_seed = r["per_seed"].values()
    branch1 = [s for s in per_seed if s["net"] >= 5 and s["p_one_sided"] < 0.05]
    assert len(branch1) >= 1

    at_least_three = sum(1 for s in per_seed if s["net"] >= 3)
    assert at_least_three >= 2
    assert r["pooled"]["p_one_sided"] < 0.05


def test_heterogeneity_is_real_not_a_data_artifact(r):
    """217 is a big win, 471 is a loss -- pooling is doing real work here,
    not just adding a redundant confirmation. Any doc citing this claim must
    show the per-seed spread, not just the pooled net."""
    nets = sorted(s["net"] for s in r["per_seed"].values())
    assert nets == [-1, 4, 9]
