"""Builds benchmark/results/moo_calibration_table.csv from the EXISTING M1
blended-workload eval data (benchmark/results/moo_m1_eval.jsonl) -- NO new
paid API calls. This is the calibration memory (docs/mixture-of-
orchestrations-plan.md section 5.1) in its simplest static form: for every
(profile, bucket) pair that appears in the eval, the measured mean accuracy,
mean tokens/question, and escalation rate over every recorded question --
literally averaging outcomes the M1 run already paid for and logged.

`bucket` here is the ROUTER's own bucket vocabulary (quorumqa.engine.router.
_domain_bucket's output: gpqa_organic_chem / gpqa_hard_stem /
supergpqa_hard_stem / medicine / saturated_easy / unknown), NOT the raw
eval jsonl's coarser workload-bucket field (gpqa_hard / supergpqa_hard /
medqa / saturated_easy_mmlu). Router bucket is the finer, decision-relevant
granularity -- e.g. it separates gpqa_hard's Organic-Chemistry rows (routed
to stem-max, its own validated rule) from its physics/chem-flavored
"hard_stem" rows (the rule this M1-correction task actually changes) --
which the workload bucket alone conflates. Uses moo_m1_eval.jsonl's
recorded "subject" field (present on every record) to reclassify, via the
SAME _domain_bucket() the router itself calls at request time, so the
calibration table and the router's tie-break share one bucket definition.

Usage:
    python -m benchmark.build_moo_calibration
    python -m benchmark.build_moo_calibration --in benchmark/results/moo_m1_eval.jsonl --out benchmark/results/moo_calibration_table.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from quorumqa.engine.calibration import build_calibration_table, write_calibration_csv
from quorumqa.engine.router import _domain_bucket

DEFAULT_IN = Path("benchmark/results/moo_m1_eval.jsonl")
DEFAULT_OUT = Path("benchmark/results/moo_calibration_table.csv")


def load_eval_records(jsonl_path: Path) -> list[dict]:
    """Reads benchmark/run_moo_eval.py's per-(item, profile) JSONL records
    and reclassifies each one's router bucket from its recorded "subject"
    field. Returns plain dicts with the {profile, bucket, correct,
    total_tokens, escalated} keys quorumqa.engine.calibration.
    build_calibration_table expects -- "bucket" here is the router bucket,
    NOT the record's own raw "bucket" field (see module docstring)."""
    records = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            records.append(
                {
                    "profile": rec["profile"],
                    "bucket": _domain_bucket(rec["subject"]),
                    "correct": rec["correct"],
                    "total_tokens": rec["total_tokens"],
                    "escalated": rec["escalated"],
                }
            )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="in_path", type=str, default=str(DEFAULT_IN))
    parser.add_argument("--out", dest="out_path", type=str, default=str(DEFAULT_OUT))
    args = parser.parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)

    records = load_eval_records(in_path)
    entries = build_calibration_table(records)
    write_calibration_csv(entries, out_path)

    print(f"Wrote {len(entries)} (profile, bucket) calibration rows from {len(records)} eval records to {out_path}")
    print(f"\n{'bucket':22s} {'profile':20s} {'n':>4s} {'accuracy':>9s} {'mean_tokens':>12s} {'escalation':>11s}")
    for e in entries:
        print(f"{e.bucket:22s} {e.profile:20s} {e.n:4d} {e.accuracy*100:8.1f}% {e.mean_tokens:12.0f} {e.escalation_rate*100:10.1f}%")


if __name__ == "__main__":
    main()
