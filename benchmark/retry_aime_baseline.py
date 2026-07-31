"""Re-runs AIME baseline (flagship single-call) items dropped from a prior
benchmark/run_math_open.py --dataset aime run, appending recoveries to the
same file. Mirrors benchmark/retry_dropped.py's shape (GPQA engine retry) and
benchmark/qwen38_baseline.py's --retry-missing pattern, applied to the AIME
baseline arm, which run_math_open.py itself has no retry-missing path for.

Sequential (no concurrency knob) by design, matching this repo's own
precedent for chronic-timeout items (qwen38_bar_repair_preregistration.md's
--concurrency 1 retries): these items already failed 4 backed-off attempts
each inside the original run at concurrency 3, so parallelism is not the
fix -- pacing is the only thing left to try before the kill clause applies.

--timeout (default 300, matching QwenClient's own default) lets a second
retry pass try a genuinely longer wall-clock allowance -- unlike the D0 GPQA
bar repair's chronic drops (server-side 504 Gateway Timeout, a fast error
QwenClient.chat's client timeout could never have masked), THIS failure
signature is a client-side ReadTimeout: no response arrived within the
window at all, which a longer window can plausibly still resolve if the
model is genuinely still generating. QwenClient's timeout is now an
additive, default-preserving constructor param (see
tests/test_qwen_client_params.py) precisely so this script does not need to
duplicate QwenClient's HTTP/prompt-construction logic to test that
hypothesis.

    python -m benchmark.retry_aime_baseline benchmark/results/aime_open_baseline_seed101.jsonl --n 60 --seed 101
    python -m benchmark.retry_aime_baseline benchmark/results/aime_open_baseline_seed101.jsonl --n 60 --seed 101 --timeout 900 --max-attempts 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from quorumqa.qwen_client import QwenClient

from benchmark.load_aime import load_aime_set
from benchmark.math_open_engine import solve_single_math

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_BACKOFF_BASE_SECONDS = 5


async def main(results_path: Path, n: int, seed: int, timeout: float, max_attempts: int) -> None:
    existing_lines = [
        line for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    done_ids = {json.loads(line)["question_id"] for line in existing_lines}
    items = [i for i in load_aime_set(n=n, seed=seed) if i.question_id not in done_ids]
    log.info("%d/%d baseline items already present -- retrying %d missing (timeout=%.0fs, max_attempts=%d)",
              len(done_ids), n, len(items), timeout, max_attempts)

    client = QwenClient(timeout=timeout)
    recovered = 0
    still_failing = []
    for item in items:
        result = None
        for attempt in range(max_attempts):
            try:
                result = await asyncio.to_thread(solve_single_math, client, item)
                break
            except Exception as exc:
                if attempt == max_attempts - 1:
                    log.error("%s: STILL FAILING after %d attempts (%s: %s)",
                              item.question_id, max_attempts, type(exc).__name__, str(exc)[:120])
                    break
                backoff = _BACKOFF_BASE_SECONDS * (2 ** attempt)
                log.warning("%s: attempt %d/%d failed (%s), retrying in %ds",
                            item.question_id, attempt + 1, max_attempts, type(exc).__name__, backoff)
                await asyncio.sleep(backoff)
        if result is None:
            still_failing.append(item.question_id)
            continue
        with results_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")
        recovered += 1
        log.info("%s: recovered (%s)", item.question_id, "correct" if result["correct"] else "wrong")

    log.info("Recovered %d/%d. Still failing: %s", recovered, len(items), still_failing)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=str)
    parser.add_argument("--n", type=int, default=60)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--timeout", type=float, default=300, help="per-request HTTP timeout in seconds (QwenClient's own default: 300)")
    parser.add_argument("--max-attempts", type=int, default=4)
    args = parser.parse_args()
    asyncio.run(main(Path(args.results), args.n, args.seed, args.timeout, args.max_attempts))
