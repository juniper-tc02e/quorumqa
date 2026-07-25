"""S1/S2/S3 offline analysis (docs/experiment-spec-book.md section 2): reads
ONE diversified_panel or cycled_panel harvest JSONL (written by
`python -m benchmark.lever_experiments --lever diversified_panel
--n-solvers 15 --no-tribunal ...`, see that module's docstring) and derives
the entire odd-N curve (N = 3, 5, 7, ..., up to the logged panel size) by
NESTED-PREFIX SUBSAMPLING of each item's ordered `seat_answers` -- no
re-running, no additional API calls. This is section 2.3's "one run buys
the whole curve" trick, on the consuming side.

For each odd N this reports:
  - plurality accuracy@N       -- fraction of items where the first N
                                   seats' plurality letter (Counter.
                                   most_common(1) tie-break, matching
                                   benchmark.lever_experiments._plurality)
                                   equals the gold letter.
  - coverage@N (any-seat-correct) -- fraction of items where AT LEAST ONE
                                   of the first N seats' letter equals gold.
  - unanimous-wrong rate@N     -- fraction of ALL items where the first N
                                   seats unanimously agree on a WRONG
                                   letter (the joint rate, matching this
                                   repo's existing convention -- see
                                   docs/improvement-loop-state.md's
                                   per-benchmark "Unan-wrong" column, e.g.
                                   SuperGPQA-hard 23% -- NOT the ~61.6%
                                   conditional "share of wrong items that
                                   are unanimous" figure quoted elsewhere in
                                   docs/experiment-spec-book.md, which is a
                                   different quantity).
  - paired discordant counts (b, c) vs N=3, plus the exact one-sided
    McNemar p-value on those counts, using the SAME items at both N (this
    is a within-run, same-item pairing -- not a cross-run join). b = items
    the plurality gets right at N that it got wrong at N=3 (a "gain"); c =
    the reverse (a "loss"). p tests whether b significantly exceeds c under
    the null P(gain)=P(loss)=0.5 among the b+c discordant items -- the
    exact convention docs/experiment-spec-book.md section 1 pins down
    (+3 discordant, zero losses -> p=0.125; +4 -> p=0.0625; +5 -> p=0.03125,
    the minimum that clears p<0.05).

It also runs the benchmark.escalation_policies sweep (S3) at every N and
prints the (policy, threshold, N) table (escalation rate + recall of
plurality-wrong items).

`--bootstrap` puts a CI on the prefix estimator by resampling SEAT ORDER:
each item's seat_answers order is an artifact of generation, not a
meaningful ranking, so which N seats end up in a "first N" prefix is
arbitrary. Each bootstrap draw independently shuffles every item's seat
list before taking the first-N prefix, recomputes plurality accuracy@N
across all items, and repeats `--n-bootstrap` times; the reported CI is the
2.5/97.5 percentile of that distribution.

Usage:
    python -m benchmark.analyze_panel_scaling --in benchmark/results/lever_diversified_panel_supergpqa_seed42.jsonl
    python -m benchmark.analyze_panel_scaling --in benchmark/results/lever_cycled_panel_supergpqa_seed42.jsonl --bootstrap --n-bootstrap 500
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import Counter
from pathlib import Path

from benchmark import escalation_policies as ep

RESULTS_DIR = Path(__file__).resolve().parent / "results"


# ---------------------------------------------------------------------------
# Loading + item-level helpers
# ---------------------------------------------------------------------------


def load_panel_rows(path: "str | Path") -> list[dict]:
    """Reads a diversified_panel/cycled_panel harvest JSONL. Rows without a
    `seat_answers` field (i.e. not written by one of those two levers) are
    skipped rather than raising -- a harvest file is never expected to mix
    lever types, but skipping instead of crashing keeps this tolerant of a
    stray blank line or an unrelated row someone appended by hand."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("seat_answers"):
                rows.append(row)
    return rows


