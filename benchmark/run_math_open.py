"""CLI runner for the open-answer MATH-500 hard-tier pilot -- tests whether
multi-solver deliberation (solve_panel_math) beats a single flagship call
(solve_single_math) on genuinely hard OPEN-ANSWER math, where the shipped
engine's distractor-MC framing saturates the flagship and cannot
discriminate (see benchmark/load_math.py's docstring and
benchmark/results/math500_hard_pilot_seed42.log).

Mirrors benchmark/lever_experiments.py's main_live()/main_baseline()
asyncio run/gather/write-JSONL pattern: both the baseline and the panel are
plain sync functions (benchmark.math_open_engine.solve_single_math /
solve_panel_math) dispatched via asyncio.to_thread behind a SHARED
semaphore (bounding total concurrent flagship-call groups across both
sides, exactly like main_live's single semaphore bounds its per-item
tasks), run concurrently across ALL items -- baseline and panel calls for
the SAME item are independent, there is no ordering dependency between
them. Every unrecoverable per-item error is logged and the item DROPPED
rather than failing the whole run (same posture as _run_one/_run_one_
baseline).

This is a PAID pilot (real QwenClient/Token Plan calls) -- never invoked by
the offline test suite (tests/test_math_open_engine_offline.py exercises
solve_single_math/solve_panel_math directly against a fake client instead).

Usage:
  python -m benchmark.run_math_open --n 60 --seed 42 --level 5 --concurrency 6
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from quorumqa.config import MECHANICAL_MODEL, ORCHESTRATOR_MODEL
from quorumqa.qwen_client import QwenClient

from benchmark.load_aime import load_aime_set
from benchmark.load_math_open import load_math_open_set
from benchmark.math_open_engine import solve_panel_math, solve_single_math

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "results"


async def _run_baseline_one(client, item, semaphore):
    try:
        async with semaphore:
            result = await asyncio.to_thread(solve_single_math, client, item)
    except Exception:
        log.exception("%s: baseline DROPPED after unrecoverable error", item.question_id)
        return None
    log.info(
        "%s [baseline]: %s(%s)",
        item.question_id, result["final_answer"], "correct" if result["correct"] else "wrong",
    )
    return result


async def _run_panel_one(client, item, semaphore, solver_model):
    try:
        async with semaphore:
            result = await asyncio.to_thread(solve_panel_math, client, item, solver_model)
    except Exception:
        log.exception("%s: panel DROPPED after unrecoverable error", item.question_id)
        return None
    log.info(
        "%s [panel]: %s(%s, escalated=%s)",
        item.question_id, result["final_answer"],
        "correct" if result["correct"] else "wrong", result["escalated"],
    )
    return result


async def main(n: int, seed: int, level: int | None, concurrency: int, solver_tier: str = "flagship", dataset: str = "math500") -> None:
    if dataset == "aime":
        items = load_aime_set(n=n, seed=seed)
    else:
        items = load_math_open_set(n=n, seed=seed, level=level)
    solver_model = MECHANICAL_MODEL if solver_tier == "cheap" else ORCHESTRATOR_MODEL
    log.info(
        "Loaded %d %s open-answer items (level=%s, seed=%d) -- panel solver_tier=%s (%s), judge always flagship",
        len(items), dataset, level, seed, solver_tier, solver_model,
    )

    client = QwenClient()
    # ONE shared semaphore across baseline AND panel tasks, mirroring
    # main_live's single semaphore -- bounds TOTAL concurrent flagship-call
    # groups (baseline calls count for 1 flagship call each, panel calls
    # count for up to 4 -- 3 solvers + optional judge -- but each group only
    # holds the semaphore for the duration of its own asyncio.to_thread).
    semaphore = asyncio.Semaphore(concurrency)

    baseline_tasks = [asyncio.ensure_future(_run_baseline_one(client, item, semaphore)) for item in items]
    panel_tasks = [asyncio.ensure_future(_run_panel_one(client, item, semaphore, solver_model)) for item in items]

    baseline_results = [r for r in await asyncio.gather(*baseline_tasks) if r is not None]
    panel_results = [r for r in await asyncio.gather(*panel_tasks) if r is not None]

    dropped_baseline = len(items) - len(baseline_results)
    dropped_panel = len(items) - len(panel_results)
    if dropped_baseline:
        log.warning("%d/%d baseline items dropped due to unrecoverable errors", dropped_baseline, len(items))
    if dropped_panel:
        log.warning("%d/%d panel items dropped due to unrecoverable errors", dropped_panel, len(items))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    # The baseline is always a single flagship call (tier-independent), but the
    # panel varies by solver tier -- suffix the panel file so a cheap-tier run
    # never overwrites a flagship-tier run's results. Dataset prefixes the name
    # so AIME never collides with MATH-500.
    prefix = "aime_open" if dataset == "aime" else "math_open"
    baseline_path = RESULTS_DIR / f"{prefix}_baseline_seed{seed}.jsonl"
    panel_suffix = "" if solver_tier == "flagship" else f"_{solver_tier}"
    panel_path = RESULTS_DIR / f"{prefix}_panel{panel_suffix}_seed{seed}.jsonl"

    with baseline_path.open("w", encoding="utf-8") as f:
        for r in baseline_results:
            f.write(json.dumps(r) + "\n")
    with panel_path.open("w", encoding="utf-8") as f:
        for r in panel_results:
            f.write(json.dumps(r) + "\n")
    log.info("Wrote %d baseline results to %s", len(baseline_results), baseline_path)
    log.info("Wrote %d panel results to %s", len(panel_results), panel_path)

    baseline_by_id = {r["question_id"]: r for r in baseline_results}
    panel_by_id = {r["question_id"]: r for r in panel_results}
    common_ids = set(baseline_by_id) & set(panel_by_id)
    if not common_ids:
        log.warning("No common question_id intersection between baseline and panel results -- cannot compute deltas")
        return

    n_common = len(common_ids)
    baseline_correct = sum(1 for qid in common_ids if baseline_by_id[qid]["correct"])
    panel_correct = sum(1 for qid in common_ids if panel_by_id[qid]["correct"])
    escalated = sum(1 for qid in common_ids if panel_by_id[qid]["escalated"])

    baseline_acc = baseline_correct / n_common
    panel_acc = panel_correct / n_common
    escalation_rate = escalated / n_common

    log.info(
        "RESULTS (n=%d common items, seed=%d, level=%s): baseline=%.1f%% (%d/%d) "
        "panel=%.1f%% (%d/%d) delta=%+.1f pp escalation_rate=%.1f%% (%d/%d)",
        n_common, seed, level,
        baseline_acc * 100, baseline_correct, n_common,
        panel_acc * 100, panel_correct, n_common,
        (panel_acc - baseline_acc) * 100,
        escalation_rate * 100, escalated, n_common,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--level", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--solver-tier", choices=["flagship", "cheap"], default="flagship",
                        help="panel solver tier: 'flagship' (qwen3.7-max, all-strong panel) or "
                             "'cheap' (qwen3.6-flash solvers + flagship judge -- the SHIPPED engine's real tier)")
    parser.add_argument("--dataset", choices=["math500", "aime"], default="math500",
                        help="'math500' (level-filtered MATH-500) or 'aime' (AIME 2024+2025, integer answers)")
    args = parser.parse_args()
    asyncio.run(main(args.n, args.seed, args.level, args.concurrency, args.solver_tier, args.dataset))
