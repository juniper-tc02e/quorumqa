"""Re-runs benchmark questions that were dropped from a previous run's
output file, appending successes to that same file.

    python -m benchmark.retry_dropped benchmark/results/full_run2.jsonl --n 90
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


async def main(results_path: Path, n: int, seed: int, include_self_consistency: bool):
    done_ids = {
        json.loads(line)["engine"]["item"]["question_id"]
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    items = [i for i in load_benchmark_set(n=n, seed=seed, skip_huggingface=True) if i.question_id not in done_ids]
    log.info("Retrying %d dropped questions", len(items))

    client = QwenClient()
    recovered = 0
    async with verifier_tool_session() as tool_session:
        for item in items:
            try:
                baseline = await asyncio.to_thread(solve_single_agent, client, item)
                engine_result = await run_question(client, tool_session, item)
                sc5 = await asyncio.to_thread(solve_self_consistency5, client, item) if include_self_consistency else None
            except Exception:
                log.exception("%s: STILL FAILING", item.question_id)
                continue
            with results_path.open("a", encoding="utf-8") as f:
                record = {
                    "baseline": baseline.model_dump(),
                    "engine": engine_result.model_dump(),
                    "self_consistency5": sc5.model_dump() if sc5 else None,
                }
                f.write(json.dumps(record) + "\n")
            recovered += 1
            log.info("%s: recovered (baseline %s, engine %s)", item.question_id,
                     "correct" if baseline.correct else "wrong",
                     "correct" if engine_result.correct else "wrong")
    log.info("Recovered %d/%d", recovered, len(items))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=str)
    parser.add_argument("--n", type=int, default=90)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--self-consistency", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(Path(args.results), args.n, args.seed, args.self_consistency))
