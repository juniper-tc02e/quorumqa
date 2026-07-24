# W5 wrongness-predictor findings (+ F3 distribution-feature upgrade)

Rows built: 5597 panel/engine instances across 11 benchmarks. No paid API calls were made -- every row comes from an already-committed result JSONL.

Reproduce with:
```
.venv\Scripts\python.exe -m benchmark.build_wrongness_predictor --report benchmark/results/wrongness_predictor_findings.md
```

## 1. Inventory -- every committed JSONL, honestly

| file | lines | rows used | status | why |
|---|---:|---:|---|---|
| adhoc_check.jsonl | 9 | 9 | included | MC engine panel, benchmark=gpqa |
| aime_open_baseline_seed42.jsonl | 48 | 0 | excluded | baseline-only arm (single flagship call), no solver_answers/panel |
| aime_open_panel_cheap_seed42.jsonl | 28 | 28 | included | open-answer math engine panel, benchmark=aime_open |
| full_run.jsonl | 74 | 74 | included | MC engine panel, benchmark=gpqa |
| full_run2.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| gsm8k_pilot_seed42.jsonl | 50 | 50 | included | MC engine panel, benchmark=gsm8k |
| lever_baseline_gpqa_seed314.jsonl | 89 | 0 | excluded | baseline-only arm (single flagship call, no solver_answers) -- not an engine/panel output |
| lever_baseline_mmlu_pro_stem_seed42.jsonl | 60 | 0 | excluded | baseline-only arm |
| lever_baseline_seed123.jsonl | 90 | 0 | excluded | baseline-only arm |
| lever_baseline_seed7.jsonl | 89 | 0 | excluded | baseline-only arm |
| lever_baseline_supergpqa_seed123.jsonl | 86 | 0 | excluded | baseline-only arm |
| lever_baseline_supergpqa_seed7.jsonl | 88 | 0 | excluded | baseline-only arm |
| lever_chem_flagship_gate_gpqa_seed777.jsonl | 88 | 88 | included | MC engine panel, benchmark=gpqa |
| lever_chem_flagship_gate_gpqa_seed888.jsonl | 87 | 87 | included | MC engine panel, benchmark=gpqa |
| lever_chem_flagship_gate_seed555.jsonl | 88 | 88 | included | MC engine panel, benchmark=gpqa |
| lever_chem_thinking_gate_gpqa_seed217.jsonl | 89 | 89 | included | MC engine panel, benchmark=gpqa |
| lever_chem_thinking_gate_gpqa_seed314.jsonl | 88 | 88 | included | MC engine panel, benchmark=gpqa |
| lever_chem_thinking_gate_gpqa_seed471.jsonl | 87 | 87 | included | MC engine panel, benchmark=gpqa |
| lever_combined_seed42.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_combined_seed7.jsonl | 88 | 88 | included | MC engine panel, benchmark=gpqa |
| lever_control_lexam_seed42.jsonl | 90 | 90 | included | MC engine panel, benchmark=lexam |
| lever_control_seed7.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_control_seed7_replicate.jsonl | 89 | 89 | included | MC engine panel, benchmark=gpqa |
| lever_control_supergpqa_seed123.jsonl | 88 | 88 | included | MC engine panel, benchmark=supergpqa |
| lever_control_supergpqa_seed271.jsonl | 90 | 90 | included | MC engine panel, benchmark=supergpqa |
| lever_control_supergpqa_seed606.jsonl | 89 | 89 | included | MC engine panel, benchmark=supergpqa |
| lever_control_supergpqa_seed7.jsonl | 90 | 90 | included | MC engine panel, benchmark=supergpqa |
| lever_control_supergpqa_seed838.jsonl | 90 | 90 | included | MC engine panel, benchmark=supergpqa |
| lever_five_seed42.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_flagship_panel_mmlu_pro_stem_seed42.jsonl | 60 | 60 | included | MC engine panel, benchmark=mmlu_pro_stem |
| lever_flagship_panel_seed42.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_flagship_panel_seed42_replicate.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_flagship_panel_seed7.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_flagship_panel_supergpqa_seed123.jsonl | 81 | 81 | included | MC engine panel, benchmark=supergpqa |
| lever_flagship_panel_supergpqa_seed42.jsonl | 79 | 79 | included | MC engine panel, benchmark=supergpqa |
| lever_flagship_panel_supergpqa_seed7.jsonl | 83 | 83 | included | MC engine panel, benchmark=supergpqa |
| lever_gate_replay.jsonl | 56 | 0 | excluded | gate-validation replay, pre-filtered to was_unanimous_correct items only (biased sample, zero negative-label variance by construction) and has no solver_answers/reasoning at all |
| lever_qwen38_judge_gpqa_seed42.jsonl | 76 | 76 | included | MC engine panel, benchmark=gpqa |
| lever_qwen38_panel_supergpqa_seed42.jsonl | 63 | 63 | included | MC engine panel, benchmark=supergpqa |
| lever_rag_presolve_gpqa_seed42.jsonl | 86 | 86 | included | MC engine panel, benchmark=gpqa |
| lever_rag_presolve_supergpqa_seed123.jsonl | 89 | 89 | included | MC engine panel, benchmark=supergpqa |
| lever_rag_presolve_supergpqa_seed271.jsonl | 90 | 90 | included | MC engine panel, benchmark=supergpqa |
| lever_rag_presolve_supergpqa_seed42.jsonl | 90 | 90 | included | MC engine panel, benchmark=supergpqa |
| lever_rag_presolve_supergpqa_seed606.jsonl | 90 | 90 | included | MC engine panel, benchmark=supergpqa |
| lever_rag_presolve_supergpqa_seed7.jsonl | 87 | 87 | included | MC engine panel, benchmark=supergpqa |
| lever_rag_recursive_lexam_seed42.jsonl | 90 | 90 | included | MC engine panel, benchmark=lexam |
| lever_rag_recursive_supergpqa_seed42.jsonl | 89 | 89 | included | MC engine panel, benchmark=supergpqa |
| lever_rag_thinking_gate_supergpqa_seed271.jsonl | 89 | 89 | included | MC engine panel, benchmark=supergpqa |
| lever_rag_thinking_gate_supergpqa_seed606.jsonl | 87 | 87 | included | MC engine panel, benchmark=supergpqa |
| lever_rag_thinking_gate_supergpqa_seed838.jsonl | 89 | 89 | included | MC engine panel, benchmark=supergpqa |
| lever_smart_gate_seed123.jsonl | 89 | 89 | included | MC engine panel, benchmark=gpqa |
| lever_subject_seed7.jsonl | 89 | 89 | included | MC engine panel, benchmark=gpqa |
| lever_thinking_all_seed42.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_thinking_all_seed7.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_thinking_gate_lexam_seed42.jsonl | 50 | 50 | included | MC engine panel, benchmark=lexam |
| lever_thinking_gate_mmlu_pro_seed42.jsonl | 50 | 50 | included | MC engine panel, benchmark=mmlu_pro |
| lever_thinking_gate_seed123.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_thinking_gate_seed42.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_thinking_gate_seed7.jsonl | 89 | 89 | included | MC engine panel, benchmark=gpqa |
| lever_thinking_seed42.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lever_thinking_seed7.jsonl | 90 | 90 | included | MC engine panel, benchmark=gpqa |
| lexam_pilot_seed42.jsonl | 50 | 50 | included | MC engine panel, benchmark=lexam |
| math500_hard_pilot_seed42.jsonl | 49 | 49 | included | MC engine panel, benchmark=math500 |
| math_open_baseline_seed42.jsonl | 59 | 0 | excluded | baseline-only arm (single flagship call), no solver_answers/panel |
| math_open_panel_cheap_seed42.jsonl | 59 | 59 | included | open-answer math engine panel, benchmark=math_open |
| math_open_panel_seed42.jsonl | 59 | 59 | included | open-answer math engine panel, benchmark=math_open |
| medqa_pilot_seed42.jsonl | 50 | 50 | included | MC engine panel, benchmark=medqa |
| mmlu_pro_pilot_seed42.jsonl | 50 | 50 | included | MC engine panel, benchmark=mmlu_pro |
| moo_m1_eval.jsonl | 827 | 827 | included | MoO blended eval, split by bucket -> benchmark via MOO_BUCKET_MAP: {'gpqa_hard': 205, 'supergpqa_hard': 203, 'medqa': 210, 'saturated_easy_mmlu': 209} |
| qwen38_baseline_seed123.jsonl | 78 | 0 | excluded | solo qwen3.8 baseline (single call), no solver_answers/panel |
| smoke.jsonl | 2 | 2 | included | MC engine panel, benchmark=gpqa |
| smoke2.jsonl | 2 | 2 | included | MC engine panel, benchmark=gpqa |
| smoke3.jsonl | 6 | 6 | included | MC engine panel, benchmark=gpqa |
| supergpqa_hard_pilot_seed42.jsonl | 86 | 86 | included | MC engine panel, benchmark=supergpqa |

