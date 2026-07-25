"""SEL-1 / S1 zero-token selector audit (docs/experiment-spec-book.md section 3,
"S1 | Zero-token selector audit over the ... already-logged ... pools | 0 | P0",
cross-referenced in docs/capability-roadmap.md section 4's FREE tier as F3 in the
firing order: "audit_selectors.py selector audit over the deduped logged pools").

For EVERY committed benchmark/results/*.jsonl row that logs a per-seat solver
pool (letter + confidence + reasoning per seat -- the shipped panel/gate/RAG
levers, the pilot combo files, and moo_m1_eval's profile runs), reconstructs
five alternative SELECTORS over that SAME already-logged candidate pool, for
zero additional tokens:

    (a) plain letter-plurality      -- the shipped baseline (Counter.most_common,
                                        replicating src/quorumqa/engine/orchestrator.py
                                        and profiles.py's _plurality tie-break exactly)
    (b) confidence-weighted vote    -- sum confidence per letter, argmax
    (c) max-single-confidence       -- letter of the single most-confident seat
    (d) longest-reasoning           -- letter of the seat with the longest reasoning
                                        string (a DELIBERATE JUNK selector: if this
                                        wins, it means confidence/plurality carry no
                                        more signal than verbosity)
    (e) ORACLE                      -- was the gold letter proposed by ANY seat in
                                        the pool? (the coverage ceiling -- the most
                                        important number in this report)

All five are computed strictly WITHIN each row (never joined across seeds/rows on
letter identity), because `load_gpqa._shuffle_choices` reshuffles the A/B/C/D
mapping per seed -- a letter means a different choice string in every draw. Each
row supplies its own `item.correct_letter` and `item.choices`, so correctness is
always resolved from that row's own gold label. Pooling across rows (per
benchmark, and overall) sums independently-resolved per-row correctness booleans,
never letters.

Tie-break rule (applied uniformly to a, b, c, d): first-seen-order wins, matching
Python's `Counter.most_common()` stable-sort behaviour used by the shipped
`_plurality()` in orchestrator.py / profiles.py. Verified empirically: recomputed
plurality matches the logged `plurality_letter` field on all 5,451 usable rows
(0 mismatches) -- see the inventory step below.

McNemar exact test: for each of (b), (c), (d) vs (a), b_cell = rows where the
alt selector is right and plurality is wrong (alt gain), c_cell = rows where
plurality is right and the alt selector is wrong (alt loss) -- standard McNemar
contingency notation, NOT the same "(b)/(c)" as the selector labels above (the
two label sets collide; this docstring and the report spell out which is which
at every use). Exact two-sided p-value via `scipy.stats.binomtest(b_cell,
b_cell + c_cell, 0.5, alternative="two-sided")` (equivalent to the standard exact
McNemar test on the discordant pairs). net = b_cell - c_cell.

PRE-REGISTERED BAR (task spec, stated once, applied identically per benchmark
and overall): a selector WINS iff pooled discordant (b_cell + c_cell) >= 12 AND
net >= 5 AND McNemar exact two-sided p < 0.05. ORACLE is exempt from the bar (it
is a ceiling, not a deployable selector -- it cheats by knowing the gold letter).

Usage:
    .venv/Scripts/python.exe benchmark/audit_selectors.py

Writes:
    benchmark/results/selector_audit_rows.csv        -- every usable row, all 5
        selector outcomes, for re-checking any number quoted in the report
    benchmark/results/selector_audit_summary.json     -- full per-benchmark and
        overall aggregates, McNemar tables, bar verdicts

Nothing here makes a network or paid API call -- pure offline JSONL mining
against already-logged solver pools.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from scipy.stats import binomtest

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Pre-registered bar (verbatim from the task spec).
BAR_MIN_DISCORDANT = 12
BAR_MIN_NET = 5
BAR_ALPHA = 0.05

SELECTOR_LABELS = ["confidence_weighted", "max_single_confidence", "longest_reasoning"]


# ---------------------------------------------------------------------------
# Benchmark classification (self-contained; mirrors, but does not import,
# analyze_family_floor.py's already-validated mapping -- this file owns its
# own copy per the "new files only" constraint on this worker).
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

# Filename substring -> benchmark, checked top to bottom, first match wins.
FILENAME_MAP = [
    ("gsm8k_pilot", "GSM8K"),
    ("medqa_pilot", "MedQA"),
    ("mmlu_pro_pilot", "MMLU-Pro"),
    ("lexam_pilot", "LEXam"),
    ("math500_hard_pilot", "MATH-500-MC"),
    ("supergpqa_hard_pilot", "SuperGPQA-hard"),
    ("mmlu_pro_stem", "MMLU-Pro"),
]


def classify_benchmark(row: dict, fname: str, dataset_field: Optional[str], qid: str) -> str:
    if fname == "moo_m1_eval.jsonl":
        return MOO_BUCKET_MAP.get(row.get("bucket"), row.get("bucket", "UNKNOWN"))
    if dataset_field:
        return DATASET_FIELD_MAP.get(dataset_field, dataset_field)
    for needle, bench in FILENAME_MAP:
        if needle in fname:
            return bench
    if qid.startswith("rec"):
        return "GPQA-Diamond"
    if len(qid) == 32 and all(c in "0123456789abcdef" for c in qid):
        return "SuperGPQA-hard"
    return "UNKNOWN"


def config_label(row: dict, fname: str) -> str:
    if "lever" in row:
        return str(row["lever"])
    if fname == "moo_m1_eval.jsonl":
        return f"moo:{row.get('profile', 'unknown')}"
    if "baseline" in row and "engine" in row:
        return "shipped_engine(pilot)"
    return "unknown_config"


# ---------------------------------------------------------------------------
# Pool extraction: a usable "pool" is any dict with a solver_answers list
# where EVERY entry carries both 'letter' and 'confidence', plus an 'item'
# dict carrying 'choices' and 'correct_letter'. This excludes: single-call
# baselines (no solver_answers at all), open-answer math panels
# (solver_answers present but entries carry 'answer'/'temperature', not
# 'letter'/'confidence'), and the gate-replay analysis artifact (different
# schema entirely, no solver_answers).
# ---------------------------------------------------------------------------


def _looks_like_pool(obj) -> bool:
    if not isinstance(obj, dict):
        return False
    sa = obj.get("solver_answers")
    if not sa or not isinstance(sa, list):
        return False
    if not all(isinstance(s, dict) and "letter" in s and "confidence" in s for s in sa):
        return False
    item = obj.get("item")
    if not isinstance(item, dict):
        return False
    if "choices" not in item or "correct_letter" not in item:
        return False
    return True


def extract_pool(row: dict):
    """Return (pool_obj, wrap_kind) for the first usable pool found in this
    row, trying flat, then engine-wrapped, then moo's result-wrapped. None
    if this row carries no usable pool."""
    for wrap_kind, obj in (("flat", row), ("engine", row.get("engine")), ("result", row.get("result"))):
        if _looks_like_pool(obj):
            return obj, wrap_kind
    return None, None


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


# ---------------------------------------------------------------------------
# Selectors -- all tie-break "first-seen order", matching Counter.most_common.
# ---------------------------------------------------------------------------


def sel_plurality(letters: list[str]) -> str:
    return Counter(letters).most_common(1)[0][0]


def sel_confidence_weighted(letters: list[str], confidences: list[float]) -> str:
    sums: dict[str, float] = {}
    for letter, conf in zip(letters, confidences):
        sums[letter] = sums.get(letter, 0.0) + conf
    return max(sums.items(), key=lambda kv: kv[1])[0]


def sel_max_single_confidence(letters: list[str], confidences: list[float]) -> str:
    best_i = 0
    best_c = confidences[0]
    for i in range(1, len(letters)):
        if confidences[i] > best_c:
            best_c = confidences[i]
            best_i = i
    return letters[best_i]


def sel_longest_reasoning(letters: list[str], reasoning_lens: list[int]) -> str:
    best_i = 0
    best_len = reasoning_lens[0]
    for i in range(1, len(letters)):
        if reasoning_lens[i] > best_len:
            best_len = reasoning_lens[i]
            best_i = i
    return letters[best_i]


# ---------------------------------------------------------------------------
# Row record
# ---------------------------------------------------------------------------


@dataclass
class Row:
    source_file: str
    benchmark: str
    config: str
    question_id: str
    n_candidates: int
    correct_letter: str
    logged_plurality_letter: Optional[str]
    plurality_letter: str
    plurality_correct: bool
    plurality_matches_logged: Optional[bool]
    confw_letter: str
    confw_correct: bool
    maxconf_letter: str
    maxconf_correct: bool
    longest_letter: str
    longest_correct: bool
    oracle_covered: bool
    n_reasoning_empty: int


def build_rows() -> tuple[list[Row], list[tuple]]:
    rows: list[Row] = []
    inventory: list[tuple] = []  # (fname, n_lines, n_usable, note)

    files = sorted(RESULTS_DIR.glob("*.jsonl"))
    for path in files:
        fname = path.name
        n_lines = 0
        n_usable = 0
        zero_reason = None
        for row in iter_jsonl(path):
            n_lines += 1
            pool, wrap_kind = extract_pool(row)
            if pool is None:
                if zero_reason is None:
                    # Diagnose why, for the inventory note.
                    if "solver_answers" in row or (isinstance(row.get("engine"), dict) and "solver_answers" in row["engine"]):
                        zero_reason = "solver_answers present but entries lack letter+confidence (open-answer math panel, not a MC letter pool)"
                    elif "baseline" in row and "engine" not in row:
                        zero_reason = "single flagship call only, no panel (lever_baseline_*)"
                    elif set(row.keys()) & {"was_unanimous_correct", "gate_doubt", "gate_cost_usd"}:
                        zero_reason = "gate-replay analysis artifact, different schema, no fresh solver pool"
                    elif "answer_letter" in row and "usage" in row:
                        zero_reason = "flat single-model row (qwen38_baseline), no panel"
                    else:
                        zero_reason = "no solver_answers field (single-call baseline)"
                continue
            item = pool["item"]
            gold = str(item["correct_letter"]).strip().upper()
            solver_answers = pool["solver_answers"]
            letters = [str(s.get("letter") or "").strip().upper() for s in solver_answers]
            confidences = [float(s.get("confidence") or 0.0) for s in solver_answers]
            reasoning_lens = [len(s.get("reasoning") or "") for s in solver_answers]
            n_reasoning_empty = sum(1 for r in reasoning_lens if r == 0)

            plur = sel_plurality(letters)
            confw = sel_confidence_weighted(letters, confidences)
            maxc = sel_max_single_confidence(letters, confidences)
            longr = sel_longest_reasoning(letters, reasoning_lens)
            oracle = gold in letters

            logged_plur = pool.get("plurality_letter")
            logged_plur_norm = str(logged_plur).strip().upper() if logged_plur is not None else None

            qid = str(item.get("question_id") or pool.get("question_id") or "")
            dataset_field = row.get("dataset")
            benchmark = classify_benchmark(row, fname, dataset_field, qid)
            config = config_label(row, fname)

            rows.append(Row(
                source_file=fname,
                benchmark=benchmark,
                config=config,
                question_id=qid,
                n_candidates=len(letters),
                correct_letter=gold,
                logged_plurality_letter=logged_plur_norm,
                plurality_letter=plur,
                plurality_correct=(plur == gold),
                plurality_matches_logged=(plur == logged_plur_norm) if logged_plur_norm is not None else None,
                confw_letter=confw,
                confw_correct=(confw == gold),
                maxconf_letter=maxc,
                maxconf_correct=(maxc == gold),
                longest_letter=longr,
                longest_correct=(longr == gold),
                oracle_covered=oracle,
                n_reasoning_empty=n_reasoning_empty,
            ))
            n_usable += 1

        note = "" if n_usable > 0 else (zero_reason or "no rows in file")
        inventory.append((fname, n_lines, n_usable, note))

    return rows, inventory


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


SELECTOR_FIELD = {
    "confidence_weighted": ("confw_correct",),
    "max_single_confidence": ("maxconf_correct",),
    "longest_reasoning": ("longest_correct",),
}


def mcnemar_exact(b_cell: int, c_cell: int):
    n = b_cell + c_cell
    if n == 0:
        return 1.0
    return binomtest(b_cell, n, 0.5, alternative="two-sided").pvalue


def bar_verdict(b_cell: int, c_cell: int, p: float) -> bool:
    net = b_cell - c_cell
    return (b_cell + c_cell) >= BAR_MIN_DISCORDANT and net >= BAR_MIN_NET and p < BAR_ALPHA


def aggregate(rows: list[Row]) -> dict:
    n = len(rows)
    if n == 0:
        return {}
    out = {
        "n_items": n,
        "n_configs": len(sorted({r.config for r in rows})),
        "configs": sorted({r.config for r in rows}),
        "plurality_accuracy": sum(r.plurality_correct for r in rows) / n,
        "oracle_coverage": sum(r.oracle_covered for r in rows) / n,
        "selectors": {},
    }
    out["headroom_oracle_minus_plurality_pp"] = (out["oracle_coverage"] - out["plurality_accuracy"]) * 100
    out["headroom_oracle_minus_plurality_items"] = sum(r.oracle_covered for r in rows) - sum(r.plurality_correct for r in rows)

    plur_bool = [r.plurality_correct for r in rows]
    for sel_name, (field,) in SELECTOR_FIELD.items():
        sel_bool = [getattr(r, field) for r in rows]
        acc = sum(sel_bool) / n
        b_cell = sum(1 for p_ok, s_ok in zip(plur_bool, sel_bool) if s_ok and not p_ok)   # selector gain
        c_cell = sum(1 for p_ok, s_ok in zip(plur_bool, sel_bool) if p_ok and not s_ok)   # selector loss
        p_val = mcnemar_exact(b_cell, c_cell)
        net = b_cell - c_cell
        out["selectors"][sel_name] = {
            "accuracy": acc,
            "delta_vs_plurality_pp": (acc - out["plurality_accuracy"]) * 100,
            "b_selector_right_plurality_wrong": b_cell,
            "c_plurality_right_selector_wrong": c_cell,
            "n_discordant": b_cell + c_cell,
            "net": net,
            "mcnemar_exact_two_sided_p": p_val,
            "clears_bar": bar_verdict(b_cell, c_cell, p_val),
        }
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    rows, inventory = build_rows()

    print("=" * 100)
    print("INVENTORY -- all committed benchmark/results/*.jsonl")
    print("=" * 100)
    n_files_used = 0
    n_files_excluded = 0
    for fname, n_lines, n_usable, note in inventory:
        status = "USED" if n_usable > 0 else "EXCLUDED"
        if n_usable > 0:
            n_files_used += 1
        else:
            n_files_excluded += 1
        print(f"[{status:8s}] {fname:55s} lines={n_lines:5d} usable_pools={n_usable:5d}  {note}")
    print()
    print(f"Files used: {n_files_used}  Files excluded: {n_files_excluded}  Total usable rows (pools): {len(rows)}")

    # Sanity check: recomputed plurality vs the logged plurality_letter field.
    checked = [r for r in rows if r.plurality_matches_logged is not None]
    mismatches = [r for r in checked if not r.plurality_matches_logged]
    print()
    print(f"Sanity check: recomputed plurality vs logged plurality_letter -- "
          f"{len(checked)} rows checked, {len(mismatches)} mismatches "
          f"({'METHODOLOGY VALIDATED' if not mismatches else 'INVESTIGATE'})")
    if mismatches:
        for r in mismatches[:10]:
            print(f"    MISMATCH {r.source_file} {r.question_id}: mine={r.plurality_letter} logged={r.logged_plurality_letter}")

    n_reasoning_empty_total = sum(r.n_reasoning_empty for r in rows)
    n_candidates_total = sum(r.n_candidates for r in rows)
    print()
    print(f"Reasoning-field coverage: {n_reasoning_empty_total}/{n_candidates_total} seat-answers "
          f"({100*n_reasoning_empty_total/n_candidates_total:.1f}%) carry an empty reasoning string "
          f"(affects the longest-reasoning junk selector's tie-break behaviour on those rows).")

    # Per-benchmark aggregation.
    by_bench: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_bench[r.benchmark].append(r)

    per_bench_agg = {bench: aggregate(rs) for bench, rs in sorted(by_bench.items())}
    overall_agg = aggregate(rows)

    print()
    print("=" * 100)
    print("PER-BENCHMARK SELECTOR AUDIT")
    print("=" * 100)
    for bench, agg in per_bench_agg.items():
        print(f"\n[{bench}]  n={agg['n_items']}  configs={agg['n_configs']}  "
              f"plurality_acc={agg['plurality_accuracy']*100:.2f}%  "
              f"oracle_coverage={agg['oracle_coverage']*100:.2f}%  "
              f"headroom={agg['headroom_oracle_minus_plurality_pp']:+.2f}pp "
              f"({agg['headroom_oracle_minus_plurality_items']:+d} items)")
        for sel_name, d in agg["selectors"].items():
            verdict = "WINS (clears bar)" if d["clears_bar"] else "does not clear bar"
            print(f"    {sel_name:24s} acc={d['accuracy']*100:6.2f}% "
                  f"delta={d['delta_vs_plurality_pp']:+6.2f}pp  "
                  f"b={d['b_selector_right_plurality_wrong']:3d} c={d['c_plurality_right_selector_wrong']:3d} "
                  f"n_disc={d['n_discordant']:3d} net={d['net']:+3d}  "
                  f"p={d['mcnemar_exact_two_sided_p']:.4f}   {verdict}")

    print()
    print("=" * 100)
    print("OVERALL (all benchmarks pooled)")
    print("=" * 100)
    agg = overall_agg
    print(f"n={agg['n_items']}  configs={agg['n_configs']}  "
          f"plurality_acc={agg['plurality_accuracy']*100:.2f}%  "
          f"oracle_coverage={agg['oracle_coverage']*100:.2f}%  "
          f"headroom={agg['headroom_oracle_minus_plurality_pp']:+.2f}pp "
          f"({agg['headroom_oracle_minus_plurality_items']:+d} items)")
    for sel_name, d in agg["selectors"].items():
        verdict = "WINS (clears bar)" if d["clears_bar"] else "does not clear bar"
        print(f"    {sel_name:24s} acc={d['accuracy']*100:6.2f}% "
              f"delta={d['delta_vs_plurality_pp']:+6.2f}pp  "
              f"b={d['b_selector_right_plurality_wrong']:3d} c={d['c_plurality_right_selector_wrong']:3d} "
              f"n_disc={d['n_discordant']:3d} net={d['net']:+3d}  "
              f"p={d['mcnemar_exact_two_sided_p']:.4f}   {verdict}")

    # --- write artifacts ---
    RESULTS_DIR.mkdir(exist_ok=True)

    row_fields = [f.name for f in Row.__dataclass_fields__.values()] if False else list(asdict(rows[0]).keys())
    with (RESULTS_DIR / "selector_audit_rows.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=row_fields)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))

    summary = {
        "bar": {
            "min_discordant": BAR_MIN_DISCORDANT,
            "min_net": BAR_MIN_NET,
            "alpha": BAR_ALPHA,
        },
        "inventory": [
            {"file": f, "n_lines": n, "n_usable_pools": u, "note": note}
            for f, n, u, note in inventory
        ],
        "n_files_used": n_files_used,
        "n_files_excluded": n_files_excluded,
        "n_usable_rows_total": len(rows),
        "plurality_sanity_check": {
            "n_checked": len(checked),
            "n_mismatches": len(mismatches),
        },
        "reasoning_coverage": {
            "n_empty": n_reasoning_empty_total,
            "n_total_seat_answers": n_candidates_total,
        },
        "per_benchmark": per_bench_agg,
        "overall": overall_agg,
    }
    with (RESULTS_DIR / "selector_audit_summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)

    print()
    print("Wrote: benchmark/results/selector_audit_rows.csv, benchmark/results/selector_audit_summary.json")
    print()
    print("Reproduce with: .venv/Scripts/python.exe benchmark/audit_selectors.py")


if __name__ == "__main__":
    main()
