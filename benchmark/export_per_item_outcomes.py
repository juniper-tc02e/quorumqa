"""Publish per-item OUTCOMES without publishing the benchmark.

WHY THIS EXISTS. Two problems with one shape, both raised by an external review
on 2026-08-03:

  REPRODUCIBILITY. Every raw run lives in `benchmark/results/*.jsonl`, all of
  which `.gitignore` excludes -- 107 files, ~36 MiB. So a fresh clone runs 2 of
  15 analyses and the README's "every input is a committed file" was not true of
  most of them. The claims ledger checks that published prose matches published
  prose; it never recomputes anything from raw outcomes.

  BENCHMARK INTEGRITY. Those same files carry full GPQA question text, choices
  and correct letters. GPQA asks users not to reveal examples online, precisely
  so models are not trained on them. Committing the raw files to fix
  reproducibility would make the contamination problem worse.

Both are solved by publishing the DERIVED table rather than the source: for each
item, what happened -- not what was asked.

WHAT IS EXPORTED, and nothing else:

    question_id      the dataset's own id, already public in the dataset index
    seed, arm        which run this row belongs to
    completed        did the arm return a parseable answer at all. A row with
                     completed=0 is a DROP, reconstructed by comparison with
                     sibling arms at the same seed -- the runner writes only
                     survivors, so drops have no line of their own
    correct          was it right
    escalated        did the cascade fire
    unanimous        did the cheap panel agree
    tokens           input+output for this item
    n_calls          how many model calls it took

WHAT IS NOT EXPORTED, deliberately:

    question text, choices, correct_letter, solver reasoning, skeptic rebuttals,
    verifier findings, judge verdicts

A question_id alone reveals nothing to a model that does not already have the
dataset, and reveals nothing NEW to one that does. Correctness is a property of
our run, not of the benchmark. Every paired statistic this repo publishes --
McNemar b/c/net/p, drop rates, the dropout sensitivity table -- is computable
from these columns alone.

    python -m benchmark.export_per_item_outcomes --write

Offline. Reads local runs, writes one CSV plus a checksum manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
OUT_CSV = RESULTS / "per_item_outcomes.csv"
OUT_MANIFEST = RESULTS / "per_item_outcomes.manifest.json"

FIELDS = [
    "arm", "dataset", "seed", "question_id",
    "completed", "correct", "escalated", "unanimous",
    "tokens", "n_calls",
]

#: Filename -> (arm label, dataset). Anything unmatched is exported under its
#: own stem, so a new run is never silently dropped from the export.
_SEED_RE = re.compile(r"seed(\d+)")


def _tokens(calls) -> int:
    return sum((c.get("input_tokens") or 0) + (c.get("output_tokens") or 0)
               for c in (calls or []))


def _rows_from(path: Path):
    stem = path.stem
    m = _SEED_RE.search(stem)
    seed = int(m.group(1)) if m else -1
    dataset = ("supergpqa" if "supergpqa" in stem else
               "gpqa" if "gpqa" in stem else
               "lexam" if "lexam" in stem else
               "mmlu_pro" if "mmlu_pro" in stem else
               "medqa" if "medqa" in stem else
               "aime" if "aime" in stem else
               "math" if "math" in stem else "unknown")
    arm = _SEED_RE.sub("", stem).rstrip("_")

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rec = row.get("engine") or row.get("baseline")
            if not rec:
                continue
            item = rec.get("item") or {}
            qid = item.get("question_id")
            if not qid:
                continue

            seats = row.get("seat_answers") or rec.get("solver_answers") or []
            letters = [str(s.get("letter") or "").strip().upper()
                       for s in seats if s.get("letter")]
            final = rec.get("final_letter")
            gold = item.get("correct_letter")
            correct = rec.get("correct")
            if correct is None:
                correct = (final == gold) if (final and gold) else None

            yield {
                "arm": arm,
                "dataset": dataset,
                "seed": seed,
                "question_id": str(qid),
                # "completed" is the column the whole dropout sensitivity
                # analysis turns on: an arm that returned nothing is a FAILURE
                # in deployment, not a missing observation.
                "completed": int(bool(final) or correct is not None),
                "correct": "" if correct is None else int(bool(correct)),
                "escalated": "" if rec.get("escalated") is None else int(bool(rec.get("escalated"))),
                "unanimous": "" if not letters else int(len(set(letters)) == 1),
                "tokens": _tokens(rec.get("calls")),
                "n_calls": len(rec.get("calls") or []),
            }


def build() -> tuple[list[dict], dict]:
    rows: list[dict] = []
    manifest: dict = {"source_files": {}}
    for path in sorted(RESULTS.glob("*.jsonl")):
        before = len(rows)
        rows.extend(_rows_from(path))
        n = len(rows) - before
        if n:
            manifest["source_files"][path.name] = {
                "rows": n,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
    rows.extend(_absent_rows(rows))
    return rows, manifest


def _absent_rows(rows: list[dict]) -> list[dict]:
    """Emit an explicit completed=0 row for every DROP.

    A dropped item produces no line in the .jsonl at all -- the runner writes
    only survivors -- so a `completed` flag derived from existing rows can never
    be 0, and the first version of this export duly reported 0 incomplete rows
    across 7,318 rows while the repo elsewhere documents ~5 drops per seed.
    That is the survivorship trap this project has hit before, reappearing in
    the artifact built to expose it.

    A drop is only visible by comparison: an item that a SIBLING arm answered at
    the same (dataset, seed) and this arm did not. That is exactly the
    reconstruction `analyze_dropout_sensitivity` performs, made explicit here so
    the CSV is self-sufficient and a reader does not have to know the trick.

    Items no arm at that seed ever reached remain invisible -- nothing in the
    logs can distinguish them from items never sampled. Closing that needs an
    intended-ID manifest written by the runner BEFORE it starts.
    """
    by_seed: dict[tuple, set] = {}
    by_arm: dict[tuple, set] = {}
    for r in rows:
        key = (r["dataset"], r["seed"])
        by_seed.setdefault(key, set()).add(r["question_id"])
        by_arm.setdefault((r["arm"], r["dataset"], r["seed"]), set()).add(r["question_id"])

    out: list[dict] = []
    for (arm, dataset, seed), answered in by_arm.items():
        if seed == -1:
            continue  # no seed parsed: cannot establish a sibling set
        missing = by_seed[(dataset, seed)] - answered
        for qid in sorted(missing):
            out.append({
                "arm": arm, "dataset": dataset, "seed": seed, "question_id": qid,
                "completed": 0, "correct": 0,   # a non-answer is WRONG, not missing
                "escalated": "", "unanimous": "", "tokens": 0, "n_calls": 0,
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="write the CSV + manifest")
    a = ap.parse_args()

    rows, manifest = build()
    if not rows:
        print("No local .jsonl runs found -- nothing to export. This is expected "
              "on a clone that has not run any benchmarks.")
        return 0

    arms = {r["arm"] for r in rows}
    qids = {(r["dataset"], r["question_id"]) for r in rows}
    incomplete = sum(1 for r in rows if not r["completed"])

    manifest.update({
        "generated": "2026-08-03",
        "regenerate": "python -m benchmark.export_per_item_outcomes --write",
        "rows": len(rows),
        "arms": len(arms),
        "unique_questions": len(qids),
        "incomplete_rows": incomplete,
        "what_this_is": (
            "Per-item OUTCOMES only. No question text, no choices, no correct "
            "letter, no model reasoning. Sufficient to recompute every paired "
            "statistic this repo publishes; insufficient to reconstruct the "
            "benchmark."
        ),
        "why_not_the_raw_runs": (
            "The raw .jsonl files carry full GPQA question text and answer keys. "
            "GPQA asks that examples not be revealed online, to avoid training "
            "contamination. Committing them to fix reproducibility would trade "
            "one problem for a worse one."
        ),
    })

    print(f"{len(rows):,} rows | {len(arms)} arms | {len(qids):,} unique "
          f"(dataset, question_id) | {incomplete:,} incomplete")
    if not a.write:
        print("\n(dry run -- pass --write)")
        return 0

    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    manifest["csv_sha256"] = hashlib.sha256(OUT_CSV.read_bytes()).hexdigest()
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {OUT_CSV.relative_to(RESULTS.parent.parent)} "
          f"({OUT_CSV.stat().st_size/1024:.0f} KiB)")
    print(f"wrote {OUT_MANIFEST.relative_to(RESULTS.parent.parent)} "
          f"({len(manifest['source_files'])} source checksums)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
