"""Offline tests for benchmark/reproduce_all.py.

The harness exists so a reader can check the repo's central claim -- every
published number recomputes -- with one command instead of seventeen pulled out
of seven documents.

The property that matters most is NOT that it reports OK here. It is that it
reports SKIP, loudly and with a reason, on a machine that does not hold the
gitignored raw runs. A reproduction harness that reports FAIL there says "the
repo does not reproduce" when the truth is "the data is not in the repo, by
design"; one that silently omits those analyses is worse still, because a short
all-green list reads as full verification. A fresh clone is this tool's
audience, so that path is what these tests pin.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import benchmark.reproduce_all as R


def test_every_analysis_declares_its_input_requirement():
    """A module missing from NEEDS_GLOB defaults to "" and is treated as
    runnable anywhere. That is the silent-FAIL path on a fresh clone, so an
    unlisted analysis must be a test failure rather than a surprise later."""
    declared = set(R.NEEDS_GLOB)
    listed = {mod for mod, _, _ in [*R.ANALYSES, R.LEDGER]}
    undeclared = listed - declared
    assert not undeclared, (
        f"{sorted(undeclared)} are in the run list but not in NEEDS_GLOB, so "
        f"they would report FAIL rather than SKIP on a clone without the raw "
        f"runs. Add a representative glob, or \"\" if the analysis reads only "
        f"committed CSV/JSON."
    )


def test_no_stale_entries_in_the_requirement_map():
    listed = {mod for mod, _, _ in [*R.ANALYSES, R.LEDGER]}
    stale = set(R.NEEDS_GLOB) - listed
    assert not stale, f"{sorted(stale)} are declared but never run"


def test_missing_inputs_are_skipped_not_failed(tmp_path, monkeypatch):
    """The behaviour on a fresh clone, which is where this harness is read."""
    monkeypatch.setattr(R, "RESULTS", tmp_path)
    status, note = R.run_one("benchmark.verify_universal_gate", [], quiet=True)
    assert status == "SKIP"
    assert "gitignored" in note
    assert "lever_universal_gate_gpqa_seed" in note, "name the file that is absent"


def test_analyses_reading_only_committed_data_still_run_on_a_fresh_clone(tmp_path, monkeypatch):
    """At least the ledger check must work with no raw runs present -- it is
    the one that verifies published numbers against their cited docs, and it is
    the whole reason a fresh clone can check anything at all."""
    monkeypatch.setattr(R, "RESULTS", tmp_path)
    assert R.NEEDS_GLOB["benchmark.figure_data"] == ""
    status, note = R.run_one("benchmark.figure_data", ["--check"], quiet=True)
    assert status == "OK", f"ledger check must run on a fresh clone: {note}"


def test_explicit_path_arguments_are_checked_too(tmp_path):
    """analyze_unanimous_stability takes its inputs as arguments rather than
    globbing, so the glob map cannot see them."""
    missing = R._missing_inputs(["--control", "benchmark/results/nope_missing.jsonl"])
    assert missing == ["benchmark/results/nope_missing.jsonl"]
    assert R._missing_inputs(["--out", "somewhere.md"]) == [], "only .jsonl inputs"


def test_the_ledger_check_runs_last():
    """It verifies published numbers against their cited docs, so its result is
    the summary line a reader actually cares about; burying it mid-list makes a
    scan of the tail misleading."""
    assert R.LEDGER[0] == "benchmark.figure_data"
    assert [*R.ANALYSES, R.LEDGER][-1] is R.LEDGER


def test_a_nonzero_exit_is_reported_as_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "RESULTS", tmp_path)
    monkeypatch.setitem(R.NEEDS_GLOB, "benchmark.reproduce_all", "")
    # --list exits 0; a bogus flag exits 2.
    status, note = R.run_one("benchmark.reproduce_all", ["--not-a-flag"], quiet=True)
    assert status == "FAIL"
    assert note


def test_the_module_never_makes_network_calls():
    """The headline promise on the harness is 'no API calls, no network'. Cheap
    to assert, and it is the claim a sceptical reader checks first."""
    src = Path(R.__file__).read_text(encoding="utf-8")
    for banned in ("requests", "httpx", "urllib.request", "openai", "QwenClient"):
        assert banned not in src, f"{banned} would break the no-network promise"
