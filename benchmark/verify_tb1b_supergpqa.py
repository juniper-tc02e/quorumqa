"""TB-1B -- does the cheap-seat architecture beat a flagship call on the
surface where the flagship is weak?

Implements `docs/spec-tb1b-supergpqa.md` §5 verbatim. Built BEFORE the screen's
result is read, so the analysis cannot be chosen after seeing it.

THE THREE ARMS, and why arm C exists:
  A  universal_gate on SuperGPQA-hard   (cheap 3-seat panel, escalate EVERYTHING)
  B  flagship 1x solo                    (already run -- lever_baseline_supergpqa_*)
  C  cheap panel under the SHIPPED rule  (free: derived from arm A's own log)

A-vs-B is "does the architecture beat one flagship call". A-vs-C is "does
universal escalation beat the shipped escalate-on-split rule". They are
DIFFERENT CLAIMS, and conflating them is exactly the error that made
universal_gate's GPQA +25 read as a flagship win when it was a cheap-panel win.
This script always reports both, and labels which is which.

PRIMARY: pooled exact one-sided McNemar over the fired seeds, net >= +5 and
p < 0.05. Pooling sums per-seed 2x2 tables. SuperGPQA seeds are near-disjoint
(measured: 2 shared items of 88 between seeds 7 and 123), unlike GPQA's, so
pooling here does not double-count the way it would there.

ANALYSIS SET: per seed, S = A intersect B on question_id, gated at |S| >= 81 --
90% of the INTENDED 90, not of either arm's row count, so drops cannot hide.

Offline. No API calls, no tokens.

    python -m benchmark.verify_tb1b_supergpqa
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

RESULTS = Path(__file__).resolve().parent / "results"
SEEDS = (7, 42, 123)
INTENDED_N = 90
MIN_ANALYSIS_SET = 81

ARM_A = "TB1B_universal_gate_supergpqa_seed{seed}.jsonl"
ARM_B = "lever_baseline_supergpqa_seed{seed}.jsonl"

PRIMARY_ALPHA = 0.05
MIN_NET = 5

# Screen kill (spec §6.1): if the first seed lands net <= 0 against arm B, the
# extension is not funded.
SCREEN_SEED = 7
SCREEN_KILL_MAX_NET = 0

# Measured comparators, for the cost kill (§6.2).
FLAGSHIP_TOK_PER_ITEM = 2969.0   # lever_baseline_supergpqa_*, 3 seeds
COST_KILL_RATIO = 4.0


def _load(name: str) -> list[dict]:
    path = RESULTS / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _is_unanimous(engine: dict) -> bool:
    letters = {a["letter"] for a in engine["solver_answers"]}
    return len(letters) == 1


def _arm_a(seed: int) -> dict[str, dict]:
    """universal_gate rows -> per-item outcomes for BOTH arm A and arm C.

    Arm C (the shipped rule) is reconstructed from this same run: a unanimous
    panel would have returned `plurality_letter` without escalating, and a
    split panel escalates under the shipped orchestrator too, so its
    `final_letter` is unchanged. No second live run is needed -- the same
    counterfactual `verify_universal_gate.py` already uses on GPQA.
    """
    out = {}
    for row in _load(ARM_A.format(seed=seed)):
        e = row["engine"]
        qid = e["item"]["question_id"]
        gold = e["item"]["correct_letter"]
        shipped_letter = e["plurality_letter"] if _is_unanimous(e) else e["final_letter"]
        out[str(qid)] = {
            "gated_ok": e["final_letter"] == gold,
            "shipped_ok": shipped_letter == gold,
            "tokens": sum(c["input_tokens"] + c["output_tokens"] for c in e.get("calls", [])),
            "unanimous": _is_unanimous(e),
            "unanimous_wrong": _is_unanimous(e) and e["plurality_letter"] != gold,
            "recovered": (
                _is_unanimous(e)
                and e["plurality_letter"] != gold
                and e["final_letter"] == gold
            ),
            "broken": (
                _is_unanimous(e)
                and e["plurality_letter"] == gold
                and e["final_letter"] != gold
            ),
        }
    return out


def _arm_b(seed: int) -> dict[str, bool]:
    out = {}
    for row in _load(ARM_B.format(seed=seed)):
        b = row.get("baseline")
        if not isinstance(b, dict):
            continue
        qid = (b.get("item") or {}).get("question_id")
        if qid:
            out[str(qid)] = bool(b["correct"])
    return out


def _paired(a_ok: dict[str, bool], b_ok: dict[str, bool], shared: list[str]) -> dict:
    b = sum(1 for q in shared if a_ok[q] and not b_ok[q])
    c = sum(1 for q in shared if b_ok[q] and not a_ok[q])
    return {
        "b": b, "c": c, "net": b - c, "n": len(shared),
        "p_one_sided": mcnemar_exact_one_sided(b, c),
        "a_correct": sum(1 for q in shared if a_ok[q]),
        "other_correct": sum(1 for q in shared if b_ok[q]),
    }


def verify() -> dict:
    per_seed = {}
    for seed in SEEDS:
        a = _arm_a(seed)
        b = _arm_b(seed)
        if not a or not b:
            continue
        shared = sorted(set(a) & set(b))
        gated = {q: a[q]["gated_ok"] for q in shared}
        shipped = {q: a[q]["shipped_ok"] for q in shared}
        tok = sum(a[q]["tokens"] for q in shared) / len(shared) if shared else None
        per_seed[seed] = {
            "seed": seed,
            "n_shared": len(shared),
            "gate_ok": len(shared) >= MIN_ANALYSIS_SET,
            "dropped_vs_intended": INTENDED_N - len(shared),
            "vs_flagship": _paired(gated, b, shared),          # PRIMARY
            "vs_shipped_rule": _paired(gated, shipped, shared),  # SECONDARY
            "tokens_per_item": tok,
            "unanimous": sum(1 for q in shared if a[q]["unanimous"]),
            "unanimous_wrong": sum(1 for q in shared if a[q]["unanimous_wrong"]),
            "recovered": sum(1 for q in shared if a[q]["recovered"]),
            "broken": sum(1 for q in shared if a[q]["broken"]),
        }

    def _pool(key: str) -> dict:
        b = sum(s[key]["b"] for s in per_seed.values())
        c = sum(s[key]["c"] for s in per_seed.values())
        n = sum(s[key]["n"] for s in per_seed.values())
        p = mcnemar_exact_one_sided(b, c)
        return {"b": b, "c": c, "net": b - c, "n": n, "p_one_sided": p,
                "clears": (b - c) >= MIN_NET and p < PRIMARY_ALPHA}

    pooled_flagship = _pool("vs_flagship") if per_seed else {}
    pooled_shipped = _pool("vs_shipped_rule") if per_seed else {}

    screen = per_seed.get(SCREEN_SEED)
    screen_killed = bool(screen and screen["vs_flagship"]["net"] <= SCREEN_KILL_MAX_NET)

    tok = [s["tokens_per_item"] for s in per_seed.values() if s["tokens_per_item"]]
    mean_tok = sum(tok) / len(tok) if tok else None
    cost_ratio = (mean_tok / FLAGSHIP_TOK_PER_ITEM) if mean_tok else None
    cost_killed = bool(
        cost_ratio and cost_ratio > COST_KILL_RATIO
        and pooled_flagship and pooled_flagship["net"] < MIN_NET
    )

    return {
        "per_seed": per_seed,
        "pooled_vs_flagship": pooled_flagship,
        "pooled_vs_shipped_rule": pooled_shipped,
        "screen_killed": screen_killed,
        "cost": {"tokens_per_item": mean_tok, "flagship_tokens_per_item": FLAGSHIP_TOK_PER_ITEM,
                 "ratio": cost_ratio, "cost_killed": cost_killed},
        "seeds_present": sorted(per_seed),
    }


def main() -> None:
    r = verify()
    print("=" * 82)
    print("TB-1B -- universal_gate (cheap seats + escalate all) on SuperGPQA-hard")
    print("=" * 82)
    if not r["per_seed"]:
        print("  No TB1B arm-A files found yet -- nothing to analyse.")
        return

    for seed, s in r["per_seed"].items():
        print(f"  seed {seed}: |S|={s['n_shared']}"
              f"{'' if s['gate_ok'] else '   *** VOID: below the 81-item gate ***'}")
        if s["dropped_vs_intended"]:
            print(f"    {s['dropped_vs_intended']} short of the intended {INTENDED_N}; "
                  f"drops are 504-correlated and NOT MCAR.")
        f, c = s["vs_flagship"], s["vs_shipped_rule"]
        print(f"    PRIMARY   vs flagship 1x  : A={f['a_correct']}/{f['n']} vs B={f['other_correct']}/{f['n']}"
              f"  b={f['b']} c={f['c']} net={f['net']:+d} p={f['p_one_sided']:.5f}")
        print(f"    SECONDARY vs shipped rule : b={c['b']} c={c['c']} net={c['net']:+d} "
              f"p={c['p_one_sided']:.5f}   (a DIFFERENT claim -- see module docstring)")
        print(f"    unanimous={s['unanimous']} of which wrong={s['unanimous_wrong']}; "
              f"recovered={s['recovered']} broken={s['broken']}; {s['tokens_per_item']:.0f} tok/item")
        print()

    pf, ps = r["pooled_vs_flagship"], r["pooled_vs_shipped_rule"]
    print("-" * 82)
    print(f"POOLED over seeds {r['seeds_present']}")
    print("-" * 82)
    print(f"  PRIMARY   vs flagship 1x  : b={pf['b']} c={pf['c']} net={pf['net']:+d} "
          f"n={pf['n']} p={pf['p_one_sided']:.6f}  -> {'CLEARS' if pf['clears'] else 'does not clear'}")
    print(f"  SECONDARY vs shipped rule : b={ps['b']} c={ps['c']} net={ps['net']:+d} "
          f"n={ps['n']} p={ps['p_one_sided']:.6f}")
    print()
    print("  KILL CLAUSES (spec section 6):")
    if len(r["seeds_present"]) == 1 and r["seeds_present"][0] == SCREEN_SEED:
        print(f"    screen kill (seed {SCREEN_SEED} net <= {SCREEN_KILL_MAX_NET}): "
              f"{'FIRED -- do NOT fund the extension' if r['screen_killed'] else 'did not fire'}")
    cost = r["cost"]
    if cost["ratio"]:
        print(f"    cost: {cost['tokens_per_item']:.0f} vs flagship {cost['flagship_tokens_per_item']:.0f} "
              f"tok/item = {cost['ratio']:.1f}x"
              + ("  -> DOMINATED (>4x for net < +5)" if cost["cost_killed"] else ""))
    print()
    print("  Reminder: PRIMARY and SECONDARY are different claims. A win against the")
    print("  shipped rule is NOT a win against a flagship call, and reporting the")
    print("  former as the latter is the error this spec exists to prevent.")
    print()
    print("  reproduce: python -m benchmark.verify_tb1b_supergpqa")


if __name__ == "__main__":
    main()
