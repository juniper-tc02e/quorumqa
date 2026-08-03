"""The sensitivity analysis, and the corrections it forced.

WHY. An external review on 2026-08-03 pointed out that every paired figure in
this repo is a COMPLETE-CASE analysis -- an item counts only if both arms
answered -- while the repo's own verifiers print, on every seed, that drops are
504/timeout-correlated and land on long-generation items. Non-random
missingness plus complete-case analysis excuses an arm the items it failed to
finish.

Recomputed with a timeout counted as the failure it would be in deployment, two
headline results reverse. These tests pin the reversal so it cannot be quietly
un-published, and pin the two claims that had to be withdrawn.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmark.analyze_dropout_sensitivity import COMPARISONS, compare

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run(label_fragment):
    for label, xt, yt, seeds, intended in COMPARISONS:
        if label_fragment in label:
            return compare(xt, yt, seeds, intended)
    raise AssertionError(f"no comparison matching {label_fragment!r}")


def _have(label_fragment) -> bool:
    r = _run(label_fragment)
    return bool(r["complete_case"]["n"])


def test_tb1_arm_c_sign_flips_between_the_two_readings():
    """The correction itself. Complete case says the stack loses by 6; counting
    timeouts as failures says it wins by 1."""
    if not _have("stack vs SC@5"):
        pytest.skip("TB-1 raw runs are gitignored")
    r = _run("stack vs SC@5")
    assert r["complete_case"]["net"] == -6
    assert r["timeout_as_failure"]["net"] == +1
    assert r["complete_case"]["n"] < r["timeout_as_failure"]["n"], (
        "complete case must be the SMALLER set -- it drops unanswered items"
    )


def test_neither_direction_was_ever_significant_for_arm_c():
    """The second error: p=0.9807 tests whether the STACK is superior. It is
    not evidence that sampling is. The reverse test is 0.0730 complete-case and
    0.6682 under timeout-as-failure -- neither clears 0.05."""
    if not _have("stack vs SC@5"):
        pytest.skip("TB-1 raw runs are gitignored")
    r = _run("stack vs SC@5")
    cc, tf = r["complete_case"], r["timeout_as_failure"]
    assert cc["p_x_superior"] == pytest.approx(0.9807, abs=1e-3)
    assert cc["p_y_superior"] == pytest.approx(0.0730, abs=1e-3)
    for d in (cc, tf):
        assert min(d["p_x_superior"], d["p_y_superior"]) >= 0.05, (
            "if either direction ever clears 0.05, the withdrawn claim can be "
            "restated -- but only then"
        )


def test_the_supergpqa_win_also_reverses():
    """The project's ONLY advertised orchestration win. +7 (p=0.0327) complete
    case becomes -4 (p=0.85) when non-completions count as failures, because
    the candidate arm completed fewer items than the reference."""
    if not _have("SuperGPQA"):
        pytest.skip("SuperGPQA raw runs are gitignored")
    r = _run("SuperGPQA")
    assert r["complete_case"]["net"] == +7
    assert r["complete_case"]["p_x_superior"] == pytest.approx(0.0327, abs=1e-3)
    assert r["timeout_as_failure"]["net"] < 0, (
        "the reversal is the finding; if this ever stops flipping, the claim "
        "can be restated as robust"
    )


def test_pooled_gpqa_figures_report_their_unique_question_count():
    """GPQA has ~198 questions and three 90-item seeds, so pooled n overstates
    independent evidence. McNemar assumes independent pairs."""
    if not _have("stack vs SC@5"):
        pytest.skip("TB-1 raw runs are gitignored")
    cc = _run("stack vs SC@5")["complete_case"]
    assert cc["unique_questions"] < cc["n"], "seeds must overlap on GPQA"
    assert cc["unique_questions"] == 164
    assert cc["repeated_ids"] == 81


@pytest.mark.parametrize("doc", [
    "README.md",
    "docs/FINDINGS-2026-08.md",
    "benchmark/results/tb1_flagship_comparison_result.md",
])
def test_the_withdrawn_claims_are_not_restated_anywhere(doc):
    """Two sentences had to go: that sampling is measurably better, and that
    the drops could not reverse the result. Both were wrong."""
    text = (PROJECT_ROOT / doc).read_text(encoding="utf-8")
    banned = [
        "sampling is measurably better",
        "spend the tribunal's own budget on sampling and you do measurably better",
    ]
    for phrase in banned:
        assert phrase not in text, f"{doc} restates a withdrawn claim: {phrase!r}"

    # "could not reverse it" may still appear, but only inside its retraction.
    idx = text.find("could not reverse it")
    while idx != -1:
        window = text[idx: idx + 400].lower()
        assert "wrong" in window or "corrected" in window, (
            f"{doc} still asserts the drops could not reverse the result"
        )
        idx = text.find("could not reverse it", idx + 1)


def test_every_headline_comparison_is_covered():
    """A sensitivity table that silently omits a headline is worse than none."""
    labels = [c[0] for c in COMPARISONS]
    for needed in ("stack vs SC@5", "stack vs one flagship call", "SuperGPQA"):
        assert any(needed in l for l in labels), f"{needed} not in the sweep"
