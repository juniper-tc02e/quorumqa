"""Cross-document consistency of the headline figures.

WHY THIS EXISTS. On 2026-08-03 a five-way documentation audit found two
numbers stated inconsistently across the published record:

  - the SuperGPQA win's p-value appeared as BOTH 0.0195 (README, the 2-seed
    figure) and 0.0327 (FINDINGS-2026-08, the 3-seed figure) after a third
    seed landed and only one file was updated;
  - the GPQA token multiple appeared as BOTH 4.5x and 4.7x, each traceable to
    a different pair of committed measurements.

Neither was caught by the existing guards. `verify_ledger()` checks that a
ledger cell appears *somewhere* in its cited doc -- it cannot notice that two
docs disagree, because it only ever reads one at a time. These tests close
that gap: they assert that where a headline figure appears at all, every
document agrees on it.

DESIGN NOTE -- why "forbidden strings" rather than "expected strings". Asserting
a number is PRESENT everywhere would fail on any doc that legitimately does not
mention it. Asserting a SUPERSEDED number is ABSENT is the property that
actually matters and does not force every file to recite every figure. Each
forbidden value below is a real number this repo once published and has since
replaced, so a reappearance means a regression or a bad revert, not a new
measurement.

Offline. No API calls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Docs that make reader-facing claims. Result write-ups under
#: benchmark/results/ are deliberately EXCLUDED: they are dated records of what
#: a specific run measured, and a superseded number appearing there inside its
#: own historical context is correct, not a defect.
CLAIM_DOCS = [
    "README.md",
    "docs/FINDINGS.md",
    "docs/FINDINGS-2026-08.md",
    "docs/architecture.md",
    "docs/submission.md",
    "docs/product/PRODUCT.md",
    "docs/negative-results.md",
    "docs/capability-roadmap.md",
    "docs/mixture-of-orchestrations-plan.md",
    "docs/same-provider-scaling-research.md",
    # Added 2026-08-03. The FIRST version of this list omitted these two, and
    # both were carrying the stale 2-seed SuperGPQA figures ("77.2% ... +7 at
    # p=0.0195") at the moment the list was written -- so the very test built
    # to catch that drift walked straight past two live instances of it.
    # figures/README.md is as reader-facing as any doc here, and the figure
    # module's docstring is what a maintainer reads before touching the plot.
    "docs/figures/README.md",
    "benchmark/make_figures_frontier.py",
]

#: (forbidden string, what replaced it, why it is wrong now)
SUPERSEDED = [
    ("4.5× the tokens", "4.7× the tokens",
     "the published table is 13,175 vs 2,792 tok/item = 4.7x; 4.5x came from a "
     "different pair (13,541/3,022) and made two figures for one claim"),
    ("+7, p = 0.0195", "+7, p = 0.0327",
     "p=0.0195 was the 2-seed SuperGPQA figure; the committed result is 3 seeds"),
    ("(+7, p=0.0195)", "(+7, p=0.0327)",
     "same 2-seed/3-seed drift, parenthesised form"),
    ("[81.1%, 94.4%]", "[83.3%, 94.4%]",
     "D0's three paced retries recovered 2 of 12 items, moving the floor to 83.3%"),
    ("flagship sits at 77.2%", "flagship sits at 79.2%",
     "77.2% was the 2-seed SuperGPQA flagship accuracy; the 3-seed paired "
     "figure the F10 plot actually renders is 79.2%"),
]

#: Docs deliberately OUTSIDE the drift check, each with its reason.
#:
#: The governing distinction is **frozen vs current**. A pre-registration's
#: numbers are bars and budget estimates fixed BEFORE the data existed;
#: retroactively editing them to match the result destroys the only property
#: that makes a pre-registration worth having. The same logic already excludes
#: benchmark/results/ write-ups, which are dated records of what one run
#: measured. Only documents that speak in the present tense about what is
#: currently true get checked for agreement with each other.
FROZEN_OR_NON_CLAIM_DOCS = {
    # --- frozen pre-registrations: numbers fixed before the data existed ---
    "docs/experiment-spec-book.md",
    "docs/spec-trackb-flagship-comparison.md",
    "docs/spec-sci1-and-knowledge-injection.md",
    "docs/spec-tb1b-supergpqa.md",
    # --- forward-looking plans: proposed work, not measured claims ---
    "docs/agentic-rebuild-scoping.md",
    "docs/reasoning-supercharge-plan.md",
    "docs/recursive-rag-plan.md",
    "docs/orchestration-contract.md",
    # --- working notes and external research: not our measurements ---
    "docs/improvement-loop-state.md",
    "docs/rag-corpus-notes.md",
    "docs/frontier-oss-model-research.md",
    # --- positioning and sources ---
    "docs/prior-art-and-positioning.md",      # no measured claims of our own
    "docs/demo-script.md",                    # checked separately, below
    "docs/figures/figure_claims_ledger.md",   # the ledger's own source of truth
}

#: Figures whose only correct source is the analyzer, checked live below rather
#: than trusted as transcribed. (value, dataset, point, field, scale)
#:
#: UPDATED 2026-08-03 when TB-1 arm C landed. GPQA's numbers moved because the
#: analysis set is the intersection of every registered arm, and arm C added a
#: third: S went from A n B to A n B n C, 265 items to 255. flagship_1x reads
#: 90.6% on the smaller set where it read 89.4% on the larger, and
#: universal_gate's p moved 0.50 -> 0.605 as its net went +1 -> +0.
#:
#: Nothing was re-measured and nothing was corrected. A paired statistic is
#: defined on its item set; changing the set changes the number, and the spec
#: requires all arms share one set so arm A's accuracy is a single number
#: across both comparisons. SuperGPQA is untouched because arm C is GPQA-only.
DERIVED_HEADLINES = [
    (90.6, "gpqa", "flagship_1x", "accuracy", 100),
    (79.2, "supergpqa", "flagship_1x", "accuracy", 100),
    (82.2, "supergpqa", "flagship_panel", "accuracy", 100),
    (0.0327, "supergpqa", "flagship_panel", "p_one_sided", 1),
    (0.605, "gpqa", "universal_gate", "p_one_sided", 1),
    # Arm C itself: the compute-matched control beats the lever it controls for.
    (92.9, "gpqa", "flagship_sc5", "accuracy", 100),
]


def _read(rel: str) -> str | None:
    p = PROJECT_ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


@pytest.mark.parametrize("forbidden,replacement,why", SUPERSEDED)
def test_superseded_figures_do_not_reappear(forbidden, replacement, why):
    offenders = []
    for rel in CLAIM_DOCS:
        text = _read(rel)
        if text and forbidden in text:
            offenders.append(rel)
    assert not offenders, (
        f"{offenders} still contain the superseded value {forbidden!r}. "
        f"Use {replacement!r} instead. Reason: {why}"
    )


@pytest.mark.parametrize("published,dataset,point,field,scale", DERIVED_HEADLINES)
def test_published_headlines_match_what_the_analyzer_computes(
        published, dataset, point, field, scale):
    """The forbidden-string checks catch a value that was replaced. They cannot
    catch a value that was WRONG FROM THE START, because nothing tells them what
    right looks like. This one asks the analyzer.

    It is the check that would have caught the F10 caption drift at its source
    instead of two documents downstream: the plot recomputes from data on every
    render, so any prose disagreeing with the analyzer is prose that has gone
    stale.
    """
    pytest.importorskip("pandas")
    from benchmark.analyze_cost_frontier import analyze

    pt = analyze(dataset)["points"].get(point)
    assert pt is not None, f"{point} absent from the {dataset} frontier"
    got = pt[field] * scale
    assert got == pytest.approx(published, abs=0.05), (
        f"docs publish {published} for {dataset}/{point}/{field} but the "
        f"analyzer computes {got:.4f}. The analyzer is the source."
    )


def test_every_reader_facing_claim_doc_is_actually_in_the_list():
    """A drift check is only as wide as its file list, and the first version of
    this one omitted docs/figures/README.md and make_figures_frontier.py --
    both of which were carrying the stale figures at that exact moment. This
    fails when a new top-level doc appears that nobody added here, so the
    omission is loud instead of silent."""
    known = set(CLAIM_DOCS) | FROZEN_OR_NON_CLAIM_DOCS
    found = {
        str(p.relative_to(PROJECT_ROOT)).replace("\\", "/")
        for p in (PROJECT_ROOT / "docs").glob("*.md")
    }
    missing = sorted(found - known)
    assert not missing, (
        f"{missing} are reader-facing docs not covered by the drift check. Add "
        f"them to CLAIM_DOCS, or to the exclusion set with a reason."
    )


def test_the_tb1_null_is_stated_consistently_wherever_stated():
    """Any doc that mentions the TB-1 result must give the same net and p.

    The null is the single most consequential number in the record -- it is
    what moved GPQA-Diamond into the dominated set -- so a doc quoting a
    DIFFERENT net or p for it is the highest-value inconsistency to catch.
    """
    bad = []
    for rel in CLAIM_DOCS:
        text = _read(rel)
        if not text:
            continue
        mentions_tb1 = "p=0.50" in text or "p = 0.50" in text
        if not mentions_tb1:
            continue
        # Wherever the null is stated, it is net +1. A different net beside a
        # p=0.50 for this comparison would be a transcription error.
        if "net +1" not in text and "+1, p" not in text and "net = +1" not in text:
            bad.append(rel)
    assert not bad, (
        f"{bad} state a p=0.50 result without the matching net +1 -- check "
        f"whether the TB-1 figures were transcribed correctly"
    )


#: Phrases pre-registered as prohibited in
#: docs/spec-trackb-flagship-comparison.md. `universal_gate` issues one
#: qwen3.7-max judge call per item (measured: judge calls/item = 1.00), so it is
#: a SCAFFOLDED flagship call, not a cheap panel that outperformed one.
BANNED_CLAIMS = [
    "cheap society beats the expensive model",
    "cheap seats beat a stronger model",
    "cheap seats beating a stronger model",
]

_RETRACTION_MARKERS = (
    "never be described", "must not be", "prohibited", "retract",
    "not that", "is not", "superseded", "corrected", "withdrawn",
)

#: A bare negation immediately before the quoted phrase. This is the commonest
#: retraction form in this repo -- FINDINGS.md:90 reads `a claim about when to
#: escalate, **NOT** "cheap seats beat a stronger model"` -- and the marker list
#: above misses it, which produced a false positive on a correctly-retracted
#: line the first time this test ran.
_NEGATIONS = ("not ", "not*", "never ", "rather than ")


def unretracted_occurrences(text: str, phrase: str) -> int:
    """Count occurrences of `phrase` that are NOT accompanied by a retraction.

    Extracted from the test body so the negation allowance can be guarded
    directly. A too-permissive allowance would silently make the whole check
    toothless -- it would pass on a doc that actively asserts the banned claim,
    and nothing would notice.
    """
    count, idx = 0, text.find(phrase)
    while idx != -1:
        window = text[max(0, idx - 400): idx + 400].lower()
        run_up = text[max(0, idx - 60): idx].lower()
        retracted = (any(m in window for m in _RETRACTION_MARKERS)
                     or any(n in run_up for n in _NEGATIONS))
        if not retracted:
            count += 1
        idx = text.find(phrase, idx + 1)
    return count


def test_the_retraction_allowance_still_catches_a_bare_assertion():
    """Guard on the guard. If `_NEGATIONS` or `_RETRACTION_MARKERS` ever grow
    permissive enough to excuse a plain assertion, this fails first."""
    phrase = "cheap seats beat a stronger model"
    assert unretracted_occurrences(
        f"Our headline result: {phrase}, at a fraction of the price.", phrase) == 1
    assert unretracted_occurrences(
        f'A claim about when to escalate, **NOT** "{phrase}".', phrase) == 0
    assert unretracted_occurrences(
        f"We retract the earlier framing that {phrase}.", phrase) == 0
    # Two bare assertions in one doc must both be counted, not collapsed.
    assert unretracted_occurrences(f"{phrase}. Again: {phrase}.", phrase) == 2


def test_no_claim_doc_asserts_cheap_seats_beat_a_flagship():
    offenders = []
    for rel in CLAIM_DOCS + ["docs/demo-script.md"]:
        text = _read(rel)
        if not text:
            continue
        for phrase in BANNED_CLAIMS:
            n = unretracted_occurrences(text, phrase)
            if n:
                offenders.append((rel, phrase, n))
    assert not offenders, (
        f"{offenders} assert cheap-seats-beat-flagship without a retraction. "
        f"universal_gate calls the flagship on every item."
    )


def test_cost_claims_in_dollars_state_their_unit():
    """The engine is ~11% cheaper in DOLLARS and 3.1x more expensive in TOKENS.
    A bare '11% lower cost' therefore tells a reader the opposite of what the
    billing unit now says."""
    offenders = []
    for rel in CLAIM_DOCS:
        text = _read(rel)
        if not text:
            continue
        idx = text.find("11% lower cost")
        while idx != -1:
            window = text[idx: idx + 300].lower()
            # Use vs mention. A doc explaining *why* the bare phrase is
            # misleading has to quote it, and that quotation is the fix, not
            # the defect. FINDINGS.md:158 does exactly this. Only a bare,
            # unquoted use is an offence.
            quoted = idx > 0 and text[idx - 1] in '"“‘`'
            if not quoted and "dollar" not in window:
                offenders.append(rel)
            idx = text.find("11% lower cost", idx + 1)
    assert not offenders, (
        f"{offenders} claim '11% lower cost' without naming the unit within "
        f"300 chars. In tokens the same engine costs 3.1x MORE."
    )


# ---------------------------------------------------------------------------
# A document must not contradict ITSELF
# ---------------------------------------------------------------------------

#: Quantities that have exactly one current value, and the values a document
#: must not mix. Each pair is (label, current, superseded) where BOTH are real
#: numbers this repo published for the same thing on different item sets.
SINGLE_VALUED = [
    ("GPQA flagship_1x accuracy", "90.6%", "89.4%"),
    ("GPQA universal_gate tok/item", "12,991", "13,175"),
    ("GPQA flagship_1x tok/item", "2,627", "2,792"),
]


@pytest.mark.parametrize("label,current,superseded", SINGLE_VALUED)
def test_no_document_states_two_values_for_one_quantity(label, current, superseded):
    """The gap every other check in this file structurally misses.

    The drift tests compare documents to EACH OTHER and to the analyzer. A
    document that contradicts ITSELF passes all of them, and on 2026-08-03
    FINDINGS-2026-08 did exactly that twice: it said "the flagship is already at
    89.4%" three lines under a table reading 90.6%, and section 6 repeated the
    old figure. Both were found by reading the file top to bottom, which is not
    a repeatable process.

    A document may still MENTION the superseded value -- explaining that a
    figure was replaced requires naming it -- so an occurrence is only an
    offence when the doc gives no indication it is talking about the older item
    set.
    """
    offenders = []
    for rel in CLAIM_DOCS:
        text = _read(rel)
        if not text or current not in text:
            continue  # doc does not discuss this quantity at all
        idx = text.find(superseded)
        while idx != -1:
            window = text[max(0, idx - 400): idx + 250].lower()
            explained = any(k in window for k in (
                "replace", "superseded", "earlier", "2-arm", "before arm c",
                "n=265", "recomputed", "previously", "retired", "corrected",
            ))
            if not explained:
                offenders.append((rel, text[max(0, idx - 60): idx + 40].replace("\n", " ")))
            idx = text.find(superseded, idx + 1)
    assert not offenders, (
        f"a document states BOTH {current!r} and {superseded!r} for "
        f"{label} with nothing marking the second as superseded:\n"
        + "\n".join(f"  {r}: ...{c}..." for r, c in offenders)
    )


def test_the_self_contradiction_check_is_not_vacuous():
    """If every CLAIM_DOC stopped mentioning the current values, the test above
    would pass by skipping everything."""
    for label, current, _ in SINGLE_VALUED:
        assert any(current in (_read(rel) or "") for rel in CLAIM_DOCS), (
            f"no claim doc mentions {current!r} ({label}), so its "
            f"self-contradiction check inspects nothing"
        )


def test_the_null_catalogue_count_matches_its_entries():
    """negative-results.md is described repo-wide as the largest artifact, and
    its own intro states how many nulls it holds. That count has now been wrong
    twice -- once when D5 was added and once when F3/F4 were -- because the
    catalogue and the sentence describing it live 700 lines apart.

    Counted from the A1..F4 headings, never incremented by hand.
    """
    text = _read("docs/negative-results.md")
    assert text, "the catalogue is missing"
    import re
    n = len(re.findall(r"^\*\*([A-F]\d+)\.", text, re.M))
    assert n >= 20, f"only {n} catalogue entries parsed -- the heading format changed"

    words = {22: "twenty-two", 23: "twenty-three", 24: "twenty-four",
             25: "twenty-five", 26: "twenty-six", 27: "twenty-seven"}
    assert n in words, f"extend the word map for {n} entries"

    low = text.lower()
    assert f"{words[n]} distinct measured nulls" in low, (
        f"the catalogue holds {n} entries but its intro does not say "
        f"'{words[n]} distinct measured nulls'"
    )
    for k, w in words.items():
        if k != n:
            assert f"{w} distinct measured nulls" not in low, (
                f"catalogue intro says '{w}' but there are {n} entries"
            )

    readme = _read("README.md") or ""
    assert f"{n} measured nulls" in readme, (
        f"README should cite {n} measured nulls to match the catalogue"
    )
