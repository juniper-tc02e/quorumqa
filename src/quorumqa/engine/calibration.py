"""The M1-corrected router's calibration table (docs/mixture-of-orchestrations-
plan.md section 5.1, "calibration memory... adopt first -- highest value,
lowest risk"), in its simplest form: a STATIC table of per-(profile, bucket)
outcome statistics -- measured accuracy, measured mean tokens/question, and
measured escalation rate -- built once from benchmark/results/moo_m1_eval.jsonl's
already-recorded outcomes (benchmark/build_moo_calibration.py) and checked in
as benchmark/results/moo_calibration_table.csv.

This module is deliberately dependency-free with respect to the rest of the
engine (no import of quorumqa.engine.router, no import of the benchmark
harness) so it has no circular-import entanglement with router.py, which
imports THIS module to drive its cost-aware tie-break (see router.py's
_default_calibration_table / cheapest_within_margin usage). The bucket
classification that groups raw eval records into (profile, bucket) pairs is
the CALLER's job (benchmark/build_moo_calibration.py uses
quorumqa.engine.router._domain_bucket to do it) -- build_calibration_table
here only aggregates records that already carry a "bucket" key.

benchmark/results/moo_m1_corrected_findings.md documents the calibration
table this module produces and the router rules it feeds.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CSV_FIELDS: tuple[str, ...] = ("profile", "bucket", "n", "accuracy", "mean_tokens", "escalation_rate")

# The default location benchmark/build_moo_calibration.py writes to and
# router.py's _default_calibration_table() reads from -- a bare relative
# path, same convention as benchmark/run_moo_eval.py's DEFAULT_OUT (assumes
# cwd == repo root, the project's standing convention for every benchmark/
# results/ path).
DEFAULT_CALIBRATION_CSV = Path("benchmark/results/moo_calibration_table.csv")


@dataclass(frozen=True)
class CalibrationEntry:
    """One measured (profile, bucket) cell: plan section 5.1's "accuracy,
    escalation rate, ... cost tokens" outcome statistics, averaged over
    every moo_m1_eval.jsonl record recorded for that pair. `bucket` is
    whatever bucket vocabulary the caller grouped by -- see the module
    docstring; router.py uses its own _domain_bucket() bucket names
    (gpqa_hard_stem, supergpqa_hard_stem, ...), not the raw eval jsonl's
    coarser workload-bucket field."""

    profile: str
    bucket: str
    n: int
    accuracy: float
    mean_tokens: float
    escalation_rate: float


CalibrationTable = dict[tuple[str, str], CalibrationEntry]


def build_calibration_table(records: Iterable[dict]) -> list[CalibrationEntry]:
    """Groups `records` by (record["profile"], record["bucket"]) and
    averages record["correct"] (bool), record["total_tokens"] (int/float),
    and record["escalated"] (bool) into one CalibrationEntry per group --
    the calibration memory's simplest static form (plan section 5.1),
    literally the mean of every already-recorded outcome for that pair. No
    live calls; pure arithmetic over whatever records are passed in."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["profile"], r["bucket"])].append(r)

    entries = []
    for (profile, bucket), rs in groups.items():
        n = len(rs)
        entries.append(
            CalibrationEntry(
                profile=profile,
                bucket=bucket,
                n=n,
                accuracy=sum(1 for r in rs if r["correct"]) / n,
                mean_tokens=sum(r["total_tokens"] for r in rs) / n,
                escalation_rate=sum(1 for r in rs if r["escalated"]) / n,
            )
        )
    entries.sort(key=lambda e: (e.bucket, -e.accuracy, e.profile))
    return entries


def write_calibration_csv(entries: Iterable[CalibrationEntry], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_FIELDS)
        for e in entries:
            writer.writerow([e.profile, e.bucket, e.n, f"{e.accuracy:.6f}", f"{e.mean_tokens:.2f}", f"{e.escalation_rate:.6f}"])


def load_calibration_table(path: Path) -> CalibrationTable:
    """Raises FileNotFoundError if `path` does not exist -- callers that
    want a soft-fail default (router.py's _default_calibration_table)
    catch that explicitly rather than this module silently returning {}."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"calibration table not found at {path} -- run benchmark/build_moo_calibration.py first")
    table: CalibrationTable = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry = CalibrationEntry(
                profile=row["profile"],
                bucket=row["bucket"],
                n=int(row["n"]),
                accuracy=float(row["accuracy"]),
                mean_tokens=float(row["mean_tokens"]),
                escalation_rate=float(row["escalation_rate"]),
            )
            table[(entry.profile, entry.bucket)] = entry
    return table


def cheapest_within_margin(
    table: CalibrationTable,
    bucket: str,
    candidates: Iterable[str],
    margin: float = 0.01,
    min_n: int = 10,
) -> str | None:
    """The corrected router's cost-aware tie-break (moo_m1_corrected_
    findings.md item 2c): among `candidates` that have a calibration entry
    for `bucket` with at least `min_n` measured questions, keep whichever
    are within `margin` (accuracy fraction, default 1 percentage point) of
    the best measured accuracy among them, then return the cheapest of that
    tied set by measured mean_tokens (ties broken by profile name, for a
    deterministic result independent of dict/candidate ordering).

    Returns None if no candidate has an entry for `bucket` meeting min_n --
    callers MUST fall back to a hardcoded default in that case rather than
    routing off a thin/noisy sample (moo_m1_corrected_findings.md flags
    exactly this for gpqa_hard_stem, whose calibration n=4-5 per profile is
    too small to trust; supergpqa_hard_stem's n=26-30 clears the bar)."""
    rows = [
        table[(p, bucket)]
        for p in candidates
        if (p, bucket) in table and table[(p, bucket)].n >= min_n
    ]
    if not rows:
        return None
    best_acc = max(r.accuracy for r in rows)
    tied = [r for r in rows if best_acc - r.accuracy <= margin]
    tied.sort(key=lambda r: (r.mean_tokens, r.profile))
    return tied[0].profile
