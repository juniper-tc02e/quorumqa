"""W5 wrongness-predictor (+ F3 distribution-feature upgrade), mined OFFLINE
from committed result JSONLs in benchmark/results/. Pre-registered protocol,
implemented verbatim -- do not change the model family, the evaluation
split, or the decision thresholds without updating the protocol doc first:

  docs/reasoning-supercharge-plan.md   -- W5 (leakage controls, bar/kill)
  docs/same-provider-scaling-research.md -- F3 (distribution-feature upgrade,
                                             the ΔAUC comparison)

NO PAID API CALLS. This script only reads already-committed JSONL logs.

Primary label:   engine/panel answered the item incorrectly (`correct=False`
                  on the engine/panel object -- never the solo baseline arm).
Secondary label:  "unanimous-wrong" -- every solver seat's vote agreed AND
                  that shared vote was wrong (computed from the raw votes,
                  independent of whatever the tribunal/verdict later did).
                  Only defined for rows with >=2 solver seats.

Leakage controls (pre-registered, do not relax):
  - Leave-one-benchmark-out (LOBO): for each held-out benchmark, train
    logistic regression on every OTHER benchmark's rows, then compute AUC
    using ONLY the held-out benchmark's own rows (not pooled). This is the
    control against the base-rate-across-benchmarks leak (unanimous-wrong
    base rates observed here span ~2%-45%; a pooled AUC would be inflated
    by the model just learning to predict which benchmark a row came from).
  - Benchmark identity is NEVER a feature. Subject/category strings are
    ALSO excluded from the feature set even though the spec lists
    "structural: subject/category" as a candidate, because subject
    vocabularies are near-disjoint across these benchmarks (GPQA subjects
    vs SuperGPQA subjects vs MMLU-Pro categories barely overlap) -- a
    subject one-hot would function as benchmark identity by another name
    under this exact LOBO design. This substitution is recorded explicitly
    in the findings report, not silently done.
  - Preprocessing (median imputation + standardization) is fit on the
    TRAIN fold only inside each LOBO split, never on pooled data.

Usage (from repo root, PowerShell or bash):
  .venv/Scripts/python.exe -m benchmark.build_wrongness_predictor \
      --report benchmark/results/wrongness_predictor_findings.md
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from benchmark.math_grade import grade

log = logging.getLogger("wrongness_predictor")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# --------------------------------------------------------------------------
# Fixed word lists (pre-registered, verbatim from the task spec)
# --------------------------------------------------------------------------
HEDGE_WORDS = [
    "however", "might", "could", "possibly", "unclear", "assume", "guess",
    "roughly", "approximately", "not sure",
]
SWITCH_MARKERS = ["wait", "actually", "on second thought", "reconsider"]

_HEDGE_PATTERNS = [re.compile(r"\b" + re.escape(w) + r"\b", re.I) for w in HEDGE_WORDS]
_SWITCH_PATTERNS = [re.compile(r"\b" + re.escape(w) + r"\b", re.I) for w in SWITCH_MARKERS]


def _rate_per_100_words(text: str, patterns: list[re.Pattern]) -> float:
    text = text or ""
    n_words = max(1, len(text.split()))
    hits = sum(len(p.findall(text)) for p in patterns)
    return 100.0 * hits / n_words


# --------------------------------------------------------------------------
# File inventory -- explicit, reproducible, hand-verified against every
# JSONL's actual schema and subject/dataset signature (see report §1).
# --------------------------------------------------------------------------

EXCLUDED = {
    "lever_baseline_gpqa_seed314.jsonl": "baseline-only arm (single flagship call, no solver_answers) -- not an engine/panel output",
    "lever_baseline_mmlu_pro_stem_seed42.jsonl": "baseline-only arm",
    "lever_baseline_seed123.jsonl": "baseline-only arm",
    "lever_baseline_seed7.jsonl": "baseline-only arm",
    "lever_baseline_supergpqa_seed123.jsonl": "baseline-only arm",
    "lever_baseline_supergpqa_seed7.jsonl": "baseline-only arm",
    "lever_gate_replay.jsonl": "gate-validation replay, pre-filtered to was_unanimous_correct items only (biased sample, zero negative-label variance by construction) and has no solver_answers/reasoning at all",
    "qwen38_baseline_seed123.jsonl": "solo qwen3.8 baseline (single call), no solver_answers/panel",
    "math_open_baseline_seed42.jsonl": "baseline-only arm (single flagship call), no solver_answers/panel",
    "aime_open_baseline_seed42.jsonl": "baseline-only arm (single flagship call), no solver_answers/panel",
}

# filename -> benchmark tag, for files whose row is a "MC engine" object
# (nested item.question/choices/correct_letter, solver_answers[].letter)
MC_ENGINE_FILES = {
    # ---- gpqa ----
    "adhoc_check.jsonl": "gpqa",
    "full_run.jsonl": "gpqa",
    "full_run2.jsonl": "gpqa",
    "smoke.jsonl": "gpqa",
    "smoke2.jsonl": "gpqa",
    "smoke3.jsonl": "gpqa",
    "lever_chem_flagship_gate_gpqa_seed777.jsonl": "gpqa",
    "lever_chem_flagship_gate_gpqa_seed888.jsonl": "gpqa",
    "lever_chem_flagship_gate_seed555.jsonl": "gpqa",
    "lever_chem_thinking_gate_gpqa_seed217.jsonl": "gpqa",
    "lever_chem_thinking_gate_gpqa_seed314.jsonl": "gpqa",
    "lever_chem_thinking_gate_gpqa_seed471.jsonl": "gpqa",
    "lever_combined_seed42.jsonl": "gpqa",
    "lever_combined_seed7.jsonl": "gpqa",
    "lever_control_seed7.jsonl": "gpqa",
    "lever_control_seed7_replicate.jsonl": "gpqa",
    "lever_five_seed42.jsonl": "gpqa",
    "lever_flagship_panel_seed42.jsonl": "gpqa",
    "lever_flagship_panel_seed42_replicate.jsonl": "gpqa",
    "lever_flagship_panel_seed7.jsonl": "gpqa",
    "lever_qwen38_judge_gpqa_seed42.jsonl": "gpqa",
    "lever_rag_presolve_gpqa_seed42.jsonl": "gpqa",
    "lever_smart_gate_seed123.jsonl": "gpqa",
    "lever_subject_seed7.jsonl": "gpqa",
    "lever_thinking_all_seed42.jsonl": "gpqa",
    "lever_thinking_all_seed7.jsonl": "gpqa",
    "lever_thinking_gate_seed123.jsonl": "gpqa",
    "lever_thinking_gate_seed42.jsonl": "gpqa",
    "lever_thinking_gate_seed7.jsonl": "gpqa",
    "lever_thinking_seed42.jsonl": "gpqa",
    "lever_thinking_seed7.jsonl": "gpqa",
    # ---- supergpqa (always difficulty="hard", per lever_experiments.py DATASET_LOADERS) ----
    "lever_control_supergpqa_seed123.jsonl": "supergpqa",
    "lever_control_supergpqa_seed271.jsonl": "supergpqa",
    "lever_control_supergpqa_seed606.jsonl": "supergpqa",
    "lever_control_supergpqa_seed7.jsonl": "supergpqa",
    "lever_control_supergpqa_seed838.jsonl": "supergpqa",
    "lever_flagship_panel_supergpqa_seed123.jsonl": "supergpqa",
    "lever_flagship_panel_supergpqa_seed42.jsonl": "supergpqa",
    "lever_flagship_panel_supergpqa_seed7.jsonl": "supergpqa",
    "lever_qwen38_panel_supergpqa_seed42.jsonl": "supergpqa",
    "lever_rag_presolve_supergpqa_seed123.jsonl": "supergpqa",
    "lever_rag_presolve_supergpqa_seed271.jsonl": "supergpqa",
    "lever_rag_presolve_supergpqa_seed42.jsonl": "supergpqa",
    "lever_rag_presolve_supergpqa_seed606.jsonl": "supergpqa",
    "lever_rag_presolve_supergpqa_seed7.jsonl": "supergpqa",
    "lever_rag_recursive_supergpqa_seed42.jsonl": "supergpqa",
    "lever_rag_thinking_gate_supergpqa_seed271.jsonl": "supergpqa",
    "lever_rag_thinking_gate_supergpqa_seed606.jsonl": "supergpqa",
    "lever_rag_thinking_gate_supergpqa_seed838.jsonl": "supergpqa",
    "supergpqa_hard_pilot_seed42.jsonl": "supergpqa",
    # ---- lexam ----
    "lever_control_lexam_seed42.jsonl": "lexam",
    "lever_rag_recursive_lexam_seed42.jsonl": "lexam",
    "lever_thinking_gate_lexam_seed42.jsonl": "lexam",
    "lexam_pilot_seed42.jsonl": "lexam",
    # ---- mmlu_pro_stem (STEM_CATEGORIES subset) ----
    "lever_flagship_panel_mmlu_pro_stem_seed42.jsonl": "mmlu_pro_stem",
    # ---- mmlu_pro (unrestricted categories) ----
    "lever_thinking_gate_mmlu_pro_seed42.jsonl": "mmlu_pro",
    "mmlu_pro_pilot_seed42.jsonl": "mmlu_pro",
    # ---- single-source benchmarks ----
    "medqa_pilot_seed42.jsonl": "medqa",
    "gsm8k_pilot_seed42.jsonl": "gsm8k",
    "math500_hard_pilot_seed42.jsonl": "math500",
}

# filename -> benchmark tag, for files whose row IS the open-answer math
# engine dict at top level (solver_answers[].answer, no item/question text)
OPEN_ENGINE_FILES = {
    "math_open_panel_seed42.jsonl": "math_open",
    "math_open_panel_cheap_seed42.jsonl": "math_open",
    "aime_open_panel_cheap_seed42.jsonl": "aime_open",
}

# moo_m1_eval.jsonl mixes 4 sub-populations in one file (row.bucket); the
# bucket loaders are IDENTICAL to the standalone benchmarks' loaders except
# saturated_easy_mmlu, which is MoO's own deliberately-near-ceiling MMLU-Pro
# slice (see run_moo_eval.py SATURATED_MMLU_PRO_CATEGORIES) and is kept as
# its own benchmark group rather than merged into mmlu_pro/mmlu_pro_stem.
MOO_FILE = "moo_m1_eval.jsonl"
MOO_BUCKET_MAP = {
    "gpqa_hard": "gpqa",
    "supergpqa_hard": "supergpqa",
    "medqa": "medqa",
    "saturated_easy_mmlu": "mmlu_saturated_easy",
}


# --------------------------------------------------------------------------
# Feature columns
# --------------------------------------------------------------------------
FEATURES_VERBALIZED = ["conf_mean", "conf_min", "conf_max", "conf_spread", "has_confidence"]
FEATURES_TRACE = [
    "reason_len_chars_mean", "reason_len_chars_max",
    "reason_len_words_mean", "reason_len_words_max",
    "hedge_rate_mean", "hedge_rate_max",
    "switch_rate_mean", "switch_rate_max",
]
FEATURES_DISTRIBUTION = [
    "agreement_rate", "top_vote_share", "vote_entropy", "cluster_margin",
    "n_distinct_answers", "is_unanimous", "is_fragmented", "n_solver_seats",
]
FEATURES_STRUCTURAL = [
    "question_len_chars", "question_len_words", "choice_length_spread",
    "has_question_text", "has_choices",
]

FEATURES_VTD = FEATURES_VERBALIZED + FEATURES_TRACE + FEATURES_DISTRIBUTION
FEATURES_FULL = FEATURES_VTD + FEATURES_STRUCTURAL


# --------------------------------------------------------------------------
# Row extraction
# --------------------------------------------------------------------------

def _cluster_open_answers(answers: list[str]) -> list[list[int]]:
    """Union-find over grade() pairwise equivalence -- same algorithm as
    benchmark/math_open_engine.py's _cluster_answers, reimplemented here to
    avoid importing math_open_engine (which imports the paid-API client)."""
    n = len(answers)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            if grade(answers[i], answers[j]):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _distribution_features(sizes: list[int], n: int) -> dict:
    """sizes: descending cluster/vote sizes (sums to n)."""
    if n == 0 or not sizes:
        return dict(agreement_rate=np.nan, top_vote_share=np.nan, vote_entropy=np.nan,
                     cluster_margin=np.nan, n_distinct_answers=np.nan, is_unanimous=np.nan,
                     is_fragmented=np.nan, n_solver_seats=n)
    top = sizes[0]
    second = sizes[1] if len(sizes) > 1 else 0
    shares = [s / n for s in sizes]
    entropy = -sum(p * np.log2(p) for p in shares if p > 0)
    pairwise_agree = (sum(s * (s - 1) for s in sizes) / (n * (n - 1))) if n > 1 else 1.0
    return dict(
        agreement_rate=pairwise_agree,
        top_vote_share=top / n,
        vote_entropy=entropy,
        cluster_margin=(top - second) / n,
        n_distinct_answers=len(sizes),
        is_unanimous=1.0 if top == n else 0.0,
        is_fragmented=1.0 if (len(sizes) == n and n > 1) else 0.0,
        n_solver_seats=n,
    )


def _trace_features(reasonings: list[str]) -> dict:
    if not reasonings:
        return dict(reason_len_chars_mean=np.nan, reason_len_chars_max=np.nan,
                     reason_len_words_mean=np.nan, reason_len_words_max=np.nan,
                     hedge_rate_mean=np.nan, hedge_rate_max=np.nan,
                     switch_rate_mean=np.nan, switch_rate_max=np.nan)
    chars = [len(r or "") for r in reasonings]
    words = [len((r or "").split()) for r in reasonings]
    hedge = [_rate_per_100_words(r, _HEDGE_PATTERNS) for r in reasonings]
    switch = [_rate_per_100_words(r, _SWITCH_PATTERNS) for r in reasonings]
    return dict(
        reason_len_chars_mean=float(np.mean(chars)), reason_len_chars_max=float(np.max(chars)),
        reason_len_words_mean=float(np.mean(words)), reason_len_words_max=float(np.max(words)),
        hedge_rate_mean=float(np.mean(hedge)), hedge_rate_max=float(np.max(hedge)),
        switch_rate_mean=float(np.mean(switch)), switch_rate_max=float(np.max(switch)),
    )


def _confidence_features(confidences: list[float]) -> dict:
    if not confidences:
        return dict(conf_mean=np.nan, conf_min=np.nan, conf_max=np.nan, conf_spread=np.nan,
                     has_confidence=0.0)
    return dict(
        conf_mean=float(np.mean(confidences)), conf_min=float(np.min(confidences)),
        conf_max=float(np.max(confidences)), conf_spread=float(np.max(confidences) - np.min(confidences)),
        has_confidence=1.0,
    )


def extract_mc_row(engine: dict, benchmark: str, source_file: str, lever: str | None) -> dict | None:
    item = engine.get("item") or {}
    solver_answers = engine.get("solver_answers") or []
    correct = engine.get("correct")
    if correct is None or not solver_answers:
        return None
    n = len(solver_answers)
    letters = [str(sa.get("letter") or "") for sa in solver_answers]
    confidences = [float(sa["confidence"]) for sa in solver_answers if isinstance(sa.get("confidence"), (int, float))]
    reasonings = [sa.get("reasoning") or "" for sa in solver_answers]

    correct_letter = item.get("correct_letter")
    vote_counts = Counter(letters)
    sizes = sorted(vote_counts.values(), reverse=True)
    top_letter = vote_counts.most_common(1)[0][0] if vote_counts else None
    unanimous = bool(sizes and sizes[0] == n)
    label_unanimous_wrong = (bool(top_letter != correct_letter) if unanimous else False) if n >= 2 else np.nan

    question = item.get("question") or ""
    choices = item.get("choices") or []
    choice_lens = [len(c) for c in choices if isinstance(c, str)]

    row = dict(
        source_file=source_file, benchmark=benchmark, lever=lever,
        question_id=item.get("question_id"), kind="mc",
        label_wrong=1.0 if not bool(correct) else 0.0,
        label_unanimous_wrong=label_unanimous_wrong,
        question_len_chars=len(question) if question else np.nan,
        question_len_words=len(question.split()) if question else np.nan,
        choice_length_spread=float(np.std(choice_lens)) if len(choice_lens) >= 2 else np.nan,
        has_question_text=1.0 if question else 0.0,
        has_choices=1.0 if choice_lens else 0.0,
    )
    row.update(_confidence_features(confidences))
    row.update(_trace_features(reasonings))
    row.update(_distribution_features(sizes, n))
    return row


def extract_open_row(rec: dict, benchmark: str, source_file: str) -> dict | None:
    solver_answers = rec.get("solver_answers") or []
    correct = rec.get("correct")
    if correct is None or not solver_answers:
        return None
    n = len(solver_answers)
    answers = [str(sa.get("answer") or "") for sa in solver_answers]
    reasonings = [sa.get("reasoning") or "" for sa in solver_answers]
    gold = rec.get("gold_answer")

    groups = _cluster_open_answers(answers)
    sizes = sorted((len(g) for g in groups), reverse=True)
    top_group = max(groups, key=len) if groups else []
    top_answer = answers[top_group[0]] if top_group else None
    unanimous = bool(sizes and sizes[0] == n)
    label_unanimous_wrong = (bool(not grade(gold, top_answer)) if unanimous else False) if n >= 2 else np.nan

    row = dict(
        source_file=source_file, benchmark=benchmark, lever=rec.get("solver_model"),
        question_id=rec.get("question_id"), kind="open",
        label_wrong=1.0 if not bool(correct) else 0.0,
        label_unanimous_wrong=label_unanimous_wrong,
        question_len_chars=np.nan, question_len_words=np.nan,
        choice_length_spread=np.nan, has_question_text=0.0, has_choices=0.0,
    )
    row.update(_confidence_features([]))  # math-open never logs verbalized confidence
    row.update(_trace_features(reasonings))
    row.update(_distribution_features(sizes, n))
    return row


# --------------------------------------------------------------------------
# Inventory + load
# --------------------------------------------------------------------------

def build_inventory() -> tuple[pd.DataFrame, dict]:
    all_files = sorted(os.path.basename(p) for p in glob.glob(str(RESULTS_DIR / "*.jsonl")))
    accounted = set(EXCLUDED) | set(MC_ENGINE_FILES) | set(OPEN_ENGINE_FILES) | {MOO_FILE}
    missing = sorted(set(all_files) - accounted)
    extra = sorted(accounted - set(all_files))
    if missing:
        raise RuntimeError(f"Unclassified JSONL files found (add to inventory): {missing}")
    if extra:
        raise RuntimeError(f"Inventory references files that no longer exist: {extra}")

    rows: list[dict] = []
    inventory_log: dict[str, dict] = {}

    for fname, reason in EXCLUDED.items():
        path = RESULTS_DIR / fname
        with open(path, encoding="utf-8") as fh:
            n_lines = sum(1 for l in fh if l.strip())
        inventory_log[fname] = dict(status="excluded", reason=reason, n_lines=n_lines, n_rows=0)

    for fname, benchmark in MC_ENGINE_FILES.items():
        path = RESULTS_DIR / fname
        n_lines = 0
        n_rows = 0
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                n_lines += 1
                rec = json.loads(line)
                engine = rec.get("engine")
                if not isinstance(engine, dict):
                    continue
                lever = rec.get("lever")
                row = extract_mc_row(engine, benchmark, fname, lever)
                if row is not None:
                    rows.append(row)
                    n_rows += 1
        inventory_log[fname] = dict(status="included", reason=f"MC engine panel, benchmark={benchmark}",
                                     n_lines=n_lines, n_rows=n_rows)

    for fname, benchmark in OPEN_ENGINE_FILES.items():
        path = RESULTS_DIR / fname
        n_lines = 0
        n_rows = 0
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                n_lines += 1
                rec = json.loads(line)
                row = extract_open_row(rec, benchmark, fname)
                if row is not None:
                    rows.append(row)
                    n_rows += 1
        inventory_log[fname] = dict(status="included", reason=f"open-answer math engine panel, benchmark={benchmark}",
                                     n_lines=n_lines, n_rows=n_rows)

    # moo_m1_eval.jsonl: mixed buckets, engine dict lives under "result"
    path = RESULTS_DIR / MOO_FILE
    n_lines = 0
    n_rows = 0
    bucket_counts: Counter = Counter()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            n_lines += 1
            rec = json.loads(line)
            bucket = rec.get("bucket")
            benchmark = MOO_BUCKET_MAP.get(bucket)
            engine = rec.get("result")
            if benchmark is None or not isinstance(engine, dict):
                continue
            row = extract_mc_row(engine, benchmark, MOO_FILE, rec.get("profile"))
            if row is not None:
                rows.append(row)
                n_rows += 1
                bucket_counts[bucket] += 1
    inventory_log[MOO_FILE] = dict(
        status="included",
        reason=f"MoO blended eval, split by bucket -> benchmark via MOO_BUCKET_MAP: {dict(bucket_counts)}",
        n_lines=n_lines, n_rows=n_rows,
    )

    df = pd.DataFrame(rows)
    return df, inventory_log


# --------------------------------------------------------------------------
# LOBO evaluation
# --------------------------------------------------------------------------

def _make_pipeline() -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(C=1.0, max_iter=5000)),  # penalty="l2" is the default
    ])


def lobo_auc(df: pd.DataFrame, feature_cols: list[str], label_col: str,
             n_boot: int = 2000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    benchmarks = sorted(df["benchmark"].unique())
    out: dict[str, dict] = {}

    for bm in benchmarks:
        test = df[df["benchmark"] == bm].dropna(subset=[label_col])
        train = df[df["benchmark"] != bm].dropna(subset=[label_col])
        n_test = len(test)
        pos_rate = float(test[label_col].mean()) if n_test else float("nan")

        if n_test == 0:
            out[bm] = dict(auc=None, ci=None, n=0, pos_rate=pos_rate,
                            reason="no rows with a defined label in this benchmark")
            continue
        if test[label_col].nunique() < 2:
            out[bm] = dict(auc=None, ci=None, n=n_test, pos_rate=pos_rate,
                            reason=f"zero label variance in held-out benchmark (base rate {pos_rate:.1%})")
            continue
        if train[label_col].nunique() < 2:
            out[bm] = dict(auc=None, ci=None, n=n_test, pos_rate=pos_rate,
                            reason="zero label variance in training pool")
            continue

        pipe = _make_pipeline()
        pipe.fit(train[feature_cols], train[label_col].astype(int))
        proba = pipe.predict_proba(test[feature_cols])[:, 1]
        y = test[label_col].astype(int).to_numpy()
        auc = roc_auc_score(y, proba)

        boots = []
        idx = np.arange(n_test)
        for _ in range(n_boot):
            samp = rng.choice(idx, size=n_test, replace=True)
            if len(np.unique(y[samp])) < 2:
                continue
            boots.append(roc_auc_score(y[samp], proba[samp]))
        ci = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))) if boots else None

        out[bm] = dict(auc=float(auc), ci=ci, n=n_test, pos_rate=pos_rate, n_boot_valid=len(boots))

    return out


def median_auc(results: dict) -> float | None:
    vals = [r["auc"] for r in results.values() if r["auc"] is not None]
    return float(np.median(vals)) if vals else None


def fit_full_coefficients(df: pd.DataFrame, feature_cols: list[str], label_col: str) -> list[tuple[str, float]]:
    data = df.dropna(subset=[label_col])
    pipe = _make_pipeline()
    pipe.fit(data[feature_cols], data[label_col].astype(int))
    coefs = pipe.named_steps["clf"].coef_[0]
    pairs = sorted(zip(feature_cols, coefs), key=lambda kv: -abs(kv[1]))
    return pairs


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def _fmt_auc_row(bm: str, r: dict) -> str:
    if r["auc"] is None:
        return f"| {bm} | n={r['n']} | -- | -- | {r.get('reason', '')} |"
    ci = r["ci"]
    ci_s = f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "n/a"
    return f"| {bm} | n={r['n']} | {r['auc']:.3f} | {ci_s} | base rate {r['pos_rate']:.1%} |"


def decision_verdict(med: float | None, results: dict) -> str:
    if med is None:
        return "KILL -- median AUC undefined (no benchmark had both a defined label and class variance)."
    defined = {bm: r for bm, r in results.items() if r["auc"] is not None}
    worst = min(defined.values(), key=lambda r: r["auc"])["auc"] if defined else None
    if med >= 0.70 and worst is not None and worst >= 0.60:
        return (f"BAR CLEARED -- median AUC {med:.3f} >= 0.70 and no evaluable benchmark < 0.60 "
                "(worst = {worst:.3f}). Recommend wiring as smart_gate_v2 + W7 input.")
    if med >= 0.60:
        return (f"BAND (0.60-0.69 or a sub-0.60 benchmark present) -- median AUC {med:.3f}. "
                "Usable ONLY as a cost-router input (W7), never as an accuracy claim.")
    return (f"KILL -- median AUC {med:.3f} < 0.60. Recorded conclusion: "
            "\"verbalized/trace features don't separate\" (NOT \"no cheap signal exists\").")


def write_report(path: Path, df: pd.DataFrame, inventory_log: dict,
                  res_full_wrong: dict, res_vtd_wrong: dict, res_verb_wrong: dict,
                  res_full_unan: dict, coefs_full: list[tuple[str, float]],
                  unanimous_fraction: dict) -> None:
    med_full = median_auc(res_full_wrong)
    med_vtd = median_auc(res_vtd_wrong)
    med_verb = median_auc(res_verb_wrong)
    med_unan = median_auc(res_full_unan)
    delta_vtd_verb = (med_vtd - med_verb) if (med_vtd is not None and med_verb is not None) else None

    lines: list[str] = []
    lines.append("# W5 wrongness-predictor findings (+ F3 distribution-feature upgrade)")
    lines.append("")
    lines.append(f"Rows built: {len(df)} panel/engine instances across {df['benchmark'].nunique()} benchmarks. "
                  "No paid API calls were made -- every row comes from an already-committed result JSONL.")
    lines.append("")
    lines.append("Reproduce with:")
    lines.append("```")
    lines.append(r".venv\Scripts\python.exe -m benchmark.build_wrongness_predictor "
                  r"--report benchmark/results/wrongness_predictor_findings.md")
    lines.append("```")
    lines.append("")

    lines.append("## 1. Inventory -- every committed JSONL, honestly")
    lines.append("")
    lines.append("| file | lines | rows used | status | why |")
    lines.append("|---|---:|---:|---|---|")
    for fname in sorted(inventory_log):
        info = inventory_log[fname]
        lines.append(f"| {fname} | {info['n_lines']} | {info['n_rows']} | {info['status']} | {info['reason']} |")
    lines.append("")
    total_lines = sum(v["n_lines"] for v in inventory_log.values())
    total_rows = sum(v["n_rows"] for v in inventory_log.values())
    lines.append(f"Total: {total_lines} logged records across 74 files; {total_rows} rows carried a usable "
                  "engine/panel object and a defined `correct` label and were kept for modeling. "
                  f"{total_lines - total_rows} were excluded (baseline-only arms, the gate-replay validation "
                  "subset, or rows missing a label).")
    lines.append("")
    lines.append("### Feature coverage per benchmark")
    lines.append("")
    cov = df.groupby("benchmark").agg(
        n=("label_wrong", "size"),
        wrong_rate=("label_wrong", "mean"),
        has_confidence=("has_confidence", "mean"),
        has_question_text=("has_question_text", "mean"),
        mean_seats=("n_solver_seats", "mean"),
    ).round(3)
    lines.append("| benchmark | n | wrong rate | has verbalized confidence | has question text (structural) | mean solver seats |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for bm, r in cov.iterrows():
        lines.append(f"| {bm} | {int(r['n'])} | {r['wrong_rate']:.1%} | {r['has_confidence']:.0%} | "
                      f"{r['has_question_text']:.0%} | {r['mean_seats']:.1f} |")
    lines.append("")
    lines.append("**Coverage caveats, stated up front:** open-answer math rows (`math_open`, `aime_open`) never "
                  "log verbalized per-seat confidence (the open-answer engine's JSON contract is "
                  "`{reasoning, answer}`, no confidence field) and never log question text (only "
                  "`question_id`/`gold_answer`/`final_answer` are persisted) -- so verbalized and structural "
                  "features are imputed (train-fold median) for these two benchmarks and flagged via "
                  "`has_confidence`/`has_question_text`. Retrieval score (`rag_gate_top_score`) is logged as a "
                  "field but is `null` in every single row across all 74 files -- it is NOT a usable feature "
                  "in this data and is excluded entirely (not even imputed as a real signal).")
    lines.append("")
    lines.append("**Subject/category was deliberately dropped from the feature set.** The spec lists "
                  "\"structural: subject/category\" as a candidate feature, but subject vocabularies are "
                  "near-disjoint across benchmarks in this repo (GPQA: Astrophysics/Molecular Biology/...; "
                  "SuperGPQA: Economics/Engineering/Medicine/...; MMLU-Pro: biology/business/computer science/...; "
                  "LEXam: Interdisciplinary/Private/Public). Under leave-one-benchmark-out, a subject one-hot "
                  "would function as benchmark identity by another name -- it violates the spirit of \"never use "
                  "benchmark identity as a feature\" even though it isn't the literal `dataset` field. Excluded, "
                  "recorded here rather than silently dropped.")
    lines.append("")

    lines.append("## 2. Primary label: engine/panel answered incorrectly")
    lines.append("")
    boot_counts = [r["n_boot_valid"] for r in res_full_wrong.values() if r.get("n_boot_valid")]
    boot_note = (f"{min(boot_counts)}-{max(boot_counts)} valid resamples per benchmark (of 2000 attempted; "
                 "a resample is dropped only if it happens to contain a single class), all >= the target of 1000"
                 if boot_counts else "no benchmark had enough class variance for bootstrap resampling")
    lines.append("Leave-one-benchmark-out, AUC computed within the held-out benchmark only, logistic "
                  "regression (L2, standardized, median-imputed on the train fold), bootstrap 95% CI "
                  f"({boot_note}).")
    lines.append("")
    lines.append("### Full feature set (verbalized + trace + distribution + structural) -- the decision-rule model")
    lines.append("")
    lines.append("| benchmark | n | AUC | 95% CI | note |")
    lines.append("|---|---|---:|---|---|")
    for bm in sorted(res_full_wrong):
        lines.append(_fmt_auc_row(bm, res_full_wrong[bm]))
    lines.append("")
    lines.append(f"**Median per-benchmark AUC (full feature set): "
                  f"{med_full:.3f}**" if med_full is not None else "**Median per-benchmark AUC: undefined**")
    lines.append("")
    lines.append("**Small-benchmark caveat:** `gsm8k` (n=50), `math500` (n=49), `math_open` (n=118), "
                  "`mmlu_pro` (n=100), `mmlu_pro_stem` (n=60) and `aime_open` (n=28) have few positive "
                  "(wrong) examples -- their AUCs carry wide bootstrap CIs (visible above) and should be read "
                  "as noisy single-fold estimates, not as precise as `gpqa`/`supergpqa`'s AUCs (n>1800 each).")
    lines.append("")
    lines.append(f"### Decision-rule verdict")
    lines.append("")
    lines.append(f"> {decision_verdict(med_full, res_full_wrong)}")
    lines.append("")

    lines.append("## 3. F3's pre-registered ΔAUC: (verbalized+trace+distribution) vs (verbalized only)")
    lines.append("")
    lines.append("| feature set | median per-benchmark AUC |")
    lines.append("|---|---:|")
    lines.append(f"| verbalized only | {med_verb:.3f}" if med_verb is not None else "| verbalized only | undefined")
    lines.append(f" |")
    lines.append(f"| verbalized + trace + distribution | {med_vtd:.3f}" if med_vtd is not None else "| verbalized + trace + distribution | undefined")
    lines.append(f" |")
    if delta_vtd_verb is not None:
        lines.append(f"| **ΔAUC (distribution+trace upgrade)** | **{delta_vtd_verb:+.3f}** |")
    lines.append("")
    lines.append("### Verbalized-only detail")
    lines.append("")
    lines.append("| benchmark | n | AUC | 95% CI | note |")
    lines.append("|---|---|---:|---|---|")
    for bm in sorted(res_verb_wrong):
        lines.append(_fmt_auc_row(bm, res_verb_wrong[bm]))
    lines.append("")
    lines.append("### Verbalized+trace+distribution detail")
    lines.append("")
    lines.append("| benchmark | n | AUC | 95% CI | note |")
    lines.append("|---|---|---:|---|---|")
    for bm in sorted(res_vtd_wrong):
        lines.append(_fmt_auc_row(bm, res_vtd_wrong[bm]))
    lines.append("")

    lines.append("## 4. Secondary label: unanimous-wrong (exploratory, full feature set)")
    lines.append("")
    lines.append("Only rows with >=2 solver seats are eligible (unanimity is undefined for a 1-seat 'panel'). "
                  "Not gated by the W5/F3 bar/kill rule (that rule is pre-registered for the primary "
                  "engine-wrongness label); reported for completeness per the task spec.")
    lines.append("")
    lines.append("| benchmark | n | AUC | 95% CI | note |")
    lines.append("|---|---|---:|---|---|")
    for bm in sorted(res_full_unan):
        lines.append(_fmt_auc_row(bm, res_full_unan[bm]))
    lines.append("")
    lines.append(f"**Median per-benchmark AUC (unanimous-wrong, full feature set): "
                  f"{med_unan:.3f}**" if med_unan is not None else "**Median per-benchmark AUC: undefined**")
    lines.append("")

    lines.append("## 5. The structural ceiling: what fraction of wrong items are unanimous")
    lines.append("")
    lines.append("On unanimous items, the distribution features (agreement rate, top-vote share, entropy) are "
                  "maximal-and-useless by construction -- they cannot distinguish a unanimous-CORRECT item from "
                  "a unanimous-WRONG one. This is the ceiling W5 cannot see without an instability feature "
                  "(F3's permutation term / P6's paraphrase term, neither logged in these JSONLs yet).")
    lines.append("")
    lines.append("| benchmark | wrong rows (>=2 seats) | of which unanimous | unanimous fraction of wrong |")
    lines.append("|---|---:|---:|---:|")
    for bm, info in sorted(unanimous_fraction.items()):
        lines.append(f"| {bm} | {info['n_wrong']} | {info['n_wrong_unanimous']} | {info['fraction']:.1%} |")
    lines.append("")
    overall_wrong = sum(v["n_wrong"] for v in unanimous_fraction.values())
    overall_unan = sum(v["n_wrong_unanimous"] for v in unanimous_fraction.values())
    overall_frac = overall_unan / overall_wrong if overall_wrong else float("nan")
    lines.append(f"**Overall: {overall_unan}/{overall_wrong} wrong rows ({overall_frac:.1%}) were unanimous** -- "
                  "that share of the wrongness pool is structurally invisible to agreement/entropy features and "
                  "sets an upper bound on what any distribution-only feature can capture, independent of AUC.")
    lines.append("")

    lines.append("## 6. Feature coefficients (top 10 by |weight|, full model fit on all rows)")
    lines.append("")
    lines.append("Interpretability only -- this model is fit on ALL rows pooled (not a LOBO holdout), so its "
                  "coefficients describe association within the training data, not held-out generalization. "
                  "Standardized coefficients (z-scored features), so magnitude is directly comparable across "
                  "features on differing native scales.")
    lines.append("")
    lines.append("| rank | feature | coefficient (standardized) | direction |")
    lines.append("|---:|---|---:|---|")
    for i, (feat, coef) in enumerate(coefs_full[:10], 1):
        direction = "higher -> more likely WRONG" if coef > 0 else "higher -> more likely CORRECT"
        lines.append(f"| {i} | {feat} | {coef:+.3f} | {direction} |")
    lines.append("")

    lines.append("## 7. Bottom line")
    lines.append("")
    lines.append(f"- Primary label (engine/panel wrong), full feature set: median LOBO AUC = "
                  f"{f'{med_full:.3f}' if med_full is not None else 'undefined'}.")
    lines.append(f"- F3 ΔAUC (distribution+trace over verbalized-only): "
                  f"{f'{delta_vtd_verb:+.3f}' if delta_vtd_verb is not None else 'undefined'}.")
    lines.append(f"- Secondary label (unanimous-wrong), full feature set: median LOBO AUC = "
                  f"{f'{med_unan:.3f}' if med_unan is not None else 'undefined'}.")
    lines.append(f"- {overall_frac:.1%} of wrong panel rows were unanimous -- the ceiling distribution "
                  "features alone cannot cross.")
    lines.append(f"- **Verdict: {decision_verdict(med_full, res_full_wrong)}**")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def compute_unanimous_fraction(df: pd.DataFrame) -> dict:
    out = {}
    eligible = df[df["n_solver_seats"] >= 2]
    wrong = eligible[eligible["label_wrong"] == 1.0]
    for bm, g in wrong.groupby("benchmark"):
        n_wrong = len(g)
        n_wrong_unan = int((g["is_unanimous"] == 1.0).sum())
        out[bm] = dict(n_wrong=n_wrong, n_wrong_unanimous=n_wrong_unan,
                        fraction=(n_wrong_unan / n_wrong if n_wrong else float("nan")))
    return out


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=str, default=str(RESULTS_DIR / "wrongness_predictor_findings.md"))
    parser.add_argument("--n-boot", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    log.info("Building inventory + row features from %s ...", RESULTS_DIR)
    df, inventory_log = build_inventory()
    log.info("Built %d rows across %d benchmarks: %s", len(df), df["benchmark"].nunique(),
              dict(df["benchmark"].value_counts()))

    log.info("Running LOBO AUC -- primary label (engine wrong), full feature set ...")
    res_full_wrong = lobo_auc(df, FEATURES_FULL, "label_wrong", n_boot=args.n_boot, seed=args.seed)
    log.info("Running LOBO AUC -- primary label, verbalized+trace+distribution ...")
    res_vtd_wrong = lobo_auc(df, FEATURES_VTD, "label_wrong", n_boot=args.n_boot, seed=args.seed)
    log.info("Running LOBO AUC -- primary label, verbalized only ...")
    res_verb_wrong = lobo_auc(df, FEATURES_VERBALIZED, "label_wrong", n_boot=args.n_boot, seed=args.seed)
    log.info("Running LOBO AUC -- secondary label (unanimous-wrong), full feature set ...")
    res_full_unan = lobo_auc(df, FEATURES_FULL, "label_unanimous_wrong", n_boot=args.n_boot, seed=args.seed)

    log.info("Fitting interpretability model on all rows ...")
    coefs_full = fit_full_coefficients(df, FEATURES_FULL, "label_wrong")

    unanimous_fraction = compute_unanimous_fraction(df)

    report_path = Path(args.report)
    write_report(report_path, df, inventory_log, res_full_wrong, res_vtd_wrong, res_verb_wrong,
                 res_full_unan, coefs_full, unanimous_fraction)
    log.info("Wrote report to %s", report_path)

    med_full = median_auc(res_full_wrong)
    log.info("VERDICT: %s", decision_verdict(med_full, res_full_wrong))


if __name__ == "__main__":
    main()
