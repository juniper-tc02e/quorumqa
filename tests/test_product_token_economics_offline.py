"""The per-path token figures in docs/product/PRODUCT.md must match the run.

WHY. PRODUCT.md's unit economics were stated in dollars under pre-Token-Plan
pricing, where `qwen3.6-flash` input costs 0.60 and `qwen3.7-max` input costs
2.50 USD/Mtok. The entire "cheaper than the flagship" claim lived in that ~4x
price spread. The Token Plan bills a token quota instead, and in tokens the
same engine is MORE expensive -- so the dollar figures now point the opposite
way from the unit that bills.

On 2026-08-03 the doc was re-derived in tokens from the frozen submission run.
These tests recompute those figures from the committed .jsonl and assert the
doc still agrees, so the table cannot silently drift from its source.

A SECOND, SUBTLER HAZARD this guards. The repo already publishes a token pair
for the same-sounding quantity -- 8,690 vs 2,792, quoted in README.md,
architecture.md and FINDINGS-2026-08.md -- measured on the 3-seed paired TB-1
item set (seeds 1001/2311/3407, n=265). The PRODUCT.md table is the frozen
n=90 seed-42 submission run and gives different numbers. BOTH ARE CORRECT;
they are different item sets. The failure mode is someone "fixing" one to match
the other. The reconciliation paragraph is therefore asserted to exist.

Offline: reads committed result files, no API calls.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRODUCT_MD = PROJECT_ROOT / "docs" / "product" / "PRODUCT.md"
SUMMARY = PROJECT_ROOT / "benchmark" / "results" / "submission_token_economics.json"
RUN_FILES = ["benchmark/results/full_run.jsonl", "benchmark/results/full_run2.jsonl"]

#: The other, legitimate token pair. Measured on a DIFFERENT item set.
TB1_PAIRED_TOKENS = (8690, 2792)


def _tokens(calls) -> int:
    return sum(c.get("input_tokens", 0) + c.get("output_tokens", 0) for c in calls)


@pytest.fixture(scope="module")
def measured():
    """Read the COMMITTED summary, not the raw run.

    The raw .jsonl is gitignored (benchmark/results/*.jsonl). A fixture that
    read it directly would pytest.skip everywhere except the machine that
    happened to run the benchmark -- a guard that does not guard. The committed
    aggregate is the source of record here; the separate test below re-derives
    it from the raw run wherever that run is actually present, so the summary
    itself cannot go stale unnoticed.
    """
    assert SUMMARY.exists(), (
        f"{SUMMARY.name} is missing. Regenerate with "
        f"`python -m benchmark.derive_token_economics --write`."
    )
    d = json.loads(SUMMARY.read_text(encoding="utf-8"))
    t = d["tokens_per_item"]
    return {
        "n": d["n_items"],
        "unanimous": t["unanimous"],
        "escalated": t["escalated"],
        "blended": t["blended"],
        "baseline": t["baseline_flagship_1x"],
        "escalation_rate": d["escalation_rate_pct"],
        "multiples": d["multiples_vs_flagship_1x"],
    }


def test_the_committed_summary_still_matches_the_raw_run():
    """Runs only where the gitignored source is present -- on the machine that
    holds it, which is the only place the summary can be regenerated wrong."""
    seen = {}
    for rel in RUN_FILES:
        p = PROJECT_ROOT / rel
        if not p.exists():
            pytest.skip(f"{rel} not present (raw results are gitignored)")
        with p.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if "engine" in row:
                    seen[row["engine"]["item"]["question_id"]] = row

    unanimous, escalated, baseline = [], [], []
    for r in seen.values():
        e = r["engine"]
        (escalated if e["escalated"] else unanimous).append(_tokens(e["calls"]))
        if r.get("baseline"):
            baseline.append(_tokens(r["baseline"]["calls"]))

    d = json.loads(SUMMARY.read_text(encoding="utf-8"))
    t = d["tokens_per_item"]
    assert d["n_items"] == len(seen)
    assert t["unanimous"] == round(statistics.mean(unanimous))
    assert t["escalated"] == round(statistics.mean(escalated))
    assert t["blended"] == round(statistics.mean(unanimous + escalated))
    assert t["baseline_flagship_1x"] == round(statistics.mean(baseline))


def test_the_run_is_the_full_90_item_set(measured):
    assert measured["n"] == 90, "PRODUCT.md cites n=90; a partial run invalidates the table"


@pytest.mark.parametrize("label,published", [
    ("unanimous", 4638),
    ("escalated", 16218),
    ("blended", 9013),
    ("baseline", 3415),
])
def test_published_per_path_tokens_match_the_run(measured, label, published):
    assert round(measured[label]) == published, (
        f"PRODUCT.md publishes {published} tok/item for '{label}' but the run "
        f"measures {measured[label]:.0f}. Update the doc, not this test -- the "
        f"run is the source."
    )


def test_the_escalation_rate_matches(measured):
    assert measured["escalation_rate"] == pytest.approx(37.8, abs=0.1)


def test_the_multiples_in_the_doc_are_arithmetically_right(measured):
    """Ratios are the numbers a reader actually acts on, so they get checked
    against the means rather than trusted as transcribed."""
    text = PRODUCT_MD.read_text(encoding="utf-8")
    for label, shown in [("unanimous", "1.36×"), ("escalated", "4.75×"), ("blended", "2.64×")]:
        got = measured[label] / measured["baseline"]
        assert f"{got:.2f}×" == shown, f"{label}: doc says {shown}, run gives {got:.2f}×"
        assert shown in text, f"{shown} missing from PRODUCT.md"


def test_the_two_token_pairs_are_explicitly_reconciled():
    """8,690/2,792 (TB-1 paired, n=265) and 9,013/3,415 (submission, n=90) are
    different item sets measuring different things. Without the reconciliation
    paragraph they read as a contradiction and invite a wrong 'fix'."""
    text = PRODUCT_MD.read_text(encoding="utf-8")
    assert "8,690" in text and "2,792" in text, (
        "PRODUCT.md must name the other published token pair so the two are not "
        "mistaken for competing estimates of one quantity"
    )
    assert "different item sets" in text
    assert "not two\n  estimates of one quantity" in text or \
           "not two estimates of one quantity" in text.replace("\n  ", " ")


def test_no_unverifiable_margin_claim_survives():
    """The Token Plan rate is not in this repo, so no margin figure can be
    defended. The doc must say so rather than restate the old dollar claim as
    though it still held."""
    text = PRODUCT_MD.read_text(encoding="utf-8")
    i = text.find("stays well under subscription price")
    assert i != -1, "bullet moved; re-point this test"
    following = text[i: i + 1200]
    assert "not currently verifiable" in following, (
        "the superseded margin claim must be marked unverifiable at the point "
        "of use, not silently left standing"
    )


# ---------------------------------------------------------------------------
# The live site data must quote THIS run's cost, not another run's
# ---------------------------------------------------------------------------


def test_site_stats_quote_the_run_they_describe():
    """site_data/cases.json's stats block describes the frozen n=90 seed-42
    run -- accuracy 78.9/84.4/58.9, 90 items, generated_from full_run2.jsonl.

    Until 2026-08-03 its tokens_per_question read 8,690 / 2,792. Those are real,
    published, correct numbers -- for a DIFFERENT run (the TB-1 paired set,
    seeds 1001/2311/3407, n=265). I put them there myself while fixing a
    separate defect in the same block, which is precisely the confusion the
    do_not_confuse_with note in submission_token_economics.json was written to
    prevent, committed hours earlier.

    A stats block about one run must quote that run's own cost.
    """
    cases = json.loads(
        (PROJECT_ROOT / "site_data" / "cases.json").read_text(encoding="utf-8"))
    econ = json.loads(SUMMARY.read_text(encoding="utf-8"))

    stats = cases["stats"]
    assert stats["n"] == econ["n_items"], "same run, same item count"

    tpq = stats["tokens_per_question"]
    assert tpq["engine"] == econ["tokens_per_item"]["blended"]
    assert tpq["baseline"] == econ["tokens_per_item"]["baseline_flagship_1x"]
    assert tpq["unanimous_path"] == econ["tokens_per_item"]["unanimous"]
    assert tpq["escalated_path"] == econ["tokens_per_item"]["escalated"]
    assert tpq["multiple_vs_baseline"] == econ["multiples_vs_flagship_1x"]["blended"]


def test_site_stats_do_not_silently_carry_the_other_token_pair():
    """The specific regression: the TB-1 pair appearing as this run's cost."""
    tpq = json.loads(
        (PROJECT_ROOT / "site_data" / "cases.json").read_text(encoding="utf-8")
    )["stats"]["tokens_per_question"]
    assert (tpq["engine"], tpq["baseline"]) != TB1_PAIRED_TOKENS, (
        "cases.json describes the n=90 seed-42 run; 8,690/2,792 is the n=265 "
        "TB-1 paired set. Both correct, different runs."
    )
    # It must still NAME the other pair, so the next reader is warned rather
    # than left to rediscover the distinction.
    assert "8,690" in tpq["do_not_confuse_with"]


def test_the_generator_computes_tokens_rather_than_hardcoding_them():
    """The durable fix. The field was a literal, so it could not track the run
    it was emitted alongside; now it is derived from that run's own call logs
    and the mismatch is unrepresentable."""
    src = (PROJECT_ROOT / "site_data" / "build_cases.py").read_text(encoding="utf-8")
    assert '"engine": 8690' not in src and "8690" not in src, (
        "build_cases.py hardcodes a token count again -- compute it from the "
        "records instead"
    )
    assert "def tokens_of(" in src
    assert "tok_engine = round(" in src


def test_dollar_anchored_claims_quote_the_dollar_run_token_pair():
    """The rule, applied mechanically: quote the run the claim is about.

    Both token pairs measure the same quantity -- shipped engine vs one
    flagship call -- on different item sets. 9,013/3,415 (2.64x) is the frozen
    n=90 seed-42 submission run; 8,690/2,792 (3.1x) is the TB-1 paired n=265
    set. Neither is wrong; using the wrong one for the surrounding claim is.

    This error has now appeared in THREE places, all in the most-read text:
    site_data/cases.json's stats block, README.md's opening paragraph, and
    architecture.md's cost-cascade note. Each time it was the TB-1 pair
    standing next to the n=90 DOLLAR figures ($0.0213 vs $0.0240, "11% lower
    cost"), which is the tell -- those dollars are the n=90 run's, so the
    tokens beside them must be too.

    So: within 400 characters of a dollar-anchored claim, the token pair must
    be the n=90 one.
    """
    for rel in ["README.md", "docs/architecture.md", "docs/FINDINGS.md"]:
        text = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
        for anchor in ("$0.0213", "11% lower cost", "11% cheaper"):
            idx = text.find(anchor)
            while idx != -1:
                window = text[idx: idx + 400]
                # A paragraph that explicitly names the OTHER item set is
                # reconciling the two pairs, not confusing them -- the same
                # use/mention escape hatch the sibling test uses.
                labelled = any(k in window for k in ("n=265", "TB-1", "1001/2311/3407"))
                if "8,690" in window and "9,013" not in window and not labelled:
                    raise AssertionError(
                        f"{rel}: {anchor!r} is a figure from the n=90 seed-42 run, "
                        f"but the token pair beside it is 8,690/2,792 (the TB-1 "
                        f"paired n=265 set). Use 9,013/3,415 (2.64x) here, or name "
                        f"the other set explicitly."
                    )
                idx = text.find(anchor, idx + 1)


def test_both_pairs_stay_reconciled_wherever_the_tb1_pair_appears():
    """8,690/2,792 may still be used -- it is correct for TB-1's item set. But
    wherever it appears in reader-facing text it must say which set, or the
    next person to notice the two pairs will 'fix' one of them."""
    for rel in ["README.md", "docs/architecture.md"]:
        text = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
        idx = text.find("8,690")
        while idx != -1:
            window = text[max(0, idx - 350): idx + 350]
            assert ("n=265" in window or "TB-1" in window
                    or "1001/2311/3407" in window), (
                f"{rel}: 8,690 appears without naming the item set it was "
                f"measured on. Two correct pairs exist for this quantity; an "
                f"unlabelled one invites a wrong reconciliation."
            )
            idx = text.find("8,690", idx + 1)


def test_the_site_wall_is_internally_consistent_with_its_stats_block():
    """cases.json carries a 90-entry `wall` that build_cases.py does not
    generate -- it was added by hand outside the generator, which is why both
    of 2026-08-03's corrections were surgical text edits rather than a
    regeneration (regenerating would have destroyed it).

    Hand-maintained data next to generated data is exactly what drifts, and
    nothing was checking it. Every one of these cross-checks passes today; the
    point is that they will keep being checked.
    """
    d = json.loads(
        (PROJECT_ROOT / "site_data" / "cases.json").read_text(encoding="utf-8"))
    wall, stats = d["wall"], d["stats"]

    assert len(wall) == stats["n"], "the wall should hold one entry per question"

    escalated = [w for w in wall if w["kind"] != "unanimous"]
    assert round(100 * len(escalated) / len(wall), 1) == stats["escalation_rate"]

    correct = [w for w in wall if w["correct"]]
    assert round(100 * len(correct) / len(wall), 1) == stats["accuracy"]["engine"]

    overruled = [w for w in wall if w["kind"] == "overruled"]
    assert len(overruled) == stats["overturns"], (
        "wall 'overruled' entries must equal the published overturn count"
    )

    detailed = [w for w in wall if w.get("hasDetail")]
    assert len(detailed) == len(d["cases"]), (
        "every wall entry flagged hasDetail needs a case transcript behind it, "
        "or the site links to nothing"
    )

    assert {w["kind"] for w in wall} <= {"unanimous", "overruled", "confirmed"}
