# External comparability audit

What stands between QuorumQA's current accuracy numbers and a number
someone could cite next to a published leaderboard score, benchmark by
benchmark. Two problems apply project-wide, both documented in this repo's
own loader docstrings before this audit: **(1) reshaping** -- several
benchmarks are converted into a 4-choice multiple-choice format their
published protocol does not use (SuperGPQA/MMLU-Pro trimmed from up to
10 native options down to 4; MATH-500/GSM8K synthesized into distractor-MC
from a genuinely open-answer source); **(2) subsampling** -- every runner
in this repo defaults to n=50-90 items against full test sets of
198-26,529. This document does not re-argue that those tradeoffs were
reasonable engineering calls under a real quota constraint (they were,
and each loader says so); it inventories exactly what remains before each
surface's number would hold up against a citation.

**Scope note:** this only covers the single-agent baseline path to
comparability (what published leaderboards actually measure -- one model,
one call per item). Whether QuorumQA's panel/escalation *engine* beats
that baseline is this project's own research question, answered
separately in the lever results; it is not what "externally comparable"
means here.

**Quota reality, used throughout:** the measured 1-week Token Plan quota
is **~43.8M tokens** (17.9M in / 25.9M out, logged lower bound across 48
run-files -- see `benchmark/results/quota_token_audit.md`). Every cost
figure below is stated against that number. Figures pulled directly from a
logged run-file's own token count are marked **measured**; everything else
is an **estimate**, extrapolated from the closest comparable logged run
and clearly flagged as such -- several of these benchmarks have never been
run live at all.

## Ranked summary

Ranked by how much remains before a citable number exists, closest first.

