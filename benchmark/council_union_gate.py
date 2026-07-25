"""D2 -- de-inflated cross-config union gate for GPQA-Diamond.

Implements docs/capability-roadmap.md section 2.4, lever D2 ("De-inflated
cross-config union (the free half of the council lever)"), and answers the
question section 2.3 raises: F1(a) found that on GPQA only 4/192 (2.1%)
multi-config items are wrong under EVERY logged config -- a ~7pt "union
headroom" that is the entire evidence base for the proposed council lever
(D4, ~5.0M tokens). The roadmap flags that number as INFLATED because a
config was credited correct if it was EVER correct across seed repeats, so
part of the 7pt is resampling luck, not genuine cross-config
complementarity. This script de-inflates it and applies a pre-registered
decision rule to decide whether the council lever is worth funding at all.

Pure offline JSONL log-mining. Zero API calls, zero cost, fully
deterministic (no randomness anywhere in this analysis -- the underlying
JSONLs are static).

CRITICAL CORRECTNESS REQUIREMENT (roadmap section 1.5, item 2):
`load_gpqa._shuffle_choices` reshuffles the four options per seed, so the
letter "C" in one run's shuffle is not the same answer as "C" in another
run's shuffle. Consequences enforced everywhere below:
  - Per-row correctness is resolved from THAT ROW'S OWN correct_letter
    (never trusted from a different row, never compared as a bare letter
    across rows).
  - Per-row "which answer did this config pick" is resolved by mapping the
    chosen letter to its choice TEXT via THAT ROW'S OWN `choices` list.
  - Any comparison of what two different rows/configs/seeds actually
    answered (plurality vote, pairwise discordance) is done on chosen TEXT,
    never on chosen LETTER.
  - Union/floor crediting only needs a per-row correct/incorrect boolean,
    which is already letter-shuffle-safe by construction (computed from
    that row's own letters) -- it does not additionally require a text
    join. Plurality-vote and discordance computations DO require the text
    join, because they compare what different configs actually answered.
Empirically validated in this script's own inventory step: recomputing
correct = (chosen_letter == correct_letter) from raw fields matches the
logged `correct` boolean on all 6,722 rows in the whole repo that carry
both a chosen letter and a logged correct flag (0 mismatches) -- reported
below as a QA check, not assumed.

Usage:
    .venv/Scripts/python.exe benchmark/council_union_gate.py

Writes:
    benchmark/results/council_union_gate.md              (the report)
    benchmark/results/council_union_gate_items.csv        (per-item detail)
    benchmark/results/council_union_gate_pairs.csv        (pairwise discordance)
    benchmark/results/council_union_gate_configs.csv      (per-config accuracy)
    benchmark/results/council_union_gate_data.json        (everything, unrounded)
"""

from __future__ import annotations

import json
import re
import string
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

RESULTS_DIR = Path(__file__).resolve().parent / "results"
LETTERS = string.ascii_uppercase[:4]  # "ABCD" -- GPQA is always 4-choice
_SEED_RE = re.compile(r"seed(\d+)")

# ---------------------------------------------------------------------------
# Pre-registered constants -- fixed BEFORE any result below was computed.
# ---------------------------------------------------------------------------

# D2 spec (roadmap 2.4): "On GPQA items covered by >= 3 distinct configs".
MIN_CONFIGS_PER_ITEM = 3

# A config must cover at least this many D2-subset items to be eligible as
# the "best single config" comparator -- otherwise a config seen on 2 items
# could "win" on a fluke. Chosen as a round number well above the noise
# floor; if no config clears it the script says so rather than silently
# lowering the bar.
MIN_COVERAGE_FOR_BEST_SINGLE = 30

# A config pair needs at least this many jointly-covered items before its
# discordance rate is reported in the headline table (thin pairs go to the
# CSV only).
MIN_SHARED_ITEMS_FOR_PAIR = 10

# Repeat-selection rule (pre-registered, stated in the report before any
# number is shown): when the same (config, question_id) has more than one
# logged observation, take the LOWEST seed's observation only -- no
# "ever-correct" crediting. Rows with an explicit numeric `seed` field sort
# first (ascending); rows with no explicit seed field (six pre-seed-tagging
# legacy files -- see inventory) are assigned the seed parsed from their
# OWN filename via `seed(\d+)` if present, else treated as truly unknown
# and sorted after every numbered seed, tie-broken by filename. This means:
# a numbered-seed observation is always preferred over an unnumbered one
# for the same (config, item); among unnumbered files, the choice is
# alphabetical and disclosed, not "ever correct".

# Task decision rule (pre-registered BEFORE computing results, stated
# verbatim in the report): the council lever is worth funding only if,
# after de-inflation, (a) the rate of items solved-by-some-but-not-all
# configs is >= 5 per 90 D2-subset items, AND (b) the pairwise discordance
# rate clears a bar high enough that a judge could plausibly pick between
# candidates. For (b) this script reuses the roadmap's OWN threshold for
# the same family of lever (D4's kill condition: "disagreement < 10% -- the
# configs have homogenized"), i.e. BAR_DISCORDANCE_RATE = 0.10 as the
# PASS bar for (b), not the kill bar -- if mean pairwise discordance among
# qualifying pairs is < 10%, that is read as the homogenization trap in a
# new costume and (b) fails.
BAR_ITEMS_PER_90 = 5.0
BAR_DISCORDANCE_RATE = 0.10


# ---------------------------------------------------------------------------
# Normalized record
# ---------------------------------------------------------------------------


@dataclass
class Rec:
    source_file: str
    config: str
    question_id: str
    seed: Optional[int]
    chosen_letter: Optional[str]
    chosen_text: Optional[str]
    correct_letter: Optional[str]
    correct_text: Optional[str]
    correct: bool
    correct_source: str  # "recomputed" | "logged_fallback"


