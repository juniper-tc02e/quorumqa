"""Offline tests for src/quorumqa/engine/calibration.py -- the M1-corrected
router's calibration table (docs/mixture-of-orchestrations-plan.md section
5.1, "calibration memory... adopt first", in its simplest static form: a
table of measured (profile, bucket) -> {accuracy, mean_tokens,
escalation_rate} built from benchmark/results/moo_m1_eval.jsonl's own
already-recorded outcomes).

No live API calls, no dataset downloads: pure arithmetic over hand-built
fixture records + CSV round-tripping through tmp_path, per CLAUDE.md's
TDD-over-re-running-benchmarks rule.
"""

import csv

import pytest

from quorumqa.engine.calibration import (
    CalibrationEntry,
    build_calibration_table,
    cheapest_within_margin,
    load_calibration_table,
    write_calibration_csv,
)


def _rec(profile, bucket, correct, tokens, escalated=False):
    return {"profile": profile, "bucket": bucket, "correct": correct, "total_tokens": tokens, "escalated": escalated}


# ---------------------------------------------------------------------------
# build_calibration_table: groups by (profile, bucket), averages measured outcomes
# ---------------------------------------------------------------------------


def test_build_calibration_table_groups_and_averages():
    records = [
        _rec("flagship_panel", "supergpqa_hard_stem", True, 9000, escalated=False),
        _rec("flagship_panel", "supergpqa_hard_stem", True, 10000, escalated=True),
        _rec("flagship_panel", "supergpqa_hard_stem", False, 9500, escalated=False),
        _rec("single-call", "supergpqa_hard_stem", True, 4000, escalated=False),
    ]
    table = {(e.profile, e.bucket): e for e in build_calibration_table(records)}

    fp = table[("flagship_panel", "supergpqa_hard_stem")]
    assert fp.n == 3
    assert fp.accuracy == pytest.approx(2 / 3)
    assert fp.mean_tokens == pytest.approx((9000 + 10000 + 9500) / 3)
    assert fp.escalation_rate == pytest.approx(1 / 3)

    sc = table[("single-call", "supergpqa_hard_stem")]
    assert sc.n == 1
    assert sc.accuracy == 1.0
    assert sc.mean_tokens == 4000
    assert sc.escalation_rate == 0.0


def test_build_calibration_table_keeps_buckets_separate():
    records = [
        _rec("standard-tribunal", "medicine", True, 1000),
        _rec("standard-tribunal", "saturated_easy", False, 2000),
    ]
    table = {(e.profile, e.bucket): e for e in build_calibration_table(records)}
    assert set(table) == {("standard-tribunal", "medicine"), ("standard-tribunal", "saturated_easy")}
    assert table[("standard-tribunal", "medicine")].accuracy == 1.0
    assert table[("standard-tribunal", "saturated_easy")].accuracy == 0.0


# ---------------------------------------------------------------------------
# CSV round-trip
# ---------------------------------------------------------------------------


def test_write_and_load_calibration_csv_round_trips(tmp_path):
    records = [
        _rec("flagship_panel", "supergpqa_hard_stem", True, 9553, escalated=False),
        _rec("flagship_panel", "supergpqa_hard_stem", False, 9600, escalated=True),
        _rec("rag_thinking_gate", "supergpqa_hard_stem", False, 17719, escalated=True),
    ]
    entries = build_calibration_table(records)
    out_path = tmp_path / "calib.csv"
    write_calibration_csv(entries, out_path)

    loaded = load_calibration_table(out_path)
    assert ("flagship_panel", "supergpqa_hard_stem") in loaded
    assert ("rag_thinking_gate", "supergpqa_hard_stem") in loaded

    fp = loaded[("flagship_panel", "supergpqa_hard_stem")]
    assert fp.n == 2
    assert fp.accuracy == pytest.approx(0.5)
    assert fp.mean_tokens == pytest.approx((9553 + 9600) / 2)
    assert fp.escalation_rate == pytest.approx(0.5)
    assert isinstance(fp, CalibrationEntry)


def test_write_calibration_csv_has_stable_header(tmp_path):
    entries = build_calibration_table([_rec("single-call", "saturated_easy", True, 900)])
    out_path = tmp_path / "calib.csv"
    write_calibration_csv(entries, out_path)
    with out_path.open(encoding="utf-8", newline="") as f:
        header = next(csv.reader(f))
    assert header == ["profile", "bucket", "n", "accuracy", "mean_tokens", "escalation_rate"]