| # | Benchmark | Reshaped? | n run / full | Grader fidelity | Full-scale cost (single-agent baseline) | What's left |
|---|---|---|---|---|---|---|
| 1 | **IFEval** | Never | 0 / 541 (runner just built, never run live) | Independently validated against Google's own reference implementation (77.22% vs their 77.0-77.2% on their own 540-row file) | ~1.6-3.2M tok (**est.**, ~4-7% of quota) | Run it. Panel arm deliberately deferred (see `run_ifeval.py`), doesn't block the single-arm number. |
| 2 | **AIME** (2024+2025) | Never | ~48-60 / 60 (already run, near-complete) | `math_grade.py`, unvalidated in general but airtight on AIME's pure-integer answer space | ~320K tok (**measured** baseline, ~0.7%) | Close out the last few dropped items; decide whether combined-years or per-year is the citation convention wanted. |
| 3 | **GPQA-Diamond** | Never (native `Correct Answer`/`Incorrect Answer 1-3`) | ~86-90 / 198 | Trivial exact-letter match, no fidelity question | ~586K tok (**measured**, ~1.3%) | Just run n=198 (the whole set, no filter exists). Cheapest full-scale run of any candidate here. |
| 4 | **MedQA** | Never (native `MedQA-USMLE-4-options`) | ~50 / 1,273 | Trivial exact-letter match | ~3.96M tok (**measured**, combined baseline+engine, ~9%) | Just run n=1,273. |
| 5 | **LEXam** | Never for `mcq_4_choices` (English subset, by design) | ~50-90 / 619 (English) | Trivial exact-letter match | ~2.95M tok (**measured**, combined, ~6.7%) | Just run n=619; flag the English-only scope decision when citing. |
| 6 | **MATH-500 (open)** | Never | ~59-90 / 500 (further level=5-filtered to 134 by default) | Custom CAS-equivalence grader (`math_grade.py`), **not** independently validated against an official reference | ~1.35-1.75M tok (**est.**, baseline, ~3-4%) | Run all levels at full n; get the grader cross-checked against a reference (e.g. `math_verify` or a hand-labeled sample). |
| 7 | **MMLU-Pro (untrimmed)** | Now optional (`mmlu_pro_full`, prior work) | 0 / 12,032 untrimmed (never run; old trimmed pilot only, n=50) | Trivial exact-letter match once untrimmed | Baseline-only ~18-24M tok (**est.**, ~41-55%); full engine pass ~84-114M tok (**est.**, ~190-260% -- exceeds one week's quota) | Run it -- baseline-only fits in a week; full engine pass needs multiple weeks or a partial-but-large n compromise. |
| 8 | **SimpleQA** | Never | 0 / 4,326 (never run live at any n) | Official OpenAI `GRADER_TEMPLATE`, reproduced verbatim, but run through a **substitute** grading model (qwen3.7-max, not GPT-4) | ~4.3-10.8M tok (**est.**, baseline only, ~10-25%); panel+retrieval+verify+grade unmeasured | Run a real pilot to get actual cost data; separately, validate or disclose the grader-model substitution's agreement rate. |
| 9 | **SuperGPQA (untrimmed)** | Now optional (`supergpqa_full`, this task) | 0 / 26,529 unfiltered (never run untrimmed; old trimmed/hard-only pilot only, n=86) | Trivial exact-letter match once untrimmed | Baseline-only ~93-133M tok (**est.**, ~212-303% -- exceeds ONE WEEK'S ENTIRE quota alone) | By far the most expensive candidate. Needs several weeks minimum for baseline alone, or an explicit, disclosed n compromise. |
| 10 | **GSM8K** | Always (distractor-MC; no open-answer path exists) | ~50 / 1,319, MC only | N/A (grading an MC path nothing publishes) | N/A until built | Needs a **new loader** (`load_gsm8k_open.py`, mirroring `load_math_open.py`) wired to the existing `math_open_engine`/`math_grade.grade` -- real engineering, not just a bigger run. Grading itself would be the easiest case once built (plain integers). |
| 11 | **MATH-500 (MC)** | Always, and **unfixable via a flag** | ~49-90 / 500, MC only | N/A (grading a task nothing publishes) | N/A -- dead end | Not on the path to comparability at all. MATH-500's native format is open-answer; the MC loader is a different synthetic task, not a trim of a native MC set (unlike SuperGPQA/MMLU-Pro). Superseded by MATH-500 (open), row 6 -- use that loader instead. |

## Per-benchmark detail

### 1. IFEval -- closest to citable

- **Reshaping:** none, ever. `benchmark/load_ifeval.py` loads all 541
  prompts verbatim -- no distractor synthesis, no answer-shape filtering
  (there is no gold "answer" field to reshape against in the first place).
- **n vs full:** the runner built in this task (`benchmark/run_ifeval.py`)
  supports both a cheap gap probe (`--n 60`, IFEval's own established IF-2
  size) and the complete 541-prompt set (`--n 541`, the default). Zero
  live rows have been scored as of this writing -- the runner exists but
  has not been executed against a real model.
- **Grader fidelity:** the strongest in this repo. `benchmark/
  ifeval_verify.py` is a line-by-line port of Google's own
  `instruction_following_eval` checkers, cross-checked against the actual
  reference package (not re-derived from a spec): 50/50 hand-written
  cases, 126/126 real-dataset-kwargs cases, and a full-file run against
  the reference implementation's own published GPT-4 output achieving
  77.22% strict-prompt accuracy vs. the official 77.0-77.2% (416-417/540,
  a documented nondeterminism bug in the *official* grader itself, not in
  this port -- see `benchmark/results/ifeval_scorer_validation.md`).
- **What's left:** run it. The single-arm baseline (`--arm single`) is
  fully implemented, with retry-with-backoff and both strict/loose
  scoring. The panel arm is deliberately not built -- see
  `run_ifeval.py`'s "WHY NO PANEL ARM" docstring section -- but that
  absence does not block a citable single-agent number.
- **Cost:** never measured live. Estimated **1.6-3.2M tokens** for a full
  single-arm run (541 prompts x an estimated 3,000-6,000 tok/row for one
  flagship call with thinking on and up to 2048 output tokens) -- roughly
  **4-7% of a week's quota**. Cheap enough to run alongside other work in
  the same week.

### 2. AIME 2024+2025 -- already near-complete

- **Reshaping:** none. `benchmark/load_aime.py` keeps AIME's genuinely
  open integer answers (0-999), fed through `math_open_engine.py` and
  graded by `math_grade.grade`.
- **n vs full:** AIME only has 30 problems/year; this repo already
  combines 2024+2025 for 60 total and runs at `n=60` by default. Live logs
  already exist: `aime_open_baseline_seed42.jsonl` (48/60 items,
  **measured** 5,327 tok/row) and `aime_open_panel_cheap_seed42.jsonl`
  (28/60 items, **measured** ~73,234 tok/row -- cheap-tier panel with
  heavy retry cost). This is effectively already a near-full-scale run,
  not a small subsample of a much larger set.
- **Grader fidelity:** `math_grade.py` is a custom SymPy/`latex2sympy2_
  extended`-based CAS-equivalence checker, built because HuggingFace's
  `math_verify` spawn-storms on Windows. It has **not** been independently
  cross-validated against an official reference the way `ifeval_verify.py`
  was. On AIME specifically this matters much less than it does for
  MATH-500-open: every AIME gold answer is a plain integer, the easiest
  possible case for any equivalence checker (exact value match, no
  fractions/radicals/tuples/sets/±-expressions to parse). Practically
  foolproof even without formal validation.
- **What's left:** re-run the handful of dropped items to close out full
  60/60 coverage on both arms; decide the citation convention (most model
  cards report AIME 2024 and AIME 2025 as separate 30-problem scores, not
  a combined 60 -- our combined number is defensible but should be
  reported alongside, not instead of, the per-year split if citing against
  a specific paper).
- **Cost:** **measured** 255,698 tokens for the 48-item baseline run
  already logged; the remaining 12 items would cost a similar
  per-item rate, i.e. tens of thousands more tokens. Trivial relative to
  quota (<1%).

### 3. GPQA-Diamond -- cheapest full-scale run available

- **Reshaping:** never. Verified directly in `benchmark/load_gpqa.py`:
  the primary path reads `Correct Answer` / `Incorrect Answer 1/2/3`
  straight off the HuggingFace `idavidrein/gpqa` `gpqa_diamond` config --
  natively 4-choice, nothing to trim.
- **n vs full:** confirmed live against the cached dataset: **198 rows**
  total. Most committed runs use n=86-90. No difficulty/subject filter
  exists in this loader at all, so a full run is simply `n=198` -- the
  entire dataset, unfiltered, exactly as published.
- **Grader fidelity:** exact single-letter match against the dataset's own
  gold answer -- this *is* how GPQA-Diamond is graded everywhere it's
  published. No fidelity question at all.
- **What's left:** nothing but spending the (very small) quota to run at
  n=198 instead of n=90.
- **Cost:** **measured** ~2,959 tok/row (baseline-only,
  `lever_baseline_gpqa_seed314.jsonl`) x 198 = **~586,000 tokens, ~1.3% of
  a week's quota**. The single cheapest full-scale run of any benchmark in
  this repo.

### 4. MedQA -- native 4-option, just needs full n

- **Reshaping:** never. `GBaker/MedQA-USMLE-4-options` -- the dataset
  itself ships exactly 4 options per row (a native dict keyed A-D), as its
  own name states. `benchmark/load_medqa.py` does zero trimming.
- **n vs full:** **1,273 rows** in the test split (confirmed in the
  loader's own docstring); committed runs use n=50. No filter exists.
- **Grader fidelity:** trivial exact-letter match, matching the standard
  MedQA-USMLE-4-options evaluation protocol.
- **What's left:** run at n=1,273.
- **Cost:** **measured** ~3,112 tok/row (`medqa_pilot_seed42.jsonl`,
  combined baseline+engine, since `run_medqa.py` writes both per row) x
  1,273 = **~3.96M tokens, ~9.0% of quota**.

### 5. LEXam -- native 4-option English subset, just needs full n

- **Reshaping:** never, for the `mcq_4_choices` config this repo uses.
  `benchmark/load_lexam.py` defaults to `language="en"` to avoid
  conflating "hard law" with German-language ability -- a deliberate,
  documented scope decision, not a limitation. 619 of the config's 1,655
  rows are English.
- **n vs full:** committed runs use n=50-90 of 619 English rows.
- **Grader fidelity:** trivial exact-letter match against the dataset's
  own `gold` index.
- **What's left:** run at n=619; when citing, note the run covers the
  English subset of `mcq_4_choices`, not the full bilingual config (a
  defensible, disclosed scope, but a scope nonetheless -- flag it rather
  than let a reader assume "LEXam" means the whole 1,655-row config).
- **Cost:** **measured** ~4,765 tok/row (`lexam_pilot_seed42.jsonl`,
  combined baseline+engine) x 619 = **~2.95M tokens, ~6.7% of quota**.

### 6. MATH-500 (open) -- clean data, unvalidated grader

- **Reshaping:** none. `benchmark/load_math_open.py` keeps MATH-500's raw
  open `answer` field untouched -- no distractor synthesis, no MC framing,
  unlike its sibling `load_math.py` (row 11 below).
- **n vs full:** committed runs use n=59-90, further filtered to
  `level=5` (134 of 500 rows) by default -- the same "give the flagship
  real headroom" rationale SuperGPQA's difficulty filter uses. A citable
  number needs either `level=None` (all 500, matching how most papers
  report overall MATH-500 accuracy) or an explicit per-level breakdown
  (which several papers also report).
- **Grader fidelity:** `benchmark/math_grade.py`, a custom-built
  SymPy/`latex2sympy2_extended` CAS-equivalence checker, is genuinely
  capable (handles fractions, radicals, pi-multiples, coordinate tuples,
  intervals, multi-valued/±-expression answers) and fails closed (returns
  False rather than a lenient guess on any parse failure). It has **not**
  been independently cross-validated against an official reference
  implementation the way `ifeval_verify.py` was -- no side-by-side run
  against `math_verify` (unusable on this Windows environment, which is
  *why* this grader exists) or against a hand-labeled fixture. This is the
  single largest remaining gap for this benchmark specifically.
- **What's left:** run all levels at full n=500; get the grader
  cross-checked (even a modest hand-labeled sample, or a non-Windows CI
  run of `math_verify` against the same rows, would close most of the
  gap).
- **Cost:** **measured** ~2,703 tok/row (baseline, level=5,
  `math_open_baseline_seed42.jsonl`) extrapolated to all levels/full n=500
  ≈ **1.35-1.75M tokens, ~3-4% of quota** for baseline; panel measured
  ~6,409 tok/row ⇒ full-scale panel ≈ 3.2M tokens, ~7.3%. Both cheap.

### 7. MMLU-Pro (untrimmed) -- ready but genuinely expensive at true scale

- **Reshaping:** now optional, from prior work (not this task): `benchmark/
  load_mmlu_pro.py`'s `max_choices=None` path / `load_mmlu_pro_full_set` /
  the `mmlu_pro_full` `DATASET_LOADERS` entry keep every native option
  (up to 10) instead of trimming to 4.
- **n vs full:** **12,032 rows** in the test split. The untrimmed path has
  **never been run live** -- only the old trimmed-to-4 pilot exists
  (`mmlu_pro_pilot_seed42.jsonl`, n=50).
- **Grader fidelity:** trivial exact-letter match once untrimmed --
  matches MMLU-Pro's actual published (up-to-10-way) protocol.
- **What's left:** run it -- but be deliberate about scope. A
  baseline-only full run (**estimated** ~18-24M tokens, ~41-55% of quota,
  extrapolating from the measured 1,212 tok/row trimmed-baseline-only
  figure with an upward adjustment for longer untrimmed choice blocks)
  plausibly fits in a single week if nothing else runs. The full
  baseline+engine pass at true full scale does not: **estimated**
  ~84-114M tokens, **190-260% of one week's entire quota** -- would need
  multiple weeks, or a large-but-partial n (e.g. 2,000-3,000, still
  20-40x this repo's current n and far more citable, at an estimated
  14-25M tokens / 30-60% of quota).
- **Cost:** see above; this is the first candidate where "just run it"
  stops being a one-line answer and becomes a real scheduling decision.

### 8. SimpleQA -- built, but never run, and a substitute grader

- **Reshaping:** never. `benchmark/load_simpleqa.py` keeps SimpleQA's free
  text gold answers untouched.
- **n vs full:** **4,326 rows** in the test split; this repo's own
  pre-registered pilot size is 300. **No SimpleQA run has been logged at
  any n** -- it does not appear anywhere in
  `benchmark/results/quota_token_audit.md`'s 48 run-files, unlike every
  benchmark above it in this ranking.
- **Grader fidelity:** two graders exist, and only one is the headline.
  `exact_match_normalized` is a deterministic, honestly-disclosed *lower
  bound* (under-counts paraphrases like "JFK" vs "John F. Kennedy").
  `grade_simpleqa` reproduces OpenAI's actual published `GRADER_TEMPLATE`
  prompt verbatim (fetched directly from `openai/simple-evals`) -- this
  *is* the official methodology. But it runs that prompt through
  `ORCHESTRATOR_MODEL` (qwen3.7-max) as the grading judge, **not** the
  GPT-4-class model OpenAI's own paper uses -- an explicitly disclosed
  substitution in `factuality_engine.py`, and the one genuine open
  question here: nobody has measured how often qwen3.7-max-as-grader
  agrees with what a GPT-4-class grader would have said on the same
  (question, gold, predicted) triples.
- **What's left:** (a) run an actual pilot to get real cost data --
  everything below is an estimate against surfaces that were run; (b)
  either validate the grader-model substitution (a spot-check agreement
  rate against a sample re-graded by a stronger model) or disclose it
  plainly alongside any headline number, which is a materially different
  ask than "just run more items."
- **Cost:** **estimated** ~4.3-10.8M tokens for baseline generation at full
  n=4,326 (~10-25% of quota, extrapolating from short-free-text-answer
  economics elsewhere in this repo); panel adds retrieval + judge +
  verify, meaningfully more, genuinely unmeasured.
- **Cost correction (audited 2026-07-26): the grader pass belongs to BOTH
  arms, not just the panel.** This bullet previously filed the per-item
  `grade_simpleqa` call under the panel arm alone. But
  `benchmark/factuality_engine.py:491` states plainly that **"THE HEADLINE
  METRIC REQUIRES grade_simpleqa; exact_match_normalized is a floor for a
  zero-cost sanity check only"**, and `solve_single_factual` — the baseline
  arm — computes only that floor. So the baseline arm needs one grader call
  per item too, and that cost was missing entirely.
  Measured, not extrapolated: `GRADER_TEMPLATE` is 5,960 chars = **1,373
  cl100k tokens**, so at n=4,326 the grading pass alone is
  **~6.1-6.4M tokens (~14-15% of quota)**. Corrected total for a reportable
  baseline number: **~10.4-17.2M, i.e. ~24-39% of one week.**
  This does **not** change the scheduling bucket — SimpleQA was already
  filed under "fits in a week, but only if it's the main thing running" —
  and it corrupts no aggregate, since SimpleQA is excluded from the
  six-run plan below. The operative advice stands: run a pilot to replace
  this estimate before committing. Note also there is currently **no
  SimpleQA runner at all** (`grade_simpleqa` has no non-test callers), so
  nothing can be launched against this figure by accident.

### 9. SuperGPQA (untrimmed) -- most expensive candidate by a wide margin

- **Reshaping:** now optional, from this task: `benchmark/
  load_supergpqa.py`'s `max_choices=None` path / `load_supergpqa_full_set`
  / the `supergpqa_full` `DATASET_LOADERS` entry keep every native option.
  **SuperGPQA's actual native option-count distribution, verified live
  against a full download of all 26,529 rows (not guessed):** 4=438,
  5=204, 6=280, 7=441, 8=683, 9=1,325, **10=23,158 (87.3%)**. Minimum 4,
  maximum 10 -- SuperGPQA's own ceiling happens to equal
  `quorumqa.letters`' A-J vocabulary limit exactly, so the `max_choices=
  None` path's defensive ">10 -> skip" branch is real code but has never
  been observed to actually fire against this dataset.
- **n vs full:** **26,529 rows** total; this repo's existing pilot uses
  n=86 of the `difficulty="hard"` subset (7,050 rows) with 4-choice
  trimming. The untrimmed path has never been run live at any scale.
  Matching a published *overall* SuperGPQA number additionally needs
  `difficulty=None` (most leaderboards report accuracy across the full
  dataset, sometimes broken out by difficulty tier as a secondary cut) --
  our own difficulty="hard" default, kept unchanged by
  `load_supergpqa_full_set`, is itself a deliberate non-default selection
  relative to a pooled published number, separate from the trimming
  question.
- **Grader fidelity:** trivial exact-letter match once untrimmed.
- **What's left:** run it -- but this is the one candidate where cost
  alone rules out "just run it" within the current week. Baseline-only,
  untrimmed, unfiltered full scale is **estimated at ~93-133M tokens**,
  **212-303% of one week's ENTIRE quota**, for the single-agent baseline
  alone. The full engine pass would cost several times that. This would
  need multiple weeks minimum, run with nothing else in flight, or an
  explicit, disclosed n compromise (e.g. a stratified few-thousand-row
  sample across difficulty tiers) that reopens exactly the subsampling
  question this whole document exists to close out -- worth stating
  plainly rather than quietly defaulting back to n=90.
- **Cost:** see above. By a wide margin the most expensive candidate here.

### 10. GSM8K -- needs a new loader, not just a bigger run

- **Reshaping:** always, and there is currently **no way to disable it** --
  unlike SuperGPQA/MMLU-Pro (which were natively multi-choice and only
  needed a trim-vs-keep flag), GSM8K's native format is open-answer
  arithmetic. `benchmark/load_gsm8k.py` synthesizes 3 distractor answers
  per item from named arithmetic-error patterns and forces the question
  into this engine's 4-choice schema; the loader's own docstring already
  states the result is "NOT comparable to any published GSM8K score."
  There is no `load_gsm8k_open.py` and no engine path that grades GSM8K's
  raw numeric answers -- MATH-500 has both an MC loader (`load_math.py`)
  and a genuinely open one (`load_math_open.py`); GSM8K only has the
  former.
- **n vs full:** 1,319 rows in the test split (confirmed 0 stragglers on
  the `#### <integer>` extraction regex); committed runs use n=50, MC
  only.
- **Grader fidelity:** not applicable yet -- there is nothing to grade
  against a published protocol until an open-answer path exists. Once
  built, this would be the *easiest* grading case of any benchmark here:
  every GSM8K gold answer is a plain integer (0 decimals observed in the
  full 1,319-row scan), so even a trivial `int(pred) == int(gold)` check
  -- no CAS, no `math_grade.py` needed at all -- would be fully faithful
  to the official protocol.
- **What's left:** build `benchmark/load_gsm8k_open.py` (mirrors
  `load_math_open.py`'s ~40 lines almost exactly: same `MathItem`
  dataclass, same seeded-shuffle loader shape, `gold_answer` set to the
  extracted `#### <integer>` value instead of `answer`) and wire it into
  `math_open_engine`'s existing `solve_single_math`/`solve_panel_math` via
  a new `--dataset gsm8k` branch in `run_math_open.py` (which already
  supports a `--dataset` switch for `math500`/`aime`). This is genuinely
  new engineering, not a parameter flip -- **outside this task's file
  set**, flagged here as the clear next step for GSM8K specifically.
- **Cost:** not applicable until built; once built, likely cheap
  (**estimated** ~2-3.3M tokens for a full 1,319-item baseline+engine
  run, ~4.5-7.5% of quota, extrapolating from grade-school-arithmetic
  response-length economics elsewhere in this repo).

### 11. MATH-500 (MC) -- dead end, use MATH-500 (open) instead

- **Reshaping:** always, and **unfixable by adding a flag** -- this is the
  structurally different case from SuperGPQA/MMLU-Pro. Those two datasets
  are *natively* multi-choice; trimming them to 4 options is a lossy but
  same-task operation, which is exactly why a `max_choices=None` flag
  fully restores comparability. MATH-500's native format is open-answer;
  `benchmark/load_math.py` doesn't trim an existing choice set, it
  *synthesizes* one from scratch (3 arithmetic-error-pattern distractors
  per item, `_numeric_distractors`/`_frac_distractors`, generated by this
  loader's own RNG, not by any published error taxonomy) and additionally
  drops the 27% of level-5 rows whose answers are expression-shaped rather
  than numeric-perturbable. No leaderboard publishes "MATH-500 accuracy
  under this loader's synthetic 4-choice framing" -- there is no protocol
  to converge toward by running more items or removing a filter.
- **n vs full:** irrelevant to comparability for the reason above; for
  completeness, committed runs use n=49-90 of the (further-filtered)
  numeric-eligible level-5 subset.
- **Grader fidelity:** not applicable -- grading an MC task nothing
  publishes cannot be "faithful" or "unfaithful" to an external protocol
  that doesn't exist for this task shape.
- **What's left:** nothing productive to do to *this* loader for
  comparability purposes. `benchmark/load_math_open.py` (row 6) already
  exists, already keeps the same rows' genuinely open answers, and is the
  loader to use instead. This loader remains useful for this project's own
  internal purposes (it was built to test whether MC framing saturates the
  flagship, and it does -- see `benchmark/results/math500_hard_pilot_
  seed42.log`), just not for external comparability.
- **Cost:** not applicable.

## Cost reality check, stated plainly

Against the measured **~43.8M-token weekly quota**:

- **Cheap enough to run this week without a second thought:** GPQA-Diamond
  full (1.3%), IFEval full (4-7% est.), LEXam full (6.7%), MATH-500-open
  full (3-4% baseline / 7.3% panel), GSM8K-once-built (4.5-7.5% est.),
  AIME (<1%, already nearly done), MedQA full (9.0%).
- **Fits in a week, but only if it's the main thing running:**
  SimpleQA full baseline (10-25% est.), MMLU-Pro-untrimmed baseline-only
  (41-55% est.).
- **Does not fit in a single week at all:** MMLU-Pro-untrimmed full
  baseline+engine (190-260% of quota, est.), SuperGPQA-untrimmed-
  unfiltered baseline ALONE (212-303% of quota, est.) -- SuperGPQA's
  engine pass would be several times that again. Either of these needs
  multiple consecutive weeks with nothing else in flight, or an explicit,
  disclosed n compromise rather than a silent return to n=90.

The practical near-term order this ranking implies: **IFEval, AIME
closeout, GPQA-Diamond, MedQA, LEXam, and MATH-500-open full-scale runs
are all affordable in a single week combined**, and would take this
project from "zero benchmarks are externally comparable" to "six are"
without touching the two genuinely expensive candidates
(MMLU-Pro-untrimmed, SuperGPQA-untrimmed) at all.

The summands, so the total is checkable rather than asserted:

| run | % of one week |
|---|---|
| IFEval full | 4.0 – 7.0 |
| AIME closeout | <1 |
| GPQA-Diamond full | 1.3 |
| MedQA full | 9.0 |
| LEXam full | 6.7 |
| MATH-500-open full | 3.0 – 7.3 (baseline-only – panel) |
| **total for the six** | **~24.5 – 32.3** |

**Correction (audited 2026-07-26).** This paragraph previously claimed
"roughly 35-45% of one week's quota for all six put together." That does
not follow from the document's own per-benchmark figures, which sum to
**~24.5-32.3%** (or 24.5-29.3% reading MATH-500-open as baseline-only) —
an over-statement of up to **1.8x**. The error is in the conservative
direction, so it could not have caused a quota overrun, but it would have
made the six look barely affordable and invited cutting one when in fact
there is headroom left over for the SimpleQA pilot. GSM8K (4.5-7.5%) sits
in the cheap bucket but is *not* one of the six; adding it gives
~29-40%.
