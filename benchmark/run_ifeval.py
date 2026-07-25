"""Runs QuorumQA's own validated IFEval scorer (benchmark/ifeval_verify.py)
against live model calls -- the runner docs/capability-roadmap.md section
3.11 (F6/IF-2) has been waiting on. This is the one number in this repo's
whole benchmark suite that is genuinely comparable to a published
leaderboard score end to end, for three independent reasons stacked
together: (1) the data is UNTRIMMED -- benchmark/load_ifeval.py loads all
541 prompts verbatim, no distractor synthesis, no MC conversion, no
answer-shape filtering (IFEval has no gold "answer" to reshape in the
first place); (2) the grader is INDEPENDENTLY VALIDATED against the
official reference implementation -- 50/50 hand-written cases, 126/126
real-dataset-kwargs cases, and 77.22% vs Google's own published 77.0-77.2%
strict-prompt accuracy on their own 540-row GPT-4 reference file (see
benchmark/results/ifeval_scorer_validation.md); (3) both flavours IFEval's
own published numbers report -- strict and loose -- are scored and
reported, not just one.

Usage:
  python -m benchmark.run_ifeval --n 60 --seed 42            # IF-2 cheap gap probe
  python -m benchmark.run_ifeval --n 541 --seed 42           # the full, comparable set (default)

ARMS -- `single` is fully implemented; `panel` is deliberately not.

  single: one flagship (ORCHESTRATOR_MODEL) call per prompt, RAW text --
    NOT chat_json. This mirrors quorumqa.baseline.solve_single_agent /
    benchmark.math_open_engine.solve_single_math /
    benchmark.factuality_engine.solve_single_factual (one flagship call, no
    ensemble, the REQUIRED baseline every axis in this repo reports), and
    it deliberately follows benchmark.factuality_engine.grade_simpleqa's
    precedent of using client.chat() with a BARE user message and no system
    prompt at all: IFEval instructions directly constrain response
    FORMATTING (lowercase-only, no commas, must parse as JSON, must be
    wrapped in quotes, must not start with any preamble...), so (a)
    wrapping the model's output in this repo's usual JSON-mode scaffolding
    (chat_json's "Respond with ONLY a single valid JSON object" system
    suffix) would corrupt the exact thing being measured, and (b) even a
    neutral-sounding injected system persona risks nudging phrasing/
    preamble habits that some checkers (startend:end_checker,
    combination:repeat_prompt, detectable_format:constrained_response) are
    sensitive to. The prompt is sent EXACTLY as the dataset provides it
    (item.prompt), matching how every published IFEval number is produced:
    response = model(prompt), full stop.

  panel: DELIBERATELY NOT IMPLEMENTED. `--arm panel` is a recognized CLI
    value that raises NotImplementedError with the explanation below rather
    than silently running something fabricated -- per the build spec, "a
    defensible panel aggregation is not obvious here, state that honestly
    rather than inventing one that can't be justified."

    WHY NO PANEL ARM (read before adding one): IFEval answers are long
    free-form text under a COMBINATORIAL set of format constraints (exact
    paragraph counts, banned punctuation, JSON-vs-prose, language,
    capitalization...), not a letter (every MC axis in this repo) or a
    short factual phrase (SimpleQA). This repo's one existing free-text
    panel precedent, benchmark.factuality_engine.solve_panel_factual,
    clusters candidate answers by normalize_answer() string-equivalence and
    only escalates to a judge on a no-clear-margin split -- that works
    because SimpleQA answers are short and a genuinely correct answer
    converges to close-to-identical surface strings across independent
    solvers ("JFK" / "John F. Kennedy" is the documented near-miss, not the
    norm; see that module's normalize_answer docstring). Two independent,
    EQUALLY VALID completions of an IFEval prompt ("write a 3-paragraph
    story about X, no commas, all lowercase") will differ in nearly every
    word while both perfectly satisfying every instruction -- clustering by
    string similarity would produce N singleton clusters on almost every
    item, degenerating the panel into "always escalate to the judge" (N+1x
    the cost of single, for a mechanism no more discriminating than single
    plurality-of-one), which defeats the plurality-vote economics premise
    the shipped MC engine and solve_panel_factual are both built on.

    Two alternative mechanisms were considered and rejected, not just
    skipped:
      (a) Use ifeval_verify.verify_all itself to pick the "best" of N panel
          candidates at inference time. Rejected: this is rejection
          sampling against the EXACT grader that then scores the result --
          it inflates the panel's number in a way no real single-shot
          deployed system could reproduce (a real user never gets N free
          tries scored by the answer key before submitting one). This
          would be exactly the "fabricated mechanism that cannot be
          justified" the build spec warns against, dressed up as an
          aggregation.
      (b) A flagship judge picks the best of N candidate responses
          (mirroring factuality_engine.judge_factual). Rejected for the
          opposite reason: manually eyeballing "did this response use
          exactly 3 highlighted sections" or "does the letter e appear at
          least 20 times" is exactly the class of mechanical, countable
          constraint a language-model judge is UNRELIABLE at -- which is
          the entire reason ifeval_verify.py's deterministic checkers exist
          instead of a judge prompt in the first place (see that module's
          docstring). A judge that is worse at the task than the
          deterministic grader it would be standing in for is not a
          credible aggregation mechanism.
    Neither is defensible, and no other mechanism was obvious given this
    repo's own precedents. If IFEval ever gets a real panel arm, the design
    question above is exactly what needs answering first -- this comment
    is the record of what was already ruled out and why.

SCORING: every response is scored with BOTH ifeval_verify.verify_all
(strict-prompt) and verify_all_loose (loose upper bound), since IFEval's
own published numbers come in both flavours.

HEADLINE METRIC: the HELD-OUT constraint-type subset (
ifeval_verify.HELD_OUT_INSTRUCTION_TYPES, 8/25 instruction types, ~115/541
prompts whose ENTIRE instruction_id_list is a subset of those 8) -- this
anti-gaming control was frozen (benchmark/results/ifeval_scorer_
validation.md, committed before ANY run against this surface) specifically
so a future repair loop built against extract_constraints_from_prompt's
in-domain-only vocabulary can never be caught grading itself against the
same types it was tuned on. Applying it starting with this FIRST run (not
only once a repair lever exists) gives any future comparison a clean,
pre-registered baseline to diff against. The full-vocabulary number (over
every scored prompt, all 25 types mixed) is reported alongside it as the
in-domain ceiling, per the build spec -- not the headline.

Retry-with-backoff: the QwenClient retries only JSON-parse failures (N/A
here, this runner never calls chat_json); transient transport failures
(ReadTimeout, 429, 5xx) are the dominant drop cause on long/hard prompts,
and IFEval prompts requiring long free-text output are exactly the slow
ones -- dropping on first error would silently bias the surviving sample
away from prompts with heavy length/structure constraints. Mirrors
benchmark/run_math_open.py's _attempt_with_retries exactly (same
MAX_ATTEMPTS=4, same 5/10/20s exponential backoff schedule).

OUTPUT: one JSON object per line (per-prompt, `--out`) plus a
`<out>.summary.json` with strict/loose accuracy overall (full_vocabulary),
on the held-out subset (held_out_subset, the headline), and per
instruction family (per_instruction_family) -- mirrors
benchmark/run_moo_eval.py's `out_path.with_suffix(".summary.json")`
convention.
"""

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