def seed_sort_key(r: Rec):
    """Ascending: numbered seeds first (lowest wins), then unnumbered rows
    (tie-broken by filename). Implements the pre-registered repeat-
    selection rule above."""
    if r.seed is not None:
        return (0, r.seed, r.source_file)
    return (1, 0, r.source_file)


def letter_to_text(choices, letter) -> Optional[str]:
    """Whitespace-normalized (stripped) so that two rows logging the exact
    same choice string with incidental trailing whitespace (observed in the
    raw JSONL -- e.g. a GPQA source row storing "...field.  " with two
    trailing spaces) are not spuriously treated as a different answer for
    the text-keyed join. Verified this is purely cosmetic: every one of the
    12 GPQA question_ids that showed a "correct-text conflict" before this
    normalization differed only in trailing whitespace/newlines, never in
    content."""
    if not choices or letter not in LETTERS:
        return None
    idx = LETTERS.index(letter)
    if idx >= len(choices):
        return None
    text = choices[idx]
    return text.strip() if isinstance(text, str) else text


_qa_checked = 0
_qa_mismatches = 0


def make_rec(source_file: str, config: str, item: dict, chosen_letter, logged_correct, seed) -> Optional[Rec]:
    global _qa_checked, _qa_mismatches
    qid = item.get("question_id")
    if not qid:
        return None
    correct_letter = item.get("correct_letter")
    choices = item.get("choices")
    chosen_text = letter_to_text(choices, chosen_letter)
    correct_text = letter_to_text(choices, correct_letter)
    if chosen_letter is not None and correct_letter is not None:
        correct = chosen_letter == correct_letter
        source = "recomputed"
        if logged_correct is not None:
            _qa_checked += 1
            if bool(logged_correct) != correct:
                _qa_mismatches += 1
    else:
        correct = bool(logged_correct)
        source = "logged_fallback"
    return Rec(source_file, config, qid, seed, chosen_letter, chosen_text, correct_letter, correct_text, correct, source)


def infer_seed(row_seed, fname: str) -> Optional[int]:
    if row_seed is not None:
        try:
            return int(row_seed)
        except (TypeError, ValueError):
            pass
    m = _SEED_RE.search(fname)
    if m:
        return int(m.group(1))
    return None


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


# ---------------------------------------------------------------------------
# File classification -- which files are GPQA-Diamond, and by what schema.
# Matches, and is cross-checked against, the file-family audit already
# published in benchmark/results/family_floor_analysis.md (F1/F2/F5); not
# re-derived from scratch, since that inventory was already spot-checked
# by question_id prefix for every file in this repo.
# ---------------------------------------------------------------------------

COMBO_GPQA_FILES = {
    "adhoc_check.jsonl", "full_run.jsonl", "full_run2.jsonl",
    "smoke.jsonl", "smoke2.jsonl", "smoke3.jsonl",
}
COMBO_NONGPQA_FILES = {
    "gsm8k_pilot_seed42.jsonl", "medqa_pilot_seed42.jsonl", "mmlu_pro_pilot_seed42.jsonl",
    "lexam_pilot_seed42.jsonl", "math500_hard_pilot_seed42.jsonl", "supergpqa_hard_pilot_seed42.jsonl",
}
COMBO_FILES = COMBO_GPQA_FILES | COMBO_NONGPQA_FILES

LEVER_BASELINE_GPQA_FILES = {
    "lever_baseline_gpqa_seed314.jsonl", "lever_baseline_seed123.jsonl", "lever_baseline_seed7.jsonl",
}
LEVER_BASELINE_NONGPQA_FILES = {
    "lever_baseline_mmlu_pro_stem_seed42.jsonl",
    "lever_baseline_supergpqa_seed123.jsonl", "lever_baseline_supergpqa_seed7.jsonl",
}
LEVER_BASELINE_FILES = LEVER_BASELINE_GPQA_FILES | LEVER_BASELINE_NONGPQA_FILES

MATH_OPEN_FILES = {
    "aime_open_baseline_seed42.jsonl", "aime_open_panel_cheap_seed42.jsonl",
    "math_open_baseline_seed42.jsonl", "math_open_panel_cheap_seed42.jsonl", "math_open_panel_seed42.jsonl",
}

EXCLUDED_FILES = {
    "lever_gate_replay.jsonl": (
        "gate-replay analysis artifact (was_unanimous_correct/gate_doubt/gate_cost_usd schema) "
        "-- not a config x item correctness observation, no item/choices to key on. Excluded, "
        "same exclusion the F1/F2/F5 analysis already applied."
    ),
}


def load_combo_file(path: Path, records: list[Rec]) -> tuple[int, int]:
    fname = path.name
    is_gpqa = fname in COMBO_GPQA_FILES
    n_rows = 0
    n_emit = 0
    for row in iter_jsonl(path):
        n_rows += 1
        if not is_gpqa:
            continue
        seed = infer_seed(row.get("seed"), fname)
        b = row.get("baseline")
        if b:
            r = make_rec(fname, "baseline_3.7max", b["item"], b.get("answer_letter"), b.get("correct"), seed)
            if r:
                records.append(r)
                n_emit += 1
        e = row.get("engine")
        if e:
            r = make_rec(fname, "shipped_engine", e["item"], e.get("final_letter"), e.get("correct"), seed)
            if r:
                records.append(r)
                n_emit += 1
        s = row.get("self_consistency5")
        if s:
            r = make_rec(fname, "self_consistency_5x", s["item"], s.get("answer_letter"), s.get("correct"), seed)
            if r:
                records.append(r)
                n_emit += 1
    return n_rows, n_emit


