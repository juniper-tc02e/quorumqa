"""Run the compute-matched control `flagship_panel`'s claim never received.

`docs/capability-roadmap.md` mandates a compute-matched control for every
whole-pipeline swap: "the same base config sampled the same number of times,
aggregated by majority. Without it, a gain is indistinguishable from plain
self-consistency, which Self-MoA (ICML 2025) predicts will dominate." No such
control was ever run for flagship_panel, whose only validated accuracy claim
(SuperGPQA-hard, pooled b=11 c=1 net +10 p=0.0032, n=241) is a ~3.0x-compute
comparison against a 1x flagship call.

This runs `quorumqa.baseline.solve_compute_matched_control` -- 3 independent
BASELINE_MODEL (flagship) calls, text-majority vote, no tribunal -- on the
IDENTICAL items and seeds behind the claim. `--seed` must be one of 42, 7, 123
to be comparable; the loader is deterministic (verified 2026-07-29: fresh
DATASET_LOADERS['supergpqa'](90, seed, ...) reproduces every question_id
present in the committed lever_flagship_panel_supergpqa_seed{seed}.jsonl as a
subset), so no special item-freezing is needed -- just call it with the same
(n=90, seed) pair.

Output is written in the same `{"baseline": ..., "seed": ...}` shape
`lever_experiments.main_baseline` uses, so it is a drop-in comparator for
`benchmark/verify_compute_matched_control.py`.

    python -m benchmark.run_compute_matched_control --seed 42
    python -m benchmark.run_compute_matched_control --seed 7
    python -m benchmark.run_compute_matched_control --seed 123
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from benchmark.lever_experiments import DATASET_LOADERS
from quorumqa.baseline import solve_compute_matched_control
from quorumqa.qwen_client import QwenClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Seeds the flagship claim was measured at. A run at any other seed is not
# comparable to the published +4.1/+10 and this is enforced, not just noted.
CLAIM_SEEDS = (42, 7, 123)


async def _run_one(client: QwenClient, item, semaphore: asyncio.Semaphore):
    try:
        async with semaphore:
            result = await asyncio.to_thread(solve_compute_matched_control, client, item)
    except Exception:
        log.exception("%s: DROPPED after unrecoverable error", item.question_id)
        return None
    log.info(
        "%s [compute_matched_control]: %s(%s) latency=%.1fs",
        item.question_id, result.answer_letter,
        "correct" if result.correct else "wrong", result.latency_s,
    )
    return result


async def main(seed: int, n: int, concurrency: int, out_path: Path, skip_huggingface: bool, dataset: str, retry_missing: bool = False) -> None:
    items = DATASET_LOADERS[dataset](n, seed, skip_huggingface)
    log.info("Loaded %d %s items (seed=%d) for the compute-matched control", len(items), dataset, seed)

    existing: list[dict] = []
    if retry_missing and out_path.exists():
        with out_path.open(encoding="utf-8") as fh:
            existing = [json.loads(line) for line in fh if line.strip()]
        done_ids = {r["baseline"]["item"]["question_id"] for r in existing}
        items = [it for it in items if it.question_id not in done_ids]
        log.info(
            "Retry mode: %d already done, %d missing, retrying only the missing ones",
            len(existing), len(items),
        )

    client = QwenClient()
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [asyncio.ensure_future(_run_one(client, item, semaphore)) for item in items]
    results = []
    for coro in asyncio.as_completed(tasks):
        outcome = await coro
        if outcome is not None:
            results.append(outcome)

    dropped = len(items) - len(results)
    if dropped:
        log.warning("%d/%d questions dropped", dropped, len(items))

    fresh_rows = [{"baseline": r.model_dump(), "seed": seed} for r in results]
    all_rows = existing + fresh_rows

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row) + "\n")

    correct = sum(1 for row in all_rows if row["baseline"]["correct"])
    total_in = sum(c.get("input_tokens") or 0 for row in all_rows for c in row["baseline"]["calls"])
    total_out = sum(c.get("output_tokens") or 0 for row in all_rows for c in row["baseline"]["calls"])
    log.info(
        "SUMMARY n=%d accuracy=%.1f%% total_input_tokens=%d total_output_tokens=%d",
        len(all_rows), 100 * correct / len(all_rows) if all_rows else 0, total_in, total_out,
    )
    log.info("Wrote %d results to %s (%d retried this pass)", len(all_rows), out_path, len(fresh_rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True, choices=list(CLAIM_SEEDS),
                         help="Must be one of the flagship claim's own seeds (42, 7, 123) to be comparable.")
    parser.add_argument("--n", type=int, default=90)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--dataset", type=str, default="supergpqa", choices=list(DATASET_LOADERS.keys()))
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--skip-huggingface", action="store_true")
    parser.add_argument("--retry-missing", action="store_true",
                         help="Only re-run question_ids not already present in --out, appending to it. "
                              "Added after seed 123's first attempt dropped 75/90 items to the shared "
                              "QwenClient's fixed 300s per-call timeout (3 sequential thinking=True "
                              "flagship calls per item makes this arm far more timeout-prone than a "
                              "single-call baseline) -- mirrors qwen38_baseline.py's own resume path.")
    args = parser.parse_args()
    out_path = (
        Path(args.out) if args.out
        else RESULTS_DIR / f"compute_matched_control_{args.dataset}_seed{args.seed}.jsonl"
    )
    asyncio.run(main(args.seed, args.n, args.concurrency, out_path, args.skip_huggingface, args.dataset, args.retry_missing))
