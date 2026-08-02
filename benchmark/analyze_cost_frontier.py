"""Paired accuracy-per-token frontier, on IDENTICAL items.

Answers the only question that decides whether this project's architecture is
worth running: does any configuration earn its tokens against the obvious
alternative of one flagship call?

WHY THIS EXISTS ALONGSIDE benchmark/results/f2_compute_frontier.csv. That file
pools each configuration across whatever seeds it happened to run on --
`baseline_3.7max` over 7/123/314, `chem_thinking_gate` over 217/314/471, and so
on. Those are different item samples. The flagship's own measured seed spread on
GPQA is 83.0 / 86.5 / 94.3%, so a cross-seed frontier can invert purely from
sampling. This script refuses to compare arms that did not run on the same
items: every number below is computed on the per-seed intersection.

RETIRED POINT ESTIMATES ARE EXCLUDED BY CONSTRUCTION. A frontier is a claim
about what is achievable; a withdrawn number cannot support one. See
benchmark/figure_data.RETIRED_POINT_ESTIMATES -- `qwen3.8_solo`'s 93.6% was
found setting the ceiling of a published frontier figure on 2026-08-02 despite
having been retired on 2026-07-30.

Offline. No API calls, no tokens.

    python -m benchmark.analyze_cost_frontier
    python -m benchmark.analyze_cost_frontier --dataset supergpqa
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided
from benchmark.figure_data import RETIRED_POINT_ESTIMATES

RESULTS = Path(__file__).resolve().parent / "results"

#: dataset -> {config: (filename template, seeds)}. Only configs with a real
#: committed file are used; missing ones are reported, never silently skipped.
ARMS = {
    "gpqa": {
        "flagship_1x": ("TB1_flagship1x_gpqa_seed{s}.jsonl", (1001, 2311, 3407)),
        "universal_gate": ("lever_universal_gate_gpqa_seed{s}.jsonl", (1001, 2311, 3407)),
    },
    "supergpqa": {
        "flagship_1x": ("lever_baseline_supergpqa_seed{s}.jsonl", (7, 42, 123)),
        "flagship_panel": ("lever_flagship_panel_supergpqa_seed{s}.jsonl", (7, 42, 123)),
        "flagship_sc3": ("compute_matched_control_supergpqa_seed{s}.jsonl", (7, 42, 123)),
        "cheap_panel": ("lever_control_supergpqa_seed{s}.jsonl", (7, 42, 123)),
    },
}

#: The reference every other arm is paired against.
REFERENCE = "flagship_1x"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _record(row: dict) -> dict | None:
    """Tolerates this repo's three row wrappers -- engine / baseline / result."""
    for key in ("engine", "baseline", "result"):
        rec = row.get(key)
        if isinstance(rec, dict) and "correct" in rec:
            return rec
    return None


def _arm(path: Path) -> dict[str, tuple[bool, int]]:
    out = {}
    for row in _load(path):
        rec = _record(row)
        if not rec:
            continue
        qid = (rec.get("item") or {}).get("question_id")
        if not qid:
            continue
        tokens = sum(c["input_tokens"] + c["output_tokens"] for c in rec.get("calls", []))
        out[str(qid)] = (bool(rec["correct"]), tokens)
    return out


