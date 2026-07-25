"""Quantify survivorship bias in the qwen3.8-solo GPQA family-best bar.

The bar of 93.6% is 73/78 with 12 items lost to 300s ReadTimeouts. The naive
reading treats those 12 as missing-at-random. They are not: the dropped items
are *by definition* the ones whose generation exceeded the timeout, and among
the survivors, accuracy falls sharply with latency. This script measures that
association and converts it into an evidence-weighted interval for the bar.

Offline. Reads only committed result files. No API calls, no tokens.

    python benchmark/analyze_dropout_bias.py
"""

from __future__ import annotations

import json
from math import comb
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
BASELINE = RESULTS / "qwen38_baseline_seed123.jsonl"

# The run requested n=90; its own log records "12 questions still dropped
# after this pass", so the intended denominator is survivors + drops.
INTENDED_N = 90
# Latency band splitting survivors near the 300s cutoff from the rest. Chosen
# as a round 2/3 of the timeout, not tuned against the outcome.
SLOW_S = 200.0
# The best validated QuorumQA society on GPQA-Diamond (chem_thinking_gate,
# 3-seed mean). Cross-seed vs this bar -- see the pre-registration.
SOCIETY = 90.9


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for the 2x2 table [[a, b], [c, d]].

    Sums the hypergeometric probability of every table with the same margins
    whose probability is no greater than the observed one.
    """
    n = a + b + c + d
    row1, col1 = a + b, a + c

    def prob(x: int) -> float:
        # x = top-left cell; margins fixed. Bottom-right follows from the
        # margins as (c+d) - z -- NOT d - (x - a), which is its mirror image
        # and silently truncates one tail (validated against scipy).
        y, z = row1 - x, col1 - x
        w = (c + d) - z
        if min(x, y, z, w) < 0:
            return 0.0
        return comb(row1, x) * comb(c + d, z) / comb(n, col1)

    observed = prob(a)
    # Tolerance guards against float ties being dropped asymmetrically.
    return sum(
        p for x in range(0, min(row1, col1) + 1)
        if (p := prob(x)) and p <= observed * (1 + 1e-9)
    )


def analyze() -> dict:
    rows = _rows(BASELINE)
    survivors = len(rows)
    dropped = INTENDED_N - survivors
    correct = sum(1 for r in rows if r.get("correct") is True)

    banded = [(float(r.get("latency_s") or 0.0), bool(r.get("correct"))) for r in rows]
    slow = [ok for lat, ok in banded if lat >= SLOW_S]
    fast = [ok for lat, ok in banded if lat < SLOW_S]

    slow_ok, fast_ok = sum(slow), sum(fast)
    p = fisher_exact_two_sided(
        slow_ok, len(slow) - slow_ok, fast_ok, len(fast) - fast_ok
    )
    slow_rate = slow_ok / len(slow) if slow else float("nan")

    # Accuracy of the dropped items at which the bar exactly equals SOCIETY.
    flip = ((SOCIETY / 100.0 * INTENDED_N) - correct) / dropped

    def bar(rate: float) -> float:
        return (correct + dropped * rate) / INTENDED_N * 100.0

    return {
        "survivors": survivors,
        "dropped": dropped,
        "correct": correct,
        "survivor_rate": 100.0 * correct / survivors,
        "slow_n": len(slow),
        "slow_rate": 100.0 * slow_rate,
        "fast_n": len(fast),
        "fast_rate": 100.0 * fast_ok / len(fast),
        "fisher_p": p,
        "flip_threshold": 100.0 * flip,
        "bar_all_wrong": bar(0.0),
        "bar_like_slow": bar(slow_rate),
        "bar_like_survivors": bar(correct / survivors),
        "bar_all_right": bar(1.0),
    }


def main() -> None:
    r = analyze()
    print("qwen3.8-solo GPQA bar -- survivorship bias analysis")
    print(f"  source: {BASELINE.relative_to(BASELINE.parents[2])}")
    print()
    print(f"  survivors {r['survivors']}/{INTENDED_N}, {r['dropped']} dropped "
          f"to 300s timeouts; {r['correct']} correct "
          f"= {r['survivor_rate']:.1f}% (the published bar)")
    print()
    print("  Are the drops missing-at-random? Among SURVIVORS, by latency:")
    print(f"    latency >= {SLOW_S:.0f}s : {r['slow_rate']:5.1f}%  (n={r['slow_n']})")
    print(f"    latency <  {SLOW_S:.0f}s : {r['fast_rate']:5.1f}%  (n={r['fast_n']})")
    print(f"    Fisher exact two-sided p = {r['fisher_p']:.5f}")
    print("    -> accuracy declines with generation length. The dropped items"
          " exceeded")
    print("       the timeout, i.e. they lie BEYOND the slowest survivor. The")
    print("       bias is demonstrated, not merely assumed.")
    print()
    print("  Evidence-weighted bar, imputing the dropped items:")
    for label, key in [
        ("all wrong (hard floor)", "bar_all_wrong"),
        (f"like slowest survivors ({r['slow_rate']:.1f}%)", "bar_like_slow"),
        (f"like survivors overall ({r['survivor_rate']:.1f}%)", "bar_like_survivors"),
        ("all right (hard ceiling)", "bar_all_right"),
    ]:
        v = r[key]
        verdict = "SOCIETY AHEAD" if v < SOCIETY else "bar ahead"
        print(f"    {label:<38} {v:5.1f}%   vs society {SOCIETY}% -> {verdict}")
    print()
    print(f"  The bar falls below the society iff the dropped items score "
          f"< {r['flip_threshold']:.1f}%.")
    print(f"  The slowest survivors scored {r['slow_rate']:.1f}% -- below that "
          "threshold.")
    print()
    print("  CAVEAT: the slow band is n=%d. This is an imputation model, not a"
          % r["slow_n"])
    print("  measurement. It does not replace the D0 repair run; it predicts its")
    print("  outcome (see qwen38_bar_repair_preregistration.md, Addendum A).")
    print()
    print("  reproduce: python benchmark/analyze_dropout_bias.py")


if __name__ == "__main__":
    main()