from quorumqa.config import ORCHESTRATOR_MODEL
from quorumqa.qwen_client import QwenClient

from benchmark.ifeval_verify import HELD_OUT_INSTRUCTION_TYPES, verify_all, verify_all_loose
from benchmark.load_ifeval import IFEvalItem, load_ifeval_set

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "results"

PANEL_ARM_NOT_IMPLEMENTED = (
    "run_ifeval --arm panel is not implemented. IFEval responses are long "
    "free-form text under combinatorial format constraints, not a letter "
    "or a short factual phrase -- this repo's only free-text panel "
    "precedent (benchmark.factuality_engine.solve_panel_factual's "
    "normalize_answer string-equivalence clustering) does not generalize: "
    "two equally-valid completions of the same instruction-following "
    "prompt will differ in nearly every word, so clustering would "
    "degenerate to 'always escalate' on almost every item. Using this "
    "repo's own deterministic verifier (ifeval_verify.verify_all) to pick "
    "the best of N candidates would be rejection sampling against the "
    "exact grader that then scores the result -- not a fair aggregation. "
    "A flagship judge picking the best candidate would be asking a "
    "language model to do the mechanical constraint-counting the "
    "deterministic verifier exists specifically because judges are "
    "unreliable at. See this module's docstring ('WHY NO PANEL ARM') for "
    "the full reasoning. Run --arm single instead, or design and "
    "implement a defensible panel mechanism before adding this arm."
)

