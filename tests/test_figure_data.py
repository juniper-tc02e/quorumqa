"""Offline tests for benchmark/figure_data.py -- the figure-set provenance
firewall. No live API calls, no network: every test reads committed files
already in the repo (figure_claims_ledger.csv/.md, f2_compute_frontier.csv,
f5_difficulty_map.csv, moo_calibration_table.csv,
family_floor_analysis_data.json, agent_cost_calibration.csv) or constructs
small synthetic frames in-memory.

The load-bearing test is `test_verify_ledger_passes_against_real_docs`: it
runs the same check `python -m benchmark.figure_data --check` runs, against
the real *_findings.md files, so a future transcription typo in the ledger
CSV (a flipped sign, a copy-pasted wrong seed's number) fails this suite
rather than silently shipping a wrong figure.
"""

from __future__ import annotations

import pandas as pd
import pytest

from benchmark.figure_data import (
    CONTAMINATION_FOOTNOTES,
    EXCLUDED_BENCHMARKS,
    LedgerVerificationError,
    LocalFrame,
    MCNEMAR_MIN_NET,
    NOISE_FLOOR_PP,
    PairedFrame,
    PooledFrame,
    SmallNPairedFrame,
    load_agent_eras,
    load_frontier,
    load_ledger,
    load_moo_small_n,
    load_subject_deltas,
    verify_ledger,
)

ALLOWED_BUILD_STAGES = {"v1", "v2", "reference"}
ALLOWED_VERDICTS = {"validated", "screen", "negative", "inert", "invalidated"}
ALLOWED_CONTAMINATED = {"TRUE", "FALSE"}


# ---------------------------------------------------------------------------
# Ledger loads and is well-formed
# ---------------------------------------------------------------------------


def test_load_ledger_returns_paired_frame_nonempty():
    frame = load_ledger()
    assert isinstance(frame, PairedFrame)
    assert frame.tier == "A"
    assert frame.provenance_tag == "[PAIRED]"
    assert len(frame.data) > 0
    assert all(p.exists() for p in frame.source_paths)


def test_ledger_has_expected_columns():
    df = load_ledger().data
    expected = {
        "benchmark_label", "config", "build_stage", "comparator",
        "n_common_items", "seeds", "per_seed_delta_pp", "mean_delta_pp",
        "absolute_accuracy_pct", "net_discordant_items", "mcnemar_p",
        "verdict", "contaminated", "contamination_note",
        "unanimous_wrong_rate_pct", "escalation_rate_pct",
        "mean_tokens_per_q", "source_doc", "source_heading",
    }
    assert expected <= set(df.columns)


def test_ledger_build_stage_values_are_in_allowed_set():
    df = load_ledger().data
    values = set(df["build_stage"]) - {""}
    assert values <= ALLOWED_BUILD_STAGES, f"unexpected build_stage values: {values - ALLOWED_BUILD_STAGES}"


def test_ledger_verdict_values_are_in_allowed_set():
    df = load_ledger().data
    # verdict is legitimately blank for `reference` rows (a solo baseline
    # is not itself a "lever claim" to verdict) -- only non-empty values
    # are constrained to the controlled vocabulary.
    values = set(df["verdict"]) - {""}
    assert values <= ALLOWED_VERDICTS, f"unexpected verdict values: {values - ALLOWED_VERDICTS}"


def test_ledger_contaminated_values_are_in_allowed_set():
    df = load_ledger().data
    values = set(df["contaminated"]) - {""}
    assert values <= ALLOWED_CONTAMINATED, f"unexpected contaminated values: {values - ALLOWED_CONTAMINATED}"


# ---------------------------------------------------------------------------
# AIME exclusion
# ---------------------------------------------------------------------------


def test_no_aime_rows_in_ledger():
    df = load_ledger().data
    for label in df["benchmark_label"]:
        for excluded in EXCLUDED_BENCHMARKS:
            assert excluded not in str(label).upper(), (
                f"found an excluded-benchmark row: benchmark_label={label!r} "
                f"matches excluded token {excluded!r}"
            )


def test_excluded_benchmarks_contains_aime():
    # Guards against EXCLUDED_BENCHMARKS silently losing its one entry.
    assert "AIME" in EXCLUDED_BENCHMARKS


# ---------------------------------------------------------------------------
# Contaminated rows carry a non-empty contamination_note
# ---------------------------------------------------------------------------


