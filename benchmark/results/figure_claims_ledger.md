# Figure claims ledger — the transcription contract

`figure_claims_ledger.csv` is the **only** file in this repository that a
figure script may cite as "our published, validated record." It exists
because that record otherwise lives nowhere machine-readable — it is prose,
scattered across a dozen `*_findings.md` files, and the one CSV that *is*
machine-readable (`f2_compute_frontier.csv`) answers a different question
and gives different numbers for the same-sounding (benchmark, config) pairs.
Plotting that CSV as if it were our record would silently publish numbers
that contradict our own docs. This document is the provenance firewall that
makes that structurally impossible: it defines four evidence tiers, states
which one each figure-relevant file belongs to, documents the three
confirmed traps where two tiers disagree, and maps every ledger row back to
the exact document and heading it was transcribed from.

`benchmark/figure_data.py` enforces this document programmatically:
`load_ledger()` / `load_frontier()` / `load_moo_small_n()` /
`load_subject_deltas()` / `load_agent_eras()` return four *distinct,
non-interchangeable* dataclasses (`PairedFrame`, `PooledFrame`,
`SmallNPairedFrame`, `LocalFrame`), and `verify_ledger()` greps every
non-empty numeric cell in the CSV against its cited source document, failing
loudly on any number that doesn't appear verbatim there.

---

## 1. The four provenance tiers

| Tier | Name | What it is | Legal use | Illegal use |
|---|---|---|---|---|
| **A** | Paired / published | Same-item, apples-to-apples comparisons transcribed from `*_findings.md` prose (or `agent_cost_calibration.csv`'s real `hardening_era` pairing). This is the number that appears in `docs/FINDINGS.md`, `docs/negative-results.md`, or a benchmark's own `_findings.md`. | Any figure captioned "our validated record," "shipped vs baseline," "N-seed result." | — |
| **B** | Pooled-marginal | `f2_compute_frontier.csv` — each (benchmark, config) accuracy computed over *whatever items that config happened to run*, pooled across every logged result file for that pair (full runs, resumes, adhoc checks, smoke tests, different seeds mixed together). | A whole-record compute-frontier / Pareto scatter, or an investment-allocation argument ("N of M benchmarks a bare flagship call dominates"). Always render with the `[POOLED-MARGINAL]` tag visible. | Citing one cell as "the" number for a (benchmark, config) pair without cross-checking the Tier A ledger first — see the three confirmed traps below. |
| **C** | Paired-small-n | `f5_difficulty_map.csv`, `moo_calibration_table.csv` (per-router-bucket calibration, n as low as 4–5 for `gpqa_hard_stem`), `family_floor_analysis_data.json`'s `f5_subject_breakdown` (per-subject deltas, some subjects at n=5). Paired by construction (same bucket / same subject's items) but at an n where per-row noise can swamp the effect. | Directional/diagnostic figures (e.g. "which router bucket needs more calibration data"), always labelled with its n. | Presenting a single small-n cell as a validated claim on its own. |
| **D** | Local-only | Raw `.jsonl` run logs and any other gitignored, uncommitted artifact. Never reproducible from a fresh clone. | Ad hoc local debugging only. | Any committed figure. `LocalFrame` exists in `figure_data.py` for interface completeness; no committed loader instantiates one — every figure-relevant number already has a Tier A/B/C home. |

The rule of thumb: **Tier A is what you plot as fact. Tier B is what you
plot as "everything we ever logged." Tier C is what you plot with error
bars the reader cannot ignore. Tier D never leaves your own terminal.**

---

## 2. The three confirmed CSV traps

Every trap below is the *same* shape: `f2_compute_frontier.csv` (Tier B,
pooled-marginal) and a `*_findings.md` write-up (Tier A, paired) both report
a number for the same (benchmark, config) pair, and the numbers disagree
because they answer different questions — "accuracy over every item this
config was ever run against" vs. "accuracy on the exact item set shared with
its comparator." Confirmed by direct inspection of both files as of this
writing:

