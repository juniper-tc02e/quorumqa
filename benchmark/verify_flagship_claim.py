"""Verify the repo's flagship positive claim end-to-end from committed files.

The claim: `flagship_panel` beats a matched `qwen3.7-max` single call on
SuperGPQA-hard by **+4.1pp mean over 3 seeds (+3.8 / +2.4 / +6.2)**.

Why this script exists. Two independent problems converged on it:

  1. `figure_claims_ledger.csv`'s `net_discordant_items` and `mcnemar_p` columns
     are, by the ledger's own admission, "left empty on almost every row" -- so
     the repo's most important claim had never had its paired test computed and
     recorded. The deltas were transcribed; the statistic behind them was not.

  2. An audit found `docs/negative-results.md`'s evidence table citing
     `lever_baseline_supergpqa_seed{42,7,123}.jsonl`, but **seed 42 does not
     exist** under that name. That is the worst kind of clerical error, because
     a reader cannot distinguish "mis-cited filename" from "the seed-42 third of
     the mean was never run." This script settles it: the seed-42 comparator is
     the `baseline` arm carried inside `supergpqa_hard_pilot_seed42.jsonl`, and
     the +3.8 it yields reproduces exactly.

Everything here is a PAIRED test on the intersection of question_ids present in
both arms -- never an accuracy subtraction across differently-sized files.

Offline. No API calls, no tokens.

    python -m benchmark.verify_flagship_claim
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

RESULTS = Path(__file__).resolve().parent / "results"

# seed -> (candidate file, comparator file). Seed 42's comparator is the pilot's
# own baseline arm; there is no lever_baseline_supergpqa_seed42.jsonl and the
# evidence table used to imply otherwise.
ARMS = {
    7: ("lever_flagship_panel_supergpqa_seed7.jsonl", "lever_baseline_supergpqa_seed7.jsonl"),
    42: ("lever_flagship_panel_supergpqa_seed42.jsonl", "supergpqa_hard_pilot_seed42.jsonl"),
    123: ("lever_flagship_panel_supergpqa_seed123.jsonl", "lever_baseline_supergpqa_seed123.jsonl"),
}

# The published per-seed deltas we are trying to reproduce.
PUBLISHED_PP = {7: 2.4, 42: 3.8, 123: 6.2}


def _load(name: str) -> list[dict]:
    with (RESULTS / name).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _outcomes(rows: list[dict]) -> dict[str, bool]:
    """question_id -> correct, tolerating the three wrapper layouts in use.

    Result files wrap the record under "engine" (lever runs), "baseline"
    (baseline runs), or carry both (pilot runs). Reading the wrong key yields an
    EMPTY dict, which silently looks like "no shared items" rather than an
    error -- so callers must assert on the shared count.
    """
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
            "candidate_n": len(cand),
            "comparator_n": len(base),
            "shared": len(shared),
            "b": b,
            "c": c,
            "net": b - c,
            "delta_pp": 100.0 * (b - c) / len(shared),
            "p_one_sided": mcnemar_exact_one_sided(b, c),
        }
        pooled_b += b
        pooled_c += c
        pooled_n += len(shared)

    return {
        "per_seed": per_seed,
        "pooled": {
            "shared": pooled_n,
            "b": pooled_b,
            "c": pooled_c,
            "net": pooled_b - pooled_c,
            "delta_pp": 100.0 * (pooled_b - pooled_c) / pooled_n,
            "p_one_sided": mcnemar_exact_one_sided(pooled_b, pooled_c),
        },
    }


def main() -> None:
    r = verify()
    print("flagship_panel vs matched qwen3.7-max single call, SuperGPQA-hard")
    print("PAIRED on the question_id intersection of each arm.")
    print()
    print(f"  {'seed':<6}{'cand_n':>7}{'base_n':>7}{'shared':>7}{'b':>4}{'c':>4}"
          f"{'net':>6}{'delta':>8}{'p':>10}  published")
    ok = True
    for seed, s in r["per_seed"].items():
        pub = PUBLISHED_PP[seed]
        match = abs(s["delta_pp"] - pub) < 0.1
        ok &= match
        print(f"  {seed:<6}{s['candidate_n']:>7}{s['comparator_n']:>7}"
              f"{s['shared']:>7}{s['b']:>4}{s['c']:>4}{s['net']:>+6}"
              f"{s['delta_pp']:>+8.1f}{s['p_one_sided']:>10.4f}"
              f"  {pub:+.1f} {'OK' if match else 'MISMATCH'}")
    p = r["pooled"]
    print()
    print(f"  POOLED: n={p['shared']}, b={p['b']} gains, c={p['c']} losses, "
          f"net={p['net']:+d}, delta={p['delta_pp']:+.2f}pp")
    print(f"  pooled one-sided exact McNemar p = {p['p_one_sided']:.5f}"
          f"  -> {'CLEARS p<0.05' if p['p_one_sided'] < 0.05 else 'DOES NOT CLEAR'}")
    print()
    print("  Against the repo bar -- 'net >= +5 at one seed with McNemar p<0.05,")
    print("  OR net >= +3 at 2 of 3 seeds with the pooled McNemar clearing':")
    single = [s for s in r["per_seed"].values()
              if s["net"] >= 5 and s["p_one_sided"] < 0.05]
    two_of_three = sum(1 for s in r["per_seed"].values() if s["net"] >= 3)
    print(f"    branch 1 -- seeds with net>=+5 AND p<0.05 : {len(single)}"
          f" {'(satisfied)' if single else '(not satisfied)'}")
    print(f"    branch 2 -- seeds with net>=+3            : {two_of_three} of 3, "
          f"pooled p={p['p_one_sided']:.5f}"
          f" {'(satisfied)' if two_of_three >= 2 and p['p_one_sided'] < 0.05 else '(not satisfied)'}")
    print()
    print(f"  per-seed deltas reproduce published values: {'YES' if ok else 'NO'}")
    print()
    print("  CAVEAT -- the candidate arm dropped items on every seed")
    print("  (79/83/81 rows against comparators of 86/88/86). The PAIRED test is")
    print("  unaffected in kind, because both arms are compared on the same")
    print("  surviving items, but the item SAMPLE is survivor-selected. Unlike")
    print("  the D0 bar, a drop here biases the estimate only if dropping")
    print("  correlates with the treatment effect itself, not merely with")
    print("  difficulty. Pooled n=241, not the 270 the roadmap's bar names.")
    print()
    print("  reproduce: python -m benchmark.verify_flagship_claim")


if __name__ == "__main__":
    main()
