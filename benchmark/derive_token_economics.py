"""Derive per-routing-path token costs from the frozen submission run.

Emits benchmark/results/submission_token_economics.json -- aggregates only, no
question text, no transcripts, no answer keys -- so the figures published in
docs/product/PRODUCT.md have a committed source. The raw run .jsonl files are
gitignored (benchmark/results/*.jsonl), which would otherwise leave the test
that pins those figures skipping on every machine except the one that ran the
benchmark.

    python -m benchmark.derive_token_economics            # print
    python -m benchmark.derive_token_economics --write    # regenerate the JSON

WHY THESE THREE PATHS. The dollar figures PRODUCT.md was built on came from
`PRICING_USD_PER_MTOK`, where qwen3.6-flash input is 0.60 and qwen3.7-max input
is 2.50 USD/Mtok. Every claim of the engine being "cheaper" lived in that ~4x
model price spread. The Token Plan bills a token quota instead, so the split
that matters is no longer flash-vs-max dollars but how many tokens each routing
path burns: the cheap path (unanimous, no escalation), the expensive path
(escalated through Skeptic/Verifier/Judge), and the blend the product actually
serves.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
SOURCES = ["full_run.jsonl", "full_run2.jsonl"]
OUT = RESULTS / "submission_token_economics.json"

#: The OTHER published token pair, measured on the TB-1 paired item set. Carried
#: into the output so nobody reconciles two correct measurements of different
#: item sets by editing one of them.
TB1_PAIR = (8690, 2792)
TB1_NOTE = ("TB-1 paired item set, seeds 1001/2311/3407, n=265 shared items")


def _tokens(calls) -> int:
    return sum(c.get("input_tokens", 0) + c.get("output_tokens", 0) for c in calls)


def load_rows(results_dir: Path = RESULTS) -> list[dict]:
    """Deduplicate by question_id; full_run2 continues full_run, later wins."""
    seen: dict[str, dict] = {}
    for name in SOURCES:
        p = results_dir / name
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if "engine" in row:
                    seen[row["engine"]["item"]["question_id"]] = row
    return list(seen.values())


def derive(rows: list[dict]) -> dict:
    if not rows:
        raise SystemExit(
            "no engine rows found -- the raw run files are gitignored; this "
            "regenerator only works on the machine holding them"
        )
    unanimous, escalated, baseline = [], [], []
    for r in rows:
        e = r["engine"]
        (escalated if e["escalated"] else unanimous).append(_tokens(e["calls"]))
        if r.get("baseline"):
            baseline.append(_tokens(r["baseline"]["calls"]))

    blended = statistics.mean(unanimous + escalated)
    base = statistics.mean(baseline)
    per_item = {
        "unanimous": round(statistics.mean(unanimous)),
        "escalated": round(statistics.mean(escalated)),
        "blended": round(blended),
        "baseline_flagship_1x": round(base),
    }
    return {
        "_what": ("Aggregate token cost per routing path for the frozen "
                  "submission run. Derived artifact: aggregates only, no "
                  "question text, no transcripts, no answer keys -- safe to "
                  "commit where the source .jsonl is gitignored."),
        "_why": ("docs/product/PRODUCT.md publishes these figures. Their source "
                 "(benchmark/results/full_run*.jsonl) is gitignored, so without "
                 "this file the test that pins the doc to the data would skip "
                 "on every machine but the one that ran it -- a guard that does "
                 "not guard."),
        "_source": [f"benchmark/results/{n}" for n in SOURCES],
        "_source_note": ("full_run2 continues full_run; rows are deduplicated by "
                         "question_id with later rows winning."),
        "_generated": "2026-08-03",
        "_regenerate": "python -m benchmark.derive_token_economics",
        "benchmark": "GPQA-Diamond",
        "seed": 42,
        "n_items": len(rows),
        "escalation_rate_pct": round(100 * len(escalated) / len(rows), 1),
        "tokens_per_item": per_item,
        "counts": {"unanimous": len(unanimous), "escalated": len(escalated)},
        "multiples_vs_flagship_1x": {
            "unanimous": round(per_item["unanimous"] / base, 2),
            "escalated": round(per_item["escalated"] / base, 2),
            "blended": round(blended / base, 2),
        },
        "_do_not_confuse_with": {
            "pair": list(TB1_PAIR),
            "multiple": round(TB1_PAIR[0] / TB1_PAIR[1], 2),
            "measured_on": TB1_NOTE,
            "note": ("Quoted in README.md, docs/architecture.md and "
                     "docs/FINDINGS-2026-08.md. A DIFFERENT item set, not a "
                     "competing estimate of the same quantity. Do not reconcile "
                     "them by editing either one."),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help=f"overwrite {OUT.name}")
    args = ap.parse_args()

    data = derive(load_rows())
    text = json.dumps(data, indent=2) + "\n"
    if args.write:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT}")
    else:
        print(text)
        print("(dry run -- pass --write to regenerate)")


if __name__ == "__main__":
    main()