def test_contaminated_rows_have_nonempty_contamination_note():
    df = load_ledger().data
    contaminated_rows = df[df["contaminated"] == "TRUE"]
    assert len(contaminated_rows) > 0, "expected at least one contaminated row (qwen38_judge / qwen3.8_solo / qwen38_panel)"
    for row in contaminated_rows.itertuples(index=False):
        note = getattr(row, "contamination_note", "")
        assert note.strip() != "", f"contaminated row {row.benchmark_label}/{row.config} has an empty contamination_note"


def test_noncontaminated_rows_have_empty_contamination_note():
    df = load_ledger().data
    clean_rows = df[df["contaminated"] == "FALSE"]
    nonempty = clean_rows[clean_rows["contamination_note"].str.strip() != ""]
    assert nonempty.empty, (
        f"non-contaminated rows should not carry a contamination_note: "
        f"{nonempty[['benchmark_label', 'config']].to_dict('records')}"
    )


def test_contamination_footnotes_cover_every_contaminated_config():
    df = load_ledger().data
    contaminated_configs = set(df[df["contaminated"] == "TRUE"]["config"])
    assert contaminated_configs, "expected at least one contaminated config"
    assert contaminated_configs <= set(CONTAMINATION_FOOTNOTES.keys()), (
        f"CONTAMINATION_FOOTNOTES is missing an entry for: "
        f"{contaminated_configs - set(CONTAMINATION_FOOTNOTES.keys())}"
    )
    for text in CONTAMINATION_FOOTNOTES.values():
        assert isinstance(text, str) and text.strip()


# ---------------------------------------------------------------------------
# verify_ledger() passes against the real docs
# ---------------------------------------------------------------------------


def test_verify_ledger_passes_against_real_docs():
    """The load-bearing test: runs the real grep-verification pass against
    the actual committed *_findings.md / docs/negative-results.md files.
    A future edit that flips a sign, swaps a seed's number, or points a row
    at the wrong source_doc must fail this test."""
    verify_ledger()  # raises LedgerVerificationError on any failure


def test_verify_ledger_fails_on_a_fabricated_number(tmp_path, monkeypatch):
    """Sanity-checks that verify_ledger() actually has teeth: point a fake
    ledger row's source_doc at a doc that does NOT contain the claimed
    number, and confirm it fails loudly rather than passing."""
    import benchmark.figure_data as fd

    fake_doc = tmp_path / "fake_findings.md"
    fake_doc.write_text("Nothing numeric here at all, just prose.", encoding="utf-8")

    fake_df = pd.DataFrame([
        {
            "benchmark_label": "GPQA-Diamond", "config": "shipped_engine",
            "build_stage": "v1", "comparator": "flagship_baseline",
            "n_common_items": "90", "seeds": "42", "per_seed_delta_pp": "",
            "mean_delta_pp": "+99.9", "absolute_accuracy_pct": "78.9",
            "net_discordant_items": "", "mcnemar_p": "", "verdict": "negative",
            "contaminated": "FALSE", "contamination_note": "",
            "unanimous_wrong_rate_pct": "", "escalation_rate_pct": "",
            "mean_tokens_per_q": "",
            "source_doc": str(fake_doc),  # absolute path -- resolves as-is
            "source_heading": "fabricated",
        }
    ])
    fake_ledger_csv = tmp_path / "fake_ledger.csv"
    fake_df.to_csv(fake_ledger_csv, index=False)

    def fake_load_ledger():
        return fd.PairedFrame(
            data=pd.read_csv(fake_ledger_csv, dtype=str, keep_default_na=False),
            tier="A", source_paths=[fake_ledger_csv], caveat="synthetic",
        )

    monkeypatch.setattr(fd, "load_ledger", fake_load_ledger)

    with pytest.raises(LedgerVerificationError, match=r"\+99\.9"):
        verify_ledger()


# ---------------------------------------------------------------------------
# Typed frames carry the right tier/tag, and type separation holds
# ---------------------------------------------------------------------------


def test_load_frontier_returns_pooled_frame_with_pooled_tag():
    frame = load_frontier()
    assert isinstance(frame, PooledFrame)
    assert frame.tier == "B"
    assert frame.provenance_tag == "[POOLED-MARGINAL]"
    assert len(frame.data) > 0


