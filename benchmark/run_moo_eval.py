"""M1 blended-workload eval (docs/mixture-of-orchestrations-plan.md section 3
"ceiling analysis discipline", section 7 "M1 -- Router R1 + `single-call` +
blended-workload eval").

This is where the Mixture of Orchestrations thesis is tested: does
src/quorumqa/engine/router.py's route() beat the best single fixed profile
on a workload that mixes domains no single profile is validated across?

Assembles a blended workload from four existing loaders, tagged by the
domain-gap pattern each one represents (see benchmark/results/*_findings.md,
docs/improvement-loop-state.md's gap-lens table):
  - gpqa_hard          -- GPQA-Diamond (moderate gap, ~11% unanimous-wrong;
                           the domain thinking_gate/stem-max were validated on)
  - supergpqa_hard      -- SuperGPQA difficulty="hard" (large gap, 23%
                           unanimous-wrong; flagship_panel/rag_thinking_gate's
                           domain)
  - medqa               -- MedQA (tiny gap, 4% unanimous-wrong; the
                           cheap-tier-is-competent control case)
  - saturated_easy_mmlu -- MMLU-Pro restricted to the categories mmlu_pro_
                           findings.md measured as fully saturated (single-
                           call's domain: deliberation subtracts value here)

For EVERY item, runs EVERY REGISTRY profile (via quorumqa.engine.profiles.
run_profile, reused unchanged from M0) so flat-best and oracle can be
computed, plus records which profile the router picked -- since the routed
profile is always one of the seven already being run, "routed accuracy" is
looked up from that profile's own result for the item, at zero extra API
cost. This is the expensive part by design (n_per_bucket * 7 profiles calls,
each 1-9+ underlying chat calls) -- run ONCE at the capped size.

Usage:
    python -m benchmark.run_moo_eval --n-per-bucket 30 --seed 42 --concurrency 4
    python -m benchmark.run_moo_eval --analyze-only --in benchmark/results/moo_m1_eval.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path

from quorumqa.engine import profiles
from quorumqa.engine.router import BUDGETS, ROUTING_RULES, SATURATED_MMLU_PRO_CATEGORIES, route
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import GPQAItem, QuestionResult
from quorumqa.tools.mcp_client import verifier_tool_session

from benchmark.lever_experiments import build_rag_presolve_config, resolve_rag_db_path
from benchmark.load_gpqa import load_benchmark_set
from benchmark.load_medqa import load_medqa_set
from benchmark.load_mmlu_pro import load_mmlu_pro_set
from benchmark.load_supergpqa import load_supergpqa_set

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PROFILE_NAMES = list(profiles.REGISTRY.keys())

DEFAULT_OUT = Path("benchmark/results/moo_m1_eval.jsonl")


# ---------------------------------------------------------------------------
# Workload assembly
# ---------------------------------------------------------------------------


def _retag(item: GPQAItem, bucket: str) -> GPQAItem:
    """Bucket-prefix question_id so four independent loaders' ids can't
    collide once merged into one flat list (several loaders use a plain
    row index as question_id -- see load_medqa.py/load_gsm8k.py)."""
    return item.model_copy(update={"question_id": f"{bucket}:{item.question_id}"})


def assemble_blend(n_per_bucket: int, seed: int) -> dict[str, list[GPQAItem]]:
    gpqa_items = [_retag(it, "gpqa_hard") for it in load_benchmark_set(n=n_per_bucket, seed=seed)]

    supergpqa_items = [
        _retag(it, "supergpqa_hard")
        for it in load_supergpqa_set(n=n_per_bucket, seed=seed, difficulty="hard")
    ]

    medqa_items = [_retag(it, "medqa") for it in load_medqa_set(n=n_per_bucket, seed=seed)]

    # Saturated-easy: load_mmlu_pro_set only filters to ONE category at a
    # time, but we want the whole safe set (router.SATURATED_MMLU_PRO_
    # CATEGORIES -- the categories mmlu_pro_findings.md's per-category
    # breakdown measured as fully saturated, excluding the three that
    # regressed). Draw a wider flat pool, filter client-side, same seed so
    # it stays reproducible.
    mmlu_pool = load_mmlu_pro_set(n=n_per_bucket * 8, seed=seed, category=None)
    saturated_items = [it for it in mmlu_pool if it.subject in SATURATED_MMLU_PRO_CATEGORIES][:n_per_bucket]
    if len(saturated_items) < n_per_bucket:
        log.warning(
            "saturated_easy_mmlu bucket short: wanted %d, got %d from an n=%d pool -- "
            "widen the pool multiplier if this recurs",
            n_per_bucket, len(saturated_items), n_per_bucket * 8,
        )
    saturated_items = [_retag(it, "saturated_easy_mmlu") for it in saturated_items]

    blend = {
        "gpqa_hard": gpqa_items,
        "supergpqa_hard": supergpqa_items,
        "medqa": medqa_items,
        "saturated_easy_mmlu": saturated_items,
    }
    for bucket, items in blend.items():
        log.info("bucket %s: %d items", bucket, len(items))
    return blend


# ---------------------------------------------------------------------------
# Run: every (item, profile) pair
# ---------------------------------------------------------------------------


async def _run_one(client, tool_session, rag, bucket, item, profile_name, semaphore):
    profile = profiles.REGISTRY[profile_name]
    try:
        async with semaphore:
            result: QuestionResult = await profiles.run_profile(client, tool_session, item, profile, rag=rag)
    except Exception:
        log.exception("%s [%s] profile=%s: DROPPED", item.question_id, item.subject, profile_name)
        return None
    log.info(
        "%s [%s] profile=%s: final=%s(%s) escalated=%s tokens=%d",
        item.question_id, item.subject, profile_name,
        result.final_letter, "correct" if result.correct else "wrong",
        result.escalated, result.total_tokens,
    )
    return {
        "question_id": item.question_id,
        "bucket": bucket,
        "subject": item.subject,
        "profile": profile_name,
        "correct": result.correct,
        "escalated": result.escalated,
        "total_tokens": result.total_tokens,
        "latency_s": result.latency_s,
        "result": result.model_dump(),
    }


async def run_eval(n_per_bucket: int, seed: int, concurrency: int, out_path: Path, budget: str) -> Path:
    profiles.set_benchmark_mode(True)  # plan section 5: benchmark firewall, memory OFF

    blend = assemble_blend(n_per_bucket, seed)
    all_items = [(bucket, item) for bucket, items in blend.items() for item in items]
    log.info("Blended workload: %d items across %d buckets, x %d profiles = %d run_profile calls",
              len(all_items), len(blend), len(PROFILE_NAMES), len(all_items) * len(PROFILE_NAMES))

    rag = build_rag_presolve_config(resolve_rag_db_path())
    client = QwenClient()
    semaphore = asyncio.Semaphore(concurrency)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_written = 0
    async with verifier_tool_session() as tool_session:
        tasks = [
            asyncio.ensure_future(_run_one(client, tool_session, rag, bucket, item, profile_name, semaphore))
            for bucket, item in all_items
            for profile_name in PROFILE_NAMES
        ]
        with out_path.open("w", encoding="utf-8") as f:
            for coro in asyncio.as_completed(tasks):
                record = await coro
                if record is not None:
                    f.write(json.dumps(record) + "\n")
                    f.flush()
                    n_written += 1

    log.info("Wrote %d/%d (item, profile) records to %s", n_written, len(tasks), out_path)

    # Router decisions are pure functions of (item, budget) -- no API cost --
    # recorded in a companion file so analyze() doesn't need the items again.
    routes_path = out_path.with_suffix(".routes.json")
    route_records = [
        {"question_id": item.question_id, "bucket": bucket, "subject": item.subject,
         "routed_profile": route(item, budget=budget)}
        for bucket, item in all_items
    ]
    routes_path.write_text(json.dumps({"budget": budget, "routes": route_records}, indent=2), encoding="utf-8")
    log.info("Wrote %d router decisions (budget=%s) to %s", len(route_records), budget, routes_path)

    return out_path


# ---------------------------------------------------------------------------
# Analysis: flat-best / routed / oracle, cost, per-bucket routing-vs-oracle
# ---------------------------------------------------------------------------


def load_results(jsonl_path: Path) -> dict[str, dict[str, dict]]:
    """question_id -> {profile_name -> record}."""
    by_question: dict[str, dict[str, dict]] = defaultdict(dict)
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_question[rec["question_id"]][rec["profile"]] = rec
    return by_question


def load_routes(routes_path: Path) -> tuple[str, dict[str, str]]:
    data = json.loads(routes_path.read_text(encoding="utf-8"))
    routed = {r["question_id"]: r["routed_profile"] for r in data["routes"]}
    return data["budget"], routed


def analyze(jsonl_path: Path, routes_path: Path) -> dict:
    by_question = load_results(jsonl_path)
    budget, routed_profile = load_routes(routes_path)

    # bucket/subject metadata: recover from any one profile's record per question
    meta = {}
    for qid, per_profile in by_question.items():
        any_rec = next(iter(per_profile.values()))
        meta[qid] = {"bucket": any_rec["bucket"], "subject": any_rec["subject"]}

    all_qids = set(by_question)
    drop_counts = {p: 0 for p in PROFILE_NAMES}
    for qid in all_qids:
        for p in PROFILE_NAMES:
            if p not in by_question[qid]:
                drop_counts[p] += 1

    # Apples-to-apples: the intersection of questions where EVERY profile
    # AND the router's own chosen profile completed (project convention --
    # see supergpqa_findings.md's "apples-to-apples on N common items").
    common_qids = sorted(
        qid for qid in all_qids
        if all(p in by_question[qid] for p in PROFILE_NAMES) and qid in routed_profile
    )
    n_common = len(common_qids)

    per_profile_correct = {p: 0 for p in PROFILE_NAMES}
    per_profile_tokens = {p: 0 for p in PROFILE_NAMES}
    routed_correct = 0
    routed_tokens = 0
    oracle_correct = 0
    routing_hit = 0
    routing_miss = 0

    per_bucket = defaultdict(lambda: {
        "n": 0,
        "profile_correct": {p: 0 for p in PROFILE_NAMES},
        "routed_correct": 0,
        "oracle_correct": 0,
        "routed_profile_counts": Counter(),
        "routing_hit": 0,
        "routing_miss": 0,
    })

    for qid in common_qids:
        bucket = meta[qid]["bucket"]
        b = per_bucket[bucket]
        b["n"] += 1

        any_correct = False
        for p in PROFILE_NAMES:
            rec = by_question[qid][p]
            per_profile_tokens[p] += rec["total_tokens"]
            if rec["correct"]:
                per_profile_correct[p] += 1
                b["profile_correct"][p] += 1
                any_correct = True
        if any_correct:
            oracle_correct += 1
            b["oracle_correct"] += 1

        chosen = routed_profile[qid]
        b["routed_profile_counts"][chosen] += 1
        chosen_rec = by_question[qid][chosen]
        routed_tokens += chosen_rec["total_tokens"]
        if chosen_rec["correct"]:
            routed_correct += 1
            b["routed_correct"] += 1
            if any_correct:
                routing_hit += 1
                b["routing_hit"] += 1
        else:
            if any_correct:
                routing_miss += 1
                b["routing_miss"] += 1

    profile_accuracy = {p: (per_profile_correct[p] / n_common if n_common else 0.0) for p in PROFILE_NAMES}
    profile_avg_tokens = {p: (per_profile_tokens[p] / n_common if n_common else 0.0) for p in PROFILE_NAMES}
    flat_best_profile = max(profile_accuracy, key=profile_accuracy.get) if n_common else None
    flat_best_accuracy = profile_accuracy.get(flat_best_profile, 0.0)

    routed_accuracy = routed_correct / n_common if n_common else 0.0
    oracle_accuracy = oracle_correct / n_common if n_common else 0.0
    routed_avg_tokens = routed_tokens / n_common if n_common else 0.0

    bucket_summary = {}
    for bucket, b in per_bucket.items():
        n = b["n"]
        bucket_summary[bucket] = {
            "n": n,
            "profile_accuracy": {p: (b["profile_correct"][p] / n if n else 0.0) for p in PROFILE_NAMES},
            "routed_accuracy": (b["routed_correct"] / n if n else 0.0),
            "oracle_accuracy": (b["oracle_correct"] / n if n else 0.0),
            "routed_profile_counts": dict(b["routed_profile_counts"]),
            "routing_hit": b["routing_hit"],
            "routing_miss": b["routing_miss"],
        }

    return {
        "budget": budget,
        "n_common": n_common,
        "n_total_distinct_questions": len(all_qids),
        "drop_counts": drop_counts,
        "profile_accuracy": profile_accuracy,
        "profile_avg_tokens": profile_avg_tokens,
        "flat_best_profile": flat_best_profile,
        "flat_best_accuracy": flat_best_accuracy,
        "routed_accuracy": routed_accuracy,
        "routed_avg_tokens": routed_avg_tokens,
        "oracle_accuracy": oracle_accuracy,
        "routing_hit": routing_hit,
        "routing_miss": routing_miss,
        "bucket_summary": bucket_summary,
    }


def print_report(summary: dict) -> None:
    print(f"\n=== MoO M1 blended-workload eval (budget={summary['budget']}) ===")
    print(f"n_common (apples-to-apples, all 7 profiles + router complete) = {summary['n_common']} "
          f"of {summary['n_total_distinct_questions']} distinct questions")
    print("drops per profile:", summary["drop_counts"])

    print("\n-- per-profile accuracy (n_common) + avg tokens/item --")
    for p in PROFILE_NAMES:
        print(f"  {p:20s} acc={summary['profile_accuracy'][p]*100:5.1f}%  "
              f"avg_tokens={summary['profile_avg_tokens'][p]:8.0f}")

    print(f"\nflat-best  = {summary['flat_best_profile']:20s} {summary['flat_best_accuracy']*100:5.1f}%")
    print(f"routed     = {'router':20s} {summary['routed_accuracy']*100:5.1f}%  "
          f"avg_tokens={summary['routed_avg_tokens']:8.0f}")
    print(f"oracle     = {'per-item best':20s} {summary['oracle_accuracy']*100:5.1f}%")
    denom = (summary["oracle_accuracy"] - summary["flat_best_accuracy"])
    if abs(denom) > 1e-9:
        pct_of_gap = (summary["routed_accuracy"] - summary["flat_best_accuracy"]) / denom * 100
        print(f"routed closes {pct_of_gap:.1f}% of the flat-best -> oracle gap")
    print(f"routing_hit={summary['routing_hit']}  routing_miss={summary['routing_miss']} "
          "(miss = oracle had a correct option, router picked a wrong one)")

    print("\n-- per-bucket --")
    for bucket, b in summary["bucket_summary"].items():
        print(f"\n  [{bucket}] n={b['n']}")
        for p in PROFILE_NAMES:
            print(f"    {p:20s} {b['profile_accuracy'][p]*100:5.1f}%")
        print(f"    {'routed':20s} {b['routed_accuracy']*100:5.1f}%  "
              f"router picked: {b['routed_profile_counts']}")
        print(f"    {'oracle':20s} {b['oracle_accuracy']*100:5.1f}%")
        print(f"    routing_hit={b['routing_hit']} routing_miss={b['routing_miss']}")


def print_rules_table() -> None:
    print("\n=== Router rules table ===")
    for rule in ROUTING_RULES:
        print(f"- bucket={rule.bucket}")
        print(f"  match: {rule.match}")
        print(f"  profile_by_budget: {rule.profile_by_budget}")
        print(f"  finding: {rule.finding}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-per-bucket", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--budget", type=str, default="balanced", choices=BUDGETS)
    parser.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--analyze-only", action="store_true", help="Skip the run; analyze an existing --out/.routes.json pair")
    args = parser.parse_args()

    out_path = Path(args.out)
    routes_path = out_path.with_suffix(".routes.json")

    print_rules_table()

    if not args.analyze_only:
        asyncio.run(run_eval(args.n_per_bucket, args.seed, args.concurrency, out_path, args.budget))

    summary = analyze(out_path, routes_path)
    print_report(summary)

    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("Wrote summary to %s", summary_path)


if __name__ == "__main__":
    main()