def test_load_calibration_table_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_calibration_table(tmp_path / "does_not_exist.csv")


# ---------------------------------------------------------------------------
# cheapest_within_margin: the router's cost-aware tie-break
# ---------------------------------------------------------------------------


def _entry(profile, bucket, n, accuracy, mean_tokens, escalation_rate=0.0):
    return CalibrationEntry(profile=profile, bucket=bucket, n=n, accuracy=accuracy, mean_tokens=mean_tokens, escalation_rate=escalation_rate)


def _table(*entries):
    return {(e.profile, e.bucket): e for e in entries}


def test_cheapest_within_margin_picks_clear_accuracy_winner():
    # flagship_panel is both more accurate AND cheaper -- the supergpqa_hard_stem
    # pattern moo_m1_findings.md diagnosed (escalation-heavy "cheap" stacks are
    # the expensive ones on hard STEM).
    table = _table(
        _entry("flagship_panel", "supergpqa_hard_stem", 26, 0.846, 9553),
        _entry("rag_thinking_gate", "supergpqa_hard_stem", 30, 0.733, 17719),
        _entry("single-call", "supergpqa_hard_stem", 29, 0.793, 4106),
    )
    picked = cheapest_within_margin(
        table, bucket="supergpqa_hard_stem",
        candidates=["flagship_panel", "rag_thinking_gate", "single-call"],
    )
    assert picked == "flagship_panel"


def test_cheapest_within_margin_picks_cheapest_among_ties():
    # Two candidates tie within 1pt accuracy -- pick the cheaper one by tokens.
    table = _table(
        _entry("standard-tribunal", "medicine", 30, 0.967, 1683),
        _entry("single-call", "medicine", 30, 0.967, 1072),
        _entry("flagship_panel", "medicine", 30, 0.967, 3367),
    )
    picked = cheapest_within_margin(
        table, bucket="medicine",
        candidates=["standard-tribunal", "single-call", "flagship_panel"],
    )
    assert picked == "single-call"


def test_cheapest_within_margin_respects_margin_width():
    table = _table(
        _entry("a", "bucketX", 20, 0.90, 100),
        _entry("b", "bucketX", 20, 0.895, 50),  # within 1pt (0.005 below) -> ties, cheaper
        _entry("c", "bucketX", 20, 0.85, 10),  # 5pts below -> excluded even though cheapest
    )
    picked = cheapest_within_margin(table, bucket="bucketX", candidates=["a", "b", "c"], margin=0.01)
    assert picked == "b"


def test_cheapest_within_margin_excludes_entries_below_min_n():
    table = _table(
        _entry("thin", "bucketY", 4, 1.0, 10),  # perfect accuracy but n too small to trust
        _entry("robust", "bucketY", 25, 0.80, 5000),
    )
    picked = cheapest_within_margin(table, bucket="bucketY", candidates=["thin", "robust"], min_n=10)
    assert picked == "robust"


def test_cheapest_within_margin_returns_none_when_no_candidate_has_enough_data():
    table = _table(_entry("thin", "bucketZ", 3, 1.0, 10))
    assert cheapest_within_margin(table, bucket="bucketZ", candidates=["thin"], min_n=10) is None


def test_cheapest_within_margin_returns_none_for_unknown_bucket():
    table = _table(_entry("flagship_panel", "supergpqa_hard_stem", 26, 0.846, 9553))
    assert cheapest_within_margin(table, bucket="not_a_real_bucket", candidates=["flagship_panel"]) is None


def test_cheapest_within_margin_ignores_candidates_missing_from_table():
    table = _table(_entry("flagship_panel", "supergpqa_hard_stem", 26, 0.846, 9553))
    picked = cheapest_within_margin(
        table, bucket="supergpqa_hard_stem", candidates=["flagship_panel", "made_up_profile"],
    )
    assert picked == "flagship_panel"


def test_cheapest_within_margin_ties_broken_by_profile_name_for_determinism():
    table = _table(
        _entry("zzz_profile", "bucketW", 20, 0.90, 100),
        _entry("aaa_profile", "bucketW", 20, 0.90, 100),
    )
    picked = cheapest_within_margin(table, bucket="bucketW", candidates=["zzz_profile", "aaa_profile"])
    assert picked == "aaa_profile"
