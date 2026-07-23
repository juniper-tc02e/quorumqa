"""Re-scores the CORRECTED router (src/quorumqa/engine/router.py, post
moo_m1_corrected_findings.md) against the EXISTING M1 blended-workload eval
data (benchmark/results/moo_m1_eval.jsonl) -- NO new paid API calls.

Every (item, profile) result the M1 eval already ran and recorded is reused
as-is; this script only recomputes WHICH profile the corrected route()
would pick for each of the 120 questions (a pure function of item.subject,
zero cost, zero latency), then looks up that profile's already-recorded
correct/tokens for the question -- exactly benchmark/run_moo_eval.py's
`analyze()`, reused unchanged, just fed a new routes file instead of a new
eval run.

Usage:
    python -m benchmark.rescore_moo_router
    python -m benchmark.rescore_moo_router --eval benchmark/results/moo_m1_eval.jsonl --old-routes benchmark/results/moo_m1_eval.routes.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from quorumqa.engine.router import route
from quorumqa.schemas import GPQAItem

from benchmark.run_moo_eval import analyze, print_report

DEFAULT_EVAL = Path("benchmark/results/moo_m1_eval.jsonl")
DEFAULT_OLD_ROUTES = Path("benchmark/results/moo_m1_eval.routes.json")
DEFAULT_NEW_ROUTES = Path("benchmark/results/moo_m1_eval.routes.corrected.json")
DEFAULT_SUMMARY = Path("benchmark/results/moo_m1_eval.routes.corrected.summary.json")


def build_corrected_routes(old_routes_path: Path, budget: str) -> dict:
    """Reads the ORIGINAL eval run's routes file (question_id/bucket/subject
    per question -- router decisions cost nothing, so this metadata is all
    that's needed) and recomputes routed_profile through the CORRECTED
    route(). A minimal GPQAItem is synthesized per question: route()'s
    heuristic path (use_classifier=False, the M1 eval's path) only reads
    item.subject, so question/choices/correct_letter are structurally
    required placeholders, never actually consulted."""
    old = json.loads(old_routes_path.read_text(encoding="utf-8"))
    new_routes = []
    for r in old["routes"]:
        item = GPQAItem(
            question_id=r["question_id"],
            question="",
            choices=["A", "B", "C", "D"],
            correct_letter="A",
            subject=r["subject"],
        )
        new_routes.append(
            {
                "question_id": r["question_id"],
                "bucket": r["bucket"],
                "subject": r["subject"],
                "routed_profile": route(item, budget=budget),
            }
        )
    return {"budget": budget, "routes": new_routes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", type=str, default=str(DEFAULT_EVAL))
    parser.add_argument("--old-routes", type=str, default=str(DEFAULT_OLD_ROUTES))
    parser.add_argument("--new-routes-out", type=str, default=str(DEFAULT_NEW_ROUTES))
    parser.add_argument("--summary-out", type=str, default=str(DEFAULT_SUMMARY))
    parser.add_argument("--budget", type=str, default="balanced")
    args = parser.parse_args()

    eval_path = Path(args.eval)
    old_routes_path = Path(args.old_routes)
    new_routes_path = Path(args.new_routes_out)
    summary_path = Path(args.summary_out)

    old_summary = json.loads(eval_path.with_suffix(".summary.json").read_text(encoding="utf-8")) if eval_path.with_suffix(".summary.json").exists() else None

    corrected = build_corrected_routes(old_routes_path, args.budget)
    new_routes_path.write_text(json.dumps(corrected, indent=2), encoding="utf-8")
    print(f"Wrote {len(corrected['routes'])} corrected-router decisions (budget={args.budget}) to {new_routes_path}")

    summary = analyze(eval_path, new_routes_path)
    print_report(summary)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote corrected-router re-score summary to {summary_path}")

    if old_summary is not None:
        print("\n=== OLD (R1) router vs CORRECTED router vs flat-best vs oracle ===")
        print(f"{'':22s} {'accuracy':>10s} {'avg_tokens':>12s}")
        print(f"{'OLD routed (R1)':22s} {old_summary['routed_accuracy']*100:9.1f}% {old_summary['routed_avg_tokens']:12.0f}")
        print(f"{'CORRECTED routed':22s} {summary['routed_accuracy']*100:9.1f}% {summary['routed_avg_tokens']:12.0f}")
        print(f"{'flat-best':22s} {summary['flat_best_accuracy']*100:9.1f}% {'--':>12s}  ({summary['flat_best_profile']})")
        print(f"{'oracle':22s} {summary['oracle_accuracy']*100:9.1f}% {'--':>12s}")
        cost_saving_vs_flat_best = None
        flat_best_tokens = summary["profile_avg_tokens"].get(summary["flat_best_profile"])
        if flat_best_tokens:
            cost_saving_vs_flat_best = (flat_best_tokens - summary["routed_avg_tokens"]) / flat_best_tokens * 100
            print(f"\nCorrected-router cost saving vs flat-best ({summary['flat_best_profile']}): {cost_saving_vs_flat_best:.1f}%")
        acc_delta_vs_old = (summary["routed_accuracy"] - old_summary["routed_accuracy"]) * 100
        cost_delta_vs_old = (old_summary["routed_avg_tokens"] - summary["routed_avg_tokens"]) / old_summary["routed_avg_tokens"] * 100
        print(f"Corrected router vs OLD (R1) router: {acc_delta_vs_old:+.1f}pt accuracy, {cost_delta_vs_old:+.1f}% cheaper")


if __name__ == "__main__":
    main()
