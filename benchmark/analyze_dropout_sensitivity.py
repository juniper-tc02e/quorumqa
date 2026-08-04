"""Every headline, recomputed with non-completions counted as failures.

WHY THIS EXISTS. An external review on 2026-08-03 made a point this repo had
the evidence for and had not acted on: every published paired figure is a
COMPLETE-CASE analysis. An item enters the comparison only if every arm
returned something. But this repo *itself* establishes that drops are
504/timeout-correlated and concentrate on long-generation items -- it says so
in the drop note printed by every verifier -- so the missingness is not random.

For a deployed system, "no answer before the timeout" is a failure, not a
missing observation. Under that reading the arm that times out more should be
penalised, not excused. Two headline conclusions reverse:

    TB-1 A vs C   complete-case  net -6   ->  timeout-as-failure  net +1
    SuperGPQA     complete-case  net +7   ->  timeout-as-failure  net -4

Neither reading is automatically correct. Complete-case answers "when both arms
answer, which is better?"; timeout-as-failure answers "deployed, which is
better?". The honest position is that a claim which flips between them is not
robust, and must be reported with both.

A SEPARATE ERROR THE SAME REVIEW CAUGHT. A large one-sided p for "A beats B" is
not evidence that B beats A. TB-1's A-vs-C carried p = 0.9807 and was written up
as "sampling is measurably better" -- but the test of that claim is the REVERSE
one-sided p, which is 0.0730 complete-case and 0.6682 under timeout-as-failure.
Neither clears 0.05. This module therefore prints BOTH directions for every
comparison, so the asymmetry cannot be read off one number again.

CLUSTERING, reported not corrected. GPQA's three seeds are drawn from a
~198-question set, so the 256 paired observations cover only 164 unique
questions -- 81 ids recur. McNemar assumes independent pairs. The repo already
quotes a de-duplicated figure for universal_gate's +25 (+21 counting each item
once); the same caveat applies to every pooled GPQA figure here, and the unique
count is printed alongside n.

    python -m benchmark.analyze_dropout_sensitivity

Offline. Reads committed run files, no API calls.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter
from pathlib import Path

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

RESULTS = Path(__file__).resolve().parent / "results"

#: (label, arm-x glob, arm-y glob, intended items per seed)
#: Intended n matters: an arm that drops an item and an arm that never attempted
#: it are different things, and only the intended count exposes the first.
COMPARISONS = [
    ("TB-1  stack vs SC@5 (compute-matched)",
     "lever_universal_gate_gpqa_seed{s}.jsonl",
     "TB1_flagship_sc5_gpqa_seed{s}.jsonl",
     (1001, 2311, 3407), 90),
    ("TB-1  stack vs one flagship call",
     "lever_universal_gate_gpqa_seed{s}.jsonl",
     "TB1_flagship1x_gpqa_seed{s}.jsonl",
     (1001, 2311, 3407), 90),
    ("TB-1  SC@5 vs one flagship call",
     "TB1_flagship_sc5_gpqa_seed{s}.jsonl",
     "TB1_flagship1x_gpqa_seed{s}.jsonl",
     (1001, 2311, 3407), 90),
    ("SuperGPQA  flagship_panel vs one call",
     "lever_flagship_panel_supergpqa_seed{s}.jsonl",
     "lever_baseline_supergpqa_seed{s}.jsonl",
     (7, 42, 123), 90),
]


#: The committed, stripped per-item table. Preferred over the raw runs so this
#: analysis works on a fresh clone -- verified to give byte-identical b/c/net/p.
OUTCOMES_CSV = RESULTS / "per_item_outcomes.csv"
_CSV_CACHE: dict | None = None


def _csv_outcomes(arm: str, seed: int) -> dict[str, bool] | None:
    """question_id -> correct, from the COMMITTED table.

    Returns None if the table is absent, so the caller falls back to the raw
    runs. Only `completed` rows are outcomes; a drop is an absence here exactly
    as it is in the raw files, which is what makes the two paths agree.
    """
    global _CSV_CACHE
    if _CSV_CACHE is None:
        if not OUTCOMES_CSV.exists():
            _CSV_CACHE = {}
        else:
            import csv
            cache: dict = {}
            with OUTCOMES_CSV.open(encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if r["completed"] != "1":
                        continue
                    cache.setdefault((r["arm"], r["seed"]), {})[r["question_id"]] = (
                        r["correct"] == "1")
            _CSV_CACHE = cache
    if not _CSV_CACHE:
        return None
    return _CSV_CACHE.get((arm, str(seed)))


def _arm_key(tmpl: str, seed: int) -> str:
    """The `arm` label the export writes: the filename stem minus the seed."""
    import re
    return tmpl.replace("seed{s}", "").replace(".jsonl", "").rstrip("_")


def _outcomes(path: Path) -> dict[str, bool]:
    """question_id -> correct, from either an engine or a baseline row."""
    out: dict[str, bool] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            rec = row.get("engine") or row.get("baseline")
            if not rec:
                continue
            qid = (rec.get("item") or {}).get("question_id")
            if not qid:
                continue
            gold = (rec.get("item") or {}).get("correct_letter")
            ok = rec.get("correct")
            if ok is None:
                ok = rec.get("final_letter") == gold
            out[str(qid)] = bool(ok)
    return out


def compare(x_tmpl: str, y_tmpl: str, seeds, intended: int) -> dict:
    """Both estimands, both directions, plus the unique-question count."""
    res = {}
    per_seed_universe: dict[str, set] = {}
    for mode in ("complete_case", "timeout_as_failure"):
        b = c = n = 0
        seen: Counter = Counter()
        for s in seeds:
            # Committed table first, raw runs as fallback. Both give the same
            # numbers (pinned in tests/test_per_item_outcomes_offline.py); the
            # table is what lets a fresh clone run this at all.
            X = _csv_outcomes(_arm_key(x_tmpl, s), s)
            if X is None:
                X = _outcomes(RESULTS / x_tmpl.format(s=s))
            Y = _csv_outcomes(_arm_key(y_tmpl, s), s)
            if Y is None:
                Y = _outcomes(RESULTS / y_tmpl.format(s=s))
            if not X or not Y:
                continue
            # complete case: both answered.
            # timeout-as-failure: either ATTEMPTED, absent counts wrong.
            universe = (set(X) & set(Y)) if mode == "complete_case" else (set(X) | set(Y))
            per_seed_universe.setdefault(mode, set()).update(universe)
            for q in universe:
                seen[q] += 1
            b += sum(1 for q in universe if X.get(q, False) and not Y.get(q, False))
            c += sum(1 for q in universe if Y.get(q, False) and not X.get(q, False))
            n += len(universe)
        res[mode] = {
            "b": b, "c": c, "net": b - c, "n": n,
            "unique_questions": len(seen),
            "repeated_ids": sum(1 for v in seen.values() if v > 1),
            "p_x_superior": mcnemar_exact_one_sided(b, c),
            "p_y_superior": mcnemar_exact_one_sided(c, b),
            "intended_total": intended * len(seeds),
        }
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()

    out = {}
    for label, xt, yt, seeds, intended in COMPARISONS:
        out[label] = compare(xt, yt, seeds, intended)

    if a.json:
        print(json.dumps(out, indent=2))
        return 0

    print("=" * 96)
    print("DROPOUT SENSITIVITY -- every headline under both missing-data readings")
    print("=" * 96)
    print("complete_case      : an item counts only if BOTH arms answered")
    print("timeout_as_failure : an item counts if EITHER arm attempted; absent = wrong")
    print()
    print("Drops are 504/timeout-correlated and concentrate on long-generation items,")
    print("so they are NOT missing at random. A claim that flips between these two")
    print("readings is not robust and must be reported with both.")
    print()

    flipped = []
    for label, r in out.items():
        cc, tf = r["complete_case"], r["timeout_as_failure"]
        print("-" * 96)
        print(f"{label}")
        print(f"  {'reading':20s} {'n':>5s} {'uniq':>5s} {'b':>4s} {'c':>4s} {'net':>5s} "
              f"{'p(X>Y)':>9s} {'p(Y>X)':>9s}")
        for name, d in (("complete case", cc), ("timeout=failure", tf)):
            print(f"  {name:20s} {d['n']:5d} {d['unique_questions']:5d} {d['b']:4d} "
                  f"{d['c']:4d} {d['net']:+5d} {d['p_x_superior']:9.4f} {d['p_y_superior']:9.4f}")
        if cc["n"] and tf["n"] and (cc["net"] > 0) != (tf["net"] > 0) and cc["net"] != tf["net"]:
            print("  ** SIGN FLIPS between the two readings -- this claim is NOT robust **")
            flipped.append(label)
        if cc["repeated_ids"]:
            print(f"  note: {cc['n']} observations cover {cc['unique_questions']} unique "
                  f"questions ({cc['repeated_ids']} ids recur); McNemar assumes independent pairs")
        neither = (min(cc["p_x_superior"], cc["p_y_superior"]) >= 0.05
                   and min(tf["p_x_superior"], tf["p_y_superior"]) >= 0.05)
        if neither and cc["n"]:
            print("  note: NEITHER direction is significant under either reading")

    print("-" * 96)
    if flipped:
        print(f"{len(flipped)} of {len(out)} comparisons flip sign:")
        for f in flipped:
            print(f"  - {f}")
    print()
    print("Reminder: a large one-sided p for 'X beats Y' is NOT evidence that Y beats X.")
    print("Both directions are printed above precisely so that cannot be misread again.")
    print()
    print("  reproduce: python -m benchmark.analyze_dropout_sensitivity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
