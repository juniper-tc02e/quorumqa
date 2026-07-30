"""Does flagship_panel's +4.1/+10 survive a compute-matched control?

`docs/FINDINGS.md` and `docs/capability-roadmap.md` flag this as the one
untested premise behind the repo's only validated accuracy claim: flagship_panel
runs ~3.0x the tokens of a single flagship call, and no run ever isolated
whether the gain is deliberation or just self-consistency at equal compute.

Pre-registered analysis plan (written before any control data existed, see the
commit that added run_compute_matched_control.py):

  - PRIMARY test: paired McNemar, flagship_panel vs the compute-matched control,
    on shared items, pooled across seeds 42/7/123 -- mirrors
    verify_flagship_claim.py exactly, just with a different comparator.
  - If the control's pooled net is >= 5 (half of flagship_panel's +10): a
    material part of the claimed gain is attributable to plain
    self-consistency, and the claim must be relabelled "deliberation adds
    <net> beyond self-consistency", not "+10 beyond a single call".
  - If the control's pooled net is small or negative: flagship_panel's gain
    survives compute-matching and the deliberation mechanism (not just
    sampling more) is what is doing the work.
  - Either outcome is publishable. This script computes the number; it does
    not pre-judge which reading is right.

Offline once the control files exist. No API calls, no tokens.

    python -m benchmark.verify_compute_matched_control
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

RESULTS = Path(__file__).resolve().parent / "results"

SEEDS = (42, 7, 123)
FLAGSHIP_PANEL_FILE = "lever_flagship_panel_supergpqa_seed{seed}.jsonl"
CONTROL_FILE = "compute_matched_control_supergpqa_seed{seed}.jsonl"

# The 1x flagship single call the ORIGINAL +4.1/+10 claim was measured against.
# Seed 42's comparator lives inside the pilot file -- see verify_flagship_claim.py.
BASELINE_FILE = {
    42: "supergpqa_hard_pilot_seed42.jsonl",
    7: "lever_baseline_supergpqa_seed7.jsonl",
    123: "lever_baseline_supergpqa_seed123.jsonl",
}

# The claim this script is checking, for the printed comparison.
CLAIM_POOLED_NET = 10
CLAIM_POOLED_P = 0.00317


def _load(name: str) -> list[dict]:
    path = RESULTS / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
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
    missing_seeds = []

    for seed in SEEDS:
        panel_rows = _load(FLAGSHIP_PANEL_FILE.format(seed=seed))
        control_rows = _load(CONTROL_FILE.format(seed=seed))
        if not control_rows:
            missing_seeds.append(seed)
            continue

        panel = _outcomes(panel_rows)
        control = _outcomes(control_rows)
        shared = sorted(set(panel) & set(control))
        if not shared:
            raise AssertionError(
                f"seed {seed}: zero shared question_ids between flagship_panel "
                f"and the compute-matched control -- wrapper key mismatch, not a null result"
            )
        b = sum(1 for q in shared if panel[q] and not control[q])
        c = sum(1 for q in shared if control[q] and not panel[q])
        per_seed[seed] = {
            "panel_n": len(panel), "control_n": len(control), "shared": len(shared),
            "b": b, "c": c, "net": b - c,
            "delta_pp": 100.0 * (b - c) / len(shared),
            "p_one_sided": mcnemar_exact_one_sided(b, c),
        }
        pooled_b += b
        pooled_c += c
        pooled_n += len(shared)

    pooled = None
    if pooled_n:
        pooled = {
            "shared": pooled_n, "b": pooled_b, "c": pooled_c, "net": pooled_b - pooled_c,
            "delta_pp": 100.0 * (pooled_b - pooled_c) / pooled_n,
            "p_one_sided": mcnemar_exact_one_sided(pooled_b, pooled_c),
        }

    # THIRD LEG, measured directly rather than inferred by subtraction. Paired
    # tests on different shared-item sets do NOT subtract cleanly, so the
    # decomposition of the original +10 has to be measured, not arithmetic'd.
    sc_b = sc_c = sc_n = 0
    sc_per_seed = {}
    for seed in SEEDS:
        control = _outcomes(_load(CONTROL_FILE.format(seed=seed)))
        baseline = _outcomes(_load(BASELINE_FILE[seed]))
        if not control or not baseline:
            continue
        shared = sorted(set(control) & set(baseline))
        if not shared:
            raise AssertionError(
                f"seed {seed}: zero shared question_ids between the control and the "
                f"1x baseline -- wrapper key mismatch, not a null result"
            )
        b = sum(1 for q in shared if control[q] and not baseline[q])
        c = sum(1 for q in shared if baseline[q] and not control[q])
        sc_per_seed[seed] = {
            "shared": len(shared), "b": b, "c": c, "net": b - c,
            "delta_pp": 100.0 * (b - c) / len(shared),
            "p_one_sided": mcnemar_exact_one_sided(b, c),
        }
        sc_b += b
        sc_c += c
        sc_n += len(shared)

    self_consistency = None
    if sc_n:
        self_consistency = {
            "per_seed": sc_per_seed, "shared": sc_n, "b": sc_b, "c": sc_c,
            "net": sc_b - sc_c, "delta_pp": 100.0 * (sc_b - sc_c) / sc_n,
            "p_one_sided": mcnemar_exact_one_sided(sc_b, sc_c),
        }

    return {
        "per_seed": per_seed, "pooled": pooled, "missing_seeds": missing_seeds,
        "self_consistency_vs_baseline": self_consistency,
    }


def main() -> None:
    r = verify()
    print("Compute-matched control vs flagship_panel, SuperGPQA-hard")
    print("PAIRED on the question_id intersection of each arm (panel wins = b, control wins = c).")
    print()
    if r["missing_seeds"]:
        print(f"  Not yet run: seed(s) {r['missing_seeds']} -- partial result below.")
        print()
    if not r["per_seed"]:
        print("  No control data yet. Run: python -m benchmark.run_compute_matched_control --seed <42|7|123>")
        return

    print(f"  {'seed':<6}{'panel_n':>8}{'ctrl_n':>8}{'shared':>7}{'b':>4}{'c':>4}{'net':>6}{'delta':>8}{'p':>10}")
    for seed, s in r["per_seed"].items():
        print(f"  {seed:<6}{s['panel_n']:>8}{s['control_n']:>8}{s['shared']:>7}"
              f"{s['b']:>4}{s['c']:>4}{s['net']:>+6}{s['delta_pp']:>+8.1f}{s['p_one_sided']:>10.4f}")

    if r["pooled"]:
        p = r["pooled"]
        print()
        print(f"  POOLED: n={p['shared']}, b={p['b']}, c={p['c']}, net={p['net']:+d}, "
              f"delta={p['delta_pp']:+.2f}pp, p={p['p_one_sided']:.5f}")
        print()
        print(f"  Original claim (flagship_panel vs 1x flagship): net={CLAIM_POOLED_NET:+d}, "
              f"p={CLAIM_POOLED_P:.5f}")
        print(f"  This control  (flagship_panel vs 3x-flagship-majority): net={p['net']:+d}, "
              f"p={p['p_one_sided']:.5f}")
        print()
        sc = r.get("self_consistency_vs_baseline")
        if sc:
            print("  DECOMPOSITION of the original +10, each leg MEASURED directly")
            print("  (paired tests on different shared-item sets do not subtract cleanly,")
            print("   so none of these numbers is inferred by arithmetic):")
            print()
            print(f"    3x flagship majority vs 1x flagship  : net={sc['net']:+d}  "
                  f"p={sc['p_one_sided']:.5f}  n={sc['shared']}  "
                  f"[{'CLEARS' if sc['p_one_sided'] < 0.05 else 'does not clear'}]")
            print(f"    flagship_panel vs 3x majority        : net={p['net']:+d}  "
                  f"p={p['p_one_sided']:.5f}  n={p['shared']}  "
                  f"[{'CLEARS' if p['p_one_sided'] < 0.05 else 'does not clear'}]")
            print()
            tribunal_significant = p["p_one_sided"] < 0.05
            sc_significant = sc["p_one_sided"] < 0.05
            if sc_significant and not tribunal_significant:
                print("    READ: the SELF-CONSISTENCY leg carries the claim and the TRIBUNAL leg")
                print("    does not. Sampling the flagship three times and taking a majority")
                print("    reproduces the bulk of the gain on its own; the skeptic/verifier/judge")
                print("    apparatus adds a residual that is statistically indistinguishable from")
                print("    zero. This is exactly what Self-MoA (ICML 2025) predicts and what")
                print("    capability-roadmap.md warned would happen without this control.")
                print("    The claim must be relabelled: flagship_panel's advantage over a single")
                print("    call is a COMPUTE effect, not a deliberation effect.")
            elif tribunal_significant and sc_significant:
                print("    READ: both legs are significant -- self-consistency explains part of the")
                print("    gain and deliberation adds a further significant increment on top.")
            elif tribunal_significant and not sc_significant:
                print("    READ: the tribunal leg is significant and self-consistency alone is not")
                print("    -- deliberation, not extra sampling, is doing the work.")
            else:
                print("    READ: neither leg is individually significant at this n. The original")
                print("    +10 is not cleanly attributable to either mechanism from this data.")
        else:
            print("  Self-consistency leg not computable -- baseline files missing.")

    print()
    print("  reproduce: python -m benchmark.verify_compute_matched_control")


if __name__ == "__main__":
    main()