# Same retry posture as benchmark/run_math_open.py's _attempt_with_retries:
# the QwenClient only retries JSON-parse failures (irrelevant here, this
# runner uses client.chat(), never chat_json), so transient transport
# failures (ReadTimeout, 429, 5xx) would otherwise drop the item outright.
# Long free-text IFEval responses are exactly the slow calls most likely to
# time out, so dropping on first error would bias survivors toward
# short/simple prompts. Same schedule: 4 attempts, 5/10/20s backoff.
_MAX_ATTEMPTS = 4


async def _attempt_with_retries(label: str, item: IFEvalItem, semaphore: asyncio.Semaphore, fn):
    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with semaphore:
                return await asyncio.to_thread(fn)
        except Exception as exc:
            if attempt == _MAX_ATTEMPTS - 1:
                log.error("key=%s: %s DROPPED after %d attempts (%s: %s)",
                          item.key, label, _MAX_ATTEMPTS, type(exc).__name__, str(exc)[:120])
                return None
            backoff = 5 * (2 ** attempt)  # 5, 10, 20s -- lets a rate-limit window clear
            log.warning("key=%s: %s attempt %d/%d failed (%s), retrying in %ds",
                        item.key, label, attempt + 1, _MAX_ATTEMPTS, type(exc).__name__, backoff)
            await asyncio.sleep(backoff)
    return None


def solve_single_ifeval(client: QwenClient, item: IFEvalItem, model: str = ORCHESTRATOR_MODEL, thinking: bool = True) -> dict:
    """The required single-agent baseline: one flagship call, bare text (see
    module docstring for why chat() not chat_json, and why no system
    message). max_tokens=2048, not the client default 1024 -- several
    length_constraints:number_words prompts ask for several hundred words,
    which 1024 output tokens can plausibly truncate before completion."""
    start = time.monotonic()
    response, usage = client.chat(
        model=model,
        messages=[{"role": "user", "content": item.prompt}],
        role="single",
        thinking=thinking,
        temperature=0.3,
        max_tokens=2048,
    )
    strict = verify_all(response, item.instruction_id_list, item.kwargs)
    loose = verify_all_loose(response, item.instruction_id_list, item.kwargs)
    is_held_out_only = bool(item.instruction_id_list) and all(
        iid in HELD_OUT_INSTRUCTION_TYPES for iid in item.instruction_id_list
    )
    return {
        "arm": "single",
        "model": model,
        "key": item.key,
        "prompt": item.prompt,
        "response": response,
        "instruction_id_list": item.instruction_id_list,
        "is_held_out_only": is_held_out_only,
        "strict_followed": strict["strict_followed"],
        "loose_followed": loose["loose_followed"],
        "per_instruction_strict": strict["per_instruction"],
        "per_instruction_loose": loose["per_instruction"],
        "calls": [usage.model_dump()],
        "latency_s": time.monotonic() - start,
    }


async def _run_single_one(client: QwenClient, item: IFEvalItem, semaphore: asyncio.Semaphore, model: str, thinking: bool):
    result = await _attempt_with_retries("single", item, semaphore, lambda: solve_single_ifeval(client, item, model, thinking))
    if result is not None:
        log.info(
            "key=%s [single]: strict=%s loose=%s held_out_only=%s (%d instructions)",
            item.key, result["strict_followed"], result["loose_followed"],
            result["is_held_out_only"], len(item.instruction_id_list),
        )
    return result


def _subset_metrics(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0, "strict_accuracy": 0.0, "loose_accuracy": 0.0}
    strict_n = sum(1 for r in rows if r["strict_followed"])
    loose_n = sum(1 for r in rows if r["loose_followed"])
    return {"n": n, "strict_accuracy": strict_n / n, "loose_accuracy": loose_n / n}