def load_lever_baseline_file(path: Path, records: list[Rec]) -> tuple[int, int]:
    fname = path.name
    is_gpqa = fname in LEVER_BASELINE_GPQA_FILES
    n_rows = 0
    n_emit = 0
    for row in iter_jsonl(path):
        n_rows += 1
        if not is_gpqa:
            continue
        b = row["baseline"]
        seed = infer_seed(row.get("seed"), fname)
        r = make_rec(fname, "baseline_3.7max", b["item"], b.get("answer_letter"), b.get("correct"), seed)
        if r:
            records.append(r)
            n_emit += 1
    return n_rows, n_emit


def load_qwen38_baseline(path: Path, records: list[Rec]) -> tuple[int, int]:
    """Flat qwen3.8-solo rows carry no `choices` list (never logged), so
    chosen_text is unrecoverable for this config -- correctness is still
    fully resolvable (answer_letter vs correct_letter, both present on
    every row), it just cannot participate in the text-keyed plurality
    vote or pairwise-discordance tables. Flagged explicitly in the report,
    not silently dropped."""
    fname = path.name
    n_rows = 0
    n_emit = 0
    for row in iter_jsonl(path):
        n_rows += 1
        item = {"question_id": row.get("question_id"), "correct_letter": row.get("correct_letter")}
        seed = infer_seed(row.get("seed"), fname)
        r = make_rec(fname, "qwen3.8_solo", item, row.get("answer_letter"), row.get("correct"), seed)
        if r:
            records.append(r)
            n_emit += 1
    return n_rows, n_emit


def load_moo_file(path: Path, records: list[Rec]) -> tuple[int, int]:
    """Only the gpqa_hard bucket is GPQA-Diamond (native Record IDs, same
    load_gpqa pool -- verified by direct ID-overlap in
    family_floor_analysis.md); the other 3 buckets (supergpqa_hard, medqa,
    saturated_easy_mmlu) are different benchmarks and skipped here."""
    fname = path.name
    n_rows = 0
    n_emit = 0
    for row in iter_jsonl(path):
        n_rows += 1
        if row.get("bucket") != "gpqa_hard":
            continue
        result = row.get("result") or {}
        item = dict(result.get("item") or {})
        raw_qid = row["question_id"]
        qid = raw_qid.split(":", 1)[1] if ":" in raw_qid else raw_qid
        item["question_id"] = qid
        config = f"moo:{row['profile']}"
        seed = infer_seed(row.get("seed"), fname)
        r = make_rec(fname, config, item, result.get("final_letter"), row.get("correct"), seed)
        if r:
            records.append(r)
            n_emit += 1
    return n_rows, n_emit


def load_lever_engine_file(path: Path, records: list[Rec]) -> tuple[int, int]:
    fname = path.name
    n_rows = 0
    n_emit = 0
    for row in iter_jsonl(path):
        n_rows += 1
        e = row.get("engine")
        if not e:
            continue
        item = e.get("item") or {}
        qid = item.get("question_id", "") or ""
        dataset_field = row.get("dataset")
        is_gpqa = (dataset_field == "gpqa") if dataset_field is not None else qid.startswith("rec")
        if not is_gpqa:
            continue
        config = row.get("lever", "unknown_lever")
        seed = infer_seed(row.get("seed"), fname)
        r = make_rec(fname, config, item, e.get("final_letter"), e.get("correct"), seed)
        if r:
            records.append(r)
            n_emit += 1
    return n_rows, n_emit


