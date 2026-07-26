"""S3 / S6 / S7 selector scorer (docs/experiment-spec-book.md section 3):
scores MANY selectors over a frozen candidate pool written by
benchmark/run_pool.py, for ZERO additional tokens -- the consuming half of
S2's "generate one frozen K=8 pool, then score many selectors against it"
economics.

Implements:
  - S3: the selector bake-off (plurality / confidence_weighted /
    max_single_confidence / longest_reasoning / oracle) on a frozen pool,
    with the exact same accuracy + paired-discordant + exact-McNemar shape
    benchmark/audit_selectors.py already established for S1. Reuses that
    file's selector implementations (sel_plurality, sel_confidence_weighted,
    sel_max_single_confidence, sel_longest_reasoning) directly instead of
    re-deriving them, and benchmark/analyze_panel_scaling.py's already-
    verified exact McNemar p-value function (mcnemar_exact_one_sided --
    known values b=3,c=0 -> p=0.125, b=4,c=0 -> 0.0625, b=5,c=0 -> 0.03125,
    matching this repo's pre-registered "net >= +5, p < 0.05" bar convention
    in docs/experiment-spec-book.md section 1) instead of writing a second
    one.
  - S6: the pool-size curve (accuracy@k for k=1..K, every selector, plus
    oracle coverage@k) by prefix subsampling of each row's ordered
    `samples` list -- free once the pool exists, since every intermediate k
    is a strict prefix of the full K-sample draw (mirrors
    analyze_panel_scaling.py's nested-prefix-subsampling trick for the
    panel-size curve).
  - S7: the ship-gate verdict -- THE ONLY spec in this family that can ship
    a selector, because it is the only one scored on pools generated at
    seeds the selector was never tuned or chosen on. A selector chosen on
    the same pool it was scored against (S1's audit) is fitted to that
    pool; S7 re-tests the winner on freshly generated pools at seeds never
    used in selection.

WHY THIS FILE EXISTS SEPARATELY FROM audit_selectors.py: audit_selectors.py
mined selectors out of already-logged pools -- pools generated (and in some
cases tuned) at seeds a "winner" verdict would otherwise be scored against
again. That is exactly the fitting failure S7 exists to catch, which is why
--ship-gate below refuses to run on a burned or previously-audited seed
(see BURNED_SEEDS / original_audit_seeds / assert_seeds_not_burned) rather
than merely documenting the rule in a runbook.

Usage (plain scoring, no ship verdict -- any number of pool files):
    .venv/Scripts/python.exe -m benchmark.score_selectors --pools \
        benchmark/results/pool_gpqa_cheap_k8_seed411.jsonl

Usage (S7 ship-gate, pooled over EXACTLY 3 held-out seeds, one benchmark):
    .venv/Scripts/python.exe -m benchmark.score_selectors --ship-gate \
        --selector max_single_confidence --pools \
        benchmark/results/pool_gpqa_cheap_k8_seed411.jsonl \
        benchmark/results/pool_gpqa_cheap_k8_seed523.jsonl \
        benchmark/results/pool_gpqa_cheap_k8_seed631.jsonl

Nothing here makes a network or paid API call -- pure offline JSONL mining
against already-generated pools, exactly like audit_selectors.py.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from benchmark.analyze_panel_scaling import mcnemar_exact_one_sided
from benchmark.audit_selectors import (
    sel_confidence_weighted,
    sel_longest_reasoning,
    sel_max_single_confidence,
    sel_plurality,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# benchmark/run_pool.py writes every frozen pool under this prefix -- used
# below to EXCLUDE S7's own freshly-generated pools from the "seeds already
# used in the S1 audit" scan (a pool doesn't burn itself the moment it's
# written; only already-existing, non-pool result files count as prior use).
POOL_FILENAME_PREFIX = "pool_"

SELECTOR_NAMES = ("plurality", "confidence_weighted", "max_single_confidence", "longest_reasoning")
# Only these two cleared the S1 zero-token audit's pre-registered bar
# (benchmark/results/selector_audit.md): confidence_weighted net +49,
# max_single_confidence net +121, both overall and on GPQA-Diamond /
# SuperGPQA-hard individually. `plurality` is the baseline being challenged,
# never a ship candidate itself; `longest_reasoning` is the deliberate junk
# control -- it losing badly is what validates the whole comparison, so it
# must never be ship-gated even by accident.
SHIPPABLE_SELECTORS = ("confidence_weighted", "max_single_confidence")

# dataset (as logged by benchmark/lever_experiments.py's DATASET_LOADERS /
# benchmark/run_pool.py) -> the benchmark label the S1 audit used. Only the
# two benchmarks large enough to ever clear the S1 bar are mapped -- see
# selector_audit.md section 3: the other five (MMLU-Pro, MedQA, LEXam,
# MATH-500-MC, GSM8K) never accumulated 12 discordant items for any
# selector, so there is no original-audit reference to hold S7 to on them,
# and --ship-gate refuses to fabricate one (see ship_gate_verdict below).
DATASET_TO_BENCHMARK = {
    "gpqa": "GPQA-Diamond",
    "supergpqa": "SuperGPQA-hard",
}

# Effect sizes (net discordant items, OVERALL pooled across every logged
# config) measured by the S1 zero-token audit (benchmark/audit_selectors.py
# -> benchmark/results/selector_audit.md, 5,451 already-logged pools).
# HARDCODED rather than re-read from selector_audit_summary.json at runtime:
# these are a FIXED published reference point for the "within 50% of the
# original effect size" ship-gate clause below, and re-deriving them from a
# file a later re-run of audit_selectors.py could silently change would let
# that comparison drift without anyone noticing. Source: selector_audit.md
# section 2's per-benchmark tables (GPQA-Diamond n=2,601, SuperGPQA-hard
# n=1,842).
#
# UNITS -- the defect this structure exists to prevent. These are net item
# COUNTS over the audit's own large denominators. An S7 run pools ~270 items
# (3 seeds x --n 90), so comparing an S7 count against one of these counts
# compares quantities whose denominators differ by 7-10x. That is what the
# clause below used to do, and it made the gate an unconditional DO NOT SHIP:
# a selector replicating the GPQA effect EXACTLY (2.1146% of items) yields an
# expected net of 5.7 over 270 items against a band floor of 27.5, and the
# floor is unreachable at any achievable size (GPQA-Diamond has only 198
# questions, so 3 seeds cap at 594 items). Inverted, a selector at ~7x the
# audited effect landed inside the band and PASSED. The denominators are
# therefore stored ALONGSIDE the counts and the clause compares RATES.
ORIGINAL_AUDIT_NET = {
    ("max_single_confidence", "GPQA-Diamond"): 55,
    ("max_single_confidence", "SuperGPQA-hard"): 76,
    ("confidence_weighted", "GPQA-Diamond"): 22,
    ("confidence_weighted", "SuperGPQA-hard"): 25,
}

# Denominators for the counts above, from selector_audit.md section 2's
# per-benchmark tables. Kept as a parallel hardcoded map for the same
# anti-drift reason as the counts themselves.
ORIGINAL_AUDIT_N = {
    "GPQA-Diamond": 2601,
    "SuperGPQA-hard": 1842,
}

# The S1 audit's raw contingency, needed for the POWER check below.
ORIGINAL_AUDIT_BC = {
    ("max_single_confidence", "GPQA-Diamond"): (141, 86),
    ("max_single_confidence", "SuperGPQA-hard"): (137, 61),
}

# ---------------------------------------------------------------------------
# POWER -- read this before choosing a home benchmark.
#
# Fixing the units bug above exposed a second, larger problem: at the S1
# audit's OWN measured effect size, the S7 design (3 seeds x --n 90 = 270
# pooled items) is underpowered on GPQA-Diamond and adequately powered only on
# SuperGPQA-hard.
#
#   GPQA-Diamond    b=141 c=86 over n=2,601 -> 5.42%/3.31% per item.
#                   At n=270 the expected contingency is b=15 c=9, one-sided
#                   exact McNemar p=0.1537. Reaching p<0.05 needs n>=600.
#                   GPQA-Diamond has only 198 questions, so three seeds cap at
#                   594 pooled observations -- and pooling more seeds of a
#                   198-question set re-uses the SAME questions, which inflates
#                   the discordant count without adding evidence (the identical
#                   duplicate-pooling trap the figure ledger documents).
#                   => S7 cannot clear its own p<0.05 clause on GPQA-Diamond.
#
#   SuperGPQA-hard  b=137 c=61 over n=1,842 -> 7.44%/3.31% per item.
#                   At n=270 the expected contingency is b=20 c=9, p=0.0307.
#                   Reaching p<0.05 needs n>=210. => adequately powered.
#
# So the home benchmark for S7 must be SuperGPQA-hard. Verify with
# minimum_pooled_n_for_audit_effect() rather than trusting this comment.
# ---------------------------------------------------------------------------


def minimum_pooled_n_for_audit_effect(
    selector: str, benchmark: str, max_n: int = 5000
) -> "int | None":
    """Smallest pooled n at which the S1 audit's own effect clears SHIP_ALPHA.

    Holds b and c at the audit-measured per-item rates and walks n upward.
    Returns None if no n <= max_n suffices. This is what makes the power claim
    in the block above checkable instead of asserted.
    """
    bc = ORIGINAL_AUDIT_BC.get((selector, benchmark))
    n_audit = ORIGINAL_AUDIT_N.get(benchmark)
    if bc is None or not n_audit:
        return None
    b_rate, c_rate = bc[0] / n_audit, bc[1] / n_audit
    for n in range(10, max_n + 1, 10):
        b, c = round(b_rate * n), round(c_rate * n)
        if b - c > 0 and mcnemar_exact_one_sided(b, c) < SHIP_ALPHA:
            return n
    return None

# ---------------------------------------------------------------------------
# S7 ship bar (docs/experiment-spec-book.md section 3 / the task spec this
# file implements, verbatim): on the HOME benchmark pooled over 3 held-out
# seeds -- net >= +5 items AND discordant b+c >= 12 AND exact McNemar
# p < 0.05 AND the point estimate within 50% of the original audit's effect
# size AND non-negative on every individual seed. Anything less is
# DO NOT SHIP, with the specific failing reason(s) stated.
# ---------------------------------------------------------------------------
SHIP_MIN_NET = 5
SHIP_MIN_DISCORDANT = 12
SHIP_ALPHA = 0.05
SHIP_EFFECT_BAND = 0.5  # "within 50%" -> observed net in [0.5x, 1.5x] of the original net

# ---------------------------------------------------------------------------
# Burned seeds -- never usable for an S7 SHIP verdict. Categorized (not one
# flat list) because "why is this seed burned" differs by category, and any
# seed added to one of these categories in the future should be added here
# with the SAME reasoning, not just appended blindly. Cross-checked against
# every benchmark/results/*.jsonl filename in the repo (see
# original_audit_seeds below) -- these 12 are exactly the seeds that scan
# finds, confirming this static list and the dynamic one currently agree.
# ---------------------------------------------------------------------------
BURNED_SEEDS = frozenset({
    # The project's default/most-reused seed (30+ committed result files):
    # every early lever-tuning pass, the historical five-solver run, the
    # MOO eval, every *_pilot_seed42 file, and the single largest
    # contributor to the S1 audit's 5,451-row pool. Anything scored
    # against seed 42 is fitted to what this project has already looked
    # at, by construction.
    42,
    # "Fresh" replicate seeds paired with 42 across baseline/control/
    # flagship_panel arms (lever_baseline_seed7/123, lever_control_seed7,
    # lever_flagship_panel_supergpqa_seed7/123, qwen38_baseline_seed123,
    # ...). Part of the S1 audit's own source pool -- scoring a selector
    # against them is circular, not held-out.
    7, 123,
    # chem_flagship_gate lever seeds (Organic Chemistry, GPQA). The
    # subject-forced-escalation lever family was derived by looking at
    # seed 42's errors, then validated at these "fresh" seeds -- burned
    # by that validation use, not free for a second, unrelated purpose.
    555, 777, 888,
    # chem_thinking_gate lever seeds (Organic Chemistry, GPQA); 314
    # doubles as a lever_baseline_gpqa seed.
    217, 314, 471,
    # SuperGPQA-hard control / rag_presolve / rag_thinking_gate seeds --
    # part of the S1 audit's SuperGPQA-hard source pool, its second-
    # largest contributor after GPQA-Diamond.
    271, 606, 838,
})


def original_audit_seeds(results_dir: "str | Path" = RESULTS_DIR) -> frozenset[int]:
    """Every seed embedded in a benchmark/results/*.jsonl FILENAME -- i.e.
    every seed the S1 audit (benchmark/audit_selectors.py, which globs the
    same directory for *.jsonl) could have scored a selector against --
    excluding pool_* files (S7's own fresh output; a pool doesn't burn
    itself the moment it's written). Dynamic, not hardcoded, so a result
    file that lands later still gets caught; BURNED_SEEDS above is the
    belt-and-suspenders static list that keeps working even if this scan
    ever misses a file (different naming convention, moved directory,
    etc.). Takes a `results_dir` override so tests can point this at a
    throwaway fixture directory instead of depending on the live,
    ever-changing benchmark/results/ contents."""
    seeds = set()
    for path in Path(results_dir).glob("*.jsonl"):
        if path.name.startswith(POOL_FILENAME_PREFIX):
            continue
        m = re.search(r"seed(\d+)", path.name)
        if m:
            seeds.add(int(m.group(1)))
    return frozenset(seeds)


def assert_seeds_not_burned(seeds, results_dir: "str | Path" = RESULTS_DIR) -> None:
    """Raises ValueError if ANY of `seeds` is in the static BURNED_SEEDS
    list OR in the dynamic original_audit_seeds() scan. Called ONLY on the
    --ship-gate path (see main() below) -- plain scoring/debugging on a
    burned seed is still legitimate (e.g. sanity-checking run_pool.py
    itself) and stays allowed; only a SHIP verdict is guarded."""
    burned = set(BURNED_SEEDS) | set(original_audit_seeds(results_dir))
    offending = sorted(set(seeds) & burned)
    if offending:
        raise ValueError(
            f"refusing to score a SHIP-GATE verdict on seed(s) {offending} -- burned "
            f"(already used in selection/tuning, or present in the S1 selector audit's "
            f"own source pools). S7 exists specifically to test a selector on seeds it "
            f"was never fitted to; scoring the ship gate on a burned seed would silently "
            f"reproduce the exact fitting failure this file exists to catch. Regenerate "
            f"the pool at a fresh seed with benchmark/run_pool.py instead."
        )


# ---------------------------------------------------------------------------
# Pool loading + per-row selector scoring
# ---------------------------------------------------------------------------


def load_pool(path: "str | Path") -> list[dict]:
    """Reads a run_pool.py-written pool JSONL: one row per item, each
    carrying `item` (question_id/choices/correct_letter) and an ordered
    `samples` list."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _row_gold(row: dict) -> str:
    return str(row["item"]["correct_letter"]).strip().upper()


def _row_samples_sorted(row: dict) -> list[dict]:
    return sorted(row["samples"], key=lambda s: s["sample_index"])


def _prefix_letters_confidences_reasoning(row: dict, k: int) -> tuple[list[str], list[float], list[int]]:
    """The first k samples (by sample_index) -- the nested-prefix subsample
    that makes k=1..K derivable offline from one frozen pool, exactly like
    analyze_panel_scaling.py's prefix_votes() does for the panel-size
    curve."""
    samples = _row_samples_sorted(row)
    if k > len(samples):
        raise ValueError(
            f"requested prefix k={k} exceeds pool size {len(samples)} for "
            f"{row.get('question_id')!r}"
        )
    prefix = samples[:k]
    letters = [str(s.get("letter") or "").strip().upper() for s in prefix]
    confidences = [float(s.get("confidence") or 0.0) for s in prefix]
    reasoning_lens = [len(s.get("reasoning") or "") for s in prefix]
    return letters, confidences, reasoning_lens


def score_row_at_k(row: dict, k: int) -> dict:
    """Every selector's verdict on ONE item's first-k samples, resolved
    against that row's OWN gold letter (never joined across rows on letter
    identity -- same discipline audit_selectors.py's module docstring
    pins down, since a shuffled-choices loader can map a different choice
    string to the same letter in a different row)."""
    letters, confidences, reasoning_lens = _prefix_letters_confidences_reasoning(row, k)
    gold = _row_gold(row)
    plur = sel_plurality(letters)
    confw = sel_confidence_weighted(letters, confidences)
    maxc = sel_max_single_confidence(letters, confidences)
    longr = sel_longest_reasoning(letters, reasoning_lens)
    return {
        "question_id": row.get("question_id"),
        "gold": gold,
        "plurality": plur == gold,
        "confidence_weighted": confw == gold,
        "max_single_confidence": maxc == gold,
        "longest_reasoning": longr == gold,
        "oracle": gold in letters,
    }


def score_pool(rows: list[dict], k: int) -> dict:
    """Aggregates score_row_at_k over every row at a fixed k. Mirrors
    audit_selectors.py's aggregate() output shape (plurality_accuracy /
    oracle_coverage top-level, per-alt-selector accuracy in `selectors`)
    plus a retained `per_item` dict, which audit_selectors.py's own
    aggregate() discards but this file needs for the McNemar pairing
    below."""
    n = len(rows)
    if n == 0:
        raise ValueError("empty pool -- nothing to score")
    per_item = {row["question_id"]: score_row_at_k(row, k) for row in rows}
    selectors = {
        name: sum(rec[name] for rec in per_item.values()) / n
        for name in ("confidence_weighted", "max_single_confidence", "longest_reasoning")
    }
    return {
        "n_items": n,
        "k": k,
        "plurality_accuracy": sum(rec["plurality"] for rec in per_item.values()) / n,
        "oracle_coverage": sum(rec["oracle"] for rec in per_item.values()) / n,
        "selectors": selectors,
        "per_item": per_item,
    }


# ---------------------------------------------------------------------------
# McNemar vs plurality (S3), reusing analyze_panel_scaling's exact p-value
# function rather than writing a second one.
# ---------------------------------------------------------------------------


def discordant_vs_plurality(per_item: dict, selector_name: str) -> tuple[int, int]:
    """b = items the selector gets right that plurality gets wrong (a
    gain); c = the reverse (a loss) -- standard McNemar contingency
    notation, matching audit_selectors.py's b_cell/c_cell exactly."""
    b = c = 0
    for rec in per_item.values():
        sel_ok, plur_ok = rec[selector_name], rec["plurality"]
        if sel_ok and not plur_ok:
            b += 1
        elif plur_ok and not sel_ok:
            c += 1
    return b, c


def selector_report(per_item: dict, selector_name: str) -> dict:
    b, c = discordant_vs_plurality(per_item, selector_name)
    return {
        "selector": selector_name,
        "b": b,
        "c": c,
        "net": b - c,
        "n_discordant": b + c,
        "p": mcnemar_exact_one_sided(b, c),
    }


# ---------------------------------------------------------------------------
# S6: pool-size curve (free once the pool exists -- prefix subsampling).
# ---------------------------------------------------------------------------


def pool_size_curve(rows: list[dict], max_k: "int | None" = None) -> dict:
    """accuracy@k (every selector) and oracle coverage@k, for k=1..max_k
    (default: the smallest sample count across all rows -- prefix
    subsampling can't go past a row's own logged sample count)."""
    if max_k is None:
        max_k = min(len(row["samples"]) for row in rows)
    return {k: score_pool(rows, k) for k in range(1, max_k + 1)}


def oracle_gap(scored: dict, selector_name: str = "plurality") -> dict:
    """oracle coverage minus a selector's accuracy, at the k `scored` was
    computed at -- the free-once-the-pool-exists number the S2/S3 ROI
    decision (docs/experiment-spec-book.md section 3) is sized by."""
    acc = scored["plurality_accuracy"] if selector_name == "plurality" else scored["selectors"][selector_name]
    gap_pp = (scored["oracle_coverage"] - acc) * 100
    gap_items = round((scored["oracle_coverage"] - acc) * scored["n_items"])
    return {"selector": selector_name, "gap_pp": gap_pp, "gap_items": gap_items}


# ---------------------------------------------------------------------------
# S7: the ship-gate verdict.
# ---------------------------------------------------------------------------


def ship_gate_verdict(selector: str, benchmark: str, per_seed_reports: list[dict]) -> tuple[str, list[str], dict]:
    """per_seed_reports: one dict per held-out seed, each {"seed": int,
    "b": int, "c": int} from selector_report() at that seed's pool.
    Pools across seeds by SUMMING b/c (this repo's established "pooled
    McNemar" convention -- e.g. docs/experiment-spec-book.md's "net >= +3
    at 2 of 3 seeds with the pooled McNemar (n=270)" -- adding independent
    per-seed contingency tables, never re-joining items across seeds on
    question_id/letter identity, since different seeds draw different
    shuffled choices).

    Returns (verdict, reasons, stats): verdict is "SHIP" iff every clause
    of the pre-registered S7 bar passes, else "DO NOT SHIP" with `reasons`
    listing every clause that failed (not just the first)."""
    reasons: list[str] = []
    pooled_b = sum(r["b"] for r in per_seed_reports)
    pooled_c = sum(r["c"] for r in per_seed_reports)
    pooled_net = pooled_b - pooled_c
    pooled_discordant = pooled_b + pooled_c
    pooled_p = mcnemar_exact_one_sided(pooled_b, pooled_c)

    if pooled_net < SHIP_MIN_NET:
        reasons.append(f"pooled net={pooled_net:+d} < required +{SHIP_MIN_NET}")
    if pooled_discordant < SHIP_MIN_DISCORDANT:
        reasons.append(f"pooled discordant b+c={pooled_discordant} < required {SHIP_MIN_DISCORDANT}")
    if not (pooled_p < SHIP_ALPHA):
        reasons.append(f"pooled exact McNemar p={pooled_p:.4f} is not < {SHIP_ALPHA}")

    original_net = ORIGINAL_AUDIT_NET.get((selector, benchmark))
    original_n = ORIGINAL_AUDIT_N.get(benchmark)
    pooled_n = sum(r.get("n_items") or 0 for r in per_seed_reports)
    observed_rate = (pooled_net / pooled_n) if pooled_n else None
    original_rate = (original_net / original_n) if (original_net is not None and original_n) else None

    if original_net is None or original_n is None:
        reasons.append(
            f"no original-audit reference for (selector={selector!r}, "
            f"benchmark={benchmark!r}) -- cannot evaluate the within-50% replication clause"
        )
    elif not pooled_n:
        # Fail CLOSED. Without denominators the clause can only be evaluated in
        # the broken count-vs-count form, so refuse to evaluate it at all
        # rather than silently reproducing the units bug.
        reasons.append(
            "per-seed reports carry no n_items, so the within-50% replication clause "
            "cannot be evaluated as a rate -- refusing to compare a ~270-item net "
            f"against the S1 audit's net={original_net:+d} over n={original_n}"
        )
    else:
        lo, hi = (1 - SHIP_EFFECT_BAND) * original_rate, (1 + SHIP_EFFECT_BAND) * original_rate
        if not (lo <= observed_rate <= hi):
            reasons.append(
                f"observed net rate={observed_rate * 100:+.4f}% ({pooled_net:+d} over "
                f"n={pooled_n}) is outside 50% of the original S1 audit's rate="
                f"{original_rate * 100:+.4f}% ({original_net:+d} over n={original_n}) "
                f"for {selector} on {benchmark} "
                f"(band=[{lo * 100:+.4f}%, {hi * 100:+.4f}%])"
            )

    negative_seeds = [r["seed"] for r in per_seed_reports if (r["b"] - r["c"]) < 0]
    if negative_seeds:
        reasons.append(
            f"negative net on seed(s) {negative_seeds} -- every individual seed must be non-negative"
        )

    verdict = "SHIP" if not reasons else "DO NOT SHIP"
    stats = {
        "pooled_b": pooled_b, "pooled_c": pooled_c, "pooled_net": pooled_net,
        "pooled_discordant": pooled_discordant, "pooled_p": pooled_p,
        "original_net": original_net, "original_n": original_n,
        "pooled_n": pooled_n,
        "observed_rate_pp": (observed_rate * 100) if observed_rate is not None else None,
        "original_rate_pp": (original_rate * 100) if original_rate is not None else None,
        "distinct_seeds": len({r["seed"] for r in per_seed_reports}),
    }
    return verdict, reasons, stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_dataset_and_seeds(pools_data: list[tuple[Path, list[dict]]]) -> tuple[str, list[int]]:
    """Every pool file must log exactly one `dataset` and one `seed` across
    all its rows (run_pool.py always writes it that way), and --ship-gate
    requires every pool to be the SAME dataset -- the ship bar is defined
    on ONE benchmark pooled over seeds, never pooled across benchmarks."""
    datasets = set()
    seeds = []
    # The caller only checks that THREE pool paths were supplied, not that they
    # are three DIFFERENT runs. Passing the same file three times used to sum
    # its b/c three times: one honest seed-411 pool (b=13, c=0) became
    # b=39/c=0/p=0.0000 and printed SHIP with exit code 0. That is precisely
    # the single-seed overfitting S7 exists to prevent, so resolve duplicates
    # here where both the paths and the seeds are visible.
    resolved_paths = [Path(p).resolve() for p, _ in pools_data]
    if len(set(resolved_paths)) != len(resolved_paths):
        raise ValueError(
            "--ship-gate was given the same pool file more than once "
            f"(resolved paths: {[str(p) for p in resolved_paths]}). Three DISTINCT "
            "held-out pools are required; repeating one multiplies its discordant "
            "pairs and fabricates significance."
        )
    for path, rows in pools_data:
        if not rows:
            raise ValueError(f"{path}: empty pool")
        row_datasets = {r.get("dataset") for r in rows}
        row_seeds = {r.get("seed") for r in rows}
        if len(row_datasets) != 1 or len(row_seeds) != 1:
            raise ValueError(
                f"{path}: pool file must log exactly one dataset and one seed across all "
                f"rows (saw datasets={row_datasets}, seeds={row_seeds})"
            )
        datasets.add(next(iter(row_datasets)))
        seeds.append(next(iter(row_seeds)))
    if len(datasets) != 1:
        raise ValueError(
            f"--ship-gate requires every pool to be the SAME dataset (saw {sorted(datasets)}) "
            f"-- pooling across benchmarks is not the pre-registered design"
        )
    # Distinct paths are not sufficient: a copy, a symlink, or a re-run written
    # to a new filename all carry the same logged seed. The seed is what makes
    # the pools independent, so it is what must be unique.
    if len(set(seeds)) != len(seeds):
        raise ValueError(
            f"--ship-gate requires 3 DISTINCT held-out seeds, saw {seeds}. Pooling "
            "the same seed more than once inflates the discordant count without "
            "adding evidence."
        )
    return next(iter(datasets)), seeds


def main(pool_paths: list[str], selector: str, k: "int | None", ship_gate: bool, out_path: "str | None") -> int:
    pools_data = [(Path(p), load_pool(p)) for p in pool_paths]

    print("=" * 100)
    print("POOL INVENTORY")
    print("=" * 100)
    for path, rows in pools_data:
        print(f"  {path}: {len(rows)} items")

    per_pool_scored = []
    for path, rows in pools_data:
        this_k = k or min(len(r["samples"]) for r in rows)
        scored = score_pool(rows, this_k)
        per_pool_scored.append((path, rows, scored))
        print()
        print(
            f"[{path.name}]  n={scored['n_items']}  k={this_k}  "
            f"plurality_acc={scored['plurality_accuracy'] * 100:.2f}%  "
            f"oracle_coverage={scored['oracle_coverage'] * 100:.2f}%"
        )
        for name in ("confidence_weighted", "max_single_confidence", "longest_reasoning"):
            rep = selector_report(scored["per_item"], name)
            print(
                f"    {name:24s} acc={scored['selectors'][name] * 100:6.2f}%  "
                f"b={rep['b']:3d} c={rep['c']:3d} net={rep['net']:+4d} "
                f"n_disc={rep['n_discordant']:3d} p={rep['p']:.4f}"
            )
        for name in ("plurality",) + SHIPPABLE_SELECTORS:
            gap = oracle_gap(scored, name)
            print(f"    oracle vs {name}: {gap['gap_pp']:+.2f}pp ({gap['gap_items']:+d} items)")

        curve = pool_size_curve(rows)
        curve_str = ", ".join(f"k={kk}:{v['plurality_accuracy'] * 100:.1f}%" for kk, v in curve.items())
        print(f"    pool-size curve (plurality accuracy@k): {curve_str}")

    verdict_payload = None
    if ship_gate:
        if len(pool_paths) != 3:
            raise ValueError(
                f"--ship-gate requires EXACTLY 3 pool files (one per held-out seed), got "
                f"{len(pool_paths)}"
            )
        dataset, seeds = _resolve_dataset_and_seeds(pools_data)
        assert_seeds_not_burned(seeds)
        benchmark = DATASET_TO_BENCHMARK.get(dataset)
        if benchmark is None:
            raise ValueError(
                f"--ship-gate has no benchmark mapping for dataset={dataset!r} "
                f"(known: {sorted(DATASET_TO_BENCHMARK)})"
            )

        per_seed_reports = []
        for (path, rows, scored), seed in zip(per_pool_scored, seeds):
            rep = selector_report(scored["per_item"], selector)
            # n_items is REQUIRED by the within-50% replication clause, which
            # compares rates rather than raw counts.
            per_seed_reports.append(
                {"seed": seed, "b": rep["b"], "c": rep["c"], "n_items": scored["n_items"]}
            )

        verdict, reasons, stats = ship_gate_verdict(selector, benchmark, per_seed_reports)
        print()
        print("=" * 100)
        print(f"S7 SHIP-GATE VERDICT -- selector={selector} benchmark={benchmark} seeds={seeds}")
        print("=" * 100)
        print(
            f"pooled: b={stats['pooled_b']} c={stats['pooled_c']} net={stats['pooled_net']:+d} "
            f"discordant={stats['pooled_discordant']} p={stats['pooled_p']:.4f} "
            f"n={stats['pooled_n']}"
        )
        if stats.get("observed_rate_pp") is not None and stats.get("original_rate_pp") is not None:
            print(
                f"        replication: observed rate={stats['observed_rate_pp']:+.4f}% vs "
                f"S1 audit rate={stats['original_rate_pp']:+.4f}% "
                f"(net={stats['original_net']:+d} over n={stats['original_n']})"
            )
        for r in per_seed_reports:
            print(f"  seed {r['seed']}: b={r['b']} c={r['c']} net={r['b'] - r['c']:+d}")
        print()
        if verdict == "SHIP":
            print(">>> SHIP")
        else:
            print(">>> DO NOT SHIP -- " + "; ".join(reasons))
        verdict_payload = {
            "verdict": verdict, "reasons": reasons, **stats,
            "selector": selector, "benchmark": benchmark, "seeds": seeds,
        }

    if out_path:
        payload = {"pools": [str(p) for p, _ in pools_data], "ship_gate": verdict_payload}
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {out_path}")

    if ship_gate:
        return 0 if verdict_payload["verdict"] == "SHIP" else 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pools", nargs="+", required=True, help="one or more pool JSONL files written by benchmark/run_pool.py")
    parser.add_argument("--selector", choices=SHIPPABLE_SELECTORS, default="max_single_confidence")
    parser.add_argument("--k", type=int, default=None, help="cap the prefix length scored (default: each pool's own full size)")
    parser.add_argument("--ship-gate", action="store_true", help="require exactly 3 pool files (one benchmark), apply the burned-seed guard, and print the S7 SHIP/DO NOT SHIP verdict")
    parser.add_argument("--out", type=str, default=None, help="optional path to write the full report as JSON")
    args = parser.parse_args()
    raise SystemExit(main(args.pools, args.selector, args.k, args.ship_gate, args.out))
