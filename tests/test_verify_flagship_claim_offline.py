"""Pins the repo's flagship positive claim to its paired statistic.

Before this, `flagship_panel`'s SuperGPQA-hard row carried the verdict
"validated" with EMPTY net_discordant_items and mcnemar_p cells -- the deltas
were transcribed but the test behind them had never been computed. These tests
make the claim break loudly if the underlying files ever change.

The most important assertion here is test_shared_counts_are_nonzero: reading the
wrong wrapper key ("engine" on a baseline file, which stores "baseline") yields
an EMPTY outcome dict, so the pairing silently reports zero shared items and
reads as "no effect" instead of raising. That exact mistake happened while
writing this analysis.
"""

from __future__ import annotations

import pytest

from benchmark.verify_flagship_claim import ARMS, PUBLISHED_PP, verify


@pytest.fixture(scope="module")
def r():
    return verify()


def test_shared_counts_are_nonzero(r):
    """Wrapper-key guard -- a silent zero would look like a null result."""
    for seed, s in r["per_seed"].items():
        assert s["shared"] > 50, f"seed {seed} shared only {s['shared']} items"


def test_all_three_seeds_present(r):
    assert set(r["per_seed"]) == {7, 42, 123} == set(ARMS)


def test_published_per_seed_deltas_reproduce(r):
    for seed, expected in PUBLISHED_PP.items():
        assert r["per_seed"][seed]["delta_pp"] == pytest.approx(expected, abs=0.1)


def test_per_seed_discordant_counts(r):
    assert (r["per_seed"][42]["b"], r["per_seed"][42]["c"]) == (3, 0)
    assert (r["per_seed"][7]["b"], r["per_seed"][7]["c"]) == (3, 1)
    assert (r["per_seed"][123]["b"], r["per_seed"][123]["c"]) == (5, 0)


def test_pooled_statistic(r):
    p = r["pooled"]
    assert p["shared"] == 241
    assert (p["b"], p["c"]) == (11, 1)
    assert p["net"] == 10
    assert p["delta_pp"] == pytest.approx(4.15, abs=0.02)
    assert p["p_one_sided"] == pytest.approx(0.00317, abs=1e-5)
    assert p["p_one_sided"] < 0.05


def test_bar_is_cleared_by_both_branches(r):
    """Branch 1: a seed with net>=+5 AND p<0.05. Branch 2: >=2 seeds at
    net>=+3 with the pooled test clearing. Both hold, so the claim does not
    rest on a single reading of the bar."""
    per_seed = r["per_seed"].values()
    branch1 = [s for s in per_seed if s["net"] >= 5 and s["p_one_sided"] < 0.05]
    assert len(branch1) >= 1

    at_least_three = sum(1 for s in per_seed if s["net"] >= 3)
    assert at_least_three >= 2
    assert r["pooled"]["p_one_sided"] < 0.05


def test_individually_only_one_seed_reaches_significance(r):
    """Honesty guard: two of three seeds do NOT clear on their own.

    If this ever starts passing for all three, someone has changed the data or
    the test -- the claim's strength genuinely comes from pooling.
    """
    clearing = [s for s in r["per_seed"].values() if s["p_one_sided"] < 0.05]
    assert len(clearing) == 1


def test_candidate_arm_dropped_items_on_every_seed(r):
    """The survivor-selection caveat is real and must stay documented."""
    for seed, s in r["per_seed"].items():
        assert s["candidate_n"] < s["comparator_n"], seed
        assert s["shared"] <= s["candidate_n"]
    assert r["pooled"]["shared"] == 241
    # The roadmap's bar names n=270; the real pooled n is smaller.
    assert r["pooled"]["shared"] < 270


def test_seed42_comparator_is_the_pilot_file():
    """This claim's seed-42 comparator is the PILOT file, and must stay so.

    Original guard (2026-07-26) asserted that `lever_baseline_supergpqa_seed42.jsonl`
    did not exist, because the evidence table had implied one when the real
    comparator was the pilot. On 2026-08-02 that file was created for real --
    a standalone flagship-1x baseline run for the SuperGPQA cost frontier --
    so the non-existence half of the guard is retired.

    What replaces it matters more, because TWO valid seed-42 flagship
    baselines now exist and they differ by 2.4pp (pilot-embedded 79.1%, new
    standalone 81.8%; 92.9% per-item agreement -- ordinary decoder noise
    between two samples of the same configuration). Whichever a downstream
    analysis picks shifts its numbers, so the binding requirement is that
    THIS claim keeps using the pilot, unchanged, and does not silently
    acquire the newer file.

    Checked for robustness rather than assumed: the SuperGPQA frontier's
    verdict holds under either choice -- flagship_panel beats flagship-1x at
    pooled net +7, p=0.0327 with the new baseline (the published, more
    conservative figure) and net +10, p=0.0032 with the pilot's.
    """
    assert ARMS[42][1] == "supergpqa_hard_pilot_seed42.jsonl"
    from benchmark.verify_flagship_claim import RESULTS
    assert (RESULTS / "supergpqa_hard_pilot_seed42.jsonl").exists()


def test_the_two_seed42_flagship_baselines_are_not_conflated():
    """Both files carry a seed-42 flagship-1x baseline. They must never be
    pooled or swapped: the frontier uses the standalone file for all three
    seeds (uniform provenance), this claim uses the pilot."""
    import json

    from benchmark.analyze_cost_frontier import ARMS as FRONTIER_ARMS
    from benchmark.verify_flagship_claim import RESULTS

    # The frontier's seed-42 flagship arm is the standalone file, not the pilot.
    template, seeds = FRONTIER_ARMS["supergpqa"]["flagship_1x"]
    assert template == "lever_baseline_supergpqa_seed{s}.jsonl"
    assert 42 in seeds

    standalone = RESULTS / "lever_baseline_supergpqa_seed42.jsonl"
    if not standalone.exists():
        pytest.skip("standalone seed-42 baseline is gitignored and absent here")

    def _acc(path, wrapper):
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        recs = [r[wrapper] for r in rows if wrapper in r]
        return sum(bool(x["correct"]) for x in recs) / len(recs)

    pilot_acc = _acc(RESULTS / "supergpqa_hard_pilot_seed42.jsonl", "baseline")
    new_acc = _acc(standalone, "baseline")
    # They disagree, which is exactly why they must not be interchanged.
    assert abs(new_acc - pilot_acc) > 0.01
    assert 0.75 < pilot_acc < 0.85 and 0.75 < new_acc < 0.90
