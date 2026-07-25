"""S2 pool generator (docs/experiment-spec-book.md section 3): draws K
independent samples from the solver seat for every item in a dataset and
writes ONE frozen JSONL row per item, containing the full ORDERED sample
list -- letter, confidence, reasoning, and the full usage for every draw.

This is a GENERATION-ONLY runner. It does no selection at all (no
plurality, no confidence-weighting, nothing) -- that split is deliberate:
a pool generated once can be scored by benchmark/score_selectors.py's five
selectors (and any future one) for ZERO additional tokens, which is the
whole economic argument for S2 ("generate one frozen K=8 pool, then score
many selectors against it"). Selecting inside this file would collapse
that reuse and make every new selector cost a fresh paid run.

Mirrors, rather than reinvents, three pieces of already-verified machinery:
  - the solver call itself: `quorumqa.engine.solver._solve_one` (cheap
    tier: thinking=False, MECHANICAL_MODEL, hardcoded inside `_solve_one`
    itself) and `benchmark.lever_experiments._solve_one_thinking`
    (flagship tier: thinking=True, ORCHESTRATOR_MODEL) -- the SAME two
    functions every GPQA/SuperGPQA/LEXam/MMLU-Pro/MedQA lever in this repo
    calls, so a pool generated here is directly comparable to every
    already-logged panel/lever row.
  - dataset dispatch: `benchmark.lever_experiments.DATASET_LOADERS`,
    imported (not copied) so a dataset added there becomes available here
    automatically.
  - the retry-with-backoff-on-transient-error discipline
    `benchmark.run_math_open._attempt_with_retries` established: retry a
    failed call up to 4 times with 5/10/20s backoff before giving up. A
    dropped ITEM silently biases the pool toward easy items -- the exact
    trap that invalidated the first AIME run (benchmark/results/
    aime_cheap_pilot_seed42.log: 32/60 panel drops concentrated on the
    hardest questions, 26 survivors scoring a meaningless 100%/100%).
    Applied here PER SAMPLE (so one flaky draw doesn't waste K-1
    already-good draws on the same item), but if any one of an item's K
    samples still fails after retries, the WHOLE item is dropped -- never
    a partial pool, since a row with fewer than k samples would silently
    corrupt score_selectors.py's prefix-subsampling pool-size curve (S6),
    which assumes every row supplies exactly k ordered samples.

CLI:
    .venv/Scripts/python.exe -m benchmark.run_pool --dataset gpqa --n 90 \
        --seed 411 --k 8 --solver-tier cheap --concurrency 6

`--seed` has NO default (unlike every other runner in this repo) --
deliberately, since this repo's own default seed (42) is burned for
selection purposes (see benchmark/score_selectors.py's BURNED_SEEDS); a
silent fallback here would generate an unusable S7 pool.

Writes benchmark/results/pool_<dataset>_<solver-tier>_k<k>_seed<seed>.jsonl
(override with --out). One JSON row per surviving item:
    {"question_id", "item": {question_id, question, choices,
     correct_letter, subject}, "dataset", "seed", "solver_tier",
     "solver_model", "k", "samples": [{"question_id", "sample_index",
     "letter", "confidence", "reasoning", "usage"}, ...]}   # ordered 0..k-1

This is a PAID runner (real QwenClient calls) -- never invoked by the
offline test suite, same posture as benchmark/run_math_open.py.
tests/test_run_pool_offline.py exercises generate_pool()/the retry wrapper
directly against a fake client instead, exactly like
tests/test_math_sc_offline.py does for benchmark/math_open_engine.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from quorumqa.config import MECHANICAL_MODEL, ORCHESTRATOR_MODEL
from quorumqa.engine.solver import _solve_one
from quorumqa.qwen_client import QwenClient

from benchmark.lever_experiments import DATASET_LOADERS, _solve_one_thinking
from benchmark.math_open_engine import SC_TEMPERATURE_SCHEDULE
from benchmark.score_selectors import BURNED_SEEDS, POOL_FILENAME_PREFIX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Same convention benchmark/math_open_engine.py's BASELINE_LENS establishes
# for self-consistency: ONE generic "solve it directly" framing, shared
# across all K draws -- diversity comes from resampling (temperature
# cycling below), not from distinct lens framing (that axis is the PANEL's
# job -- quorumqa.config.SOLVER_LENSES -- and is a different, already-
# answered question; see docs/experiment-spec-book.md MATH-6). Deliberately
# distinct wording from every SOLVER_LENSES entry so a pool row is never
# byte-identical to a panel seat's prompt.
POOL_LENS = (
    "Answer this question on your own, working the problem through directly "
    "and carefully before committing to a final choice."
)

# cheap -> _solve_one (thinking=False hardcoded inside it, MECHANICAL_MODEL
# tier); flagship -> _solve_one_thinking (thinking=True hardcoded inside
# it, ORCHESTRATOR_MODEL tier). Matches benchmark/run_math_open.py's exact
# tier dispatch (solver_model = MECHANICAL_MODEL if cheap else
# ORCHESTRATOR_MODEL; solver_thinking = solver_tier != "cheap").
SOLVER_TIER_DISPATCH = {
    "cheap": (_solve_one, MECHANICAL_MODEL),
    "flagship": (_solve_one_thinking, ORCHESTRATOR_MODEL),
}

_MAX_ATTEMPTS = 4  # matches benchmark/run_math_open.py's _attempt_with_retries exactly
_BACKOFF_BASE_SECONDS = 5  # -> 5, 10, 20s backoff, same schedule as run_math_open.py


async def _attempt_sample_with_retries(client, item, sample_index, semaphore, solve_fn, solver_model, sleep_fn=asyncio.sleep):
    """One sample draw (`sample_index`) for `item`, retried up to
    _MAX_ATTEMPTS times with exponential backoff on ANY exception --
    transient transport failures (ReadTimeout, 429 rate-limit, 5xx) are the
    dominant drop cause on hard/long questions (see benchmark/
    run_math_open.py's module docstring); the QwenClient itself only
    retries JSON-parse failures, so anything else must be retried here.
    Returns (SolverAnswer, CallUsage) on success, None if every attempt
    failed -- the caller is responsible for dropping the whole item rather
    than logging a partial pool. `sleep_fn` defaults to the real
    asyncio.sleep; tests inject a fast no-op so retry tests don't actually
    wait 5-20s."""
    temperature = SC_TEMPERATURE_SCHEDULE[sample_index % len(SC_TEMPERATURE_SCHEDULE)]
    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with semaphore:
                return await asyncio.to_thread(solve_fn, client, item.question, item.choices, POOL_LENS, solver_model, temperature)
        except Exception as exc:
            if attempt == _MAX_ATTEMPTS - 1:
                log.error(
                    "%s: sample %d DROPPED after %d attempts (%s: %s)",
                    item.question_id, sample_index, _MAX_ATTEMPTS, type(exc).__name__, str(exc)[:120],
                )
                return None
            backoff = _BACKOFF_BASE_SECONDS * (2 ** attempt)
            log.warning(
                "%s: sample %d attempt %d/%d failed (%s), retrying in %ds",
                item.question_id, sample_index, attempt + 1, _MAX_ATTEMPTS, type(exc).__name__, backoff,
            )
            await sleep_fn(backoff)
    return None


async def _run_item_pool(client, item, semaphore, k, solve_fn, solver_model, solver_tier, sleep_fn=asyncio.sleep):
    """Draws k independent samples for one item (concurrently, each with
    its own retry budget) and assembles the frozen pool row. Returns None
    (and logs a warning) if ANY sample permanently failed -- a pool with
    fewer than k samples on some items would silently bias every k-scaling
    curve derived from it downstream, so the whole item is dropped rather
    than logged incomplete."""
    sample_tasks = [
        asyncio.ensure_future(_attempt_sample_with_retries(client, item, i, semaphore, solve_fn, solver_model, sleep_fn))
        for i in range(k)
    ]
    outcomes = await asyncio.gather(*sample_tasks)  # order preserved -- matches task list order, i.e. sample_index 0..k-1
    if any(o is None for o in outcomes):
        n_ok = sum(1 for o in outcomes if o is not None)
        log.warning(
            "%s: ITEM DROPPED -- only %d/%d samples survived retries. A pool with fewer "
            "than k=%d samples on this item would silently bias every k-scaling curve "
            "derived from it (prefix subsampling assumes every row has exactly k ordered "
            "samples), so the whole item is excluded rather than logged incomplete.",
            item.question_id, n_ok, k, k,
        )
        return None
    samples = [
        {
            "question_id": item.question_id,
            "sample_index": i,
            "letter": answer.letter,
            "confidence": answer.confidence,
            "reasoning": answer.reasoning,
            "usage": usage.model_dump(),
        }
        for i, (answer, usage) in enumerate(outcomes)
    ]
    return {
        "question_id": item.question_id,
        "item": item.model_dump(),
        "solver_tier": solver_tier,
        "solver_model": solver_model,
        "k": k,
        "samples": samples,
    }


async def generate_pool(client, items, k, solver_tier, concurrency, sleep_fn=asyncio.sleep):
    """Generates a frozen K-sample pool for every item in `items`. Returns
    (rows, dropped_question_ids). ONE shared semaphore bounds total
    concurrent solver calls across ALL items x samples, mirroring
    benchmark/run_math_open.py's/benchmark/lever_experiments.py's single-
    semaphore pattern. No item's failure aborts the run -- every other item
    still gets scored/written; dropped_question_ids records what was lost
    so the caller can report the drop rate rather than hide it."""
    if solver_tier not in SOLVER_TIER_DISPATCH:
        raise ValueError(f"--solver-tier {solver_tier!r} must be one of {sorted(SOLVER_TIER_DISPATCH)}")
    if k < 1:
        raise ValueError(f"--k must be >= 1, got {k}")
    solve_fn, solver_model = SOLVER_TIER_DISPATCH[solver_tier]
    semaphore = asyncio.Semaphore(concurrency)
    item_tasks = [
        asyncio.ensure_future(_run_item_pool(client, item, semaphore, k, solve_fn, solver_model, solver_tier, sleep_fn))
        for item in items
    ]
    outcomes = await asyncio.gather(*item_tasks)
    rows = [o for o in outcomes if o is not None]
    dropped = [item.question_id for item, o in zip(items, outcomes) if o is None]
    return rows, dropped


async def main(dataset: str, n: int, seed: int, k: int, solver_tier: str, concurrency: int, out_path: Path, skip_huggingface: bool = False) -> None:
    if seed in BURNED_SEEDS:
        log.warning(
            "--seed %d is in benchmark.score_selectors.BURNED_SEEDS (already used in "
            "selection/tuning) -- a pool generated here CANNOT be used for an S7 SHIP "
            "verdict (score_selectors.py --ship-gate will refuse it). Fine for a dry run "
            "or offline sanity check, but pick a fresh seed before spending real tokens "
            "on this for S7.",
            seed,
        )

    items = DATASET_LOADERS[dataset](n, seed, skip_huggingface)
    log.info(
        "Loaded %d %s items (seed=%d) -- generating a K=%d pool at solver_tier=%s",
        len(items), dataset, seed, k, solver_tier,
    )

    client = QwenClient()
    rows, dropped = await generate_pool(client, items, k, solver_tier, concurrency)
    if dropped:
        log.warning("%d/%d items DROPPED after exhausting retries: %s", len(dropped), len(items), dropped)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({**row, "dataset": dataset, "seed": seed}) + "\n")
    log.info("Wrote %d/%d item pools (k=%d samples each) to %s", len(rows), len(items), k, out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=str, default="gpqa", choices=list(DATASET_LOADERS.keys()))
    parser.add_argument("--n", type=int, default=90)
    parser.add_argument("--seed", type=int, required=True, help="an UNBURNED seed for S7 -- see benchmark/score_selectors.py's BURNED_SEEDS (no default: this repo's usual default, 42, is burned)")
    parser.add_argument("--k", type=int, default=8)
    parser.add_argument("--solver-tier", choices=list(SOLVER_TIER_DISPATCH.keys()), default="cheap")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--skip-huggingface", action="store_true")
    args = parser.parse_args()
    out_path = Path(args.out) if args.out else RESULTS_DIR / f"{POOL_FILENAME_PREFIX}{args.dataset}_{args.solver_tier}_k{args.k}_seed{args.seed}.jsonl"
    asyncio.run(main(args.dataset, args.n, args.seed, args.k, args.solver_tier, args.concurrency, out_path, args.skip_huggingface))