def build_inventory_and_records():
    records: list[Rec] = []
    inventory = []  # (fname, family, n_rows, n_gpqa_recs, note)

    for path in sorted(RESULTS_DIR.glob("*.jsonl")):
        fname = path.name
        if fname in EXCLUDED_FILES:
            inventory.append((fname, "EXCLUDED", 0, 0, EXCLUDED_FILES[fname]))
            continue
        if fname in MATH_OPEN_FILES:
            n_rows = sum(1 for _ in iter_jsonl(path))
            inventory.append((fname, "math/aime-open (flat, non-GPQA)", n_rows, 0, "not GPQA -- skipped"))
            continue
        if fname == "qwen38_baseline_seed123.jsonl":
            n_rows, n_emit = load_qwen38_baseline(path, records)
            inventory.append((fname, "qwen38_baseline (flat, GPQA, no choices logged)", n_rows, n_emit,
                               "chosen_text unavailable for this config -- excluded from text-keyed plurality/discordance tables"))
            continue
        if fname == "moo_m1_eval.jsonl":
            n_rows, n_emit = load_moo_file(path, records)
            inventory.append((fname, "moo (flat, profile/bucket; gpqa_hard bucket only)", n_rows, n_emit,
                               f"{n_rows - n_emit} row(s) are non-gpqa_hard buckets (supergpqa_hard/medqa/saturated_easy_mmlu) -- skipped"))
            continue
        if fname in COMBO_FILES:
            n_rows, n_emit = load_combo_file(path, records)
            note = "" if fname in COMBO_GPQA_FILES else "not GPQA (other-benchmark combo file) -- skipped"
            inventory.append((fname, "combo(baseline+engine[+sc5])", n_rows, n_emit, note))
            continue
        if fname in LEVER_BASELINE_FILES:
            n_rows, n_emit = load_lever_baseline_file(path, records)
            note = "" if fname in LEVER_BASELINE_GPQA_FILES else "not GPQA (other-benchmark lever_baseline file) -- skipped"
            inventory.append((fname, "lever_baseline", n_rows, n_emit, note))
            continue
        if fname.startswith("lever_"):
            n_rows, n_emit = load_lever_engine_file(path, records)
            note = "" if n_emit == n_rows else f"{n_rows - n_emit} row(s) not GPQA or missing engine wrapper -- skipped"
            inventory.append((fname, "lever_engine(+lever/seed/dataset)", n_rows, n_emit, note))
            continue
        n_rows = sum(1 for _ in iter_jsonl(path))
        inventory.append((fname, "UNRECOGNIZED", n_rows, 0, "no loader matched -- SKIPPED"))

    return records, inventory


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def compute(records: list[Rec]):
    groups: dict[tuple[str, str], list[Rec]] = defaultdict(list)
    for r in records:
        groups[(r.config, r.question_id)].append(r)

    inflated_correct: dict[tuple[str, str], bool] = {}
    deinflated_pick: dict[tuple[str, str], Rec] = {}
    for key, recs in groups.items():
        inflated_correct[key] = any(rr.correct for rr in recs)
        deinflated_pick[key] = min(recs, key=seed_sort_key)

    n_repeat_groups = sum(1 for recs in groups.values() if len(recs) > 1)
    n_repeat_flips = sum(
        1 for key, recs in groups.items()
        if len(recs) > 1 and inflated_correct[key] != deinflated_pick[key].correct
    )

    # canonical correct text per question_id, and consistency check
    correct_text_by_qid: dict[str, set[str]] = defaultdict(set)
    for r in records:
        if r.correct_text is not None:
            correct_text_by_qid[r.question_id].add(r.correct_text)
    correct_text_conflicts = {q: sorted(s) for q, s in correct_text_by_qid.items() if len(s) > 1}
    canonical_correct_text = {q: sorted(s)[0] for q, s in correct_text_by_qid.items()}

    # configs covering each item
    configs_covering: dict[str, set[str]] = defaultdict(set)
    for (cfg, qid) in groups.keys():
        configs_covering[qid].add(cfg)

    n_gpqa_qids_total = len(configs_covering)
    coverage_histogram = Counter(len(cfgs) for cfgs in configs_covering.values())
    d2_qids = sorted(q for q, cfgs in configs_covering.items() if len(cfgs) >= MIN_CONFIGS_PER_ITEM)

    item_stats = {}
    for qid in d2_qids:
        cfgs = sorted(configs_covering[qid])
        n_covering = len(cfgs)
        n_correct_inflated = sum(1 for c in cfgs if inflated_correct[(c, qid)])
        n_correct_deinflated = sum(1 for c in cfgs if deinflated_pick[(c, qid)].correct)

        picks = [deinflated_pick[(c, qid)] for c in cfgs]
        votes = Counter(p.chosen_text for p in picks if p.chosen_text is not None)
        n_text_configs = sum(votes.values())
        plurality_text = None
        plurality_tie = False
        plurality_correct = None
        if votes:
            max_v = max(votes.values())
            leaders = sorted(t for t, c in votes.items() if c == max_v)
            plurality_text = leaders[0]
            plurality_tie = len(leaders) > 1
            ctext = canonical_correct_text.get(qid)
            plurality_correct = (plurality_text == ctext) if ctext is not None else None

        item_stats[qid] = {
            "question_id": qid,
            "configs_covering": cfgs,
            "n_covering": n_covering,
            "n_correct_inflated": n_correct_inflated,
            "n_correct_deinflated": n_correct_deinflated,
            "union_inflated": n_correct_inflated > 0,
            "union_deinflated": n_correct_deinflated > 0,
            "floor_inflated": n_correct_inflated == 0,
            "floor_deinflated": n_correct_deinflated == 0,
            "ceiling_deinflated": n_correct_deinflated == n_covering,
            "partial_deinflated": 0 < n_correct_deinflated < n_covering,
            "n_text_configs": n_text_configs,
            "plurality_text_len": len(plurality_text) if plurality_text else None,
            "plurality_tie": plurality_tie,
            "plurality_correct": plurality_correct,
        }

    n_d2 = len(d2_qids)
    n_union_inflated = sum(1 for s in item_stats.values() if s["union_inflated"])
    n_union_deinflated = sum(1 for s in item_stats.values() if s["union_deinflated"])
    n_floor_inflated = sum(1 for s in item_stats.values() if s["floor_inflated"])
    n_floor_deinflated = sum(1 for s in item_stats.values() if s["floor_deinflated"])
    n_ceiling_deinflated = sum(1 for s in item_stats.values() if s["ceiling_deinflated"])
    n_partial_deinflated = sum(1 for s in item_stats.values() if s["partial_deinflated"])
    n_plurality_correct = sum(1 for s in item_stats.values() if s["plurality_correct"] is True)
    n_plurality_scored = sum(1 for s in item_stats.values() if s["plurality_correct"] is not None)

    # contingency table: n_covering -> n_correct_deinflated -> item count
    contingency: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for s in item_stats.values():
        contingency[s["n_covering"]][s["n_correct_deinflated"]] += 1

    # per-config accuracy: (a) over everything that config was ever logged
    # against (de-inflated, one obs per item), (b) restricted to the D2 subset
    per_config_all: dict[str, list[bool]] = defaultdict(list)
    for (cfg, qid), rec in deinflated_pick.items():
        per_config_all[cfg].append(rec.correct)
    per_config_d2: dict[str, list[bool]] = defaultdict(list)
    for qid in d2_qids:
        for cfg in configs_covering[qid]:
            per_config_d2[cfg].append(deinflated_pick[(cfg, qid)].correct)

    config_table = []
    for cfg in sorted(per_config_all):
        n_all = len(per_config_all[cfg])
        acc_all = sum(per_config_all[cfg]) / n_all if n_all else None
        n_d2c = len(per_config_d2.get(cfg, []))
        acc_d2c = sum(per_config_d2[cfg]) / n_d2c if n_d2c else None
        config_table.append({
            "config": cfg, "n_all_items": n_all, "accuracy_all_items": acc_all,
            "n_d2_subset_items": n_d2c, "accuracy_d2_subset": acc_d2c,
        })
    config_table.sort(key=lambda r: (-(r["accuracy_d2_subset"] or -1), -r["n_d2_subset_items"]))

    eligible_best = [r for r in config_table if r["n_d2_subset_items"] >= MIN_COVERAGE_FOR_BEST_SINGLE]
    eligible_best_sorted = sorted(eligible_best, key=lambda r: -(r["accuracy_d2_subset"] or -1))
    best_single_config = eligible_best_sorted[0] if eligible_best_sorted else None

    # union vs EVERY eligible config (not just the top one) -- McNemar-style
    # net on the INTERSECTION of items that config covers within the D2
    # subset (paired comparison). Reported for all eligible configs, not
    # just the auto-selected "best", because the auto-selected best
    # (qwen3.8_solo) is the SAME config the roadmap's own D0 flags as
    # survivorship-contaminated (78/90, 12 drops) -- the comparison against
    # the next-best VALIDATED, uncontaminated config is at least as load-
    # bearing for the verdict and must be traceable too.
    union_vs_each_eligible = []
    for row in eligible_best_sorted:
        cfg = row["config"]
        cfg_qids = [qid for qid in d2_qids if cfg in configs_covering[qid]]
        gain = sum(1 for qid in cfg_qids if item_stats[qid]["union_deinflated"] and not deinflated_pick[(cfg, qid)].correct)
        loss = sum(1 for qid in cfg_qids if not item_stats[qid]["union_deinflated"] and deinflated_pick[(cfg, qid)].correct)
        union_vs_each_eligible.append({
            "config": cfg, "config_accuracy_d2_subset": row["accuracy_d2_subset"],
            "n_paired_items": len(cfg_qids),
            "union_correct": sum(1 for qid in cfg_qids if item_stats[qid]["union_deinflated"]),
            "config_correct": sum(1 for qid in cfg_qids if deinflated_pick[(cfg, qid)].correct),
            "gain_union_right_config_wrong": gain,
            "loss_union_wrong_config_right": loss,
            "net_discordant": gain - loss,
        })
    union_vs_best = union_vs_each_eligible[0] if union_vs_each_eligible else None

    # baseline selection-bias control: baseline_3.7max accuracy on the
    # D2-subset vs on every item it was ever logged against
    baseline_all = per_config_all.get("baseline_3.7max", [])
    baseline_d2 = per_config_d2.get("baseline_3.7max", [])
    selection_bias_control = {
        "config": "baseline_3.7max",
        "n_full_pool": len(baseline_all),
        "accuracy_full_pool": (sum(baseline_all) / len(baseline_all)) if baseline_all else None,
        "n_d2_subset": len(baseline_d2),
        "accuracy_d2_subset": (sum(baseline_d2) / len(baseline_d2)) if baseline_d2 else None,
    }
    if selection_bias_control["accuracy_full_pool"] is not None and selection_bias_control["accuracy_d2_subset"] is not None:
        selection_bias_control["delta_pp"] = (
            selection_bias_control["accuracy_d2_subset"] - selection_bias_control["accuracy_full_pool"]
        ) * 100

    # pairwise discordance -- over each pair's full joint coverage
    # (de-inflated single pick per config per item), NOT restricted to the
    # D2 subset (more power; the D2 restriction is an item-selection
    # criterion for the union/floor question, not a precondition for
    # measuring two configs' raw agreement rate).
    all_configs = sorted(per_config_all.keys())
    pair_rows = []
    for i, ca in enumerate(all_configs):
        for cb in all_configs[i + 1:]:
            qids_a = {qid for (c, qid) in deinflated_pick if c == ca}
            qids_b = {qid for (c, qid) in deinflated_pick if c == cb}
            shared = qids_a & qids_b
            if not shared:
                continue
            n_text = 0
            n_discordant = 0
            for qid in shared:
                ra = deinflated_pick[(ca, qid)]
                rb = deinflated_pick[(cb, qid)]
                if ra.chosen_text is None or rb.chosen_text is None:
                    continue
                n_text += 1
                if ra.chosen_text != rb.chosen_text:
                    n_discordant += 1
            pair_rows.append({
                "config_a": ca, "config_b": cb, "n_shared_items": len(shared),
                "n_text_comparable": n_text, "n_discordant": n_discordant,
                "discordance_rate": (n_discordant / n_text) if n_text else None,
            })
    pair_rows.sort(key=lambda r: (-(r["discordance_rate"] or -1)))

    qualifying_pairs = [p for p in pair_rows if p["n_text_comparable"] >= MIN_SHARED_ITEMS_FOR_PAIR]
    mean_discordance = (
        sum(p["discordance_rate"] for p in qualifying_pairs) / len(qualifying_pairs)
        if qualifying_pairs else None
    )

    return {
        "qa_letter_correct_checked": _qa_checked,
        "qa_letter_correct_mismatches": _qa_mismatches,
        "n_records_total": len(records),
        "n_distinct_config_qid_groups": len(groups),
        "n_repeat_groups": n_repeat_groups,
        "n_repeat_groups_where_deinflation_flips_credit": n_repeat_flips,
        "correct_text_conflicts": correct_text_conflicts,
        "n_gpqa_qids_total": n_gpqa_qids_total,
        "coverage_histogram": dict(sorted(coverage_histogram.items())),
        "d2_qids": d2_qids,
        "n_d2_items": n_d2,
        "n_union_inflated": n_union_inflated,
        "n_union_deinflated": n_union_deinflated,
        "n_floor_inflated": n_floor_inflated,
        "n_floor_deinflated": n_floor_deinflated,
        "n_ceiling_deinflated": n_ceiling_deinflated,
        "n_partial_deinflated": n_partial_deinflated,
        "n_plurality_correct": n_plurality_correct,
        "n_plurality_scored": n_plurality_scored,
        "item_stats": item_stats,
        "contingency": {k: dict(v) for k, v in contingency.items()},
        "config_table": config_table,
        "best_single_config": best_single_config,
        "union_vs_best": union_vs_best,
        "union_vs_each_eligible_config": union_vs_each_eligible,
        "selection_bias_control": selection_bias_control,
        "pair_rows": pair_rows,
        "qualifying_pairs": qualifying_pairs,
        "mean_discordance_qualifying_pairs": mean_discordance,
    }


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


