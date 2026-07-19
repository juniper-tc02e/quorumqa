"""Computes the headline benchmark numbers from a run_benchmark.py output
file: accuracy, cost/question, escalation rate, false-escalation rate, and
overturn-and-correct rate.

Usage:
    python -m benchmark.score benchmark/results/run.jsonl
"""

import argparse
import json
from pathlib import Path


def load_results(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _cost(record_side: dict) -> float:
    return sum(c["cost_usd"] for c in record_side["calls"])


def summarize(records: list[dict]) -> dict:
    n = len(records)
    if n == 0:
        raise ValueError("No records to summarize")

    baseline_correct = sum(r["baseline"]["correct"] for r in records)
    engine_correct = sum(r["engine"]["correct"] for r in records)
    baseline_cost = sum(_cost(r["baseline"]) for r in records)
    engine_cost = sum(_cost(r["engine"]) for r in records)

    escalated = [r["engine"] for r in records if r["engine"]["escalated"]]
    n_escalated = len(escalated)
    false_escalations = sum(1 for e in escalated if e["false_escalation"])
    overturns = [e for e in escalated if e["verdict"] and e["verdict"]["overturned_plurality"]]
    overturn_and_correct = sum(1 for e in overturns if e["correct"])

    sc5_present = all(r.get("self_consistency5") for r in records)

    summary = {
        "n_questions": n,
        "baseline_accuracy": baseline_correct / n,
        "engine_accuracy": engine_correct / n,
        "baseline_cost_usd": baseline_cost,
        "engine_cost_usd": engine_cost,
        "baseline_cost_per_question": baseline_cost / n,
        "engine_cost_per_question": engine_cost / n,
        "escalation_rate": n_escalated / n,
        "false_escalation_rate": (false_escalations / n_escalated) if n_escalated else None,
        "overturn_count": len(overturns),
        "overturn_and_correct_count": overturn_and_correct,
        "overturn_and_correct_rate": (overturn_and_correct / len(overturns)) if overturns else None,
    }
    if sc5_present:
        sc5_correct = sum(r["self_consistency5"]["correct"] for r in records)
        sc5_cost = sum(_cost(r["self_consistency5"]) for r in records)
        summary["self_consistency5_accuracy"] = sc5_correct / n
        summary["self_consistency5_cost_usd"] = sc5_cost
        summary["self_consistency5_cost_per_question"] = sc5_cost / n
    return summary


def render_markdown(summary: dict) -> str:
    lines = ["# QuorumQA Benchmark Results", ""]
    lines.append(f"- Questions: {summary['n_questions']}")
    lines.append(
        f"- Baseline (single flagship-tier call) accuracy: {summary['baseline_accuracy']:.1%}, "
        f"${summary['baseline_cost_per_question']:.5f}/question"
    )
    lines.append(
        f"- QuorumQA accuracy: {summary['engine_accuracy']:.1%}, "
        f"${summary['engine_cost_per_question']:.5f}/question"
    )
    if "self_consistency5_accuracy" in summary:
        lines.append(
            f"- Self-consistency@5 (stretch baseline) accuracy: {summary['self_consistency5_accuracy']:.1%}, "
            f"${summary['self_consistency5_cost_per_question']:.5f}/question"
        )
    lines.append(f"- Escalation rate (questions needing Skeptic/Verifier/Judge): {summary['escalation_rate']:.1%}")
    if summary["false_escalation_rate"] is not None:
        lines.append(
            f"- False-escalation rate (Judge invoked but only re-confirmed the plurality): "
            f"{summary['false_escalation_rate']:.1%}"
        )
    if summary["overturn_and_correct_rate"] is not None:
        lines.append(
            f"- Of {summary['overturn_count']} plurality overturns by the Judge, "
            f"{summary['overturn_and_correct_count']} were correct "
            f"({summary['overturn_and_correct_rate']:.1%})"
        )
    if summary["baseline_cost_per_question"] > 0:
        delta = summary["engine_cost_per_question"] - summary["baseline_cost_per_question"]
        lines.append(
            f"- QuorumQA cost delta vs baseline: {delta:+.5f} USD/question "
            f"({delta / summary['baseline_cost_per_question']:+.1%})"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=str, help="Path to a run.jsonl produced by run_benchmark.py")
    parser.add_argument("--out", type=str, default=None, help="Markdown output path (default: summary.md next to results)")
    args = parser.parse_args()

    results_path = Path(args.results)
    records = load_results(results_path)
    summary = summarize(records)
    markdown = render_markdown(summary)

    out_path = Path(args.out) if args.out else results_path.parent / "summary.md"
    out_path.write_text(markdown, encoding="utf-8")
    print(markdown)
