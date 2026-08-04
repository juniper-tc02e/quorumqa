"""The published per-item table must be sufficient, and must leak nothing.

WHY. An external review on 2026-08-03 made two findings that share one fix:

  a fresh clone reproduced 2 of 15 analyses, because every raw run is
  gitignored -- so the README's "every input is a committed file" was untrue of
  most of them;

  those same raw runs carry full GPQA question text, choices and answer keys,
  and GPQA asks that examples not be revealed online. Committing them to fix
  reproducibility would trade one problem for a worse one.

Publishing the derived OUTCOMES rather than the source solves both. These tests
hold that artifact to the two properties it exists for: it must contain enough
to recompute the published statistics, and nothing that reconstructs the
benchmark.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "benchmark" / "results" / "per_item_outcomes.csv"
MANIFEST = PROJECT_ROOT / "benchmark" / "results" / "per_item_outcomes.manifest.json"


@pytest.fixture(scope="module")
def rows():
    if not CSV_PATH.exists():
        pytest.skip("per_item_outcomes.csv not generated yet")
    with CSV_PATH.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_the_table_is_committed_not_gitignored():
    """The whole point is that a fresh clone gets this. If .gitignore ever
    swallows it, reproducibility silently returns to 2/15."""
    import subprocess
    r = subprocess.run(["git", "check-ignore", str(CSV_PATH)],
                       cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert r.returncode != 0, "per_item_outcomes.csv is gitignored"


def test_no_benchmark_content_leaks(rows):
    """The contamination guard. A question_id is public in the dataset index;
    question TEXT and answer keys are what GPQA asks not to be revealed."""
    forbidden_cols = {"question", "choices", "correct_letter", "reasoning",
                      "verdict", "rebuttal", "findings", "answer"}
    cols = set(rows[0].keys())
    assert not (cols & forbidden_cols), f"leaking columns: {cols & forbidden_cols}"

    # A question or a rationale is long; an id, a flag and a token count are not.
    longest = max(len(v) for r in rows for v in r.values())
    assert longest < 80, (
        f"longest cell is {longest} chars -- question text or model prose has "
        f"probably leaked into the export"
    )


def test_drops_are_represented_explicitly(rows):
    """The survivorship trap, which this artifact walked into on its first run.

    The runner writes only survivors, so a dropped item has NO line in the
    source .jsonl. A `completed` flag derived from existing rows can therefore
    never be 0 -- and the first version of this export duly reported 0
    incomplete rows across 7,318, while the repo documents ~5 drops per seed.
    Drops are reconstructed by comparison with sibling arms at the same seed.
    """
    incomplete = [r for r in rows if r["completed"] == "0"]
    assert incomplete, (
        "no completed=0 rows -- drops are invisible again, which is exactly the "
        "bias the dropout sensitivity analysis exists to measure"
    )
    for r in incomplete:
        assert r["correct"] == "0", "a non-answer must count WRONG, never missing"
        assert r["tokens"] == "0"


def test_the_table_reproduces_the_published_tb1_result(rows):
    """Sufficiency, checked against the numbers rather than asserted.

    If this table cannot rebuild TB-1's headline from scratch, publishing it
    does not restore reproducibility -- it just adds a file.
    """
    from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided as mc

    A, C = "lever_universal_gate_gpqa", "TB1_flagship_sc5_gpqa"
    present = {r["arm"] for r in rows}
    if not {A, C} <= present:
        pytest.skip("TB-1 arms not in this export")

    def outcomes(arm, seed):
        return {r["question_id"]: r["correct"] == "1" for r in rows
                if r["arm"] == arm and r["seed"] == str(seed) and r["completed"] == "1"}

    b = c = n = 0
    for s in (1001, 2311, 3407):
        a_out, c_out = outcomes(A, s), outcomes(C, s)
        shared = set(a_out) & set(c_out)
        b += sum(1 for q in shared if a_out[q] and not c_out[q])
        c += sum(1 for q in shared if c_out[q] and not a_out[q])
        n += len(shared)

    assert (b, c, n) == (3, 9, 256), f"got b={b} c={c} n={n}, published 3/9/256"
    assert mc(b, c) == pytest.approx(0.9807, abs=1e-3)


def test_the_manifest_checksums_its_sources(rows):
    """So a reader can tell whether the table was regenerated from the same
    runs, rather than trusting that it was."""
    if not MANIFEST.exists():
        pytest.skip("manifest not generated")
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert m["source_files"], "no source files recorded"
    for name, meta in m["source_files"].items():
        assert len(meta["sha256"]) == 64, f"{name} has no usable checksum"
    assert len(m["csv_sha256"]) == 64
    assert m["rows"] == len(rows)
    assert "why_not_the_raw_runs" in m, (
        "the manifest must say why the raw runs are withheld, or the omission "
        "reads as an oversight rather than a decision"
    )
