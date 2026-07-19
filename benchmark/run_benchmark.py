"""Runs the matched-question-set benchmark: single-agent baseline vs the
QuorumQA deliberation engine (and optionally self-consistency@5) over the
same GPQA-Diamond sample, writing one JSON record per question.

Usage:
    python -m benchmark.run_benchmark --n 90 --self-consistency
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from quorumqa.baseline import solve_self_consistency5, solve_single_agent
from quorumqa.engine.orchestrator import run_question
from quorumqa.qwen_client import QwenClient
from quorumqa.tools.mcp_client import verifier_tool_session

from benchmark.load_gpqa import load_benchmark_set

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


async def _run_one(client, tool_session, item, semaphore, include_self_consistency):
    # One question failing (e.g. persistent JSON truncation from a single
    # role) must not kill the whole run -- log it, drop the question from
    # BOTH systems (keeps the comparison fair), and continue.
    try:
        async with semaphore:
            baseline = await asyncio.to_thread(solve_single_agent, client, item)
            engine_result = await run_question(client, tool_session, item)
            sc5 = await asyncio.to_thread(solve_self_consistency5, client, item) if include_self_consistency else None
    except Exception:
        log.exception("%s: DROPPED after unrecoverable error", item.question_id)
        return None
    log.info(
        "%s: baseline=%s(%s) engine=%s(%s, escalated=%s) cost b=$%.5f e=$%.5f",
        item.question_id,
        baseline.answer_letter, "correct" if baseline.correct else "wrong",
        engine_result.final_letter, "correct" if engine_result.correct else "wrong",
        engine_result.escalated,
        baseline.total_cost_usd, engine_result.total_cost_usd,
    )
    return baseline, engine_result, sc5


async def main(n: int, seed: int, concurrency: int, include_self_consistency: bool, out_path: Path, skip_huggingface: bool):
    items = load_benchmark_set(n=n, seed=seed, skip_huggingface=skip_huggingface)
    log.info("Loaded %d benchmark questions", len(items))

    client = QwenClient()
    semaphore = asyncio.Semaphore(concurrency)

    results = []
    async with verifier_tool_session() as tool_session:
        tasks = [
            asyncio.ensure_future(_run_one(client, tool_session, item, semaphore, include_self_consistency))
            for item in items
        ]
        for coro in asyncio.as_completed(tasks):
            outcome = await coro
            if outcome is not None:
                results.append(outcome)

    dropped = len(items) - len(results)
    if dropped:
        log.warning("%d/%d questions dropped due to unrecoverable errors -- see log above", dropped, len(items))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for baseline, engine_result, sc5 in results:
            record = {
                "baseline": baseline.model_dump(),
                "engine": engine_result.model_dump(),
                "self_consistency5": sc5.model_dump() if sc5 else None,
            }
            f.write(json.dumps(record) + "\n")
    log.info("Wrote %d results to %s", len(results), out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=90)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=int, default=6, help="Max questions in flight at once")
    parser.add_argument(
        "--self-consistency", action="store_true",
        help="Also run the self-consistency@5 stretch-goal baseline (5x extra Solver-tier calls/question)",
    )
    parser.add_argument("--out", type=str, default="benchmark/results/run.jsonl")
    parser.add_argument(
        "--skip-huggingface", action="store_true",
        help="Go straight to the GitHub zip fallback for GPQA-Diamond, skipping the ~20s HF retry-and-fail "
             "(useful while huggingface.co is down; same effect as QUORUMQA_SKIP_HF=1)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.n, args.seed, args.concurrency, args.self_consistency, Path(args.out), args.skip_huggingface))
