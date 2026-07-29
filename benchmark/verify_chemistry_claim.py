"""Verify chem_thinking_gate's claim end-to-end from committed files.

Prior state (corrected 2026-07-26, commit 019d9da): the "+4.4" headline was ONE
matched seed (314), n=87, b=6 c=2, p=0.145 -- did not clear the bar. Seeds
217/471 had no matched flagship baseline, so the doc said so honestly and
Tier G of the approved week-1 queue was exactly this: run those two missing
baselines to complete the 3-seed paired comparison.

Both landed 2026-07-29 (seed 217: 88/90 rows; seed 471: 88/90 rows, both
exit 0). This script computes the real 3-seed result.

Everything here is a PAIRED test on the intersection of question_ids present in
both arms, exactly like verify_flagship_claim.py.

Offline. No API calls, no tokens.

    python -m benchmark.verify_chemistry_claim
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

RESULTS = Path(__file__).resolve().parent / "results"

ARMS = {
    217: ("lever_chem_thinking_gate_gpqa_seed217.jsonl", "lever_baseline_gpqa_seed217.jsonl"),
    314: ("lever_chem_thinking_gate_gpqa_seed314.jsonl", "lever_baseline_gpqa_seed314.jsonl"),
    471: ("lever_chem_thinking_gate_gpqa_seed471.jsonl", "lever_baseline_gpqa_seed471.jsonl"),
}

# The one seed that was matched before Tier G ran.
PUBLISHED_SEED314_PP = 4.60


def _load(name: str) -> list[dict]:
    with (RESULTS / name).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _outcomes(rows: list[dict]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for row in rows:
        for key in ("engine", "baseline", "result"):
            rec = row.get(key)
            if isinstance(rec, dict) and "correct" in rec:
                qid = (rec.get("item") or {}).get("question_id")
                if qid:
                    out[str(qid)] = bool(rec["correct"])
    return out


def verify() -> dict:
    per_seed = {}
    pooled_b = pooled_c = pooled_n = 0

    for seed, (cand_file, base_file) in sorted(ARMS.items()):
        cand = _outcomes(_load(cand_file))
        base = _outcomes(_load(base_file))
        shared = sorted(set(cand) & set(base))
        if not shared:
            raise AssertionError(
                f"seed {seed}: zero shared question_ids between {cand_file} and "
                f"{base_file} -- wrapper key mismatch, not a null result"
            )
        b = sum(1 for q in shared if cand[q] and not base[q])
        c = sum(1 for q in shared if base[q] and not cand[q])
        per_seed[seed] = {
            "candidate_n": len(cand), "comparator_n": len(base), "shared": len(shared),
            "b": b, "c": c, "net": b - c,
            "delta_pp": 100.0 * (b - c) / len(shared),
            "p_one_sided": mcnemar_exact_one_sided(b, c),
        }
        pooled_b += b
        pooled_c += c
        pooled_n += len(shared)

    return {
        "per_seed": per_seed,
        "pooled": {
            "shared": pooled_n, "b": pooled_b, "c": pooled_c, "net": pooled_b - pooled_c,
            "delta_pp": 100.0 * (pooled_b - pooled_c) / pooled_n,
            "p_one_sided": mcnemar_exact_one_sided(pooled_b, pooled_c),
        },
    }


def main() -> None:
    r = verify()
    print("chem_thinking_gate vs matched qwen3.7-max single call, GPQA-Diamond")
    print("PAIRED on the question_id intersection of each arm.")
    print()
    print(f"  {'seed':<6}{'cand_n':>7}{'base_n':>7}{'shared':>7}{'b':>4}{'c':>4}"
          f"{'net':>6}{'delta':>8}{'p':>10}")
    for seed, s in r["per_seed"].items():
        print(f"  {seed:<6}{s['candidate_n']:>7}{s['comparator_n']:>7}"
              f"{s['shared']:>7}{s['b']:>4}{s['c']:>4}{s['net']:>+6}"
              f"{s['delta_pp']:>+8.1f}{s['p_one_sided']:>10.4f}")
    p = r["pooled"]
    print()
    print(f"  POOLED: n={p['shared']}, b={p['b']} gains, c={p['c']} losses, "
          f"net={p['net']:+d}, delta={p['delta_pp']:+.2f}pp")
    print(f"  pooled one-sided exact McNemar p = {p['p_one_sided']:.5f}"
          f"  -> {'CLEARS p<0.05' if p['p_one_sided'] < 0.05 else 'DOES NOT CLEAR'}")
    print()
    print("  Against the repo bar -- 'net >= +5 at one seed with McNemar p<0.05,")
    print("  OR net >= +3 at 2 of 3 seeds with the pooled McNemar clearing':")
    single = [s for s in r["per_seed"].values() if s["net"] >= 5 and s["p_one_sided"] < 0.05]
    two_of_three = sum(1 for s in r["per_seed"].values() if s["net"] >= 3)
    print(f"    branch 1 -- seeds with net>=+5 AND p<0.05 : {len(single)}"
          f" {'(satisfied)' if single else '(not satisfied)'}")
    print(f"    branch 2 -- seeds with net>=+3            : {two_of_three} of 3, "
          f"pooled p={p['p_one_sided']:.5f}"
          f" {'(satisfied)' if two_of_three >= 2 and p['p_one_sided'] < 0.05 else '(not satisfied)'}")
    print()
    print("  HETEROGENEITY -- do not quote the pooled number alone:")
    for seed, s in r["per_seed"].items():
        tag = "big win" if s["net"] >= 5 else ("negative" if s["net"] < 0 else "small/noise")
        print(f"    seed {seed}: net={s['net']:+d} ({tag})")
    print()
    print("  reproduce: python -m benchmark.verify_chemistry_claim")


if __name__ == "__main__":
    main()