def gold_letter(row: dict) -> str:
    return row["engine"]["item"]["correct_letter"]


def question_id(row: dict) -> str:
    return row["engine"]["item"]["question_id"]


def ordered_seats(row: dict) -> list[dict]:
    """seat_answers sorted by seat_index -- defensive against a caller (or
    a hand-edited fixture) that doesn't preserve JSON array order."""
    return sorted(row["seat_answers"], key=lambda s: s["seat_index"])


def prefix_votes(row: dict, n: int) -> list[str]:
    """The nested-prefix subsample: the first N seats' letters, in
    generation order. Every intermediate N's vote vector for a given item
    is a strict prefix of every larger N's -- this is what "nested" means
    here, and it's what makes N=3's items directly comparable to N=15's via
    McNemar (same items, same seat identities up to N=3, just more seats
    added on top)."""
    seats = ordered_seats(row)
    if n > len(seats):
        raise ValueError(f"requested prefix N={n} exceeds logged panel size {len(seats)} for {question_id(row)!r}")
    return [s["letter"] for s in seats[:n]]


def plurality(votes: list[str]) -> tuple[str, bool]:
    """Same tie-break as benchmark.lever_experiments._plurality and
    escalation_policies.plurality_letter (Counter.most_common(1)[0])."""
    counts = Counter(votes)
    top_letter, top_count = counts.most_common(1)[0]
    return top_letter, top_count == len(votes)


def odd_ns_up_to(max_n: int) -> list[int]:
    return list(range(3, max_n + 1, 2))


def max_panel_size(rows: list[dict]) -> int:
    return min(len(row["seat_answers"]) for row in rows)


# ---------------------------------------------------------------------------
# Per-N metrics
# ---------------------------------------------------------------------------


def metrics_at_n(rows: list[dict], n: int) -> dict:
    """plurality accuracy@N, coverage@N, unanimous-wrong rate@N, plus a
    per-item record (keyed by question_id) other analyses (McNemar,
    escalation sweep) reuse instead of recomputing votes/plurality."""
    n_items = len(rows)
    n_plurality_correct = 0
    n_coverage = 0
    n_unanimous_wrong = 0
    per_item = {}
    for row in rows:
        votes = prefix_votes(row, n)
        gold = gold_letter(row)
        top_letter, unanimous = plurality(votes)
        plurality_correct = top_letter == gold
        coverage_correct = gold in votes
        if plurality_correct:
            n_plurality_correct += 1
        if coverage_correct:
            n_coverage += 1
        if unanimous and not plurality_correct:
            n_unanimous_wrong += 1
        per_item[question_id(row)] = {
            "votes": votes,
            "gold": gold,
            "plurality_letter": top_letter,
            "plurality_correct": plurality_correct,
            "coverage_correct": coverage_correct,
            "unanimous": unanimous,
        }
    return {
        "n": n,
        "n_items": n_items,
        "plurality_accuracy": (n_plurality_correct / n_items) if n_items else None,
        "coverage": (n_coverage / n_items) if n_items else None,
        "unanimous_wrong_rate": (n_unanimous_wrong / n_items) if n_items else None,
        "per_item": per_item,
    }


# ---------------------------------------------------------------------------
# Paired McNemar vs the N=3 baseline
# ---------------------------------------------------------------------------


def mcnemar_exact_one_sided(b: int, c: int) -> float:
    """Exact one-sided McNemar p-value testing b > c (b = gains, c =
    losses, among the b+c discordant pairs), under the null P(gain)=0.5.
    p = P(X <= c | X ~ Binomial(n=b+c, 0.5)) -- matches docs/experiment-
    spec-book.md section 1's pre-registered convention exactly: (b=3,c=0)
    -> 0.125, (b=4,c=0) -> 0.0625, (b=5,c=0) -> 0.03125 (the minimum that
    clears p<0.05 with zero losses)."""
    n = b + c
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(0, c + 1)) * (0.5 ** n)