def test_load_moo_small_n_returns_smalln_frame():
    frame = load_moo_small_n()
    assert isinstance(frame, SmallNPairedFrame)
    assert frame.tier == "C"
    assert frame.provenance_tag == "[PAIRED-SMALL-N]"
    assert len(frame.data) > 0
    assert "source_file" in frame.data.columns


def test_load_subject_deltas_returns_smalln_frame():
    frame = load_subject_deltas()
    assert isinstance(frame, SmallNPairedFrame)
    assert frame.tier == "C"
    assert len(frame.data) > 0
    assert "benchmark" in frame.data.columns


def test_load_agent_eras_returns_paired_frame_with_hardening_era_column():
    frame = load_agent_eras()
    assert isinstance(frame, PairedFrame)
    assert frame.tier == "A"
    assert "hardening_era" in frame.data.columns


def test_pooled_frame_is_not_a_paired_frame():
    """The type separation IS the trap-prevention: a PooledFrame must not
    be usable anywhere a PairedFrame is expected, and vice versa. They
    intentionally do not share a common data-bearing base class."""
    pooled = load_frontier()
    paired = load_ledger()
    assert not isinstance(pooled, PairedFrame)
    assert not isinstance(paired, PooledFrame)
    assert type(pooled) is not type(paired)
    # Nor should PairedFrame/PooledFrame be subclasses of one another.
    assert not issubclass(PooledFrame, PairedFrame)
    assert not issubclass(PairedFrame, PooledFrame)


def test_smalln_frame_is_not_a_paired_or_pooled_frame():
    small_n = load_moo_small_n()
    assert not isinstance(small_n, PairedFrame)
    assert not isinstance(small_n, PooledFrame)


def test_all_frame_types_are_frozen_dataclasses():
    frame = load_ledger()
    with pytest.raises(Exception):
        frame.tier = "Z"  # frozen dataclass must reject mutation


def test_local_frame_exists_for_interface_completeness():
    # No committed loader instantiates a LocalFrame (every figure-relevant
    # number already has a Tier A/B/C home) -- but the type must exist and
    # be constructible so a project-local script can build one directly.
    frame = LocalFrame(
        data=pd.DataFrame({"x": [1, 2]}),
        tier="D",
        source_paths=[],
        caveat="local only, not reproducible from a fresh clone",
    )
    assert frame.provenance_tag == "[LOCAL-ONLY]"
    assert frame.tier == "D"
    assert not isinstance(frame, (PairedFrame, PooledFrame, SmallNPairedFrame))


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_shared_visual_convention_constants():
    assert NOISE_FLOOR_PP == 2.5
    assert MCNEMAR_MIN_NET == 5
    assert isinstance(CONTAMINATION_FOOTNOTES, dict)
    assert len(CONTAMINATION_FOOTNOTES) >= 3


# ---------------------------------------------------------------------------
# USD guard fires on a synthetic cost_usd frame
# ---------------------------------------------------------------------------


def test_verify_ledger_usd_guard_fires_on_synthetic_cost_column(monkeypatch):
    """verify_ledger() asserts no loaded frame carries a usd/cost/dollar
    column. Monkeypatch load_frontier() to return an otherwise-valid
    PooledFrame with an injected `cost_usd` column and confirm the guard
    fires."""
    import benchmark.figure_data as fd

    real_frontier = fd.load_frontier()
    tainted_df = real_frontier.data.copy()
    tainted_df["cost_usd"] = 0.0
    tainted_frame = fd.PooledFrame(
        data=tainted_df,
        tier="B",
        source_paths=real_frontier.source_paths,
        caveat=real_frontier.caveat,
    )

    monkeypatch.setattr(fd, "load_frontier", lambda: tainted_frame)

    with pytest.raises(LedgerVerificationError, match=r"(?i)usd"):
        verify_ledger()


def test_usd_guard_pattern_matches_cost_and_dollar_variants():
    import re

    from benchmark.figure_data import _COST_PATTERN

    for name in ["cost_usd", "total_cost", "usd_amount", "dollar_cost", "COST"]:
        assert _COST_PATTERN.search(name), f"expected {name!r} to match the USD guard pattern"
    for name in ["total_tokens", "accuracy", "n_common_items"]:
        assert not _COST_PATTERN.search(name), f"did not expect {name!r} to match the USD guard pattern"
