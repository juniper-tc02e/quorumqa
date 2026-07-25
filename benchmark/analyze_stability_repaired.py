"""F1 stability audit, REPAIRED (docs/capability-roadmap.md section 4 FREE tier,
item F1: "Stability audit, repaired: re-key on choice TEXT (load_gpqa's
_shuffle_choices reshuffles per seed), score at item level via text-majority,
report lift vs a permutation null preserving each item's replicate-answer
multiset -- Whether the instability signal survives its own mechanical floor;
gates every stability lever and CAL-2").

Some benchmarks have the SAME question_id solved by multiple configs/seeds
across benchmark/results/*.jsonl (a bare flagship baseline, the shipped
engine under various levers, self_consistency5, and moo_m1_eval's 7
profiles all independently "solve" the same underlying item). This script
treats every one of those graded observations of the same (benchmark,
question_id) as one REPLICATE, and measures whether ANSWER INSTABILITY
(replicates disagreeing on the choice) is a wrongness signal -- with three
repairs applied, exactly as specified:

  (1) KEY ON CHOICE TEXT, NEVER LETTER. `load_gpqa._shuffle_choices`
      reshuffles the A/B/C/D <-> choice-text mapping independently per seed,
      so a bare letter comparison across rows is meaningless. Every
      replicate's chosen letter is mapped back to its own choice-text via
      THAT ROW's own `item.choices` list before any cross-row comparison.
      Choice text is whitespace-normalized (collapse runs of whitespace,
      strip) before comparison -- raw text otherwise disagreed on trailing
      newlines alone in ~12 GPQA items spot-checked during development (see
      report caveats).

  (2) SCORE AT ITEM LEVEL VIA TEXT-MAJORITY. An item's verdict is the
      plurality vote (Counter.most_common, first-seen tie-break) of its
      replicates' chosen TEXTS, not any single replicate's answer.

  (3) PERMUTATION NULL. An item whose replicates disagree is MECHANICALLY
      more likely to show a wrong majority than one whose replicates agree,
      purely from choice-space combinatorics: there is exactly one correct
      text but several (typically 3) wrong ones, so wrong replicates can
      either coincide on the same wrong text (item reads "stable & wrong")
      or scatter across different wrong texts (item reads "unstable &
      wrong") -- a coin-flip of arithmetic, not evidence of anything. The
      null holds each item's REAL right/wrong replicate COUNT fixed
      (r correct, w wrong -- "the replicate-answer multiset") and randomly
      reassigns, independently per Monte Carlo draw, which of the item's
      observed wrong choice-texts each wrong replicate lands on ("shuffles
      which replicate produced which answer"). Correct replicates are
      always the single correct text (nothing to shuffle there). Ties in
      the resulting per-draw plurality are broken uniformly at random (a
      deterministic first-seen rule has no meaning inside a synthetic
      draw). NDRAWS=5000, fixed seed 20260725, printed and reproducible.

Usage:
    .venv/Scripts/python.exe benchmark/analyze_stability_repaired.py

Writes:
    benchmark/results/stability_audit_items.csv     -- every item with >=2
        replicates: benchmark, question_id, k/r/w, stability, majority
        verdict, contributing (source_file, config) list
    benchmark/results/stability_audit_summary.json  -- full per-benchmark and
        overall real + null aggregates, for re-checking any number quoted
        in the report

Nothing here makes a network or paid API call -- pure offline JSONL mining.
"""

from __future__ import annotations

import csv
import json
import random
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

RESULTS_DIR = Path(__file__).resolve().parent / "results"

NDRAWS = 5000
NULL_SEED = 20260725

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

