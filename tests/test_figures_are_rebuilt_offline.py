"""The committed figures must be rebuilt after their source data changes.

WHY THIS EXISTS. On 2026-08-03, sweeping for stale copies of a superseded
number turned up one inside a *rendered figure*. The 4.5x -> 4.7x correction
had been applied to the source constant days earlier, the test suite passed,
and the commit went out -- but `make_figures_frontier` was never re-run, so
`docs/figures/f12_kill_list.png` kept showing 4.5x to every reader of the
figures README. The fix was real and the artifact was stale, and nothing
connected the two.

This is a different failure from the one
tests/test_headline_consistency_offline.py guards. That one compares documents
to each other and to the analyzer. This one asks whether the committed
BYPRODUCTS of the figure build still match what the build would produce now.

WHY THE CSVs AND NOT THE PNGs. Every figure writes a companion CSV of exactly
the rows it plotted. That CSV is deterministic. The PNG and SVG are not: they
carry a render date and a commit hash in a provenance comment, and matplotlib's
font subsetting emits glyph definitions in a varying order, so three of the
four figures showed a diff on rebuild with no content change at all. Comparing
images would mean a test that fails on every rebuild -- noise that trains you
to ignore it. The CSV carries the numbers, and the numbers are what go stale.

Offline: no API calls, no rendering.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pandas")
import pandas as pd  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT_ROOT / "benchmark" / "results"


def _committed(name: str) -> pd.DataFrame:
    p = RESULTS / f"figure_{name}.csv"
    if not p.exists():
        pytest.skip(f"{p.name} not committed")
    return pd.read_csv(p)


def test_the_f12_kill_list_csv_carries_no_superseded_multiple():
    """The specific row that was stale, pinned by value.

    F12 is the kill list -- the figure a sceptical reader is most likely to
    zoom into -- and its TB-1 row states the token multiple. 4.5x came from
    seed 1001 alone (13,541/3,022); the published paired figure is 4.7x
    (13,175/2,792, n=265).
    """
    df = _committed("f12_kill_list")
    blob = df.to_csv(index=False)
    assert "4.7×" in blob or "4.7x" in blob, (
        "the TB-1 row should state 4.7× the tokens"
    )
    assert "4.5×" not in blob and "4.5x" not in blob, (
        "the committed F12 data still carries the superseded 4.5× multiple. "
        "Re-run `python -m benchmark.make_figures_frontier` -- correcting the "
        "source constant does not rebuild the committed artifact."
    )


def test_committed_figure_csvs_agree_with_the_source_constants():
    """Recompute F12's table from the module constant and compare.

    F12 is built from a literal in make_figures_frontier rather than from a
    result file, which is exactly why it could drift: there is no data pipeline
    to notice. Rebuilding just this table is cheap and needs no rendering.
    """
    import benchmark.make_figures_frontier as m

    fresh = pd.DataFrame(
        m.F12_KILLS, columns=["mechanism", "test", "measured", "p_value", "source"]
    ).sort_values("p_value").reset_index(drop=True)

    committed = _committed("f12_kill_list")
    assert list(committed.columns) == list(fresh.columns)
    assert len(committed) == len(fresh), (
        f"F12 has {len(fresh)} kills in source but {len(committed)} committed -- "
        f"re-run `python -m benchmark.make_figures_frontier`"
    )
    for col in ("mechanism", "measured", "source"):
        mismatch = [
            (a, b) for a, b in zip(committed[col].tolist(), fresh[col].tolist())
            if a != b
        ]
        assert not mismatch, (
            f"column '{col}' differs between the committed F12 CSV and the "
            f"source constant: {mismatch[:3]}. Re-run the figure build."
        )


def test_the_kill_count_in_prose_matches_the_number_of_kills():
    """F12's title read "Ten mechanisms ... Ten nulls." over ELEVEN bars the
    moment TB-1B was added, and three documents said "all ten" alongside it.

    The title is now derived from len(F12_KILLS). Prose cannot be, so it is
    checked here instead: every doc that states the count must state the real
    one. This is the third instance of the same defect in this module's output
    (the F10 caption, the F12 title, and now the surrounding prose), which is
    why it gets a test rather than another careful edit.
    """
    import benchmark.make_figures_frontier as m

    n = len(m.F12_KILLS)
    words = {10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen"}
    assert n in words, f"extend the word map for {n} kills"
    correct, wrong = words[n], [w for k, w in words.items() if k != n]

    for rel in ["README.md", "docs/FINDINGS-2026-08.md", "docs/figures/README.md"]:
        p = PROJECT_ROOT / rel
        if not p.exists():
            continue
        low = p.read_text(encoding="utf-8").lower()
        if "mechanisms" not in low:
            continue
        for w in wrong:
            for phrase in (f"all {w}", f"{w} separate mechanisms",
                           f"{w} mechanisms", f"{w} controlled nulls"):
                assert phrase not in low, (
                    f"{rel} says {phrase!r} but F12_KILLS has {n} entries "
                    f"({correct}). Update the prose."
                )


@pytest.mark.parametrize("name", [
    "f10_paired_cost_frontier",
    "f11_cheap_worker_scaling",
    "f12_kill_list",
    "f13_two_comparators",
])
def test_no_figure_csv_carries_a_superseded_figure(name):
    """Belt-and-braces across the 2026-08 figure set.

    Values are checked as substrings of the whole CSV rather than per-column,
    because a superseded number is equally wrong in a label, a caption field or
    a measured cell.
    """
    blob = _committed(name).to_csv(index=False)
    for bad, why in [
        ("4.5×", "TB-1's token multiple is 4.7× on the paired n=265 set"),
        ("p=0.0195", "the SuperGPQA p-value is 0.0327 at 3 seeds"),
        ("0.0195", "the SuperGPQA p-value is 0.0327 at 3 seeds"),
        ("77.2", "the 3-seed SuperGPQA flagship accuracy is 79.2%"),
    ]:
        assert bad not in blob, f"{name} still carries {bad!r} -- {why}"