def analyze(dataset: str) -> dict:
    spec = ARMS[dataset]
    retired = [c for c in spec if c in RETIRED_POINT_ESTIMATES]

    agg = {c: {"correct": 0, "tokens": 0, "n": 0} for c in spec}
    paired = {c: {"b": 0, "c": 0} for c in spec if c != REFERENCE}
    seeds_used, seeds_missing = [], []

    for seed in sorted({s for _, seeds in spec.values() for s in seeds}):
        arms = {}
        for config, (template, seeds) in spec.items():
            if seed not in seeds:
                continue
            data = _arm(RESULTS / template.format(s=seed))
            if data:
                arms[config] = data
        # A seed is usable only if the REFERENCE and at least one other arm ran.
        if REFERENCE not in arms or len(arms) < 2:
            seeds_missing.append({"seed": seed, "arms_found": sorted(arms)})
            continue
        shared = sorted(set.intersection(*(set(v) for v in arms.values())))
        seeds_used.append({"seed": seed, "arms": sorted(arms), "n_shared": len(shared)})
        for config, data in arms.items():
            agg[config]["correct"] += sum(data[q][0] for q in shared)
            agg[config]["tokens"] += sum(data[q][1] for q in shared)
            agg[config]["n"] += len(shared)
            if config != REFERENCE:
                paired[config]["b"] += sum(1 for q in shared if data[q][0] and not arms[REFERENCE][q][0])
                paired[config]["c"] += sum(1 for q in shared if arms[REFERENCE][q][0] and not data[q][0])

    points = {}
    for config, a in agg.items():
        if not a["n"]:
            continue
        acc = a["correct"] / a["n"]
        tpi = a["tokens"] / a["n"]
        entry = {
            "accuracy": acc, "tokens_per_item": tpi, "n": a["n"],
            "accuracy_per_1k_tokens": acc / (tpi / 1000) if tpi else None,
            "retired": config in RETIRED_POINT_ESTIMATES,
        }
        if config in paired:
            b, c = paired[config]["b"], paired[config]["c"]
            entry.update({
                "b": b, "c": c, "net": b - c,
                "p_one_sided": mcnemar_exact_one_sided(b, c),
                "beats_reference": (b - c) > 0 and mcnemar_exact_one_sided(b, c) < 0.05,
            })
        points[config] = entry

    # Pareto: dominated iff another NON-RETIRED point has >= accuracy and <= cost.
    live = {k: v for k, v in points.items() if not v["retired"]}
    for config, e in points.items():
        dominators = [
            k for k, o in live.items()
            if k != config and o["accuracy"] >= e["accuracy"] and o["tokens_per_item"] <= e["tokens_per_item"]
        ]
        e["dominated_by"] = dominators
        e["on_frontier"] = not dominators and not e["retired"]

    return {
        "dataset": dataset, "points": points,
        "seeds_used": seeds_used, "seeds_missing": seeds_missing,
        "retired_excluded": retired,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", choices=sorted(ARMS), default="gpqa")
    args = parser.parse_args()
    r = analyze(args.dataset)

    print("=" * 86)
    print(f"PAIRED cost frontier -- {r['dataset']} -- identical items only")
    print("=" * 86)
    for s in r["seeds_used"]:
        print(f"  seed {s['seed']}: |S|={s['n_shared']}  arms={s['arms']}")
    for s in r["seeds_missing"]:
        print(f"  seed {s['seed']}: SKIPPED -- needs '{REFERENCE}' plus >=1 other arm, found {s['arms_found']}")
    if r["retired_excluded"]:
        print(f"  EXCLUDED as retired point estimates: {r['retired_excluded']}")
    print()

    print(f"  {'config':<18}{'acc':>8}{'n':>6}{'tok/item':>10}{'acc/1k':>9}  "
          f"{'vs ' + REFERENCE:<30}frontier")
    ref_n = r["points"].get(REFERENCE, {}).get("n")
    for config, e in sorted(r["points"].items(), key=lambda kv: kv[1]["tokens_per_item"]):
        if config == REFERENCE:
            versus = "(reference)"
        else:
            versus = (f"b={e['b']} c={e['c']} net={e['net']:+d} p={e['p_one_sided']:.4f}"
                      + (" BEATS" if e["beats_reference"] else ""))
        flag = "ON FRONTIER" if e["on_frontier"] else ("RETIRED" if e["retired"] else "dominated")
        print(f"  {config:<18}{e['accuracy']*100:>7.1f}%{e['n']:>6}{e['tokens_per_item']:>10.0f}"
              f"{e['accuracy_per_1k_tokens']:>9.3f}  {versus:<30}{flag}")
    print()
    # An arm absent from a seed shrinks ITS n while the reference keeps the
    # larger one. The PAIRED statistic is unaffected -- it only ever uses items
    # that arm shares with the reference -- but the ACCURACY column is then not
    # on one common item set. Say so rather than let it read as if it were.
    short = {k: e["n"] for k, e in r["points"].items() if ref_n and e["n"] < ref_n}
    if short:
        print(f"  NOTE: reference n={ref_n}. These arms ran on fewer seeds, so their ACCURACY "
              f"column is NOT on the same item set: "
              + ", ".join(f"{k} (n={n})" for k, n in short.items()))
        print("        Their b/c/net/p ARE still paired only on items shared with the reference.")
        print()
    ref = r["points"].get(REFERENCE)
    if ref:
        best = max((e["accuracy_per_1k_tokens"] for k, e in r["points"].items() if k != REFERENCE), default=None)
        if best:
            print(f"  {REFERENCE} is {ref['accuracy_per_1k_tokens'] / best:.1f}x more token-efficient "
                  f"than the best alternative configuration.")
    print()
    print(f"  reproduce: python -m benchmark.analyze_cost_frontier --dataset {r['dataset']}")


if __name__ == "__main__":
    main()
