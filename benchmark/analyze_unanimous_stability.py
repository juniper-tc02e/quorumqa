"""META-2 -- P(wrong | unanimous): permutation-instability probe on the
unanimous pool. docs/experiment-spec-book.md's META-2, verbatim bar.

Pre-registered BEFORE any live META-2 data exists, so the analysis can't be
chosen after seeing the result -- same discipline as every other
pre-registration this session.

Scope: this implements META-2 alone (arms A/control, B/permuted_panel,
C/resample-only-control). SCI-1's restate_probe (the merged --restate arm in
the spec's own command block) is a separate, not-yet-built lever; there is
nothing to read for it yet, so --restate is not implemented here. Extending
this file to fold it in later is additive, not a rewrite.

Arms:
  A (control)        -- shipped 3-seat cheap panel, canonical order.
  B (permuted_panel)  -- identical seats, EXCEPT each seat sees an
                          independently shuffled choice order.
  C (resample-only)   -- a SECOND `control` run at the same seed (same
                          command, different --out) -- isolates plain
                          decoder resampling from permutation itself.

UNANIMOUS, for arms A/B/C specifically: `not row["engine"]["escalated"]`.
Both `control` and `permuted_panel` lack any gate logic that could force an
escalation despite a unanimous vote (unlike e.g. universal_gate or the
verified_gate levers), so escalated is exactly the complement of unanimous
for these two lever types -- verified directly against
benchmark/lever_experiments.py's run_question_lever (the `if unanimous:`
dispatch has no branch for lever in ("control", "permuted_panel")).

FLIP, for a control-unanimous item: the SAME item is NOT unanimous under the
comparison arm (B or C). Per the spec's own hypothesis, "unanimity BREAKS"
-- not merely "the unanimous letter changed while staying unanimous."

    python -m benchmark.analyze_unanimous_stability \
        --control benchmark/results/META2_control_supergpqa_seed909.jsonl \
        --permuted benchmark/results/META2_permuted_panel_supergpqa_seed909.jsonl \
        [--resample benchmark/results/META2_control_resample_supergpqa_seed909.jsonl]

Offline. No API calls, no tokens.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark.analyze_dropout_bias import fisher_exact_two_sided
from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided

# ---------------------------------------------------------------------------
# Pre-registered bar (spec-book, verbatim).
# ---------------------------------------------------------------------------
COVERAGE_GATE_MIN = 0.10          # (a) authorises the extension
COVERAGE_BAND_MIN = 0.05          # 5-10% -> declared BAND, no verdict, no extension
CONTRAST_MIN_PP = 25.0            # (b) predictive contrast, 3-seeds-pooled
CONTRAST_ALPHA = 0.05
CONTRAST_MIN_FLIPPED = 8
KILL_CONTRAST_MAX_PP = 10.0       # gap < 10pt -> kill
KILL_P_MAX = 0.2                  # p > 0.2 -> kill
DROP_RATE_RERUN_THRESHOLD = 0.10  # >10% item drops on any seed -> re-run
ACCURACY_BAR_MIN_NET = 5
ACCURACY_BAR_2OF3_NET = 3


def load_rows(paths) -> dict[str, dict]:
    """question_id -> row, across one or more JSONL files (pooling)."""
    rows: dict[str, dict] = {}
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                qid = row["engine"]["item"]["question_id"]
                rows[qid] = row
    return rows


def is_unanimous(row: dict) -> bool:
    return not row["engine"]["escalated"]


def is_correct(row: dict) -> bool:
    return bool(row["engine"]["correct"])


def _flip_rate(control: dict, comparison: dict) -> dict:
    """Flip rate of `comparison` against control-unanimous items, on the
    shared question_id intersection. Returns counts and the rate, or a
    rate of None if there are zero control-unanimous shared items."""
    shared = sorted(set(control) & set(comparison))
    unanimous_ids = [q for q in shared if is_unanimous(control[q])]
    flipped = [q for q in unanimous_ids if not is_unanimous(comparison[q])]
    n = len(unanimous_ids)
    return {
        "n_shared": len(shared),
        "n_unanimous": n,
        "flipped_ids": flipped,
        "n_flipped": len(flipped),
        "flip_rate": (len(flipped) / n) if n else None,
    }


def analyze(control_paths, permuted_paths, resample_paths=None) -> dict:
    control = load_rows(control_paths)
    permuted = load_rows(permuted_paths)
    resample = load_rows(resample_paths) if resample_paths else {}

    ab = _flip_rate(control, permuted)
    if ab["n_unanimous"] == 0:
        raise AssertionError(
            "zero control-unanimous items in the shared control/permuted intersection "
            "-- cannot compute a flip rate; check the input files"
        )

    unanimous_ids = [q for q in sorted(set(control) & set(permuted)) if is_unanimous(control[q])]
    unanimous_wrong = [q for q in unanimous_ids if not is_correct(control[q])]
    unanimous_right = [q for q in unanimous_ids if is_correct(control[q])]
    flipped_set = set(ab["flipped_ids"])

    flipped_wrong = [q for q in unanimous_wrong if q in flipped_set]
    flipped_right = [q for q in unanimous_right if q in flipped_set]
    flip_rate_wrong = (len(flipped_wrong) / len(unanimous_wrong)) if unanimous_wrong else None
    flip_rate_right = (len(flipped_right) / len(unanimous_right)) if unanimous_right else None
    contrast_pp = (
        (flip_rate_wrong - flip_rate_right) * 100
        if flip_rate_wrong is not None and flip_rate_right is not None
        else None
    )

    a_ = len(flipped_wrong)
    b_ = len(unanimous_wrong) - a_
    c_ = len(flipped_right)
    d_ = len(unanimous_right) - c_
    fisher_p = fisher_exact_two_sided(a_, b_, c_, d_) if unanimous_wrong and unanimous_right else None

    coverage_flip_rate = ab["flip_rate"]
    if coverage_flip_rate >= COVERAGE_GATE_MIN:
        coverage_verdict = "CLEARS -- extension authorised"
    elif coverage_flip_rate >= COVERAGE_BAND_MIN:
        coverage_verdict = "BAND -- no verdict, no extension"
    else:
        coverage_verdict = "KILL -- below the band floor"

    contrast_clears = (
        contrast_pp is not None
        and contrast_pp >= CONTRAST_MIN_PP
        and fisher_p is not None
        and fisher_p < CONTRAST_ALPHA
        and (len(flipped_wrong) + len(flipped_right)) >= CONTRAST_MIN_FLIPPED
    )
    contrast_killed = (
        contrast_pp is not None and contrast_pp < KILL_CONTRAST_MAX_PP
    ) or (fisher_p is not None and fisher_p > KILL_P_MAX)

    # Accuracy side-comparison (B vs A), standard repo McNemar bar.
    b_gain = c_loss = 0
    for q in sorted(set(control) & set(permuted)):
        a_ok, p_ok = is_correct(control[q]), is_correct(permuted[q])
        if p_ok and not a_ok:
            b_gain += 1
        elif a_ok and not p_ok:
            c_loss += 1
    accuracy_net = b_gain - c_loss
    accuracy_p = mcnemar_exact_one_sided(b_gain, c_loss)

    result = {
        "n_shared_control_permuted": ab["n_shared"],
        "n_unanimous_control": ab["n_unanimous"],
        "n_flipped_ab": ab["n_flipped"],
        "flip_rate_ab": coverage_flip_rate,
        "coverage_verdict": coverage_verdict,
        "n_unanimous_wrong": len(unanimous_wrong),
        "n_unanimous_right": len(unanimous_right),
        "n_flipped_wrong": len(flipped_wrong),
        "n_flipped_right": len(flipped_right),
        "flip_rate_wrong": flip_rate_wrong,
        "flip_rate_right": flip_rate_right,
        "contrast_pp": contrast_pp,
        "fisher_p": fisher_p,
        "contrast_clears_bar": contrast_clears,
        "contrast_killed": contrast_killed,
        "accuracy_b_gain": b_gain,
        "accuracy_c_loss": c_loss,
        "accuracy_net": accuracy_net,
        "accuracy_p_one_sided": accuracy_p,
        "accuracy_bar_clears": accuracy_net >= ACCURACY_BAR_MIN_NET and accuracy_p < 0.05,
    }

    if resample:
        ac = _flip_rate(control, resample)
        result["n_shared_control_resample"] = ac["n_shared"]
        result["n_unanimous_control_for_resample"] = ac["n_unanimous"]
        result["flip_rate_c"] = ac["flip_rate"]
        if ac["flip_rate"] is not None:
            result["permutation_specific_pp"] = (coverage_flip_rate - ac["flip_rate"]) * 100
            result["mechanism_verdict"] = (
                "permutation instability" if result["permutation_specific_pp"] > 0
                else "resample-or-permute instability (not distinguishable)"
            )
        else:
            result["permutation_specific_pp"] = None
            result["mechanism_verdict"] = "arm C has zero control-unanimous items -- cannot decompose"
    else:
        result["flip_rate_c"] = None
        result["permutation_specific_pp"] = None
        result["mechanism_verdict"] = "arm C not supplied -- claim must be labelled 'resample-or-permute instability'"

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--control", nargs="+", required=True)
    parser.add_argument("--permuted", nargs="+", required=True)
    parser.add_argument("--resample", nargs="+", default=None)
    parser.add_argument("--out", type=str, default=None, help="optional path to write the full report as JSON")
    args = parser.parse_args()

    r = analyze(args.control, args.permuted, args.resample)

    print("=" * 100)
    print("META-2 -- permutation-instability probe on the unanimous pool")
    print("=" * 100)
    print(f"  control-unanimous items: {r['n_unanimous_control']} / {r['n_shared_control_permuted']} shared")
    print(f"  flip rate (B vs A): {r['flip_rate_ab'] * 100:.1f}%  ({r['n_flipped_ab']} flipped)")
    print(f"  COVERAGE GATE: {r['coverage_verdict']}")
    print()
    print(f"  unanimous & wrong: {r['n_unanimous_wrong']}  (flipped: {r['n_flipped_wrong']}, "
          f"rate: {r['flip_rate_wrong'] * 100:.1f}%)" if r["flip_rate_wrong"] is not None else "  unanimous & wrong: 0")
    print(f"  unanimous & right: {r['n_unanimous_right']}  (flipped: {r['n_flipped_right']}, "
          f"rate: {r['flip_rate_right'] * 100:.1f}%)" if r["flip_rate_right"] is not None else "  unanimous & right: 0")
    if r["contrast_pp"] is not None:
        print(f"  CONTRAST: {r['contrast_pp']:+.1f}pp  (Fisher exact p={r['fisher_p']:.4f})"
              f"  [SCREEN SEED ONLY -- underpowered, cannot carry the predictive claim alone]")
        print(f"    clears pre-registered bar (>=25pp, p<0.05, >=8 flipped): {r['contrast_clears_bar']}")
        print(f"    kill clause (gap<10pt or p>0.2): {r['contrast_killed']}")
    print()
    if r["flip_rate_c"] is not None:
        print(f"  arm C (resample-only) flip rate: {r['flip_rate_c'] * 100:.1f}%")
        print(f"  permutation-specific component: {r['permutation_specific_pp']:+.1f}pp")
    print(f"  MECHANISM: {r['mechanism_verdict']}")
    print()
    print(f"  ACCURACY (B vs A): b={r['accuracy_b_gain']} c={r['accuracy_c_loss']} net={r['accuracy_net']:+d} "
          f"p={r['accuracy_p_one_sided']:.4f}  clears standard bar: {r['accuracy_bar_clears']}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
