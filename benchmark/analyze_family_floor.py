"""F1 / F2 / F5 offline log-mining analysis (docs/same-provider-scaling-
research.md section 3, "free rungs"). Reads every committed JSONL in
benchmark/results/ (no API calls), normalizes the ~10 distinct row schemas
into one flat record type, and computes:

  F1  family blind-spot intersection (per benchmark) + GPQA qwen3.8-solo
      deficit decomposition (never-escalated vs escalated-and-lost)
  F2  compute-allocation frontier: accuracy vs mean tokens/question per
      config per benchmark, with Pareto-dominance crossovers flagged
  F5  difficulty-conditional non-monotonicity map, using moo_m1_eval's
      four blended-workload buckets (gpqa_hard / supergpqa_hard / medqa /
      saturated_easy_mmlu) as the difficulty tiers, multi-agent profile vs
      the 'single-call' comparator

Usage:
    .venv/Scripts/python.exe benchmark/analyze_family_floor.py

Writes:
    benchmark/results/f1_family_floor_items.csv
    benchmark/results/f1_gpqa_deficit_items.csv
    benchmark/results/f2_compute_frontier.csv
    benchmark/results/f5_difficulty_map.csv
    benchmark/results/family_floor_analysis_data.json  (everything, for
        re-checking any number quoted in the .md report)

Nothing here makes a network or paid API call -- pure offline JSONL mining.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

RESULTS_DIR = Path(__file__).resolve().parent / "results"


# ---------------------------------------------------------------------------
# Normalized record
# ---------------------------------------------------------------------------


@dataclass
class Rec:
    source_file: str
    benchmark: str
    config: str
    question_id: str
    correct: bool
    escalated: Optional[bool]
    tokens: Optional[int]
    seed: Optional[int]


def _sum_calls_tokens(calls) -> Optional[int]:
    if not calls:
        return None
    total = 0
    for c in calls:
        total += int(c.get("input_tokens", 0) or 0) + int(c.get("output_tokens", 0) or 0)
    return total


# ---------------------------------------------------------------------------
# Benchmark classification
# ---------------------------------------------------------------------------

DATASET_FIELD_MAP = {
    "gpqa": "GPQA-Diamond",
    "supergpqa": "SuperGPQA-hard",
    "lexam": "LEXam",
    "mmlu_pro_stem": "MMLU-Pro",
    "mmlu_pro": "MMLU-Pro",
}

MOO_BUCKET_MAP = {
    "gpqa_hard": "GPQA-Diamond",
    "supergpqa_hard": "SuperGPQA-hard",
    "medqa": "MedQA",
    "saturated_easy_mmlu": "MMLU-Pro",
}

# Filename substring -> benchmark, for files carrying no explicit `dataset`
# field. Order matters (checked top to bottom, first match wins).
FILENAME_MAP = [
    ("qwen38_baseline", "GPQA-Diamond"),
    ("gsm8k_pilot", "GSM8K"),
    ("medqa_pilot", "MedQA"),
    ("mmlu_pro_pilot", "MMLU-Pro"),
    ("lexam_pilot", "LEXam"),
    ("math500_hard_pilot", "MATH-500-MC"),
    ("supergpqa_hard_pilot", "SuperGPQA-hard"),
    ("mmlu_pro_stem", "MMLU-Pro"),
    ("aime_open", "AIME"),
    ("math_open", "MATH-500-open"),
]


def classify_benchmark(dataset_field: Optional[str], fname: str, question_id: str) -> str:
    if dataset_field:
        return DATASET_FIELD_MAP.get(dataset_field, dataset_field)
    for needle, bench in FILENAME_MAP:
        if needle in fname:
            return bench
    if question_id.startswith("rec"):
        return "GPQA-Diamond"
    if len(question_id) == 32 and all(c in "0123456789abcdef" for c in question_id):
        return "SuperGPQA-hard"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Per-family loaders
# ---------------------------------------------------------------------------

COMBO_BENCHMARK_BY_FNAME = {
    "full_run.jsonl": "GPQA-Diamond",
    "full_run2.jsonl": "GPQA-Diamond",
    "adhoc_check.jsonl": "GPQA-Diamond",
    "smoke.jsonl": "GPQA-Diamond",
    "smoke2.jsonl": "GPQA-Diamond",
    "smoke3.jsonl": "GPQA-Diamond",
    "gsm8k_pilot_seed42.jsonl": "GSM8K",
    "medqa_pilot_seed42.jsonl": "MedQA",
    "mmlu_pro_pilot_seed42.jsonl": "MMLU-Pro",
    "lexam_pilot_seed42.jsonl": "LEXam",
    "math500_hard_pilot_seed42.jsonl": "MATH-500-MC",
    "supergpqa_hard_pilot_seed42.jsonl": "SuperGPQA-hard",
}

LEVER_BASELINE_BENCHMARK_BY_FNAME = {
    "lever_baseline_gpqa_seed314.jsonl": "GPQA-Diamond",
    "lever_baseline_mmlu_pro_stem_seed42.jsonl": "MMLU-Pro",
    "lever_baseline_seed123.jsonl": "GPQA-Diamond",
    "lever_baseline_seed7.jsonl": "GPQA-Diamond",
    "lever_baseline_supergpqa_seed123.jsonl": "SuperGPQA-hard",
    "lever_baseline_supergpqa_seed7.jsonl": "SuperGPQA-hard",
}

# Files that exist but are NOT usable as fresh per-item benchmark
# observations for F1/F2/F5 -- recorded here so the inventory step can be
# honest about what was excluded and why, instead of silently skipping.
EXCLUDED_FILES = {
    "lever_gate_replay.jsonl": (
        "gate-replay analysis artifact (was_unanimous_correct/gate_doubt/"
        "gate_cost_usd schema) -- not a config x item observation, "
        "excluded from F1/F2/F5."
    ),
}


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_combo_file(path: Path, records: list[Rec]) -> int:
    fname = path.name
    bench = COMBO_BENCHMARK_BY_FNAME[fname]
    n = 0
    n_null = 0
    for row in iter_jsonl(path):
        b = row.get("baseline")
        if b is not None:
            records.append(Rec(fname, bench, "baseline_3.7max", b["item"]["question_id"],
                                bool(b["correct"]), None, _sum_calls_tokens(b.get("calls")), None))
            n += 1
        elif "baseline" in row:
            n_null += 1
        e = row.get("engine")
        if e is not None:
            records.append(Rec(fname, bench, "shipped_engine", e["item"]["question_id"],
                                bool(e["correct"]), e.get("escalated"), _sum_calls_tokens(e.get("calls")), None))
            n += 1
        elif "engine" in row:
            n_null += 1
        s = row.get("self_consistency5")
        if s is not None:
            records.append(Rec(fname, bench, "self_consistency_5x", s["item"]["question_id"],
                                bool(s["correct"]), None, _sum_calls_tokens(s.get("calls")), None))
            n += 1
        elif "self_consistency5" in row:
            n_null += 1
    if n_null:
        print(f"  [{fname}] skipped {n_null} null wrapper value(s) (dropped calls logged as null, not zero)")
    return n


def load_lever_baseline_file(path: Path, records: list[Rec]) -> int:
    fname = path.name
    bench = LEVER_BASELINE_BENCHMARK_BY_FNAME[fname]
    n = 0
    for row in iter_jsonl(path):
        b = row["baseline"]
        records.append(Rec(fname, bench, "baseline_3.7max", b["item"]["question_id"],
                            bool(b["correct"]), None, _sum_calls_tokens(b.get("calls")), row.get("seed")))
        n += 1
    return n


def load_lever_engine_file(path: Path, records: list[Rec]) -> int:
    fname = path.name
    n = 0
    for row in iter_jsonl(path):
        e = row["engine"]
        qid = e["item"]["question_id"]
        bench = classify_benchmark(row.get("dataset"), fname, qid)
        config = row.get("lever", "unknown_lever")
        records.append(Rec(fname, bench, config, qid,
                            bool(e["correct"]), e.get("escalated"), _sum_calls_tokens(e.get("calls")), row.get("seed")))
        n += 1
    return n


def load_qwen38_baseline(path: Path, records: list[Rec]) -> int:
    fname = path.name
    n = 0
    for row in iter_jsonl(path):
        usage = row.get("usage") or {}
        tokens = int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0)
        records.append(Rec(fname, "GPQA-Diamond", "qwen3.8_solo", row["question_id"],
                            bool(row["correct"]), None, tokens, None))
        n += 1
    return n


def load_moo_file(path: Path, records: list[Rec], moo_rows: list[dict]) -> int:
    fname = path.name
    n = 0
    for row in iter_jsonl(path):
        bucket = row["bucket"]
        bench = MOO_BUCKET_MAP.get(bucket, bucket)
        raw_qid = row["question_id"]
        qid = raw_qid.split(":", 1)[1] if ":" in raw_qid else raw_qid
        config = f"moo:{row['profile']}"
        records.append(Rec(fname, bench, config, qid,
                            bool(row["correct"]), row.get("escalated"), row.get("total_tokens"), None))
        moo_rows.append({
            "bucket": bucket, "profile": row["profile"], "question_id": qid,
            "correct": bool(row["correct"]), "escalated": row.get("escalated"),
            "total_tokens": row.get("total_tokens"),
        })
        n += 1
    return n


MATH_OPEN_CONFIG_BY_FNAME = {
    "aime_open_baseline_seed42.jsonl": ("AIME", "baseline_3.7max_open"),
    "aime_open_panel_cheap_seed42.jsonl": ("AIME", "panel_open_cheap"),
    "math_open_baseline_seed42.jsonl": ("MATH-500-open", "baseline_3.7max_open"),
    "math_open_panel_cheap_seed42.jsonl": ("MATH-500-open", "panel_open_cheap"),
    "math_open_panel_seed42.jsonl": ("MATH-500-open", "panel_open_flagship"),
}


def load_math_open_file(path: Path, records: list[Rec]) -> int:
    fname = path.name
    bench, config = MATH_OPEN_CONFIG_BY_FNAME[fname]
    n = 0
    for row in iter_jsonl(path):
        records.append(Rec(fname, bench, config, row["question_id"],
                            bool(row["correct"]), row.get("escalated"), _sum_calls_tokens(row.get("calls")), None))
        n += 1
    return n


# ---------------------------------------------------------------------------
# Inventory / dispatch
# ---------------------------------------------------------------------------


def build_inventory_and_records():
    records: list[Rec] = []
    moo_rows: list[dict] = []
    inventory = []  # (fname, family, n_rows_read, n_recs_emitted, note)

    files = sorted(RESULTS_DIR.glob("*.jsonl"))
    for path in files:
        fname = path.name
        if fname in EXCLUDED_FILES:
            inventory.append((fname, "EXCLUDED", 0, 0, EXCLUDED_FILES[fname]))
            continue

        with path.open(encoding="utf-8") as fh:
            n_lines = sum(1 for l in fh if l.strip())

        pre = len(records)
        if fname in COMBO_BENCHMARK_BY_FNAME:
            load_combo_file(path, records)
            family = "combo(baseline+engine[+sc5])"
        elif fname in LEVER_BASELINE_BENCHMARK_BY_FNAME:
            load_lever_baseline_file(path, records)
            family = "lever_baseline"
        elif fname == "qwen38_baseline_seed123.jsonl":
            load_qwen38_baseline(path, records)
            family = "qwen38_baseline (flat)"
        elif fname == "moo_m1_eval.jsonl":
            load_moo_file(path, records, moo_rows)
            family = "moo (flat, profile/bucket)"
        elif fname in MATH_OPEN_CONFIG_BY_FNAME:
            load_math_open_file(path, records)
            family = "math-open (flat)"
        elif fname.startswith("lever_"):
            load_lever_engine_file(path, records)
            family = "lever_engine(+lever/seed/dataset)"
        else:
            inventory.append((fname, "UNRECOGNIZED", n_lines, 0, "no loader matched -- SKIPPED"))
            continue

        emitted = len(records) - pre
        inventory.append((fname, family, n_lines, emitted, ""))

    return records, moo_rows, inventory


# ---------------------------------------------------------------------------
# F1 -- family blind-spot intersection
# ---------------------------------------------------------------------------


def compute_f1_floor(records: list[Rec]):
    """Per benchmark: qid -> config -> ever_correct (OR across all logged
    observations of that config on that item). Floor = items attempted by
    >=2 distinct configs where every one of those configs is False."""
    by_bench: dict[str, dict[str, dict[str, bool]]] = defaultdict(lambda: defaultdict(dict))
    # by_bench[bench][qid][config] = ever_correct (bool)
    for r in records:
        if r.benchmark == "UNKNOWN":
            continue
        cur = by_bench[r.benchmark][r.question_id].get(r.config)
        ever = r.correct if cur is None else (cur or r.correct)
        by_bench[r.benchmark][r.question_id][r.config] = ever

    results = {}
    for bench, qid_map in by_bench.items():
        covering_configs = set()
        n_multi = 0
        floor_items = []
        for qid, cfg_map in qid_map.items():
            covering_configs |= set(cfg_map.keys())
            if len(cfg_map) < 2:
                continue
            n_multi += 1
            if all(v is False for v in cfg_map.values()):
                floor_items.append(qid)
        results[bench] = {
            "configs_covering_benchmark": sorted(covering_configs),
            "n_items_total": len(qid_map),
            "n_attempted_by_2plus_configs": n_multi,
            "n_floor_items": len(floor_items),
            "floor_rate_of_multi": (len(floor_items) / n_multi) if n_multi else None,
            "floor_question_ids": sorted(floor_items),
        }
    return results


# ---------------------------------------------------------------------------
# F1(b) -- GPQA qwen3.8-solo deficit decomposition
# ---------------------------------------------------------------------------


def compute_f1b_gpqa_deficit(records: list[Rec]):
    solo_rows = [r for r in records if r.benchmark == "GPQA-Diamond" and r.config == "qwen3.8_solo"]
    society_files = {
        "lever_chem_thinking_gate_gpqa_seed217.jsonl",
        "lever_chem_thinking_gate_gpqa_seed314.jsonl",
        "lever_chem_thinking_gate_gpqa_seed471.jsonl",
    }
    society_rows = [r for r in records if r.source_file in society_files]

    solo_by_qid = {r.question_id: r.correct for r in solo_rows}
    solo_n = len(solo_rows)
    solo_correct = sum(1 for r in solo_rows if r.correct)

    society_by_qid: dict[str, list[Rec]] = defaultdict(list)
    for r in society_rows:
        society_by_qid[r.question_id].append(r)

    society_n_rows = len(society_rows)
    society_correct_rows = sum(1 for r in society_rows if r.correct)
    per_seed = defaultdict(lambda: [0, 0])
    for r in society_rows:
        per_seed[r.source_file][1] += 1
        if r.correct:
            per_seed[r.source_file][0] += 1

    shared_qids = sorted(set(solo_by_qid) & set(society_by_qid))

    deficit_items = []
    for qid in shared_qids:
        solo_ok = solo_by_qid[qid]
        obs = society_by_qid[qid]
        society_ever_correct = any(o.correct for o in obs)
        if solo_ok and not society_ever_correct:
            any_escalated = any(bool(o.escalated) for o in obs)
            deficit_items.append({
                "question_id": qid,
                "society_observations": [
                    {"seed_file": o.source_file, "correct": o.correct, "escalated": o.escalated}
                    for o in obs
                ],
                "classification": "escalated_and_lost" if any_escalated else "never_escalated_blind_spot",
            })

    n_never_escalated = sum(1 for d in deficit_items if d["classification"] == "never_escalated_blind_spot")
    n_escalated_lost = sum(1 for d in deficit_items if d["classification"] == "escalated_and_lost")

    return {
        "solo_n_attempted": solo_n,
        "solo_n_correct": solo_correct,
        "solo_accuracy": (solo_correct / solo_n) if solo_n else None,
        "society_files": sorted(society_files),
        "society_n_rows_total": society_n_rows,
        "society_accuracy_pooled": (society_correct_rows / society_n_rows) if society_n_rows else None,
        "society_per_seed_accuracy": {
            f: {"n": n, "correct": c, "accuracy": (c / n if n else None)}
            for f, (c, n) in per_seed.items()
        },
        "n_shared_items_solo_and_society": len(shared_qids),
        "n_3.8_right_society_wrong": len(deficit_items),
        "n_never_escalated_blind_spot": n_never_escalated,
        "n_escalated_and_lost_selection_failure": n_escalated_lost,
        "deficit_items": deficit_items,
    }


# ---------------------------------------------------------------------------
# F2 -- compute-allocation frontier
# ---------------------------------------------------------------------------


def compute_f2_frontier(records: list[Rec]):
    by_bench_config: dict[str, dict[str, list[Rec]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        if r.benchmark == "UNKNOWN":
            continue
        by_bench_config[r.benchmark][r.config].append(r)

    table = {}
    for bench, cfg_map in by_bench_config.items():
        rows = []
        for cfg, recs in cfg_map.items():
            n = len(recs)
            n_correct = sum(1 for r in recs if r.correct)
            toks = [r.tokens for r in recs if r.tokens is not None]
            mean_tokens = statistics.mean(toks) if toks else None
            n_tok_missing = n - len(toks)
            seeds = sorted({r.seed for r in recs if r.seed is not None})
            files = sorted({r.source_file for r in recs})
            rows.append({
                "config": cfg,
                "n": n,
                "accuracy": n_correct / n if n else None,
                "mean_tokens_per_q": mean_tokens,
                "n_tokens_missing": n_tok_missing,
                "seeds": seeds,
                "source_files": files,
            })
        rows.sort(key=lambda x: (x["mean_tokens_per_q"] if x["mean_tokens_per_q"] is not None else 1e18))

        # Pareto dominance: cfg A dominates cfg B if tokens(A) <= tokens(B)
        # and accuracy(A) >= accuracy(B) and not identical config.
        dominance = []
        priced = [r for r in rows if r["mean_tokens_per_q"] is not None and r["accuracy"] is not None]
        for a in priced:
            for b in priced:
                if a["config"] == b["config"]:
                    continue
                if a["mean_tokens_per_q"] <= b["mean_tokens_per_q"] and a["accuracy"] >= b["accuracy"] and (
                    a["mean_tokens_per_q"] < b["mean_tokens_per_q"] or a["accuracy"] > b["accuracy"]
                ):
                    dominance.append({"dominant": a["config"], "dominated": b["config"],
                                       "dominant_acc": a["accuracy"], "dominant_tok": a["mean_tokens_per_q"],
                                       "dominated_acc": b["accuracy"], "dominated_tok": b["mean_tokens_per_q"]})

        # Pareto FRONTIER: configs dominated by nobody (much more readable
        # than the full pairwise-dominance edge list above, which includes
        # transitive-closure noise). Sorted by tokens ascending.
        dominated_names = {d["dominated"] for d in dominance}
        frontier = [r for r in priced if r["config"] not in dominated_names]
        frontier.sort(key=lambda r: r["mean_tokens_per_q"])

        table[bench] = {"configs": rows, "dominance_pairs": dominance, "pareto_frontier": frontier}
    return table


# ---------------------------------------------------------------------------
# F5 -- difficulty-conditional non-monotonicity map (moo buckets)
# ---------------------------------------------------------------------------


def compute_f5_moo_map(moo_rows: list[dict]):
    by_bucket: dict[str, dict[str, dict[str, dict]]] = defaultdict(lambda: defaultdict(dict))
    # by_bucket[bucket][profile][qid] = row
    for row in moo_rows:
        by_bucket[row["bucket"]][row["profile"]][row["question_id"]] = row

    out = {}
    for bucket, prof_map in by_bucket.items():
        profiles = sorted(prof_map.keys())
        if "single-call" not in profiles:
            out[bucket] = {"error": "no single-call comparator logged for this bucket"}
            continue
        common_qids = set(prof_map["single-call"].keys())
        for p in profiles:
            common_qids &= set(prof_map[p].keys())
        common_qids = sorted(common_qids)
        n_common = len(common_qids)

        sc_acc = sum(1 for q in common_qids if prof_map["single-call"][q]["correct"]) / n_common if n_common else None

        rows = []
        for p in profiles:
            n_correct = sum(1 for q in common_qids if prof_map[p][q]["correct"])
            acc = n_correct / n_common if n_common else None
            delta_items = None
            if acc is not None and sc_acc is not None:
                delta_items = round((acc - sc_acc) * n_common)
            rows.append({
                "profile": p,
                "n_common_items": n_common,
                "accuracy_on_common": acc,
                "delta_vs_single_call_pp": (acc - sc_acc) * 100 if acc is not None and sc_acc is not None else None,
                "delta_vs_single_call_items": delta_items,
            })
        out[bucket] = {"n_common_items": n_common, "single_call_accuracy": sc_acc, "profiles": rows}
    return out


def compute_f5_subject_breakdown(records: list[Rec]):
    """Secondary, lower-confidence proxy: per-subject accuracy delta between
    shipped_engine and baseline_3.7max within the combo files that carry a
    `subject` field indirectly via question item -- reconstructed here from
    the underlying JSONL rather than Rec (Rec doesn't carry subject)."""
    subj_map: dict[tuple[str, str], dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for fname, bench in COMBO_BENCHMARK_BY_FNAME.items():
        path = RESULTS_DIR / fname
        if not path.exists():
            continue
        for row in iter_jsonl(path):
            if "baseline" not in row or "engine" not in row:
                continue
            subj = row["baseline"]["item"].get("subject") or "unknown"
            subj_map[(bench, subj)]["baseline_3.7max"].append(bool(row["baseline"]["correct"]))
            subj_map[(bench, subj)]["shipped_engine"].append(bool(row["engine"]["correct"]))

    out = []
    for (bench, subj), cfgmap in sorted(subj_map.items()):
        b = cfgmap["baseline_3.7max"]
        e = cfgmap["shipped_engine"]
        n = len(b)
        if n == 0:
            continue
        b_acc = sum(b) / n
        e_acc = sum(e) / n
        out.append({
            "benchmark": bench, "subject": subj, "n": n,
            "baseline_acc": b_acc, "engine_acc": e_acc,
            "delta_pp": (e_acc - b_acc) * 100,
            "delta_items": sum(e) - sum(b),
        })
    return out


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main():
    records, moo_rows, inventory = build_inventory_and_records()

    print("=" * 100)
    print("INVENTORY")
    print("=" * 100)
    for fname, family, n_lines, n_emit, note in inventory:
        print(f"{fname:55s} family={family:35s} lines={n_lines:5d} recs={n_emit:5d} {note}")

    print()
    print("Total normalized records:", len(records))
    print("Benchmarks seen:", sorted({r.benchmark for r in records}))

    f1 = compute_f1_floor(records)
    f1b = compute_f1b_gpqa_deficit(records)
    f2 = compute_f2_frontier(records)
    f5_moo = compute_f5_moo_map(moo_rows)
    f5_subject = compute_f5_subject_breakdown(records)

    print()
    print("=" * 100)
    print("F1 -- FAMILY BLIND-SPOT FLOOR PER BENCHMARK")
    print("=" * 100)
    for bench, d in sorted(f1.items()):
        print(f"\n[{bench}]  n_items_total={d['n_items_total']}  "
              f"n_attempted_by_2+_configs={d['n_attempted_by_2plus_configs']}  "
              f"n_floor_items={d['n_floor_items']}  "
              f"floor_rate_of_multi={d['floor_rate_of_multi']}")
        print(f"  configs covering benchmark ({len(d['configs_covering_benchmark'])}): "
              f"{d['configs_covering_benchmark']}")
        print(f"  floor question_ids: {d['floor_question_ids']}")

    print()
    print("=" * 100)
    print("F1(b) -- GPQA qwen3.8-solo DEFICIT DECOMPOSITION")
    print("=" * 100)
    print(json.dumps({k: v for k, v in f1b.items() if k != "deficit_items"}, indent=2))
    print("deficit_items:")
    for d in f1b["deficit_items"]:
        print(" ", d)

    print()
    print("=" * 100)
    print("F2 -- COMPUTE-ALLOCATION FRONTIER")
    print("=" * 100)
    for bench, d in sorted(f2.items()):
        print(f"\n[{bench}]")
        for row in d["configs"]:
            print(f"  {row['config']:25s} n={row['n']:4d}  acc={row['accuracy']:.3f}  "
                  f"mean_tok/q={row['mean_tokens_per_q']}  tok_missing={row['n_tokens_missing']}  "
                  f"seeds={row['seeds']}")
        print("  PARETO FRONTIER (non-dominated, sorted by tokens):")
        for r in d["pareto_frontier"]:
            print(f"    {r['config']:25s} acc={r['accuracy']:.3f}  mean_tok/q={r['mean_tokens_per_q']:.0f}  n={r['n']}")

    print()
    print("=" * 100)
    print("F5 -- DIFFICULTY-CONDITIONAL NON-MONOTONICITY MAP (moo buckets)")
    print("=" * 100)
    for bucket, d in sorted(f5_moo.items()):
        if "error" in d:
            print(f"\n[{bucket}] {d['error']}")
            continue
        print(f"\n[{bucket}]  n_common_items(all 7 profiles)={d['n_common_items']}  "
              f"single-call acc={d['single_call_accuracy']:.3f}")
        for row in sorted(d["profiles"], key=lambda x: -x["delta_vs_single_call_pp"] if x["delta_vs_single_call_pp"] is not None else 0):
            print(f"  {row['profile']:20s} acc={row['accuracy_on_common']:.3f}  "
                  f"delta_vs_single_call={row['delta_vs_single_call_pp']:+.1f}pp "
                  f"({row['delta_vs_single_call_items']:+d}/{row['n_common_items']})")

    print()
    print("=" * 100)
    print("F5 (secondary) -- subject-level shipped_engine vs baseline_3.7max, combo files")
    print("=" * 100)
    for row in f5_subject:
        print(f"  [{row['benchmark']}] {row['subject']:30s} n={row['n']:3d}  "
              f"baseline_acc={row['baseline_acc']:.2f}  engine_acc={row['engine_acc']:.2f}  "
              f"delta={row['delta_pp']:+.1f}pp ({row['delta_items']:+d} items)")

    # --- write artifacts ---
    RESULTS_DIR.mkdir(exist_ok=True)

    floor_rows = []
    for bench, d in f1.items():
        for qid in d["floor_question_ids"]:
            floor_rows.append({"benchmark": bench, "question_id": qid})
    write_csv(RESULTS_DIR / "f1_family_floor_items.csv", floor_rows, ["benchmark", "question_id"])

    deficit_rows = []
    for d in f1b["deficit_items"]:
        deficit_rows.append({
            "question_id": d["question_id"],
            "classification": d["classification"],
            "society_observations": json.dumps(d["society_observations"]),
        })
    write_csv(RESULTS_DIR / "f1_gpqa_deficit_items.csv", deficit_rows,
              ["question_id", "classification", "society_observations"])

    frontier_rows = []
    for bench, d in f2.items():
        frontier_names = {r["config"] for r in d["pareto_frontier"]}
        for row in d["configs"]:
            frontier_rows.append({
                "benchmark": bench, "config": row["config"], "n": row["n"],
                "accuracy": row["accuracy"], "mean_tokens_per_q": row["mean_tokens_per_q"],
                "n_tokens_missing": row["n_tokens_missing"], "seeds": ";".join(map(str, row["seeds"])),
                "on_pareto_frontier": row["config"] in frontier_names,
            })
    write_csv(RESULTS_DIR / "f2_compute_frontier.csv", frontier_rows,
              ["benchmark", "config", "n", "accuracy", "mean_tokens_per_q", "n_tokens_missing", "seeds",
               "on_pareto_frontier"])

    f5_rows = []
    for bucket, d in f5_moo.items():
        if "error" in d:
            continue
        for row in d["profiles"]:
            f5_rows.append({
                "bucket": bucket, "profile": row["profile"], "n_common_items": row["n_common_items"],
                "accuracy_on_common": row["accuracy_on_common"],
                "delta_vs_single_call_pp": row["delta_vs_single_call_pp"],
                "delta_vs_single_call_items": row["delta_vs_single_call_items"],
            })
    write_csv(RESULTS_DIR / "f5_difficulty_map.csv", f5_rows,
              ["bucket", "profile", "n_common_items", "accuracy_on_common",
               "delta_vs_single_call_pp", "delta_vs_single_call_items"])

    all_data = {
        "inventory": [
            {"file": f, "family": fam, "n_lines": n, "n_records": e, "note": note}
            for f, fam, n, e, note in inventory
        ],
        "f1_floor": f1,
        "f1b_gpqa_deficit": f1b,
        "f2_frontier": f2,
        "f5_moo_map": f5_moo,
        "f5_subject_breakdown": f5_subject,
    }
    with (RESULTS_DIR / "family_floor_analysis_data.json").open("w", encoding="utf-8") as fh:
        json.dump(all_data, fh, indent=2, default=str)

    print()
    print("Wrote: f1_family_floor_items.csv, f1_gpqa_deficit_items.csv, "
          "f2_compute_frontier.csv, f5_difficulty_map.csv, family_floor_analysis_data.json")


if __name__ == "__main__":
    main()
