"""Runs the same matched-question-set benchmark as run_benchmark.py --
single-agent baseline vs. the QuorumQA deliberation engine, unchanged --
but over MMLU-Pro (14-domain academic/professional MC, trimmed to 4
choices, see load_mmlu_pro.py for why) instead of GPQA-Diamond.

Usage:
    python -m benchmark.run_mmlu_pro --n 50 --seed 42
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from quorumqa.baseline import solve_single_agent
from quorumqa.engine.orchestrator import run_question
from quorumqa.qwen_client import QwenClient
from quorumqa.tools.mcp_client import verifier_tool_session

from benchmark.load_mmlu_pro import load_mmlu_pro_set

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


async def _run_one(client, tool_session, item, semaphore):
    try:
        async with semaphore:
            baseline = await asyncio.to_thread(solve_single_agent, client, item)
            engine_result = await run_question(client, tool_session, item)
    except Exception:
        log.exception("%s: DROPPED after unrecoverable error", item.question_id)
        return None
    log.info(
        "%s [%s]: baseline=%s(%s) engine=%s(%s, escalated=%s)",
        item.question_id, item.subject,
        baseline.answer_letter, "correct" if baseline.correct else "wrong",
        engine_result.final_letter, "correct" if engine_result.correct else "wrong",
        engine_result.escalated,
    )
    return baseline, engine_result


async def main(n: int, seed: int, concurrency: int, out_path: Path, category: str | None):
    items = load_mmlu_pro_set(n=n, seed=seed, category=category)
    log.info("Loaded %d MMLU-Pro questions", len(items))

    client = QwenClient()
    semaphore = asyncio.Semaphore(concurrency)

    results = []
    async with verifier_tool_session() as tool_session:
        tasks = [asyncio.ensure_future(_run_one(client, tool_session, item, semaphore)) for item in items]
        for coro in asyncio.as_completed(tasks):
            outcome = await coro
            if outcome is not None:
                results.append(outcome)

    dropped = len(items) - len(results)
    if dropped:
        log.warning("%d/%d questions dropped due to unrecoverable errors", dropped, len(items))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for baseline, engine_result in results:
            f.write(json.dumps({"baseline": baseline.model_dump(), "engine": engine_result.model_dump()}) + "\n")
    log.info("Wrote %d results to %s", len(results), out_path)

    n_ok = len(results)
    b_correct = sum(1 for b, _ in results if b.correct)
    e_correct = sum(1 for _, e in results if e.correct)
    esc = sum(1 for _, e in results if e.escalated)
    log.info(
        "SUMMARY n=%d baseline_accuracy=%.1f%% engine_accuracy=%.1f%% escalation_rate=%.1f%%",
        n_ok, 100 * b_correct / n_ok if n_ok else 0, 100 * e_correct / n_ok if n_ok else 0,
        100 * esc / n_ok if n_ok else 0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=90)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--out", type=str, default="benchmark/results/mmlu_pro_run.jsonl")
    parser.add_argument("--category", type=str, default=None, help="Filter to one MMLU-Pro category, e.g. 'physics'")
    args = parser.parse_args()
    asyncio.run(main(args.n, args.seed, args.concurrency, Path(args.out), args.category))