def _family_breakdown(rows: list[dict]) -> dict:
    """Per-instruction-type accuracy, aggregated across every occurrence of
    that instruction id in the scored rows (a prompt with 2 instructions of
    the same family contributes 2 to that family's n) -- same denominator
    convention as benchmark/results/ifeval_scorer_validation.md's recall
    table."""
    strict_counts: dict[str, list[int]] = {}
    loose_counts: dict[str, list[int]] = {}
    for row in rows:
        for r in row["per_instruction_strict"]:
            c = strict_counts.setdefault(r["instruction_id"], [0, 0])
            c[0] += int(r["followed"])
            c[1] += 1
        for r in row["per_instruction_loose"]:
            c = loose_counts.setdefault(r["instruction_id"], [0, 0])
            c[0] += int(r["followed"])
            c[1] += 1

    families = {}
    for iid in sorted(set(strict_counts) | set(loose_counts)):
        s_correct, s_n = strict_counts.get(iid, (0, 0))
        l_correct, l_n = loose_counts.get(iid, (0, 0))
        families[iid] = {
            "n": s_n,
            "strict_accuracy": (s_correct / s_n) if s_n else 0.0,
            "loose_accuracy": (l_correct / l_n) if l_n else 0.0,
            "held_out": iid in HELD_OUT_INSTRUCTION_TYPES,
        }
    return families


def compute_summary(rows: list[dict]) -> dict:
    """rows: the list of solve_single_ifeval-shaped dicts (or the panel
    arm's equivalent, once/if it exists) actually scored. held_out_subset
    (the HEADLINE metric, see module docstring) is computed over ONLY the
    rows whose entire instruction_id_list is a subset of
    HELD_OUT_INSTRUCTION_TYPES -- never over the full row set filtered some
    other way, and never including a row that mixes a held-out type with an
    in-domain one (that row's outcome could still be driven by the
    in-domain constraint, which would contaminate the headline cohort)."""
    held_out_rows = [r for r in rows if r["is_held_out_only"]]
    return {
        "n_total": len(rows),
        "full_vocabulary": _subset_metrics(rows),
        "held_out_subset": {
            **_subset_metrics(held_out_rows),
            "note": (
                "HEADLINE METRIC (docs/capability-roadmap.md MAJOR 3 anti-gaming control) -- "
                "prompts whose entire instruction_id_list is drawn from "
                "ifeval_verify.HELD_OUT_INSTRUCTION_TYPES, the 8/25 instruction types no "
                "extractor/repair loop may ever target. full_vocabulary above is the "
                "in-domain ceiling, reported separately, not the headline."
            ),
        },
        "per_instruction_family": _family_breakdown(rows),
    }


async def main(n: int, seed: int, concurrency: int, out_path: Path, model: str, thinking: bool, arm: str) -> None:
    if arm == "panel":
        raise NotImplementedError(PANEL_ARM_NOT_IMPLEMENTED)

    items = load_ifeval_set(n=n, seed=seed)
    log.info("Loaded %d IFEval items (seed=%d) -- arm=%s model=%s thinking=%s", len(items), seed, arm, model, thinking)

    client = QwenClient()
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [asyncio.ensure_future(_run_single_one(client, item, semaphore, model, thinking)) for item in items]
    rows = [r for r in await asyncio.gather(*tasks) if r is not None]

    dropped = len(items) - len(rows)
    if dropped:
        log.warning("%d/%d prompts dropped due to unrecoverable errors", dropped, len(items))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    log.info("Wrote %d per-prompt results to %s", len(rows), out_path)

    summary = compute_summary(rows)
    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("Wrote summary to %s", summary_path)

    fv, ho = summary["full_vocabulary"], summary["held_out_subset"]
    log.info(
        "SUMMARY n=%d full_vocabulary strict=%.1f%% loose=%.1f%% (n=%d) | "
        "HELD-OUT (headline) strict=%.1f%% loose=%.1f%% (n=%d)",
        summary["n_total"],
        100 * fv["strict_accuracy"], 100 * fv["loose_accuracy"], fv["n"],
        100 * ho["strict_accuracy"], 100 * ho["loose_accuracy"], ho["n"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=541,
                         help="541 = the full, published-comparable set (default). Use a smaller "
                              "value (e.g. 60, IFEval's own IF-2 gap-probe size) for a cheap probe.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--out", type=str, default="benchmark/results/ifeval_run.jsonl")
    parser.add_argument("--model", type=str, default=ORCHESTRATOR_MODEL)
    parser.add_argument("--no-thinking", action="store_true", help="disable thinking on the single-arm flagship call")
    parser.add_argument("--arm", choices=["single", "panel"], default="single",
                         help="'single' (default, fully implemented) or 'panel' (raises "
                              "NotImplementedError -- see PANEL_ARM_NOT_IMPLEMENTED / module docstring)")
    args = parser.parse_args()
    asyncio.run(main(args.n, args.seed, args.concurrency, Path(args.out), args.model, not args.no_thinking, args.arm))
