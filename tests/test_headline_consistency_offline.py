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