def paired_discordant(per_item_baseline: dict, per_item_n: dict) -> tuple[int, int]:
    """b = correct at N (the candidate) but wrong at the baseline (a gain);
    c = correct at the baseline but wrong at N (a loss). Only items present
    in BOTH per_item dicts are counted (they always are here -- both come
    from the same `rows`, just different N -- but the guard keeps this
    function honest if it's ever handed two different item sets)."""
    b = c = 0
    for qid, baseline_rec in per_item_baseline.items():
        n_rec = per_item_n.get(qid)
        if n_rec is None:
            continue
        baseline_correct = baseline_rec["plurality_correct"]
        n_correct = n_rec["plurality_correct"]
        if n_correct and not baseline_correct:
            b += 1
        elif baseline_correct and not n_correct:
            c += 1
    return b, c


# ---------------------------------------------------------------------------
# Bootstrap CI on the prefix estimator (resamples seat ORDER)
# ---------------------------------------------------------------------------


def bootstrap_prefix_accuracy(rows: list[dict], n: int, n_bootstrap: int = 200, seed: int = 0) -> dict:
    """Seat order within seat_answers is an artifact of generation, not a
    meaningful ranking, so "the first N seats" is one arbitrary draw out of
    C(panel_size, N) possible subsets (well, one arbitrary ORDERING out of
    panel_size! -- prefixes of a shuffled order approximate a random subset
    without replacement). Each bootstrap iteration independently shuffles
    every item's own seat list, takes the first N, and recomputes plurality
    accuracy across all items; the reported CI is the empirical 2.5/97.5
    percentile of `n_bootstrap` such draws."""
    rng = random.Random(seed)
    if not rows:
        return {"mean": None, "ci_low": None, "ci_high": None, "n_bootstrap": n_bootstrap}
    samples = []
    for _ in range(n_bootstrap):
        n_correct = 0
        for row in rows:
            seats = list(row["seat_answers"])
            rng.shuffle(seats)
            votes = [s["letter"] for s in seats[:n]]
            top_letter, _unanimous = plurality(votes)
            if top_letter == gold_letter(row):
                n_correct += 1
        samples.append(n_correct / len(rows))
    samples.sort()
    lo_idx = int(0.025 * len(samples))
    hi_idx = min(len(samples) - 1, int(0.975 * len(samples)))
    return {
        "mean": statistics.mean(samples),
        "ci_low": samples[lo_idx],
        "ci_high": samples[hi_idx],
        "n_bootstrap": n_bootstrap,
    }


# ---------------------------------------------------------------------------
# Escalation-policy sweep (S3), replayed at every N
# ---------------------------------------------------------------------------


def escalation_sweep_at_n(rows: list[dict], n: int) -> list[dict]:
    items = [(prefix_votes(row, n), gold_letter(row)) for row in rows]
    table = ep.sweep_all_policies(items)
    for entry in table:
        entry["n"] = n
    return table


def escalation_sweep_table(rows: list[dict], ns: list[int]) -> list[dict]:
    table = []
    for n in ns:
        table.extend(escalation_sweep_at_n(rows, n))
    return table


# ---------------------------------------------------------------------------
# Top-level analysis + reporting
# ---------------------------------------------------------------------------


