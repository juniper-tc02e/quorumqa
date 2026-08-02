"""Every path cited as EVIDENCE must exist.

WHY. This repo's central claim about itself is that every number traces to a
committed artifact. A citation pointing at a file that is not there breaks that
claim more directly than a wrong number does -- a wrong number can be checked
and corrected, a missing source cannot be checked at all.

USE VS MENTION, again. A first pass over all 82 markdown files found 388
backticked repo-path citations, of which 15 did not resolve -- and every one of
those 15 turned out to be correct writing:

    external_comparability.md  "There is no `load_gsm8k_open.py` ..."
    hle_feasibility.md         "Not building `benchmark/load_hle.py` in this pass"
    capability-roadmap.md      "Build `benchmark/load_medxpertqa.py` mirroring ..."
    experiment-spec-book.md    a build list, i.e. files that do not exist yet

Naming a file in order to say it is absent, or to propose building it, is not a
citation. So the check reads the surrounding sentence and skips mentions. That
is the same use/mention distinction that produced two false positives in
test_headline_consistency_offline.py, arrived at independently here -- which is
itself the argument for handling it explicitly rather than per-case.

Offline. No API calls.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Backticked paths rooted at a real top-level package directory.
CITATION = re.compile(
    r"`((?:benchmark|docs|src|tests|deploy|dashboard|site_data)/"
    r"[A-Za-z0-9_./-]+\.(?:md|py|csv|json|jsonl|svg|png))`"
)

#: Phrases that mark the surrounding text as proposing or denying a file rather
#: than citing one. Matched against the ~200 characters before the path.
MENTION_MARKERS = (
    "there is no", "no ", "not building", "does not exist", "doesn't exist",
    "build ", "building ", "write ", "writing ", "would need", "needs a",
    "new loader", "must be built", "to be built", "never built", "missing",
    "mirroring", "following", "should be", "would be", "planned", "propose",
    "if built", "once built", "until built", "not on the path",
)

#: Directories whose .md files are plans or spec books by nature -- their whole
#: job is to name artifacts that do not exist yet. Checked, but only for paths
#: that read as evidence.
SKIP_FILES = {
    "docs/experiment-spec-book.md",   # a build list end to end
}


def _iter_docs():
    for p in sorted(PROJECT_ROOT.rglob("*.md")):
        rel = str(p.relative_to(PROJECT_ROOT)).replace("\\", "/")
        if any(seg in rel for seg in (".venv/", ".claude/", "node_modules/")):
            continue
        yield rel, p


def _is_mention(text: str, at: int) -> bool:
    """True when the path is being proposed or denied rather than cited."""
    window = text[max(0, at - 200): at].lower()
    return any(m in window for m in MENTION_MARKERS)


def test_every_cited_repo_path_resolves():
    dangling: dict[str, set[str]] = {}
    checked = 0
    for rel, path in _iter_docs():
        if rel in SKIP_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in CITATION.finditer(text):
            target = m.group(1)
            checked += 1
            if (PROJECT_ROOT / target).exists():
                continue
            if _is_mention(text, m.start()):
                continue
            dangling.setdefault(target, set()).add(rel)

    assert checked > 200, (
        f"only {checked} citations found -- the regex probably stopped matching, "
        f"which would make this test pass by seeing nothing"
    )
    assert not dangling, (
        "cited as evidence but absent:\n" + "\n".join(
            f"  {t}  <- {sorted(s)}" for t, s in sorted(dangling.items())
        )
    )


def test_the_mention_detector_does_not_swallow_a_real_citation():
    """Guard on the guard. Too permissive and the whole check passes on a
    document citing files that were never written."""
    assert _is_mention("There is no `benchmark/load_x.py` here", 100)
    assert _is_mention("Build `benchmark/load_x.py` mirroring the others", 100)
    assert not _is_mention("Measured 2026-08-03. Source: `benchmark/x.md`", 100)
    assert not _is_mention("See the addendum in `benchmark/results/y.md`", 100)


@pytest.mark.parametrize("rel", [
    "benchmark/results/tb1b_supergpqa_result.md",
    "benchmark/results/tb1_flagship_comparison_result.md",
    "docs/FINDINGS-2026-08.md",
])
def test_the_load_bearing_result_docs_exist(rel):
    """These are named by figure footers, the claims ledger and the README. A
    figure whose footer cites a missing write-up is unfalsifiable."""
    assert (PROJECT_ROOT / rel).exists(), f"{rel} is cited across the repo"