FILENAME_MAP = [
    ("gsm8k_pilot", "GSM8K"),
    ("medqa_pilot", "MedQA"),
    ("mmlu_pro_pilot", "MMLU-Pro"),
    ("lexam_pilot", "LEXam"),
    ("math500_hard_pilot", "MATH-500-MC"),
    ("supergpqa_hard_pilot", "SuperGPQA-hard"),
    ("baseline_gpqa", "GPQA-Diamond"),
    ("baseline_supergpqa", "SuperGPQA-hard"),
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


_WS_RE = re.compile(r"\s+")


def norm_text(t) -> Optional[str]:
    if not isinstance(t, str):
        return None
    return _WS_RE.sub(" ", t).strip()


def config_label(row: dict, fname: str, role: str) -> str:
    if role == "baseline":
        return "baseline_3.7max"
    if role == "sc5":
        return "self_consistency_5x"
    if role == "moo":
        return f"moo:{row.get('profile', 'unknown')}"
    if role == "engine":
        if "lever" in row:
            return str(row["lever"])
        return "shipped_engine(pilot)"
    return "unknown_config"


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


# ---------------------------------------------------------------------------
# Observation extraction
# ---------------------------------------------------------------------------


@dataclass
class Obs:
    source_file: str
    config: str
    seed: Optional[int]
    chosen_text: str
    correct: bool
    logged_correct: Optional[bool]


def extract_observations(row: dict, fname: str) -> list[tuple]:
    """Returns list of (benchmark, question_id, Obs)."""
    out = []
    dataset_field = row.get("dataset")
    seed = row.get("seed")

    candidates = []
    if isinstance(row.get("baseline"), dict) and "item" in row["baseline"]:
        candidates.append(("baseline", row["baseline"], row["baseline"].get("answer_letter")))
    if isinstance(row.get("engine"), dict) and "item" in row["engine"]:
        candidates.append(("engine", row["engine"], row["engine"].get("final_letter")))
    if isinstance(row.get("self_consistency5"), dict) and "item" in row["self_consistency5"]:
        candidates.append(("sc5", row["self_consistency5"], row["self_consistency5"].get("answer_letter")))
    if fname == "moo_m1_eval.jsonl" and isinstance(row.get("result"), dict) and "item" in row["result"]:
        candidates.append(("moo", row["result"], row["result"].get("final_letter")))

    for role, obj, letter in candidates:
        item = obj["item"]
        choices = item.get("choices")
        correct_letter = item.get("correct_letter")
        if not choices or not correct_letter or not letter:
            continue
        letter = str(letter).strip().upper()
        correct_letter = str(correct_letter).strip().upper()
        idx = ord(letter) - ord("A") if len(letter) == 1 else -1
        gidx = ord(correct_letter) - ord("A") if len(correct_letter) == 1 else -1
        if not (0 <= idx < len(choices)) or not (0 <= gidx < len(choices)):
            continue
        chosen_text = norm_text(choices[idx])
        gold_text = norm_text(choices[gidx])
        if chosen_text is None or gold_text is None:
            continue

        raw_qid = str(item.get("question_id") or "")
        qid = raw_qid.split(":", 1)[1] if (fname == "moo_m1_eval.jsonl" and ":" in raw_qid) else raw_qid
        bench = classify_benchmark(row, fname, dataset_field, qid)
        cfg = config_label(row, fname, role)

        logged_correct = obj.get("correct")
        out.append((bench, qid, gold_text, Obs(
            source_file=fname, config=cfg, seed=seed,
            chosen_text=chosen_text, correct=(chosen_text == gold_text),
            logged_correct=(bool(logged_correct) if logged_correct is not None else None),
        )))
    return out


# ---------------------------------------------------------------------------
# Item construction
# ---------------------------------------------------------------------------


@dataclass
class Item:
    benchmark: str
    question_id: str
    gold_text: str
    observations: list  # list[Obs]
    wrong_text_pool: list  # distinct observed wrong texts for this item

    @property
    def k(self):
        return len(self.observations)

    @property
    def r(self):
        return sum(1 for o in self.observations if o.correct)

    @property
    def w(self):
        return self.k - self.r

    @property
    def stable(self):
        return len({o.chosen_text for o in self.observations}) == 1

    def majority_text(self):
        return Counter(o.chosen_text for o in self.observations).most_common(1)[0][0]

    @property
    def majority_wrong(self):
        return self.majority_text() != self.gold_text


def build_items():
    files = sorted(RESULTS_DIR.glob("*.jsonl"))
    inventory = []  # (fname, n_lines, n_obs_emitted, note)
    raw: dict[tuple, dict] = {}  # (bench, qid) -> {"gold_texts": set, "obs": [Obs]}
    gold_mismatch_items = []

    for path in files:
        fname = path.name
        n_lines = 0
        n_emit = 0
        note_reason = None
        for row in iter_jsonl(path):
            n_lines += 1
            obs_list = extract_observations(row, fname)
            if not obs_list and note_reason is None:
                if "solver_answers" in row and "letter" not in json.dumps(row.get("solver_answers", [{}])[0] if row.get("solver_answers") else {}):
                    note_reason = "open-answer schema (no letter/choices to re-key on text)"
                elif "choices" not in json.dumps(row)[:2000] and "item" not in row and "engine" not in row and "baseline" not in row and "result" not in row:
                    note_reason = "flat row with no item/choices field (cannot map letter to text)"
                elif set(row.keys()) & {"was_unanimous_correct", "gate_doubt", "gate_cost_usd"}:
                    note_reason = "gate-replay analysis artifact, no item/choices"
                else:
                    note_reason = "no usable baseline/engine/self_consistency5/moo sub-object with item+choices"
            for bench, qid, gold_text, obs in obs_list:
                key = (bench, qid)
                slot = raw.setdefault(key, {"gold_texts": set(), "obs": []})
                slot["gold_texts"].add(gold_text)
                slot["obs"].append(obs)
                n_emit += 1
        inventory.append((fname, n_lines, n_emit, "" if n_emit else (note_reason or "no rows")))

    items: list[Item] = []
    for (bench, qid), slot in raw.items():
        if len(slot["gold_texts"]) != 1:
            gold_mismatch_items.append((bench, qid, sorted(slot["gold_texts"])))
            continue
        gold_text = next(iter(slot["gold_texts"]))
        obs = slot["obs"]
        wrong_pool = sorted({o.chosen_text for o in obs if o.chosen_text != gold_text})
        items.append(Item(benchmark=bench, question_id=qid, gold_text=gold_text,
                           observations=obs, wrong_text_pool=wrong_pool))

    return items, inventory, gold_mismatch_items


# ---------------------------------------------------------------------------
# Real (observed) aggregation
# ---------------------------------------------------------------------------


def aggregate_real(items: list[Item]) -> dict:
    n = len(items)
    if n == 0:
        return {}
    stable_items = [it for it in items if it.stable]
    unstable_items = [it for it in items if not it.stable]
    n_stable, n_unstable = len(stable_items), len(unstable_items)
    n_wrong_stable = sum(1 for it in stable_items if it.majority_wrong)
    n_wrong_unstable = sum(1 for it in unstable_items if it.majority_wrong)
    p_wrong_stable = (n_wrong_stable / n_stable) if n_stable else None
    p_wrong_unstable = (n_wrong_unstable / n_unstable) if n_unstable else None
    lift = (p_wrong_unstable - p_wrong_stable) if (p_wrong_stable is not None and p_wrong_unstable is not None) else None
    return {
        "n_items": n,
        "n_stable": n_stable,
        "n_unstable": n_unstable,
        "instability_rate": n_unstable / n,
        "n_wrong_stable": n_wrong_stable,
        "n_wrong_unstable": n_wrong_unstable,
        "p_wrong_given_stable": p_wrong_stable,
        "p_wrong_given_unstable": p_wrong_unstable,
        "lift": lift,
        "mean_replicates_per_item": statistics.mean(it.k for it in items),
    }


# ---------------------------------------------------------------------------
# Permutation null
# ---------------------------------------------------------------------------


def simulate_item_draw(rng: random.Random, r: int, w: int, m: int) -> tuple[bool, bool]:
    """One null draw for an item with r correct / w wrong replicates and m
    distinct available wrong-text bins (bin 0 = correct, bins 1..m = wrong).
    Returns (stable, majority_wrong)."""
    if w == 0:
        return True, False
    if m <= 0:
        # No distinct wrong text ever observed (shouldn't occur on 4-choice
        # items with >=1 wrong replicate, but guard defensively): treat all
        # wrong replicates as landing on a single shared wrong bin.
        m = 1
    counts = [0] * (m + 1)
    counts[0] = r
    for _ in range(w):
        counts[rng.randint(1, m)] += 1
    # stable iff exactly one bin has a nonzero count (every replicate landed
    # on the same text -- correct or wrong).
    nonzero_bins = [b for b in range(m + 1) if counts[b] > 0]
    stable = len(nonzero_bins) == 1
    max_count = max(counts)
    winners = [b for b in range(m + 1) if counts[b] == max_count]
    winner = rng.choice(winners)
    majority_wrong = winner != 0
    return stable, majority_wrong


def run_permutation_null(items: list[Item], ndraws: int, seed: int):
    """Returns per-draw lift lists keyed by benchmark and 'OVERALL'."""
    rng = random.Random(seed)
    benches = sorted({it.benchmark for it in items}) + ["OVERALL"]
    lift_draws = {b: [] for b in benches}
    prewired = [(it.benchmark, it.r, it.w, len(it.wrong_text_pool)) for it in items]

    for _ in range(ndraws):
        per_bench_counts = defaultdict(lambda: [0, 0, 0, 0])  # n_stable, n_unstable, n_wrong_stable, n_wrong_unstable
        for bench, r, w, m in prewired:
            stable, wrong = simulate_item_draw(rng, r, w, m)
            acc = per_bench_counts[bench]
            oacc = per_bench_counts["OVERALL"]
            if stable:
                acc[0] += 1
                oacc[0] += 1
                if wrong:
                    acc[2] += 1
                    oacc[2] += 1
            else:
                acc[1] += 1
                oacc[1] += 1
                if wrong:
                    acc[3] += 1
                    oacc[3] += 1
        for bench in benches:
            n_s, n_u, w_s, w_u = per_bench_counts[bench]
            if n_s == 0 or n_u == 0:
                continue
            p_s = w_s / n_s
            p_u = w_u / n_u
            lift_draws[bench].append(p_u - p_s)

    return lift_draws


def summarize_null(lift_draws: list[float], observed_lift: Optional[float]) -> dict:
    if not lift_draws:
        return {"n_draws_usable": 0}
    sorted_draws = sorted(lift_draws)
    n = len(sorted_draws)
    lo = sorted_draws[int(0.025 * n)]
    hi = sorted_draws[min(n - 1, int(0.975 * n))]
    mean_null = statistics.mean(sorted_draws)
    empirical_p = None
    survives = None
    if observed_lift is not None:
        empirical_p = sum(1 for x in sorted_draws if x >= observed_lift) / n
        survives = observed_lift > hi
    return {
        "n_draws_usable": n,
        "null_lift_mean": mean_null,
        "null_lift_ci95_lo": lo,
        "null_lift_ci95_hi": hi,
        "observed_lift": observed_lift,
        "empirical_p_null_ge_observed": empirical_p,
        "observed_exceeds_null_ci95_hi": survives,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    items, inventory, gold_mismatch = build_items()

    print("=" * 100)
    print("INVENTORY -- all committed benchmark/results/*.jsonl")
    print("=" * 100)
    n_used, n_excluded = 0, 0
    for fname, n_lines, n_emit, note in inventory:
        status = "USED" if n_emit > 0 else "EXCLUDED"
        n_used += 1 if n_emit > 0 else 0
        n_excluded += 1 if n_emit == 0 else 0
        print(f"[{status:8s}] {fname:55s} lines={n_lines:5d} obs_emitted={n_emit:5d}  {note}")
    print()
    print(f"Files contributing >=1 observation: {n_used}  Files excluded entirely: {n_excluded}")

    n_multi = [it for it in items if it.k >= 2]
    print()
    print(f"Distinct (benchmark, question_id) items observed: {len(items)}")
    print(f"Items with gold-text DISAGREEMENT across replicates (excluded, logged as a data issue): {len(gold_mismatch)}")
    for bench, qid, texts in gold_mismatch[:10]:
        print(f"    {bench} {qid}: {len(texts)} distinct gold texts -- {[t[:50] for t in texts]}")
    print(f"Items with >=2 replicate observations (the analysis pool): {len(n_multi)}")

    n_choice_pool_gt3 = sum(1 for it in n_multi if len(it.wrong_text_pool) > 3)
    print(f"Items whose union of observed wrong choice-texts exceeds 3 (distractor set varies across "
          f"replicates -- loader resamples distractors, not just reorders them; see report caveat): "
          f"{n_choice_pool_gt3}")

    # Sanity check: our recomputed `correct` vs the row's own logged `correct`.
    all_obs = [o for it in items for o in it.observations]
    checked = [o for o in all_obs if o.logged_correct is not None]
    mism = [o for o in checked if o.correct != o.logged_correct]
    print()
    print(f"Sanity check: recomputed correctness (chosen_text==gold_text) vs each row's own logged "
          f"`correct` field -- {len(checked)} observations checked, {len(mism)} mismatches "
          f"({'METHODOLOGY VALIDATED' if not mism else 'INVESTIGATE'})")

    by_bench: dict[str, list[Item]] = defaultdict(list)
    for it in n_multi:
        by_bench[it.benchmark].append(it)

    real_per_bench = {b: aggregate_real(its) for b, its in sorted(by_bench.items())}
    real_overall = aggregate_real(n_multi)

    print()
    print("=" * 100)
    print(f"REAL (OBSERVED) STABILITY vs WRONGNESS, per benchmark (permutation null: NDRAWS={NDRAWS}, seed={NULL_SEED})")
    print("=" * 100)

    null_draws = run_permutation_null(n_multi, NDRAWS, NULL_SEED)

    null_per_bench = {}
    for bench, agg in real_per_bench.items():
        d = null_draws.get(bench, [])
        null_summary = summarize_null(d, agg.get("lift"))
        null_per_bench[bench] = null_summary
        print(f"\n[{bench}] n={agg['n_items']} (mean {agg['mean_replicates_per_item']:.1f} replicates/item)  "
              f"instability_rate={agg['instability_rate']*100:.1f}%  "
              f"P(wrong|stable)={agg['p_wrong_given_stable']*100:.1f}% ({agg['n_wrong_stable']}/{agg['n_stable']})  "
              f"P(wrong|unstable)={agg['p_wrong_given_unstable']*100:.1f}% ({agg['n_wrong_unstable']}/{agg['n_unstable']})  "
              f"LIFT={agg['lift']*100:+.1f}pp")
        if null_summary["n_draws_usable"]:
            verdict = "SURVIVES mechanical floor" if null_summary["observed_exceeds_null_ci95_hi"] else "DOES NOT SURVIVE (within null CI)"
            print(f"    null lift: mean={null_summary['null_lift_mean']*100:+.1f}pp  "
                  f"95% CI=[{null_summary['null_lift_ci95_lo']*100:+.1f}, {null_summary['null_lift_ci95_hi']*100:+.1f}]pp  "
                  f"empirical p(null>=observed)={null_summary['empirical_p_null_ge_observed']:.4f}   {verdict}")
        else:
            print("    null: not enough stable+unstable items in this benchmark to compute a null lift")

    print()
    print("=" * 100)
    print("OVERALL (all benchmarks pooled)")
    print("=" * 100)
    agg = real_overall
    null_overall = summarize_null(null_draws.get("OVERALL", []), agg.get("lift"))
    print(f"n={agg['n_items']} (mean {agg['mean_replicates_per_item']:.1f} replicates/item)  "
          f"instability_rate={agg['instability_rate']*100:.1f}%  "
          f"P(wrong|stable)={agg['p_wrong_given_stable']*100:.1f}% ({agg['n_wrong_stable']}/{agg['n_stable']})  "
          f"P(wrong|unstable)={agg['p_wrong_given_unstable']*100:.1f}% ({agg['n_wrong_unstable']}/{agg['n_unstable']})  "
          f"LIFT={agg['lift']*100:+.1f}pp")
    verdict = "SURVIVES mechanical floor" if null_overall["observed_exceeds_null_ci95_hi"] else "DOES NOT SURVIVE (within null CI)"
    print(f"    null lift: mean={null_overall['null_lift_mean']*100:+.1f}pp  "
          f"95% CI=[{null_overall['null_lift_ci95_lo']*100:+.1f}, {null_overall['null_lift_ci95_hi']*100:+.1f}]pp  "
          f"empirical p(null>=observed)={null_overall['empirical_p_null_ge_observed']:.4f}   {verdict}")

    # --- write artifacts ---
    RESULTS_DIR.mkdir(exist_ok=True)

    with (RESULTS_DIR / "stability_audit_items.csv").open("w", encoding="utf-8", newline="") as fh:
        fieldnames = ["benchmark", "question_id", "k", "r_correct", "w_wrong", "n_distinct_wrong_texts",
                      "stable", "majority_wrong", "configs"]
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for it in n_multi:
            w.writerow({
                "benchmark": it.benchmark, "question_id": it.question_id, "k": it.k,
                "r_correct": it.r, "w_wrong": it.w, "n_distinct_wrong_texts": len(it.wrong_text_pool),
                "stable": it.stable, "majority_wrong": it.majority_wrong,
                "configs": ";".join(f"{o.source_file}:{o.config}" for o in it.observations),
            })

    summary = {
        "ndraws": NDRAWS,
        "null_seed": NULL_SEED,
        "inventory": [{"file": f, "n_lines": n, "n_obs_emitted": e, "note": note} for f, n, e, note in inventory],
        "n_items_total": len(items),
        "n_items_gold_mismatch_excluded": len(gold_mismatch),
        "gold_mismatch_items": [{"benchmark": b, "question_id": q, "n_distinct_gold_texts": len(t)} for b, q, t in gold_mismatch],
        "n_items_multi_replicate": len(n_multi),
        "n_items_wrong_text_pool_gt3": n_choice_pool_gt3,
        "plurality_sanity_check": {"n_checked": len(checked), "n_mismatches": len(mism)},
        "per_benchmark_real": real_per_bench,
        "per_benchmark_null": null_per_bench,
        "overall_real": real_overall,
        "overall_null": null_overall,
    }
    with (RESULTS_DIR / "stability_audit_summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)

    print()
    print("Wrote: benchmark/results/stability_audit_items.csv, benchmark/results/stability_audit_summary.json")
    print()
    print("Reproduce with: .venv/Scripts/python.exe benchmark/analyze_stability_repaired.py")


if __name__ == "__main__":
    main()