1. **MMLU-Pro `flagship_panel`.** `f2_compute_frontier.csv` row
   `MMLU-Pro,flagship_panel,60,0.9666...,...,42` (accuracy 96.67%, n=60)
   against that same file's `MMLU-Pro,baseline_3.7max,110,0.9545...`
   (94.55%, **n=110** — pooled across multiple seeds/runs) reads as a
   **+1.2pp** pooled delta. But
   `flagship_panel_mmlu_pro_stem_findings.md` reports the real paired
   comparison — flagship_panel vs baseline on the **identical 60 items**,
   both scoring 96.7% — a **+0.0** delta. The pooled baseline's n=110
   blends in runs flagship_panel was never compared against; the paired
   n=60 comparison is the only one that answers "did the lever help on the
   questions it was actually tested on."

2. **GPQA-Diamond `shipped_engine`.** `f2_compute_frontier.csv` row
   `GPQA-Diamond,shipped_engine,183,0.7978...` pools `full_run.jsonl` +
   `full_run2.jsonl` + adhoc-check + smoke-test files into n=183 and a
   79.78% accuracy. The project's actual frozen, published submission
   number is **78.9% at n=90** — `full_run2.jsonl` alone, the file
   `benchmark/results/summary.md` and `docs/FINDINGS.md` both cite as *the*
   shipped result. The pooled 79.78%/n=183 figure has never appeared in any
   published write-up and should never be cited as "the shipped engine's
   accuracy."

3. **SuperGPQA-hard `flagship_panel`.** `f2_compute_frontier.csv` row
   `SuperGPQA-hard,flagship_panel,243,0.8271...` (82.7% pooled across all
   three validation seeds, n=243) sits between the per-seed raw readings
   (83.5%/81.9%/82.7%-ish, seed-dependent) but is **not** the number this
   project validated and published. The validated claim, from
   `supergpqa_findings.md`'s three-seed apples-to-apples comparison, is a
   **+4.1pp mean delta over the matched flagship baseline on each seed's
   common-item intersection** (+3.8 / +2.4 / +6.2 at seeds 42/7/123) — a
   *paired delta*, not a pooled absolute accuracy. The pooled 82.7% number
   answers a different question (what did flagship_panel score, period) and
   cannot be compared to the pooled baseline row on the same axis without
   reproducing trap #1's error.

**The general lesson:** every `f2_compute_frontier.csv` row's `n` column is
an early-warning signal. If a config's `n` doesn't match its comparator's
`n` for the same benchmark, the two rows were never scored on the same item
set, and any delta computed between them is not a paired comparison — check
the Tier A ledger (or the underlying `_findings.md`) before citing it.

---

## 3. The AIME exclusion

