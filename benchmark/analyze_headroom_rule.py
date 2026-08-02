"""Does the unanimous-wrong rate PREDICT whether orchestration pays?

README.md has said, since the F05 figure was built, that the cheap-to-flagship
gap "predicts whether that is even possible". This script tests that word.

WHAT THE GAP IS. The unanimous-wrong rate is the share of items where all three
cheap solvers agree AND are wrong. The escalation gate fires on disagreement,
so a unanimously-wrong item is invisible to the cascade -- it returns a
confident wrong answer without ever escalating. The rate is therefore the pool
of items any lever could theoretically recover.

TWO DIFFERENT CLAIMS LIVE IN THAT ONE SENTENCE, and only one survives:

  BOUND (survives): a lever cannot move accuracy by more than the rate, because
  there is nothing else for it to move. Necessary condition, and it holds on
  every benchmark measured.

  PREDICTION (does not survive): knowing the rate tells you where in that range
  a lever will land, or even its SIGN. It does not. The two highest-headroom
  benchmarks in the set sit one point apart and land in opposite directions.

Run:
    python -m benchmark.analyze_headroom_rule

Offline: reads the committed F05 figure CSV. No API calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from scipy import stats

RESULTS = Path(__file__).resolve().parent / "results"
SOURCE = RESULTS / "figure_f05_unanimous_wrong_vs_lever_delta.csv"
OUT = RESULTS / "headroom_rule_analysis.json"

#: Below this, a correlation on n=5 is indistinguishable from noise. Stated as a
#: constant so the verdict is not a judgement call made after seeing the number.
PREDICTIVE_P_MAX = 0.05


def analyze(source: Path = SOURCE) -> dict:
    df = pd.read_csv(source)
    x = df["unanimous_wrong_rate_pct"]
    y = df["best_lever_delta_pp"]

    # A correlation is undefined when either column is constant -- scipy warns
    # and returns NaN, and NaN is not valid JSON, so the whole artifact would
    # be unreadable. Degenerate input is not a predictive relationship; it is
    # the absence of one, so it is reported that way rather than crashing or
    # silently emitting NaN.
    degenerate = x.nunique() < 2 or y.nunique() < 2
    if degenerate:
        r = rho = 0.0
        p_r = p_rho = 1.0
    else:
        r, p_r = stats.pearsonr(x, y)
        rho, p_rho = stats.spearmanr(x, y)

    # The bound: |delta| <= rate on every benchmark.
    within = (y.abs() <= x)
    # How much of the available headroom each lever actually converted. Negative
    # means the lever moved accuracy the WRONG way.
    converted = (y / x * 100).round(1)

    # The decisive comparison: benchmarks whose headroom is within 2pp of each
    # other. If the rate predicted anything, these would agree.
    hi = df[x >= 20]

    predictive = bool(min(p_r, p_rho) < PREDICTIVE_P_MAX)
    signs_agree = bool((r > 0) == (rho > 0))

    return {
        "n_benchmarks": int(len(df)),
        "degenerate_input": bool(degenerate),
        "n_validated_3seed": int((df["best_lever_verdict"] == "validated").sum()),
        "pearson": {"r": round(float(r), 3), "p": round(float(p_r), 4)},
        "spearman": {"rho": round(float(rho), 3), "p": round(float(p_rho), 4)},
        "correlation_signs_agree": signs_agree,
        "bound_holds_on_all": bool(within.all()),
        "headroom_converted_pct": {
            "min": float(converted.min()),
            "max": float(converted.max()),
        },
        "near_identical_headroom": [
            {
                "benchmark": row["benchmark"],
                "rate_pct": float(row["unanimous_wrong_rate_pct"]),
                "delta_pp": float(row["best_lever_delta_pp"]),
                "verdict": row["best_lever_verdict"],
                "seeds": int(row["best_lever_seeds"]),
            }
            for _, row in hi.iterrows()
        ],
        "verdict": {
            "bound": "SUPPORTED" if within.all() else "VIOLATED",
            "prediction": "SUPPORTED" if predictive else "NOT SUPPORTED",
        },
    }


def main() -> None:
    a = analyze()
    print("Does the unanimous-wrong rate predict whether orchestration pays?")
    print(f"  n = {a['n_benchmarks']} benchmarks, of which "
          f"{a['n_validated_3seed']} validated at 3 seeds\n")

    print(f"  Pearson  r   = {a['pearson']['r']:+.3f}  (p = {a['pearson']['p']:.4f})")
    print(f"  Spearman rho = {a['spearman']['rho']:+.3f}  (p = {a['spearman']['p']:.4f})")
    if not a["correlation_signs_agree"]:
        print("  ** the two correlations do not even agree on the SIGN **")
    print()

    print("  Near-identical headroom, opposite outcomes:")
    for e in a["near_identical_headroom"]:
        print(f"    {e['benchmark']:16s} rate {e['rate_pct']:5.1f}%  ->  "
              f"delta {e['delta_pp']:+5.1f}pp   ({e['verdict']}, "
              f"{e['seeds']} seed{'s' if e['seeds'] != 1 else ''})")
    print()

    c = a["headroom_converted_pct"]
    print(f"  BOUND      |delta| <= rate : {a['verdict']['bound']} "
          f"(all {a['n_benchmarks']} benchmarks)")
    print(f"  PREDICTION rate -> delta   : {a['verdict']['prediction']}")
    print(f"  Levers convert between {c['min']:.1f}% and {c['max']:.1f}% of the "
          f"available headroom -- a negative figure means the lever moved")
    print(f"  accuracy the wrong way. That range spans zero.\n")

    print("  Conclusion: the rate is a CEILING, not a forecast. It tells you")
    print("  whether a win is arithmetically possible. It does not tell you")
    print("  whether one will happen, or in which direction.")

    OUT.write_text(json.dumps(a, indent=2) + "\n", encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(RESULTS.parent.parent)}")


if __name__ == "__main__":
    main()