Total: 6340 logged records across 74 files; 5597 rows carried a usable engine/panel object and a defined `correct` label and were kept for modeling. 743 were excluded (baseline-only arms, the gate-replay validation subset, or rows missing a label).

### Feature coverage per benchmark

| benchmark | n | wrong rate | has verbalized confidence | has question text (structural) | mean solver seats |
|---|---:|---:|---:|---:|---:|
| aime_open | 28 | 0.0% | 0% | 0% | 3.0 |
| gpqa | 2601 | 15.1% | 100% | 100% | 3.0 |
| gsm8k | 50 | 4.0% | 100% | 100% | 3.0 |
| lexam | 280 | 24.3% | 100% | 100% | 3.0 |
| math500 | 49 | 6.1% | 100% | 100% | 3.0 |
| math_open | 118 | 5.9% | 0% | 0% | 3.0 |
| medqa | 260 | 3.5% | 100% | 100% | 2.8 |
| mmlu_pro | 100 | 13.0% | 100% | 100% | 3.0 |
| mmlu_pro_stem | 60 | 3.3% | 100% | 100% | 3.0 |
| mmlu_saturated_easy | 209 | 3.8% | 100% | 100% | 2.7 |
| supergpqa | 1842 | 27.4% | 100% | 100% | 3.0 |