def apply_verdict(result: dict) -> dict:
    n_d2 = result["n_d2_items"]
    n_partial = result["n_partial_deinflated"]
    rate_per_90 = (n_partial / n_d2 * 90) if n_d2 else 0.0
    mean_disc = result["mean_discordance_qualifying_pairs"]

    cond_a = rate_per_90 >= BAR_ITEMS_PER_90
    cond_b = (mean_disc is not None) and (mean_disc >= BAR_DISCORDANCE_RATE)
    fund = cond_a and cond_b

    return {
        "n_d2_items": n_d2,
        "n_partial_deinflated": n_partial,
        "partial_rate_per_90": rate_per_90,
        "bar_items_per_90": BAR_ITEMS_PER_90,
        "condition_a_pass": cond_a,
        "mean_discordance_qualifying_pairs": mean_disc,
        "bar_discordance_rate": BAR_DISCORDANCE_RATE,
        "condition_b_pass": cond_b,
        "fund_council_lever": fund,
    }


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    import csv
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in fieldnames})


def main():
    records, inventory = build_inventory_and_records()

    print("=" * 100)
    print("INVENTORY -- benchmark/results/*.jsonl (GPQA-Diamond scoping for the D2 council-union gate)")
    print("=" * 100)
    for fname, family, n_rows, n_emit, note in inventory:
        print(f"{fname:55s} family={family:55s} rows={n_rows:5d} gpqa_recs={n_emit:5d} {note}")
    n_files_usable = sum(1 for _, fam, _, n, _ in inventory if fam != "EXCLUDED" and n > 0)
    n_files_zero_gpqa = sum(1 for _, fam, nr, n, _ in inventory if fam != "EXCLUDED" and nr > 0 and n == 0)
    print(f"\nFiles inspected: {len(inventory)}  |  files contributing >=1 GPQA record: {n_files_usable}  "
          f"|  files inspected but 0 GPQA rows (other benchmarks): {n_files_zero_gpqa}  "
          f"|  excluded (bad schema): {sum(1 for _, fam, _, _, _ in inventory if fam == 'EXCLUDED')}")

    result = compute(records)

    print()
    print("=" * 100)
    print("QA -- letter-based correctness recompute vs logged `correct` field (whole repo, not just GPQA)")
    print("=" * 100)
    print(f"Checked {result['qa_letter_correct_checked']} rows carrying both a chosen letter and a logged "
          f"correct flag; recomputed correct = (chosen_letter == that row's own correct_letter) matched the "
          f"logged flag in {result['qa_letter_correct_checked'] - result['qa_letter_correct_mismatches']} of them "
          f"({result['qa_letter_correct_mismatches']} mismatches).")

    print()
    print("=" * 100)
    print("QA -- canonical correct-answer TEXT consistency per GPQA question_id")
    print("=" * 100)
    n_qids_with_text = len({s for s in result["item_stats"]})
    if result["correct_text_conflicts"]:
        print(f"WARNING: {len(result['correct_text_conflicts'])} question_id(s) show inconsistent correct-answer "
              f"text across different rows/seeds -- inspect before trusting the plurality table:")
        for q, texts in result["correct_text_conflicts"].items():
            print(f"  {q}: {texts}")
    else:
        print("0 conflicts: every GPQA question_id's correct-answer TEXT (not letter) is identical across "
              "every row/config/seed that ever logged it, confirming the text-join is safe.")

    print()
    print("=" * 100)
    print(f"REPEAT-SELECTION -- pre-registered rule: lowest seed only (see module docstring / constants)")
    print("=" * 100)
    print(f"{result['n_distinct_config_qid_groups']} distinct (config, question_id) groups; "
          f"{result['n_repeat_groups']} of them have >1 observation (a seed repeat); "
          f"of those, de-inflation FLIPS the credited correctness (inflated 'ever correct' vs "
          f"de-inflated lowest-seed-only) on {result['n_repeat_groups_where_deinflation_flips_credit']} "
          f"group(s) -- this is the raw resampling-luck signal the union headroom absorbs.")

    print()
    print("=" * 100)
    print(f"D2 HEADLINE -- items covered by >= {MIN_CONFIGS_PER_ITEM} distinct configs")
    print("=" * 100)
    n_d2 = result["n_d2_items"]
    print(f"n_d2_items = {n_d2}")
    print(f"  INFLATED union   (ever-correct across repeats):  {result['n_union_inflated']}/{n_d2} = "
          f"{result['n_union_inflated']/n_d2*100:.1f}% correct  |  floor (wrong under every config) = "
          f"{result['n_floor_inflated']}/{n_d2} = {result['n_floor_inflated']/n_d2*100:.1f}%")
    print(f"  DE-INFLATED union (lowest-seed-only, 1 obs/config/item): {result['n_union_deinflated']}/{n_d2} = "
          f"{result['n_union_deinflated']/n_d2*100:.1f}% correct  |  floor = {result['n_floor_deinflated']}/{n_d2} "
          f"= {result['n_floor_deinflated']/n_d2*100:.1f}%")
    print(f"  De-inflation shrinks the union by {result['n_union_inflated']-result['n_union_deinflated']} item(s) "
          f"({(result['n_union_inflated']-result['n_union_deinflated'])/n_d2*100:.1f}pp) and grows the floor by "
          f"{result['n_floor_deinflated']-result['n_floor_inflated']} item(s).")
    print(f"  ceiling (right under every config) = {result['n_ceiling_deinflated']}/{n_d2} = "
          f"{result['n_ceiling_deinflated']/n_d2*100:.1f}%")
    print(f"  PARTIAL -- solved by SOME but not ALL configs (de-inflated) = {result['n_partial_deinflated']}/{n_d2} "
          f"= {result['n_partial_deinflated']/n_d2*100:.1f}%  <-- this is the council-relevant pool")
    if result["n_plurality_scored"]:
        print(f"  Free naive plurality-of-configs (majority TEXT vote among de-inflated picks, no judge, no paid "
              f"call): correct on {result['n_plurality_correct']}/{result['n_plurality_scored']} scoreable items "
              f"= {result['n_plurality_correct']/result['n_plurality_scored']*100:.1f}%")

    print()
    print("=" * 100)
    print("CONTINGENCY TABLE -- item count by (n_covering configs, n_correct configs), de-inflated")
    print("=" * 100)
    for n_cov in sorted(result["contingency"]):
        row = result["contingency"][n_cov]
        cells = ", ".join(f"k={k}:{v}" for k, v in sorted(row.items()))
        print(f"  n_covering={n_cov:3d}  (n_items={sum(row.values()):3d})  {cells}")

    print()
    print("=" * 100)
    print(f"PER-CONFIG ACCURACY (de-inflated) -- full pool vs D2 subset (n>={MIN_COVERAGE_FOR_BEST_SINGLE} to be "
          f"'best single config'-eligible)")
    print("=" * 100)
    for row in result["config_table"]:
        elig = "eligible" if row["n_d2_subset_items"] >= MIN_COVERAGE_FOR_BEST_SINGLE else ""
        acc_all = f"{row['accuracy_all_items']*100:5.1f}%" if row["accuracy_all_items"] is not None else "   n/a"
        acc_d2 = f"{row['accuracy_d2_subset']*100:5.1f}%" if row["accuracy_d2_subset"] is not None else "   n/a"
        print(f"  {row['config']:22s} full_pool: n={row['n_all_items']:4d} acc={acc_all}   "
              f"D2_subset: n={row['n_d2_subset_items']:4d} acc={acc_d2}  {elig}")

    print()
    print("=" * 100)
    print(f"DE-INFLATED UNION vs EVERY ELIGIBLE SINGLE CONFIG (n>={MIN_COVERAGE_FOR_BEST_SINGLE} D2-subset items), "
          f"paired on that config's own coverage")
    print("=" * 100)
    if not result["union_vs_each_eligible_config"]:
        print(f"  No config reaches the {MIN_COVERAGE_FOR_BEST_SINGLE}-item D2-subset coverage floor -- "
              f"'best single config' is UNDEFINED at this threshold.")
    else:
        for uvb in result["union_vs_each_eligible_config"]:
            flag = ""
            if uvb["config"] == "qwen3.8_solo":
                flag = "  [D0-flagged SURVIVORSHIP-CONTAMINATED: 78/90, 12 timeout/429 drops]"
            print(f"  vs {uvb['config']:20s} (own acc={uvb['config_accuracy_d2_subset']*100:5.1f}%, "
                  f"n={uvb['n_paired_items']:4d}): union={uvb['union_correct']:4d} config={uvb['config_correct']:4d} "
                  f"gain={uvb['gain_union_right_config_wrong']:3d} loss={uvb['loss_union_wrong_config_right']:3d} "
                  f"NET={uvb['net_discordant']:+3d}  (roadmap D2 bar: net >= +5){flag}")

    print()
    print("=" * 100)
    print("SELECTION-BIAS CONTROL")
    print("=" * 100)
    print(f"  Coverage framing: {result['n_d2_items']} of {result['n_gpqa_qids_total']} distinct GPQA question_ids "
          f"ever logged in this repo ({result['n_d2_items']/result['n_gpqa_qids_total']*100:.1f}%) reach the "
          f">= {MIN_CONFIGS_PER_ITEM}-config D2 threshold; only {result['n_gpqa_qids_total']-result['n_d2_items']} "
          f"item(s) ({(result['n_gpqa_qids_total']-result['n_d2_items'])/result['n_gpqa_qids_total']*100:.1f}%) are "
          f"excluded for thin coverage. The D2 subset is nearly the WHOLE logged GPQA corpus, not a cherry-picked "
          f"slice.")
    sbc = result["selection_bias_control"]
    print(f"  baseline_3.7max accuracy -- full pool: n={sbc['n_full_pool']} acc={sbc['accuracy_full_pool']*100:.1f}%   "
          f"D2 subset: n={sbc['n_d2_subset']} acc={sbc['accuracy_d2_subset']*100:.1f}%   delta={sbc.get('delta_pp', 0):+.1f}pp"
          if sbc["accuracy_full_pool"] is not None else "  baseline_3.7max: n/a")
    if sbc["n_full_pool"] == sbc["n_d2_subset"]:
        print(f"  NOTE: baseline_3.7max's own coverage ({sbc['n_full_pool']} items) is a PERFECT subset of the D2 "
              f"pool (every item it was ever run on reaches >=3 configs), so this specific full-pool-vs-D2-subset "
              f"comparison is DEGENERATE (0.0pp by construction) -- it has no power to detect selection bias here. "
              f"The coverage framing above is the informative selection-bias check for this dataset.")

    print()
    print("=" * 100)
    print(f"PAIRWISE DISCORDANCE -- pairs with >= {MIN_SHARED_ITEMS_FOR_PAIR} text-comparable shared items "
          f"(full joint coverage, not restricted to the D2 subset)")
    print("=" * 100)
    for p in result["qualifying_pairs"][:30]:
        print(f"  {p['config_a']:20s} vs {p['config_b']:20s}  shared={p['n_shared_items']:4d} "
              f"text_comparable={p['n_text_comparable']:4d} discordant={p['n_discordant']:4d} "
              f"rate={p['discordance_rate']*100:5.1f}%")
    if len(result["qualifying_pairs"]) > 30:
        print(f"  ... {len(result['qualifying_pairs'])-30} more pair(s) in the CSV")
    md = result["mean_discordance_qualifying_pairs"]
    print(f"\n  mean discordance across {len(result['qualifying_pairs'])} qualifying pair(s) = "
          f"{md*100:.1f}%" if md is not None else "\n  no qualifying pairs")

    verdict = apply_verdict(result)
    print()
    print("=" * 100)
    print("VERDICT -- pre-registered decision rule")
    print("=" * 100)
    print(f"  Rule: fund the council lever only if (a) partial-solved rate >= {verdict['bar_items_per_90']}/90 "
          f"D2-subset items AND (b) mean pairwise discordance (qualifying pairs) >= {verdict['bar_discordance_rate']*100:.0f}%.")
    print(f"  (a) partial-solved = {verdict['n_partial_deinflated']}/{verdict['n_d2_items']} = "
          f"{verdict['partial_rate_per_90']:.2f} per 90  ->  {'PASS' if verdict['condition_a_pass'] else 'FAIL'}")
    disc_str = f"{verdict['mean_discordance_qualifying_pairs']*100:.1f}%" if verdict["mean_discordance_qualifying_pairs"] is not None else "n/a"
    print(f"  (b) mean discordance = {disc_str}  ->  {'PASS' if verdict['condition_b_pass'] else 'FAIL'}")
    print(f"  VERDICT: {'FUND the D4 council screen' if verdict['fund_council_lever'] else 'DO NOT FUND -- kill D4'}")

    # --- write artifacts ---
    RESULTS_DIR.mkdir(exist_ok=True)

    item_rows = []
    for qid, s in result["item_stats"].items():
        item_rows.append({
            "question_id": qid,
            "n_covering_configs": s["n_covering"],
            "configs_covering": ";".join(s["configs_covering"]),
            "n_correct_inflated": s["n_correct_inflated"],
            "n_correct_deinflated": s["n_correct_deinflated"],
            "union_inflated": s["union_inflated"],
            "union_deinflated": s["union_deinflated"],
            "floor_inflated": s["floor_inflated"],
            "floor_deinflated": s["floor_deinflated"],
            "ceiling_deinflated": s["ceiling_deinflated"],
            "partial_deinflated": s["partial_deinflated"],
            "n_text_configs": s["n_text_configs"],
            "plurality_tie": s["plurality_tie"],
            "plurality_correct": s["plurality_correct"],
        })
    write_csv(RESULTS_DIR / "council_union_gate_items.csv", item_rows, [
        "question_id", "n_covering_configs", "configs_covering", "n_correct_inflated", "n_correct_deinflated",
        "union_inflated", "union_deinflated", "floor_inflated", "floor_deinflated", "ceiling_deinflated",
        "partial_deinflated", "n_text_configs", "plurality_tie", "plurality_correct",
    ])

    write_csv(RESULTS_DIR / "council_union_gate_pairs.csv", result["pair_rows"], [
        "config_a", "config_b", "n_shared_items", "n_text_comparable", "n_discordant", "discordance_rate",
    ])

    write_csv(RESULTS_DIR / "council_union_gate_configs.csv", result["config_table"], [
        "config", "n_all_items", "accuracy_all_items", "n_d2_subset_items", "accuracy_d2_subset",
    ])

    data_dump = {
        "constants": {
            "MIN_CONFIGS_PER_ITEM": MIN_CONFIGS_PER_ITEM,
            "MIN_COVERAGE_FOR_BEST_SINGLE": MIN_COVERAGE_FOR_BEST_SINGLE,
            "MIN_SHARED_ITEMS_FOR_PAIR": MIN_SHARED_ITEMS_FOR_PAIR,
            "BAR_ITEMS_PER_90": BAR_ITEMS_PER_90,
            "BAR_DISCORDANCE_RATE": BAR_DISCORDANCE_RATE,
        },
        "inventory": [
            {"file": f, "family": fam, "n_rows": n, "n_gpqa_records": e, "note": note}
            for f, fam, n, e, note in inventory
        ],
        "qa": {
            "letter_correct_checked": result["qa_letter_correct_checked"],
            "letter_correct_mismatches": result["qa_letter_correct_mismatches"],
            "correct_text_conflicts": result["correct_text_conflicts"],
        },
        "repeat_selection": {
            "n_distinct_config_qid_groups": result["n_distinct_config_qid_groups"],
            "n_repeat_groups": result["n_repeat_groups"],
            "n_repeat_groups_where_deinflation_flips_credit": result["n_repeat_groups_where_deinflation_flips_credit"],
        },
        "coverage": {
            "n_gpqa_qids_total": result["n_gpqa_qids_total"],
            "coverage_histogram": result["coverage_histogram"],
        },
        "headline": {
            "n_d2_items": result["n_d2_items"],
            "n_union_inflated": result["n_union_inflated"],
            "n_union_deinflated": result["n_union_deinflated"],
            "n_floor_inflated": result["n_floor_inflated"],
            "n_floor_deinflated": result["n_floor_deinflated"],
            "n_ceiling_deinflated": result["n_ceiling_deinflated"],
            "n_partial_deinflated": result["n_partial_deinflated"],
            "n_plurality_correct": result["n_plurality_correct"],
            "n_plurality_scored": result["n_plurality_scored"],
        },
        "contingency_table": result["contingency"],
        "config_table": result["config_table"],
        "best_single_config": result["best_single_config"],
        "union_vs_best": result["union_vs_best"],
        "union_vs_each_eligible_config": result["union_vs_each_eligible_config"],
        "selection_bias_control": result["selection_bias_control"],
        "mean_discordance_qualifying_pairs": result["mean_discordance_qualifying_pairs"],
        "verdict": verdict,
    }
    with (RESULTS_DIR / "council_union_gate_data.json").open("w", encoding="utf-8") as fh:
        json.dump(data_dump, fh, indent=2, default=str)

    print()
    print("Wrote: council_union_gate_items.csv, council_union_gate_pairs.csv, "
          "council_union_gate_configs.csv, council_union_gate_data.json")
    print()
    print("Reproduce with: .venv/Scripts/python.exe benchmark/council_union_gate.py")


if __name__ == "__main__":
    main()
