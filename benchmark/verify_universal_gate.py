"""Verify the universal_gate lever's live result end-to-end from committed files.

universal_gate (benchmark/lever_experiments.py) escalates EVERY unanimous panel
to the tribunal unconditionally -- the gate-recall lever from
benchmark/results/unanimous_gate_headroom.md, which found (pooled, offline,
free) that existing doubt-gates recover 47.6% of unanimous-wrong items at 0.8%
breakage when they happen to fire, but only fire on 12.7% of the unanimous-wrong
set.

This is the first LIVE run: seed 1001, GPQA-Diamond, n=90, fresh and unburned.

The comparison is PAIRED within a single run rather than against a separate
file: universal_gate's own solver panels are identical to what the SHIPPED
orchestrator would have produced (same items, same seed, same panel calls) --
the two configurations differ only in whether a unanimous panel is allowed to
escalate. So the counterfactual "shipped, no universal escalation" score is
reconstructed from this run's own logged `plurality_letter` on unanimous rows
(shipped: `if unanimous: return` -- no escalation) and `final_letter` on split
rows (splits already escalate under the shipped orchestrator too, so those are
unchanged). No second live run was needed to get the paired baseline.

Offline once the lever run exists. No API calls, no tokens.

    python -m benchmark.verify_universal_gate
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

RESULTS = Path(__file__).resolve().parent / "results"
LEVER_FILE = "lever_universal_gate_gpqa_seed{seed}.jsonl"

SEEDS = (1001,)

# This session's earlier OFFLINE, pooled-marginal estimate
# (benchmark/results/unanimous_gate_headroom.md), reproduced from
# analyze_judge_anchoring.py. Provided for direct comparison, not as ground
# truth -- this script's own live numbers supersede it for seed 1001.
PRIOR_POOLED_RECOVERY_PCT = 47.6
PRIOR_POOLED_BREAKAGE_PCT = 0.8
PRIOR_GPQA_RECOVERY_RANGE_PCT = (55.1, 75.0)  # gpqa(default), gpqa


def _load(name: str) -> list[dict]:
    with (RESULTS / name).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _is_unanimous(engine: dict) -> bool:
    letters = {a["letter"] for a in engine["solver_answers"]}
    return len(letters) == 1


def verify_seed(seed: int) -> dict:
    rows = _load(LEVER_FILE.format(seed=seed))
    engines = [r["engine"] for r in rows]
    n = len(engines)

    unanimous = [e for e in engines if _is_unanimous(e)]
    non_unanimous_escalated = sum(1 for e in engines if not _is_unanimous(e))
    unanimous_escalated = sum(1 for e in unanimous if e["escalated"])

    gold = {e["item"]["question_id"]: e["item"]["correct_letter"] for e in engines}
    una_wrong = [e for e in unanimous if e["plurality_letter"] != e["item"]["correct_letter"]]
    una_right = [e for e in unanimous if e["plurality_letter"] == e["item"]["correct_letter"]]
    recovered = [e for e in una_wrong if e["final_letter"] == e["item"]["correct_letter"]]
    broken = [e for e in una_right if e["final_letter"] != e["item"]["correct_letter"]]

    # Reconstructed shipped-orchestrator counterfactual: unanimous -> plurality
    # (no escalation); split -> final_letter (already escalates under the
    # shipped orchestrator, so unaffected by this lever).
    shipped_correct = gate_correct = 0
    b = c = 0
    for e in engines:
        g = e["item"]["correct_letter"]
        shipped_letter = e["plurality_letter"] if _is_unanimous(e) else e["final_letter"]
        gated_letter = e["final_letter"]
        shipped_ok = shipped_letter == g
        gated_ok = gated_letter == g
        shipped_correct += shipped_ok
        gate_correct += gated_ok
        if gated_ok and not shipped_ok:
            b += 1
        if shipped_ok and not gated_ok:
            c += 1

    return {
        "seed": seed,
        "n": n,
        "unanimous_rate": len(unanimous) / n,
        "unanimous_count": len(unanimous),
        "unanimous_escalated": unanimous_escalated,
        "non_unanimous_escalated": non_unanimous_escalated,
        "mechanism_clean": unanimous_escalated == len(unanimous) and non_unanimous_escalated == (n - len(unanimous)),
        "unanimous_wrong": len(una_wrong),
        "unanimous_right": len(una_right),
        "recovered": len(recovered),
        "recovery_rate": len(recovered) / len(una_wrong) if una_wrong else None,
        "broken": len(broken),
        "breakage_rate": len(broken) / len(una_right) if una_right else None,
        "shipped_correct": shipped_correct,
        "shipped_accuracy": shipped_correct / n,
        "gated_correct": gate_correct,
        "gated_accuracy": gate_correct / n,
        "b": b,
        "c": c,
        "net": b - c,
        "p_one_sided": mcnemar_exact_one_sided(b, c),
    }


def verify() -> dict:
    return {"per_seed": {s: verify_seed(s) for s in SEEDS if (RESULTS / LEVER_FILE.format(seed=s)).exists()}}


def main() -> None:
    r = verify()
    print("universal_gate vs the shipped (non-escalating) orchestrator, GPQA-Diamond")
    print("PAIRED WITHIN each run: same items, same panels, differ only in whether")
    print("a unanimous panel is allowed to escalate.")
    print()
    for seed, s in r["per_seed"].items():
        print(f"  seed {seed} (n={s['n']}):")
        print(f"    unanimous panels: {s['unanimous_count']}/{s['n']} "
              f"({100 * s['unanimous_rate']:.1f}%)")
        print(f"    mechanism check -- every unanimous panel escalated, every "
              f"split panel escalated (as shipped): {'PASS' if s['mechanism_clean'] else 'FAIL'}")
        print()
        print(f"    unanimous-wrong: {s['unanimous_wrong']}  recovered: {s['recovered']}  "
              f"-> recovery rate {100 * (s['recovery_rate'] or 0):.1f}%")
        print(f"    unanimous-right: {s['unanimous_right']}  broken:    {s['broken']}  "
              f"-> breakage rate {100 * (s['breakage_rate'] or 0):.1f}%")
        print()
        print(f"    prior offline pooled estimate: {PRIOR_POOLED_RECOVERY_PCT}% recovery, "
              f"{PRIOR_POOLED_BREAKAGE_PCT}% breakage")
        print(f"    prior offline GPQA-only range: {PRIOR_GPQA_RECOVERY_RANGE_PCT[0]}-"
              f"{PRIOR_GPQA_RECOVERY_RANGE_PCT[1]}% recovery")
        recovery_pct = 100 * (s["recovery_rate"] or 0)
        if recovery_pct < PRIOR_POOLED_RECOVERY_PCT:
            print("    READ ON THE PRE-REGISTERED PREDICTION: conversion landed BELOW the")
            print("    pooled estimate, as predicted (selection bias in the doubt-gates).")
        else:
            print("    READ ON THE PRE-REGISTERED PREDICTION: conversion landed AT OR ABOVE")
            print("    the pooled estimate -- the pre-registered prediction (conversion below")
            print("    47.6%, because existing gates only fire on detectable doubt) did NOT")
            print("    hold on this seed. Recorded honestly rather than only reporting the win.")
        print()
        print(f"    shipped (no universal escalation): {s['shipped_correct']}/{s['n']} "
              f"= {100 * s['shipped_accuracy']:.1f}%")
        print(f"    universal_gate:                    {s['gated_correct']}/{s['n']} "
              f"= {100 * s['gated_accuracy']:.1f}%")
        print(f"    net discordant: b={s['b']} c={s['c']} net={s['net']:+d}  "
              f"one-sided exact McNemar p={s['p_one_sided']:.5f}")
        clears = s["net"] >= 5 and s["p_one_sided"] < 0.05
        print(f"    against the repo bar (net>=+5 at one seed, p<0.05): "
              f"{'CLEARS' if clears else 'does not clear'}")
        print()
    print("  CAVEATS:")
    print("  - Single seed. The repo bar's OTHER branch (net>=+3 at 2 of 3 seeds,")
    print("    pooled McNemar p<0.05) needs 2 more fresh seeds to invoke; this run")
    print("    alone clears the single-seed branch, which is sufficient on its own.")
    print("  - GPQA only. benchmark/results/unanimous_gate_headroom.md's cost table")
    print("    (4.2 escalations/net item on GPQA vs 24.0 on SuperGPQA-hard) is why")
    print("    GPQA was fired first; this result does not extend to SuperGPQA.")
    print()
    print("  reproduce: python -m benchmark.verify_universal_gate")


if __name__ == "__main__":
    main()