def analyze(
    path: "str | Path", bootstrap: bool = False, n_bootstrap: int = 200, bootstrap_seed: int = 0,
) -> dict:
    rows = load_panel_rows(path)
    if not rows:
        raise ValueError(
            f"no diversified_panel/cycled_panel rows (rows carrying `seat_answers`) found in {path} -- "
            f"wrong lever, or the file is empty."
        )
    max_n = max_panel_size(rows)
    if max_n < 3:
        raise ValueError(f"logged panel size {max_n} < 3 -- nothing to analyze (need at least N=3).")
    ns = odd_ns_up_to(max_n)

    metrics = {n: metrics_at_n(rows, n) for n in ns}
    baseline_n = 3
    baseline = metrics[baseline_n]

    mcnemar_vs_n3 = {}
    for n in ns:
        if n == baseline_n:
            continue
        b, c = paired_discordant(baseline["per_item"], metrics[n]["per_item"])
        mcnemar_vs_n3[n] = {"b": b, "c": c, "p_one_sided": mcnemar_exact_one_sided(b, c)}

    escalation_table = escalation_sweep_table(rows, ns)

    bootstrap_results = None
    if bootstrap:
        bootstrap_results = {n: bootstrap_prefix_accuracy(rows, n, n_bootstrap, bootstrap_seed) for n in ns}

    return {
        "path": str(path),
        "n_items": len(rows),
        "max_n": max_n,
        "ns": ns,
        "metrics": metrics,
        "mcnemar_vs_n3": mcnemar_vs_n3,
        "escalation_table": escalation_table,
        "bootstrap": bootstrap_results,
    }


def _fmt_pct(x):
    return "n/a" if x is None else f"{x * 100:.1f}%"


def print_report(analysis: dict) -> None:
    print(f"panel-scaling analysis: {analysis['path']}")
    print(f"  n_items={analysis['n_items']} max_n={analysis['max_n']} ns={analysis['ns']}")
    print()
    print(f"{'N':>4} {'plurality_acc':>14} {'coverage':>10} {'unan_wrong_rate':>16} {'b':>4} {'c':>4} {'p(one-sided)':>13}")
    for n in analysis["ns"]:
        m = analysis["metrics"][n]
        if n == 3:
            b_str = c_str = p_str = "(baseline)"
        else:
            mc = analysis["mcnemar_vs_n3"][n]
            b_str, c_str, p_str = str(mc["b"]), str(mc["c"]), f"{mc['p_one_sided']:.4f}"
        print(f"{n:>4} {_fmt_pct(m['plurality_accuracy']):>14} {_fmt_pct(m['coverage']):>10} "
              f"{_fmt_pct(m['unanimous_wrong_rate']):>16} {b_str:>4} {c_str:>4} {p_str:>13}")

    if analysis["bootstrap"]:
        print()
        print("bootstrap CI on plurality accuracy@N (seat-order resampled):")
        for n in analysis["ns"]:
            bs = analysis["bootstrap"][n]
            print(f"  N={n}: mean={_fmt_pct(bs['mean'])} CI=[{_fmt_pct(bs['ci_low'])}, {_fmt_pct(bs['ci_high'])}] "
                  f"(n_bootstrap={bs['n_bootstrap']})")

    print()
    print("escalation policy sweep (S3):")
    print(f"{'N':>4} {'policy':>24} {'threshold':>10} {'esc_rate':>9} {'recall':>8} {'n_wrong':>8}")
    for entry in analysis["escalation_table"]:
        threshold_str = "-" if entry["threshold"] is None else f"{entry['threshold']}"
        recall_str = "n/a" if entry["recall"] is None else f"{entry['recall'] * 100:.1f}%"
        print(f"{entry['n']:>4} {entry['policy']:>24} {threshold_str:>10} "
              f"{_fmt_pct(entry['escalation_rate']):>9} {recall_str:>8} {entry['n_wrong']:>8}")


def _json_default(obj):
    if isinstance(obj, set):
        return sorted(obj)
    return str(obj)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_path", required=True, help="diversified_panel/cycled_panel harvest JSONL path")
    parser.add_argument("--out", type=str, default=None, help="optional path to write the full analysis as JSON")
    parser.add_argument("--bootstrap", action="store_true", help="put a CI on plurality accuracy@N by resampling seat order")
    parser.add_argument("--n-bootstrap", type=int, default=200)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    args = parser.parse_args()

    result = analyze(args.in_path, bootstrap=args.bootstrap, n_bootstrap=args.n_bootstrap, bootstrap_seed=args.bootstrap_seed)
    print_report(result)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=_json_default)
        print(f"\nWrote full analysis to {out_path}")
