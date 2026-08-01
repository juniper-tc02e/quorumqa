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

# Seed 1001 was the original single-seed run (+9, p=0.00195). Seeds 2311 and
# 3407 are the pre-registered transfer replication
# (docs/spec-sci1-and-knowledge-injection.md section 3.2), fired 2026-08-01 to
# invoke the repo bar's OTHER branch: net >= +3 at 2 of 3 seeds with pooled
# exact one-sided McNemar p < 0.05. Seeds absent from disk are skipped, so this
# script stays runnable mid-queue.
SEEDS = (1001, 2311, 3407)

# Pre-registered kill (same source, section 3.2): if BOTH fresh seeds land
# net <= +2, the seed-1001 result is seed luck and universal_gate is RETRACTED
# as a claim, not softened.
KILL_MAX_NET_BOTH_FRESH = 2
FRESH_SEEDS = (2311, 3407)

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
    per_seed = {s: verify_seed(s) for s in SEEDS if (RESULTS / LEVER_FILE.format(seed=s)).exists()}

    # Pooled McNemar: SUM the per-seed contingency tables. This repo's
    # established convention (see verify_chemistry_claim.py, ship_gate_verdict)
    # -- adding independent per-seed 2x2 tables, never re-joining items across
    # seeds on question_id, since different seeds draw different item samples.
    pooled_b = sum(s["b"] for s in per_seed.values())
    pooled_c = sum(s["c"] for s in per_seed.values())
    pooled_n = sum(s["n"] for s in per_seed.values())
    pooled_p = mcnemar_exact_one_sided(pooled_b, pooled_c)

    seeds_at_3_plus = [s["seed"] for s in per_seed.values() if s["net"] >= 3]
    single_seed_clears = [
        s["seed"] for s in per_seed.values() if s["net"] >= 5 and s["p_one_sided"] < 0.05
    ]
    two_of_three = len(seeds_at_3_plus) >= 2 and pooled_p < 0.05

    fresh_present = [s for s in per_seed.values() if s["seed"] in FRESH_SEEDS]
    killed = (
        len(fresh_present) == len(FRESH_SEEDS)
        and all(s["net"] <= KILL_MAX_NET_BOTH_FRESH for s in fresh_present)
    )

    return {
        "per_seed": per_seed,
        "pooled": {
            "n": pooled_n, "b": pooled_b, "c": pooled_c, "net": pooled_b - pooled_c,
            "p_one_sided": pooled_p,
        },
        "bar": {
            "single_seed_clears": single_seed_clears,
            "seeds_at_net_3_plus": seeds_at_3_plus,
            "two_of_three_branch_clears": two_of_three,
            "clears": bool(single_seed_clears) or two_of_three,
        },
        "kill": {
            "fresh_seeds_present": [s["seed"] for s in fresh_present],
            "killed": killed,
        },
    }


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
    p, bar, kill = r["pooled"], r["bar"], r["kill"]
    n_seeds = len(r["per_seed"])
    print("=" * 78)
    print(f"POOLED ACROSS {n_seeds} SEED(S): {sorted(r['per_seed'])}")
    print("=" * 78)
    print(f"  b={p['b']} c={p['c']} net={p['net']:+d} n={p['n']}  "
          f"pooled one-sided exact McNemar p={p['p_one_sided']:.6f}")
    print()
    print("  AGAINST THE REPO BAR (either branch suffices):")
    print(f"    branch 1 -- net>=+5 AND p<0.05 at a single seed: "
          f"{bar['single_seed_clears'] or 'none'}")
    print(f"    branch 2 -- net>=+3 at 2 of 3 seeds AND pooled p<0.05: "
          f"seeds at net>=+3 = {bar['seeds_at_net_3_plus'] or 'none'}, "
          f"pooled p={p['p_one_sided']:.6f} -> "
          f"{'CLEARS' if bar['two_of_three_branch_clears'] else 'does not clear'}")
    print(f"    >>> {'BAR CLEARED' if bar['clears'] else 'BAR NOT CLEARED'}")
    print()
    if n_seeds < len(SEEDS):
        missing = [s for s in SEEDS if s not in r["per_seed"]]
        print(f"  INCOMPLETE: seed(s) {missing} not on disk yet. The pooled figure above")
        print("  is a partial read and must not be quoted as the 3-seed result.")
        print()
    print("  PRE-REGISTERED KILL (docs/spec-sci1-and-knowledge-injection.md section 3.2):")
    print(f"    if BOTH fresh seeds {list(FRESH_SEEDS)} land net <= +{KILL_MAX_NET_BOTH_FRESH},")
    print("    the seed-1001 result is seed luck and universal_gate is RETRACTED.")
    if kill["killed"]:
        print("    >>> KILL FIRED. Retract the claim, do not soften it.")
    elif len(kill["fresh_seeds_present"]) < len(FRESH_SEEDS):
        print("    >>> not yet evaluable (both fresh seeds must be on disk).")
    else:
        print("    >>> kill did NOT fire.")
    print()
    print("  CAVEATS:")
    print("  - GPQA only. benchmark/results/unanimous_gate_headroom.md's cost table")
    print("    (4.2 escalations/net item on GPQA vs 24.0 on SuperGPQA-hard) is why")
    print("    GPQA was fired first; this result does not extend to SuperGPQA. The")
    print("    same command there projects +3.2 net at n=180 -- below the bar.")
    print("  - Mechanism is NOT established by this script. The compute-matched")
    print("    control (diversified_panel --n-solvers 9 --no-tribunal at seed 2311)")
    print("    is what separates 'the tribunal helps' from 'more tokens help'. If it")
    print("    matches or beats universal_gate, the mechanism claim is retracted on")
    print("    the spot, exactly as flagship_panel's was.")
    print()
    print("  reproduce: python -m benchmark.verify_universal_gate")


if __name__ == "__main__":
    main()