**No AIME row appears in this ledger, and none may be added until a clean
re-run produces its own result file.** The AIME cheap-tier pilot's first
(and only committed) run was invalidated by survivorship bias: 32/60 panel
items and 12/60 baseline items dropped (`ReadTimeout` ×56, HTTP 429 ×30) —
AIME's long thinking traces routinely exceeded the run's 300s timeout, and
concurrency-6 tripped the API rate limit, so the *hardest* problems (longest
traces, most likely to disagree or be wrong) were disproportionately the
ones that dropped. The n≈26–28 survivors produced a spurious "flash 100%, 0%
escalation" reading that was recognized as invalid and never reported as a
finding (`docs/improvement-loop-state.md`, "AIME cheap-tier run #1 =
INVALID"; corroborated in `docs/negative-results.md` Sec.4). Both AIME
result files present in this repo (`benchmark/results/aime_cheap_pilot_seed42.log`
and the raw survivor JSONLs) are survivor sets of that same invalidated run
— there is no clean AIME number anywhere in the committed record to
transcribe. `figure_data.py`'s `verify_ledger()` asserts this exclusion
programmatically (`EXCLUDED_BENCHMARKS`, checked against every ledger row's
`benchmark_label`).

---

## 4. Row → source map

Every row in `figure_claims_ledger.csv`, with the exact document and heading
it was transcribed from. `verify_ledger()` re-derives the verification half
of this table automatically (it greps `source_doc`, not `source_heading` —
the heading is a human navigation aid, the doc-level grep is the actual
safety check); this table is for a human auditing the transcription by eye.

| benchmark_label | config | build_stage | source_doc | source_heading |
|---|---|---|---|---|
| GPQA-Diamond | baseline_3.7max | reference | `benchmark/results/summary.md` | QuorumQA Benchmark Results |
| GPQA-Diamond | shipped_engine | v1 | `benchmark/results/summary.md` | QuorumQA Benchmark Results |
| GPQA-Diamond | thinking_gate | v2 | `benchmark/results/lever_findings.md` | Third-seed validation, and a targeting hypothesis that inverted |
| GPQA-Diamond | chem_thinking_gate | v2 | `benchmark/results/lever_findings.md` | chem_thinking_gate: the stack of both validated winners (VALIDATED: three fresh seeds) |
| GPQA-Diamond | chem_flagship_gate | v2 | `benchmark/results/lever_findings.md` | Third seed (888): validation bar met |
| GPQA-Diamond | five | v2 | `benchmark/results/lever_findings.md` | Levers tested / Full results, both seeds |
| GPQA-Diamond | thinking_all | v2 | `benchmark/results/lever_findings.md` | Full results, both seeds |
| GPQA-Diamond | subject | v2 | `benchmark/results/lever_findings.md` | Full results, both seeds — Seed 7 |
| GPQA-Diamond | combined | v2 | `benchmark/results/lever_findings.md` | Full results, both seeds |
| GPQA-Diamond | qwen38_judge | v2 | `benchmark/results/lever_findings.md` | qwen38_judge: a better judge is not the lever (negative result, mechanistically informative) |
| GPQA-Diamond | qwen3.8_solo | reference | `docs/negative-results.md` | §4 Methodological negatives — GPQA family-best bar (qwen3.8-solo) |
| GPQA-Diamond | smart_gate | v2 | `benchmark/results/lever_findings.md` | New lever tested: smart_gate |
| SuperGPQA-hard | baseline_3.7max | reference | `benchmark/results/supergpqa_findings.md` | Third seed (123): VALIDATION BAR MET |
| SuperGPQA-hard | shipped_engine | v1 | `benchmark/results/supergpqa_findings.md` | The headline refines our central hypothesis |
| SuperGPQA-hard | flagship_panel | v2 | `benchmark/results/supergpqa_findings.md` | Third seed (123): VALIDATION BAR MET |
| SuperGPQA-hard | rag_presolve | v2 | `benchmark/results/rag_r1_findings.md` | Fourth seed (271): the streak breaks — and reveals the failure mode |
| SuperGPQA-hard | rag_thinking_gate | v2 | `benchmark/results/rag_stack_findings.md` | VALIDATED (3 seeds) |
| SuperGPQA-hard | qwen38_panel | v2 | `benchmark/results/supergpqa_findings.md` | qwen38_panel (strongest solver tier): a mechanistically clean NEGATIVE |
| MMLU-Pro | baseline_3.7max | reference | `docs/negative-results.md` | §2 law table / A1. MMLU-Pro (full, 4-choice trim) — shipped engine −12 |
| MMLU-Pro | shipped_engine | v1 | `docs/negative-results.md` | §2 law table / A1. MMLU-Pro (full, 4-choice trim) — shipped engine −12 |
| MMLU-Pro | thinking_gate | v2 | `benchmark/results/lever_findings.md` | Does the doubt-gate generalize past GPQA-Diamond? |
| MMLU-Pro-STEM | baseline_3.7max | reference | `benchmark/results/flagship_panel_mmlu_pro_stem_findings.md` | Result: a clean NULL — because the benchmark is saturated for the flagship |
| MMLU-Pro-STEM | flagship_panel | v2 | `benchmark/results/flagship_panel_mmlu_pro_stem_findings.md` | Result: a clean NULL — because the benchmark is saturated for the flagship |
| LEXam | baseline_3.7max | reference | `docs/negative-results.md` | E1. LEXam law — shipped engine −14 |
| LEXam | shipped_engine | v1 | `docs/negative-results.md` | E1. LEXam law — shipped engine −14 |
| LEXam | thinking_gate | v2 | `benchmark/results/lever_findings.md` | Does the doubt-gate generalize past GPQA-Diamond? |
| MedQA | baseline_3.7max | reference | `benchmark/results/medqa_findings.md` | Headline: a tie, and that is itself the finding |
| MedQA | shipped_engine | v1 | `benchmark/results/medqa_findings.md` | Headline: a tie, and that is itself the finding |
| MATH-500-open | baseline_3.7max | reference | `benchmark/results/math_open_pilot_findings.md` | Result (corrected — see the grader caveat, it is the headline finding) |
| MATH-500-open | flagship_panel | v2 | `benchmark/results/math_open_pilot_findings.md` | Result (corrected — see the grader caveat, it is the headline finding) |
| MATH-500-open | cheap_panel | v2 | `benchmark/results/math_open_pilot_findings.md` | Follow-up: the SHIPPED-engine tier (cheap solvers + flagship judge) — DECISIVE |
| MATH-500-MC | baseline_3.7max | reference | `benchmark/results/math_findings.md` | Headline: the benchmark saturated the flagship, so it can't test us |
| MATH-500-MC | shipped_engine | v1 | `docs/negative-results.md` | A5. MATH-500 level-5 distractor-MC — shipped engine −6.1 |
| GSM8K | baseline_3.7max | reference | `benchmark/results/math_findings.md` | GSM8K (easy math, distractor-MC) — the no-harm confirmation |
| GSM8K | shipped_engine | v1 | `benchmark/results/math_findings.md` | GSM8K (easy math, distractor-MC) — the no-harm confirmation |

---

## 5. Column conventions (so a figure script doesn't have to guess)

- **`build_stage`** — `v1` (the shipped cheap-panel engine), `v2` (a lever
  variant on top of it), or `reference` (a single-flagship baseline or a
  solo model run standalone, no panel/tribunal).
- **`per_seed_delta_pp`** — semicolon-separated per-seed deltas, in the
  exact form the source doc prints them. A tied seed is transcribed as the
  literal word `tie` (not a fabricated `+0.0`) when that is what the source
  table says — see GPQA `thinking_gate`'s seed-7 entry. `verify_ledger()`
  skips non-numeric tokens like `tie` rather than treating them as an
  unverifiable claim.
- **`mean_delta_pp` / `absolute_accuracy_pct`** — filled **only** when the
  source doc states that exact aggregate figure verbatim (e.g. SuperGPQA
  `flagship_panel`'s explicit "Mean **+4.1**"). Where a doc gives per-seed
  numbers but never states a mean (e.g. GPQA `thinking_gate`'s 86.7/86.5/
  86.7), `absolute_accuracy_pct` carries the semicolon-separated per-seed
  list instead of a silently-computed average — every number in this ledger
  must be one `verify_ledger()` can find verbatim in its cited doc, and an
  average nobody printed is not transcribable, it is invented.
- **`net_discordant_items` / `mcnemar_p`** — left empty on almost every row.
  None of the `_findings.md` write-ups report a formal computed McNemar
  p-value or exact net-discordant count *per specific result*; they discuss
  the pre-registered **bar** (docs/experiment-spec-book.md §1.1: net ≥+5 at
  one seed, or ≥+3 at 2-of-3 seeds pooled) as a general house standard, not
  as a per-row measured statistic. The one exception is `qwen38_judge`,
  whose write-up states "fixed 1, broke 3 -- net **−2**" explicitly.
- **`contaminated` / `contamination_note`** — `TRUE` only for the three rows
  flagged as survivorship-contaminated in `docs/negative-results.md` §4:
  `qwen38_judge` (GPQA, n=76/90 survivors), `qwen3.8_solo` (GPQA, 73/78
  survivors), `qwen38_panel` (SuperGPQA, common-item set is the easier
  survivorship tail). Every `TRUE` row carries a non-empty
  `contamination_note`; `figure_data.py`'s `CONTAMINATION_FOOTNOTES` dict
  mirrors these three for direct use in figure captions.
- **`mean_tokens_per_q`** — left empty throughout. The paired `_findings.md`
  write-ups this ledger transcribes from report either nothing or
  pre-Token-Plan-migration USD costs (which the project's own methodology
  section, `docs/FINDINGS.md` §5, disclaims: "Cost is measured in tokens,
  not price-list dollars"); no paired doc gives a clean mean-tokens-per-
  question figure for these specific rows, so the cell is left empty rather
  than backfilled from the pooled, differently-scoped
  `f2_compute_frontier.csv`.

## 6. Rows deliberately not included

- Coding-agent hardening (`36% → 86%` graded coverage, `docs/FINDINGS.md`
  §2) is not a benchmark-accuracy row in this schema — it belongs to
  `load_agent_eras()`'s `agent_cost_calibration.csv` frame instead, which
  pairs by `(task_name, hardening_era)`, not by question id.
- GPQA `flagship_panel` (three noisy single-seed readings, "not
  statistically established" per `lever_findings.md`'s own honest framing)
  is left out of the ledger by design — the row would need the same
  same-seed-baseline discipline given to `thinking_gate`, and the source
  document itself declines to call it a settled result.