**Coverage caveats, stated up front:** open-answer math rows (`math_open`, `aime_open`) never log verbalized per-seat confidence (the open-answer engine's JSON contract is `{reasoning, answer}`, no confidence field) and never log question text (only `question_id`/`gold_answer`/`final_answer` are persisted) -- so verbalized and structural features are imputed (train-fold median) for these two benchmarks and flagged via `has_confidence`/`has_question_text`. Retrieval score (`rag_gate_top_score`) is logged as a field but is `null` in every single row across all 74 files -- it is NOT a usable feature in this data and is excluded entirely (not even imputed as a real signal).

**Subject/category was deliberately dropped from the feature set.** The spec lists "structural: subject/category" as a candidate feature, but subject vocabularies are near-disjoint across benchmarks in this repo (GPQA: Astrophysics/Molecular Biology/...; SuperGPQA: Economics/Engineering/Medicine/...; MMLU-Pro: biology/business/computer science/...; LEXam: Interdisciplinary/Private/Public). Under leave-one-benchmark-out, a subject one-hot would function as benchmark identity by another name -- it violates the spirit of "never use benchmark identity as a feature" even though it isn't the literal `dataset` field. Excluded, recorded here rather than silently dropped.

## 2. Primary label: engine/panel answered incorrectly

Leave-one-benchmark-out, AUC computed within the held-out benchmark only, logistic regression (L2, standardized, median-imputed on the train fold), bootstrap 95% CI (1733-2000 valid resamples per benchmark (of 2000 attempted; a resample is dropped only if it happens to contain a single class), all >= the target of 1000).

### Full feature set (verbalized + trace + distribution + structural) -- the decision-rule model

| benchmark | n | AUC | 95% CI | note |
|---|---|---:|---|---|
| aime_open | n=28 | -- | -- | zero label variance in held-out benchmark (base rate 0.0%) |
| gpqa | n=2601 | 0.622 | [0.589, 0.654] | base rate 15.1% |
| gsm8k | n=50 | 0.792 | [0.510, 1.000] | base rate 4.0% |
| lexam | n=280 | 0.629 | [0.555, 0.700] | base rate 24.3% |
| math500 | n=49 | 0.638 | [0.375, 0.840] | base rate 6.1% |
| math_open | n=118 | 0.537 | [0.219, 0.862] | base rate 5.9% |
| medqa | n=260 | 0.655 | [0.485, 0.810] | base rate 3.5% |
| mmlu_pro | n=100 | 0.615 | [0.431, 0.798] | base rate 13.0% |
| mmlu_pro_stem | n=60 | 0.957 | [0.897, 1.000] | base rate 3.3% |
| mmlu_saturated_easy | n=209 | 0.501 | [0.278, 0.748] | base rate 3.8% |
| supergpqa | n=1842 | 0.611 | [0.583, 0.639] | base rate 27.4% |

**Median per-benchmark AUC (full feature set): 0.625**

**Small-benchmark caveat:** `gsm8k` (n=50), `math500` (n=49), `math_open` (n=118), `mmlu_pro` (n=100), `mmlu_pro_stem` (n=60) and `aime_open` (n=28) have few positive (wrong) examples -- their AUCs carry wide bootstrap CIs (visible above) and should be read as noisy single-fold estimates, not as precise as `gpqa`/`supergpqa`'s AUCs (n>1800 each).

### Decision-rule verdict

> BAND (0.60-0.69 or a sub-0.60 benchmark present) -- median AUC 0.625. Usable ONLY as a cost-router input (W7), never as an accuracy claim.

## 3. F3's pre-registered ΔAUC: (verbalized+trace+distribution) vs (verbalized only)

| feature set | median per-benchmark AUC |
|---|---:|
| verbalized only | 0.647
 |
| verbalized + trace + distribution | 0.621
 |
| **ΔAUC (distribution+trace upgrade)** | **-0.026** |

### Verbalized-only detail

| benchmark | n | AUC | 95% CI | note |
|---|---|---:|---|---|
| aime_open | n=28 | -- | -- | zero label variance in held-out benchmark (base rate 0.0%) |
| gpqa | n=2601 | 0.720 | [0.692, 0.745] | base rate 15.1% |
| gsm8k | n=50 | 0.656 | [0.349, 0.969] | base rate 4.0% |
| lexam | n=280 | 0.619 | [0.546, 0.693] | base rate 24.3% |
| math500 | n=49 | 0.674 | [0.554, 0.787] | base rate 6.1% |
| math_open | n=118 | 0.500 | [0.500, 0.500] | base rate 5.9% |
| medqa | n=260 | 0.586 | [0.411, 0.755] | base rate 3.5% |
| mmlu_pro | n=100 | 0.692 | [0.526, 0.826] | base rate 13.0% |
| mmlu_pro_stem | n=60 | 0.957 | [0.897, 1.000] | base rate 3.3% |
| mmlu_saturated_easy | n=209 | 0.567 | [0.361, 0.786] | base rate 3.8% |
| supergpqa | n=1842 | 0.638 | [0.609, 0.666] | base rate 27.4% |

### Verbalized+trace+distribution detail

| benchmark | n | AUC | 95% CI | note |
|---|---|---:|---|---|
| aime_open | n=28 | -- | -- | zero label variance in held-out benchmark (base rate 0.0%) |
| gpqa | n=2601 | 0.642 | [0.609, 0.674] | base rate 15.1% |
| gsm8k | n=50 | 0.667 | [0.271, 1.000] | base rate 4.0% |
| lexam | n=280 | 0.587 | [0.508, 0.667] | base rate 24.3% |
| math500 | n=49 | 0.623 | [0.375, 0.812] | base rate 6.1% |
| math_open | n=118 | 0.530 | [0.214, 0.860] | base rate 5.9% |
| medqa | n=260 | 0.524 | [0.348, 0.712] | base rate 3.5% |
| mmlu_pro | n=100 | 0.740 | [0.579, 0.873] | base rate 13.0% |
| mmlu_pro_stem | n=60 | 0.957 | [0.897, 1.000] | base rate 3.3% |
| mmlu_saturated_easy | n=209 | 0.583 | [0.342, 0.808] | base rate 3.8% |
| supergpqa | n=1842 | 0.619 | [0.590, 0.647] | base rate 27.4% |

## 4. Secondary label: unanimous-wrong (exploratory, full feature set)

Only rows with >=2 solver seats are eligible (unanimity is undefined for a 1-seat 'panel'). Not gated by the W5/F3 bar/kill rule (that rule is pre-registered for the primary engine-wrongness label); reported for completeness per the task spec.

| benchmark | n | AUC | 95% CI | note |
|---|---|---:|---|---|
| aime_open | n=28 | -- | -- | zero label variance in held-out benchmark (base rate 0.0%) |
| gpqa | n=2572 | 0.833 | [0.811, 0.855] | base rate 9.5% |
| gsm8k | n=50 | 0.698 | [0.340, 1.000] | base rate 4.0% |
| lexam | n=280 | 0.819 | [0.758, 0.872] | base rate 17.1% |
| math500 | n=49 | 0.732 | [0.543, 0.894] | base rate 6.1% |
| math_open | n=118 | 0.547 | [0.166, 0.915] | base rate 1.7% |
| medqa | n=230 | 0.664 | [0.539, 0.806] | base rate 3.5% |
| mmlu_pro | n=100 | 0.770 | [0.612, 0.912] | base rate 10.0% |
| mmlu_pro_stem | n=60 | 0.966 | [0.914, 1.000] | base rate 1.7% |
| mmlu_saturated_easy | n=179 | 0.641 | [0.414, 0.865] | base rate 4.5% |
| supergpqa | n=1813 | 0.831 | [0.810, 0.851] | base rate 17.8% |

**Median per-benchmark AUC (unanimous-wrong, full feature set): 0.751**

## 5. The structural ceiling: what fraction of wrong items are unanimous

On unanimous items, the distribution features (agreement rate, top-vote share, entropy) are maximal-and-useless by construction -- they cannot distinguish a unanimous-CORRECT item from a unanimous-WRONG one. This is the ceiling W5 cannot see without an instability feature (F3's permutation term / P6's paraphrase term, neither logged in these JSONLs yet).

| benchmark | wrong rows (>=2 seats) | of which unanimous | unanimous fraction of wrong |
|---|---:|---:|---:|
| gpqa | 390 | 215 | 55.1% |
| gsm8k | 2 | 2 | 100.0% |
| lexam | 68 | 47 | 69.1% |
| math500 | 3 | 3 | 100.0% |
| math_open | 7 | 6 | 85.7% |
| medqa | 8 | 8 | 100.0% |
| mmlu_pro | 13 | 9 | 69.2% |
| mmlu_pro_stem | 2 | 1 | 50.0% |
| mmlu_saturated_easy | 7 | 6 | 85.7% |
| supergpqa | 498 | 318 | 63.9% |

**Overall: 615/998 wrong rows (61.6%) were unanimous** -- that share of the wrongness pool is structurally invisible to agreement/entropy features and sets an upper bound on what any distribution-only feature can capture, independent of AUC.

## 6. Feature coefficients (top 10 by |weight|, full model fit on all rows)

Interpretability only -- this model is fit on ALL rows pooled (not a LOBO holdout), so its coefficients describe association within the training data, not held-out generalization. Standardized coefficients (z-scored features), so magnitude is directly comparable across features on differing native scales.

| rank | feature | coefficient (standardized) | direction |
|---:|---|---:|---|
| 1 | is_unanimous | -0.572 | higher -> more likely CORRECT |
| 2 | top_vote_share | +0.398 | higher -> more likely WRONG |
| 3 | reason_len_words_mean | +0.377 | higher -> more likely WRONG |
| 4 | conf_max | -0.340 | higher -> more likely CORRECT |
| 5 | cluster_margin | +0.270 | higher -> more likely WRONG |
| 6 | is_fragmented | +0.220 | higher -> more likely WRONG |
| 7 | question_len_words | -0.206 | higher -> more likely CORRECT |
| 8 | hedge_rate_max | -0.181 | higher -> more likely CORRECT |
| 9 | reason_len_words_max | -0.176 | higher -> more likely CORRECT |
| 10 | conf_mean | -0.161 | higher -> more likely CORRECT |

## 7. Bottom line

- Primary label (engine/panel wrong), full feature set: median LOBO AUC = 0.625.
- F3 ΔAUC (distribution+trace over verbalized-only): -0.026.
- Secondary label (unanimous-wrong), full feature set: median LOBO AUC = 0.751.
- 61.6% of wrong panel rows were unanimous -- the ceiling distribution features alone cannot cross.
- **Verdict: BAND (0.60-0.69 or a sub-0.60 benchmark present) -- median AUC 0.625. Usable ONLY as a cost-router input (W7), never as an accuracy claim.**

---

## Orchestrator review annotation (2026-07-24, before commit)

The secondary-label result (unanimous-wrong, median AUC 0.751) must be read
with a structural caveat the table doesn't decompose: the label is
"unanimous-wrong vs ALL other rows" (including splits), while the feature set
includes agreement/vote-distribution features — so part of that AUC is the
model trivially separating unanimous from split rows, not detecting
WRONGNESS among unanimous answers. The load-bearing conditional question for
any gate — P(wrong | unanimous), evaluated among unanimous rows only — is
NOT answered by this number and remains unmeasured. Per the report's own §5,
61.6% of wrong rows are unanimous and agreement features are maximal-and-
useless exactly there; the conditional predictor needs instability features
(permutation flips, paraphrase flips) that no run has logged yet — W2 arm-0
and P6 produce them. Until then, the honest summary stands: **BAND (0.625)
— cost-router input only; no gate, no accuracy claim.**
