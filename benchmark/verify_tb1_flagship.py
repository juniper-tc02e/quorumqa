"""TB-1 -- does the scaffolded flagship beat the solo flagship?

Implements `docs/spec-trackb-flagship-comparison.md` §5 verbatim. Built BEFORE
arm B fires; the spec makes this script build-item 1 and BLOCKING, because
without it the runs finish and there is no number.

WHAT ARM A ACTUALLY IS -- read this before quoting anything below.
`universal_gate` escalates every item, so judge calls/item = 1.00 (measured at
all three seeds). Nothing returns without a `qwen3.7-max` call. Arm A is a
FLAGSHIP CALL, SCAFFOLDED -- not cheap seats replacing a flagship. No output of
this script may be worded "cheap-seat orchestration beats a stronger model";
the spec pre-registers that wording as prohibited.

ARMS
  A  universal_gate                      already run (no new spend)
  B  flagship 1x solo                    falsification test, NOT superiority
  B' flagship 1x with a rich prompt      prompt-richness control, diagnostic
  C  flagship SC @ N=5, compute-matched   attribution guard

THE PRIMARY TEST is the POOLED 3-seed exact one-sided McNemar at p<0.05. The
single-seed branch is SECONDARY and Bonferroni-corrected to alpha=0.0167,
whose registered consequence is that b=5,c=0 (p=0.03125) does NOT pass it --
the secondary branch needs net>=+6 with zero losses. This correction exists
because the undeclared multi-branch design was, simulated under exact
equality, a 12% test wearing a 5% label.

ANALYSIS SET. Per seed, S = intersection of every arm present, on question_id.
Gate: |S| >= 81, i.e. 90% of the INTENDED 90 -- not of arm A's row count, which
would let drops hide. Drops are 504-correlated and therefore not MCAR; that is
printed whenever a seed carries any.

Offline. No API calls, no tokens.

    python -m benchmark.verify_tb1_flagship
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided
from benchmark.verify_compute_matched_control import _outcomes

RESULTS = Path(__file__).resolve().parent / "results"
SEEDS = (1001, 2311, 3407)
INTENDED_N = 90
MIN_ANALYSIS_SET = 81  # 90% of INTENDED_N

ARM_FILES = {
    "A": "lever_universal_gate_gpqa_seed{seed}.jsonl",
    "B": "TB1_flagship1x_gpqa_seed{seed}.jsonl",
    "Bprime": "TB1_flagship1x_rich_gpqa_seed{seed}.jsonl",
    "C": "TB1_flagship_sc5_gpqa_seed{seed}.jsonl",
}

PRIMARY_ALPHA = 0.05
SECONDARY_ALPHA = 0.05 / 3  # Bonferroni over the three seeds

# --- Kill clause 4 (degeneracy), given a number ------------------------------
#
# The spec states clause 4 as "if arm C's mean pairwise seat agreement is
# approximately 1.0, the samples are degenerate and the A-vs-C comparison is
# VOID rather than favourable." That is not a threshold. An unquantified kill
# clause is decided after the data is seen, which is the one thing a
# pre-registration exists to prevent -- and the temptation runs in a specific
# direction here, since voiding A-vs-C would conveniently protect arm A's
# mechanism claim.
#
# Fixed 2026-08-03, BEFORE reading any seed-1001 accuracy. At that moment the
# only arm C numbers seen were the section 4.1 pre-flight (5 items, mean
# pairwise agreement 0.920) and a running item COUNT from the log.
#
# Two conditions, either sufficient, because "degenerate" has two distinct
# failure shapes:
#
#   AGREEMENT >= 0.98. At 0.98 over 90 items x 10 pairs, ~18 of 900 pairs
#   disagree. Self-consistency can then move only a handful of items and the
#   control cannot meaningfully differ from a single call.
#
#   DISAGREEING ITEMS < 5%. The direct statement of the same thing and the more
#   interpretable one: on fewer than ~4 of 90 items do the five seats split at
#   all. Voting over samples that never disagree IS a single call.
#
# A third figure is reported but deliberately NOT a kill: how often the majority
# differs from the first seat. That measures whether voting changed the answer,
# which is the effect under test -- gating on it would be conditioning the
# control's admissibility on its own result.
DEGENERACY_MAX_AGREEMENT = 0.98
DEGENERACY_MIN_SPLIT_ITEM_RATE = 0.05


def _load(name: str) -> list[dict]:
    path = RESULTS / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _sc_outcomes(rows: list[dict]) -> dict[str, bool]:
    """Arm C's vote, recomputed OFFLINE from the logged per-seat answers rather
    than trusting any final_letter the runner wrote.

    Rules, all pre-registered in the spec:
      - empty/unparsed seat letters are DROPPED before the majority (they are
        not votes), but
      - an item whose seats are ALL empty counts WRONG, never dropped -- a
        silent drop would bias the arm toward easy items, the survivorship
        trap that voided an earlier AIME run;
      - ties resolve to the letter of the LOWEST seat_index among those tied,
        matching `_plurality()`'s first-index convention repo-wide. NOT a
        confidence tie-break: S7 killed confidence-based selection
        out-of-sample, so reintroducing it here would be indefensible.
    """
    out: dict[str, bool] = {}
    for row in rows:
        engine = row.get("engine") or {}
        item = engine.get("item") or {}
        qid, gold = item.get("question_id"), item.get("correct_letter")
        if not qid:
            continue
        seats = row.get("seat_answers") or engine.get("seat_answers") or []
        letters = [str(s.get("letter") or "").strip().upper() for s in seats]
        valid = [(i, L) for i, L in enumerate(letters) if L]
        if not valid:
            out[str(qid)] = False  # all-unparsed counts WRONG, not dropped
            continue
        counts = Counter(L for _, L in valid)
        top = max(counts.values())
        tied = {L for L, c in counts.items() if c == top}
        winner = next(L for _, L in valid if L in tied)  # lowest seat_index
        out[str(qid)] = winner == gold
    return out


def _arm_outcomes(arm: str, seed: int) -> dict[str, bool]:
    rows = _load(ARM_FILES[arm].format(seed=seed))
    if not rows:
        return {}
    return _sc_outcomes(rows) if arm == "C" else _outcomes(rows)


def _sc_diagnostics(seed: int) -> dict | None:
    """Kill clause 4: a control whose samples are near-identical is defeated by
    construction, so its diversity must be reported, not assumed."""
    rows = _load(ARM_FILES["C"].format(seed=seed))
    if not rows:
        return None
    per_sample_correct = per_sample_total = 0
    agree_pairs = total_pairs = 0
    split_items = items = 0
    majority_differs = 0
    for row in rows:
        engine = row.get("engine") or {}
        gold = (engine.get("item") or {}).get("correct_letter")
        seats = row.get("seat_answers") or engine.get("seat_answers") or []
        letters = [str(s.get("letter") or "").strip().upper() for s in seats if s.get("letter")]
        per_sample_correct += sum(1 for L in letters if L == gold)
        per_sample_total += len(letters)
        for i in range(len(letters)):
            for j in range(i + 1, len(letters)):
                total_pairs += 1
                agree_pairs += letters[i] == letters[j]
        if letters:
            items += 1
            if len(set(letters)) > 1:
                split_items += 1
            # Did voting actually change the answer relative to taking one
            # sample? Reported, never a kill -- see the note on the constants.
            majority = max(set(letters), key=letters.count)
            majority_differs += majority != letters[0]

    agreement = (agree_pairs / total_pairs) if total_pairs else None
    split_rate = (split_items / items) if items else None
    degenerate = bool(
        agreement is not None and split_rate is not None
        and (agreement >= DEGENERACY_MAX_AGREEMENT
             or split_rate < DEGENERACY_MIN_SPLIT_ITEM_RATE)
    )
    return {
        "mean_per_sample_accuracy": (per_sample_correct / per_sample_total) if per_sample_total else None,
        "mean_pairwise_agreement": agreement,
        "pairs": total_pairs,
        "items": items,
        "split_item_rate": split_rate,
        "majority_differs_from_first_seat": (majority_differs / items) if items else None,
        "degenerate": degenerate,
    }


def _paired(a: dict[str, bool], other: dict[str, bool], shared: list[str]) -> dict:
    b = sum(1 for q in shared if a[q] and not other[q])
    c = sum(1 for q in shared if other[q] and not a[q])
    return {
        "b": b, "c": c, "net": b - c, "n": len(shared),
        "p_one_sided": mcnemar_exact_one_sided(b, c),
        "a_correct": sum(1 for q in shared if a[q]),
        "other_correct": sum(1 for q in shared if other[q]),
    }


def verify() -> dict:
    present = {
        arm: [s for s in SEEDS if (RESULTS / ARM_FILES[arm].format(seed=s)).exists()]
        for arm in ARM_FILES
    }
    comparators = [arm for arm in ("B", "Bprime", "C") if present[arm]]

    per_seed: dict[int, dict] = {}
    for seed in SEEDS:
        arms = {arm: _arm_outcomes(arm, seed) for arm in ARM_FILES}
        arms = {k: v for k, v in arms.items() if v}
        if "A" not in arms:
            continue
        # S is the intersection of EVERY arm present for this seed, so both
        # comparisons run on identical items and arm A's accuracy is the same
        # number in each.
        shared = sorted(set.intersection(*(set(v) for v in arms.values())))
        entry = {
            "arms_present": sorted(arms),
            "analysis_set_size": len(shared),
            "gate_ok": len(shared) >= MIN_ANALYSIS_SET,
            "dropped_vs_intended": INTENDED_N - len(shared),
            "comparisons": {},
        }
        for arm in comparators:
            if arm in arms:
                entry["comparisons"][arm] = _paired(arms["A"], arms[arm], shared)
        # C vs B -- does SAMPLING beat one call, independent of the scaffold?
        #
        # Not an arm-A comparison, so it lives outside `comparisons`, and it is
        # explicitly NOT a pre-registered test. It is needed to read A-vs-C
        # correctly: a negative A-vs-C says the stack loses to SC@5, but only
        # C-vs-B says whether SC@5 is itself worth the budget. Without it,
        # "the stack loses to the control" is ambiguous between "sampling is
        # good" and "the stack is bad".
        if "C" in arms and "B" in arms:
            entry["sampling_vs_one_call"] = _paired(arms["C"], arms["B"], shared)
        entry["sc_diagnostics"] = _sc_diagnostics(seed)
        per_seed[seed] = entry

    pooled = {}
    sv = [s["sampling_vs_one_call"] for s in per_seed.values()
          if "sampling_vs_one_call" in s]
    if sv:
        b, c = sum(x["b"] for x in sv), sum(x["c"] for x in sv)
        pooled_sampling = {
            "b": b, "c": c, "net": b - c, "n": sum(x["n"] for x in sv),
            "p_one_sided": mcnemar_exact_one_sided(b, c),
            "seeds": [k for k, s in per_seed.items() if "sampling_vs_one_call" in s],
        }
    else:
        pooled_sampling = None
    for arm in comparators:
        b = sum(s["comparisons"][arm]["b"] for s in per_seed.values() if arm in s["comparisons"])
        c = sum(s["comparisons"][arm]["c"] for s in per_seed.values() if arm in s["comparisons"])
        n = sum(s["comparisons"][arm]["n"] for s in per_seed.values() if arm in s["comparisons"])
        seeds_used = [k for k, s in per_seed.items() if arm in s["comparisons"]]
        pooled[arm] = {
            "b": b, "c": c, "net": b - c, "n": n, "seeds": seeds_used,
            "p_one_sided": mcnemar_exact_one_sided(b, c),
            "primary_clears": mcnemar_exact_one_sided(b, c) < PRIMARY_ALPHA and b - c > 0,
        }

    return {
        "per_seed": per_seed,
        "pooled": pooled,
        "pooled_sampling_vs_one_call": pooled_sampling,
        "arms_present": present,
        "arm_c_run": bool(present["C"]),
    }


def main() -> None:
    r = verify()
    print("=" * 78)
    print("TB-1 -- scaffolded flagship (universal_gate) vs solo flagship, GPQA-Diamond")
    print("=" * 78)
    print("Arm A issues ONE qwen3.7-max judge call per item (judge calls/item = 1.00).")
    print("This compares a SCAFFOLDED flagship call against an UNSCAFFOLDED one.")
    print("It is NOT 'cheap seats beat a stronger model' -- that wording is prohibited.")
    print()

    if not r["per_seed"]:
        print("  Arm A files not found -- nothing to compare.")
        return

    if r["arm_c_run"]:
        print("  NOTE: arm C is present, so the analysis set S is A n B n C and")
        print("  is SMALLER than the A n B set used before arm C existed. The")
        print("  A-vs-B numbers below will therefore differ from any previously")
        print("  published TB-1 figure. That is the spec's requirement (section 5:")
        print("  both comparisons on the same S, so arm A's accuracy is one")
        print("  number in both tables) -- not a contradiction, and not a")
        print("  correction. Quote the A-vs-B figure together with the S it was")
        print("  computed on.")
        print()

    for seed, s in r["per_seed"].items():
        print(f"  seed {seed}: arms present {s['arms_present']}, |S|={s['analysis_set_size']}")
        if not s["gate_ok"]:
            print(f"    *** SEED VOID: |S|={s['analysis_set_size']} < {MIN_ANALYSIS_SET} "
                  f"(90% of the intended {INTENDED_N}). Do not analyse this seed.")
        if s["dropped_vs_intended"]:
            print(f"    {s['dropped_vs_intended']} items short of the intended {INTENDED_N}. "
                  f"Drops are 504-correlated and therefore NOT MCAR.")
        for arm, cmp_ in s["comparisons"].items():
            sig = "clears" if cmp_["p_one_sided"] < SECONDARY_ALPHA else "does not clear"
            print(f"    A vs {arm}: A={cmp_['a_correct']}/{cmp_['n']} vs {arm}={cmp_['other_correct']}/{cmp_['n']}"
                  f"  b={cmp_['b']} c={cmp_['c']} net={cmp_['net']:+d} p={cmp_['p_one_sided']:.5f}"
                  f"  [secondary, alpha={SECONDARY_ALPHA:.4f}: {sig}]")
        if s["sc_diagnostics"]:
            d = s["sc_diagnostics"]
            print(f"    arm C diversity: mean per-sample acc={d['mean_per_sample_accuracy']:.3f}, "
                  f"mean pairwise agreement={d['mean_pairwise_agreement']:.3f} "
                  f"({d['pairs']} pairs)")
            print(f"      items where the 5 seats split at all: "
                  f"{d['split_item_rate']:.1%} of {d['items']}"
                  f"   | voting changed the answer on "
                  f"{d['majority_differs_from_first_seat']:.1%} (reported, not a kill)")
            if d["degenerate"]:
                print(f"      ** KILL CLAUSE 4 FIRED -- arm C is DEGENERATE "
                      f"(agreement >= {DEGENERACY_MAX_AGREEMENT} or split rate "
                      f"< {DEGENERACY_MIN_SPLIT_ITEM_RATE:.0%}). A-vs-C is VOID, "
                      f"not favourable to arm A. **")
        print()

    print("-" * 78)
    print("PRIMARY TEST -- pooled 3-seed exact one-sided McNemar, alpha=0.05")
    print("-" * 78)
    for arm, p in r["pooled"].items():
        print(f"  A vs {arm}: b={p['b']} c={p['c']} net={p['net']:+d} n={p['n']} "
              f"p={p['p_one_sided']:.6f} seeds={p['seeds']}  "
              f"-> {'CLEARS' if p['primary_clears'] else 'does not clear'}")
    print()

    if not r["arm_c_run"]:
        print("  *** arm C NOT RUN -- every A-vs-B number above is COMPUTE-UNMATCHED.")
        print("  *** universal_gate spends ~4.7x a single flagship call. Publishing an")
        print("  *** A-vs-B result without arm C is the exact failure that required")
        print("  *** retracting flagship_panel's mechanism. Say 'compute-unmatched' at")
        print("  *** every point of use until arm C lands.")
        print()
    else:
        # Kill clause 1 (attribution). Evaluated here rather than left to be
        # computed by hand at write-up time, which is where a pre-registered
        # rule quietly becomes a judgement call.
        c = r["pooled"]["C"]
        degenerate = [s for s, e in r["per_seed"].items()
                      if (e.get("sc_diagnostics") or {}).get("degenerate")]
        print("-" * 78)
        print("KILL CLAUSE 1 -- attribution (spec section 6.1)")
        print("-" * 78)
        if degenerate:
            print(f"  arm C is DEGENERATE at seed(s) {degenerate} -- kill clause 4.")
            print("  A-vs-C is VOID there, NOT favourable to arm A.")
        if len(c["seeds"]) < len(SEEDS):
            print(f"  PARTIAL: arm C has fired {len(c['seeds'])} of {len(SEEDS)} seeds "
                  f"{c['seeds']}. The primary is the pooled 3-seed test; anything")
            print("  below that is SECONDARY and EXPLORATORY and must be labelled so.")
        if c["net"] <= 0:
            print(f"  pooled A-vs-C net={c['net']:+d} <= 0  ->  ATTRIBUTION KILL FIRES.")
            print("  Report in the spec's words: a COMPUTE EFFECT, NOT AN ORCHESTRATION")
            print("  EFFECT. The tokens buy more accuracy spent on plain sampling.")
        elif c["primary_clears"]:
            print(f"  pooled A-vs-C net={c['net']:+d}, p={c['p_one_sided']:.4f} -> clears.")
            print("  Arm A earns a mechanism claim: the gain is orchestration, not budget.")
        else:
            print(f"  pooled A-vs-C net={c['net']:+d}, p={c['p_one_sided']:.4f} -- positive")
            print("  but not significant. Report as ATTRIBUTION UNRESOLVED, never as a")
            print("  win (spec section 6.1: the asymmetry that granted mechanism survival")
            print("  on net >= +1 with no significance requirement was removed).")
        print()
    sv = r.get("pooled_sampling_vs_one_call")
    if sv:
        print("-" * 78)
        print("CONTEXT (not a pre-registered test) -- does SAMPLING beat one call?")
        print("-" * 78)
        print(f"  C vs B: flagship SC@5 vs one flagship call, on the same S")
        print(f"    b={sv['b']} c={sv['c']} net={sv['net']:+d} n={sv['n']} "
              f"p={sv['p_one_sided']:.4f} seeds={sv['seeds']}")
        print("  Needed to read A-vs-C correctly. A negative A-vs-C says the stack")
        print("  loses to the control; only this says whether the control is itself")
        print("  worth the budget. Without it, 'the stack loses' is ambiguous between")
        print("  'sampling is good' and 'the stack is bad'.")
        print()
    print("  reproduce: python -m benchmark.verify_tb1_flagship")


if __name__ == "__main__":
    main()
