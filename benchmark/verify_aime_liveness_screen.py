"""MATH-1 -- AIME liveness screen: is there a cheap-to-flagship gap at all?

docs/experiment-spec-book.md section "MATH-1", verbatim bar/kill/contamination
logic. Pre-registered BEFORE benchmark/run_math_open.py --dataset aime --seed 101
--mode sc --sc-n 1 --sc-margin 1 --solver-tier cheap --concurrency 3 was ever
fired, so the analysis can't be chosen after seeing the result.

Reads the two files that command writes:
  aime_open_baseline_seed101.jsonl  -- flagship single call (qwen3.7-max, thinking)
  aime_open_sc_cheap_seed101.jsonl  -- cheap single call (qwen3.6-flash, no thinking;
                                        solve_selfconsistency_math(n=1, margin=1)
                                        collapses to exactly one call, no judge)

ADMISSIBILITY (spec, verbatim): a run is admissible iff 60/60 rows in every arm
AND question_id intersection = 60. Any drop makes the run's numbers UNANALYSABLE
-- discard and re-run, never patch or partially report. This script enforces
that by raising rather than silently computing on a smaller n.

BAR (directional, both conditions): ALIVE iff net (b-c, flagship-advantage
direction) >= 10 AND flagship accuracy <= 85% (>=9 items of headroom left).

KILL (dominates the bar -- checked first, unconditionally): kill the entire
AIME branch (MATH-2/3/4's replacement die with it) if EITHER cheap accuracy
>= 90% (saturated exactly like MATH-500 L5) OR flagship accuracy >= 95% (no
headroom for any lever to move 6 discordant items into a <=3-item gap).

CONTAMINATION FLAG (caveat, not a kill -- must travel with every later AIME
number): if 2024 cheap-correct count exceeds 2025 cheap-correct count by >=8
items, treat AIME-2024 as memorised and restrict subsequent AIME specs to the
2025 half (n=30) only.

Offline. No API calls, no tokens.

    python -m benchmark.verify_aime_liveness_screen
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

RESULTS = Path(__file__).resolve().parent / "results"

BASELINE_FILE = "aime_open_baseline_seed101.jsonl"
CHEAP_FILE = "aime_open_sc_cheap_seed101.jsonl"

BAR_MIN_NET = 10
BAR_MAX_FLAGSHIP_ACC = 0.85
KILL_CHEAP_ACC = 0.90
KILL_FLAGSHIP_ACC = 0.95
CONTAMINATION_MIN_YEAR_GAP = 8


def _load(name: str, results_dir: "str | Path" = RESULTS) -> list[dict]:
    path = Path(results_dir) / name
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _year(question_id: str) -> str:
    if question_id.startswith("aime2024"):
        return "2024"
    if question_id.startswith("aime2025"):
        return "2025"
    raise ValueError(f"question_id {question_id!r} does not encode a recognised AIME year")


def verify(results_dir: "str | Path" = RESULTS) -> dict:
    baseline_rows = _load(BASELINE_FILE, results_dir)
    cheap_rows = _load(CHEAP_FILE, results_dir)

    if len(baseline_rows) != 60 or len(cheap_rows) != 60:
        raise AssertionError(
            f"INADMISSIBLE: expected 60/60 rows in every arm, got "
            f"baseline={len(baseline_rows)} cheap={len(cheap_rows)} -- "
            f"per the pre-registered bar this run's numbers must be discarded, "
            f"not analysed. Re-run, do not patch."
        )

    baseline = {r["question_id"]: bool(r["correct"]) for r in baseline_rows}
    cheap = {r["question_id"]: bool(r["correct"]) for r in cheap_rows}
    shared = sorted(set(baseline) & set(cheap))
    if len(shared) != 60:
        raise AssertionError(
            f"INADMISSIBLE: question_id intersection = {len(shared)}, expected 60 -- "
            f"the two arms did not run on an identical item set. Re-run, do not patch."
        )

    b = sum(1 for q in shared if baseline[q] and not cheap[q])  # flagship right, cheap wrong
    c = sum(1 for q in shared if cheap[q] and not baseline[q])  # cheap right, flagship wrong
    net = b - c
    p = mcnemar_exact_one_sided(b, c)

    baseline_acc = sum(baseline.values()) / 60
    cheap_acc = sum(cheap.values()) / 60

    by_year: dict[str, dict] = {}
    for year in ("2024", "2025"):
        ids = [q for q in shared if _year(q) == year]
        by_year[year] = {
            "n": len(ids),
            "baseline_correct": sum(1 for q in ids if baseline[q]),
            "cheap_correct": sum(1 for q in ids if cheap[q]),
        }

    year_gap = by_year["2024"]["cheap_correct"] - by_year["2025"]["cheap_correct"]
    contamination_flag = year_gap >= CONTAMINATION_MIN_YEAR_GAP

    killed = cheap_acc >= KILL_CHEAP_ACC or baseline_acc >= KILL_FLAGSHIP_ACC
    kill_reasons = []
    if cheap_acc >= KILL_CHEAP_ACC:
        kill_reasons.append(f"cheap accuracy {cheap_acc * 100:.1f}% >= {KILL_CHEAP_ACC * 100:.0f}% (saturated)")
    if baseline_acc >= KILL_FLAGSHIP_ACC:
        kill_reasons.append(f"flagship accuracy {baseline_acc * 100:.1f}% >= {KILL_FLAGSHIP_ACC * 100:.0f}% (no headroom)")

    bar_cleared = net >= BAR_MIN_NET and baseline_acc <= BAR_MAX_FLAGSHIP_ACC
    bar_reasons = []
    if net < BAR_MIN_NET:
        bar_reasons.append(f"net={net:+d} < required +{BAR_MIN_NET}")
    if baseline_acc > BAR_MAX_FLAGSHIP_ACC:
        bar_reasons.append(f"flagship accuracy {baseline_acc * 100:.1f}% > {BAR_MAX_FLAGSHIP_ACC * 100:.0f}% (no headroom left)")

    if killed:
        verdict = "KILL"
    elif bar_cleared:
        verdict = "ALIVE"
    else:
        verdict = "NEITHER (does not clear the bar, not killed either)"

    return {
        "n": 60, "b": b, "c": c, "net": net, "p_one_sided": p,
        "baseline_acc": baseline_acc, "cheap_acc": cheap_acc,
        "by_year": by_year, "year_gap_cheap_correct": year_gap,
        "contamination_flag": contamination_flag,
        "killed": killed, "kill_reasons": kill_reasons,
        "bar_cleared": bar_cleared, "bar_reasons": bar_reasons,
        "verdict": verdict,
    }


def main() -> None:
    r = verify()
    print("MATH-1 -- AIME liveness screen, seed 101, n=60 (2024+2025), paired by construction")
    print("=" * 100)
    print(f"  flagship (qwen3.7-max, thinking) accuracy: {r['baseline_acc'] * 100:.1f}% ({int(r['baseline_acc'] * 60)}/60)")
    print(f"  cheap (qwen3.6-flash, no thinking) accuracy: {r['cheap_acc'] * 100:.1f}% ({int(r['cheap_acc'] * 60)}/60)")
    print(f"  b (flagship right, cheap wrong) = {r['b']}")
    print(f"  c (cheap right, flagship wrong) = {r['c']}")
    print(f"  net (flagship advantage) = {r['net']:+d}")
    print(f"  one-sided exact McNemar p = {r['p_one_sided']:.5f}")
    print()
    print("  BY YEAR:")
    for year, s in r["by_year"].items():
        print(f"    {year}: n={s['n']}  flagship={s['baseline_correct']}/{s['n']}  cheap={s['cheap_correct']}/{s['n']}")
    print(f"  2024-vs-2025 cheap-correct gap: {r['year_gap_cheap_correct']:+d}"
          f"  (contamination flag {'RAISED' if r['contamination_flag'] else 'not raised'}"
          f", threshold >= {CONTAMINATION_MIN_YEAR_GAP})")
    print()
    print(f"  KILL check (dominates): {'TRIGGERED -- ' + '; '.join(r['kill_reasons']) if r['killed'] else 'not triggered'}")
    print(f"  BAR check (net>=+{BAR_MIN_NET} AND flagship<=%d%%): " % int(BAR_MAX_FLAGSHIP_ACC * 100)
          + ("cleared" if r["bar_cleared"] else "not cleared -- " + "; ".join(r["bar_reasons"])))
    print()
    print(f"  >>> VERDICT: {r['verdict']}")
    print()
    print("  reproduce: python -m benchmark.verify_aime_liveness_screen")


if __name__ == "__main__":
    main()
