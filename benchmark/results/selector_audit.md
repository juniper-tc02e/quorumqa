# Selector audit (SEL-1 / S1) — zero-token log-mining

Implements `docs/experiment-spec-book.md` section 3's **S1** ("Zero-token selector
audit over the ... already-logged ... pools | 0 | P0") and `docs/capability-roadmap.md`
section 4 FREE-tier item **F3** in the firing order ("`audit_selectors.py` selector
audit over the deduped logged pools | SEL-1 | yes [can kill]"). Pure offline JSONL
mining, zero API calls, zero cost. Script: `benchmark/audit_selectors.py`. Reproduce:

```
.venv/Scripts/python.exe benchmark/audit_selectors.py
```

Writes `benchmark/results/selector_audit_rows.csv` (every usable row, all 5 selector
outcomes) and `benchmark/results/selector_audit_summary.json` (full per-benchmark and
overall aggregates, McNemar tables, bar verdicts) — every number below is traceable to
one of those two files.

## 0. What was audited

Five selectors were reconstructed over every already-logged multi-seat solver pool
(`solver_answers[]`, each entry carrying `letter` + `confidence` + `reasoning`),
strictly **within each row** — never joined across rows on letter identity, since
`load_gpqa._shuffle_choices` reshuffles the A–D↔choice-text mapping per seed:

- **(a) plain letter-plurality** — the shipped baseline (`Counter.most_common`,
  first-seen tie-break, verified byte-for-byte identical to
  `src/quorumqa/engine/orchestrator.py`'s and `profiles.py`'s `_plurality()`).
- **(b) confidence-weighted vote** — sum confidence per letter, argmax (same tie-break).
- **(c) max-single-confidence** — the letter of the single most-confident seat.
- **(d) longest-reasoning** — the letter of the seat with the longest reasoning string.
  A **deliberate junk selector**: if it wins, confidence/plurality signals carry no
  more information than verbosity.
- **(e) ORACLE** — was the gold letter proposed by *any* seat in the pool? The
  coverage ceiling, and the single most important number in this report.

**Methodology validated before trusting any downstream number:** the recomputed
plurality letter was cross-checked against each row's own logged `plurality_letter`
field. **5,451/5,451 rows matched exactly, 0 mismatches.**

## 1. Inventory — what's usable and what isn't

**74 committed `benchmark/results/*.jsonl` files. 61 used, 13 excluded**, every
exclusion reason mechanically diagnosed, not guessed:

| Reason | Files | n |
|---|---|---|
| Single flagship call only, no panel (`lever_baseline_*`) | `lever_baseline_gpqa_seed314`, `lever_baseline_mmlu_pro_stem_seed42`, `lever_baseline_seed123`, `lever_baseline_seed7`, `lever_baseline_supergpqa_seed123`, `lever_baseline_supergpqa_seed7` | 6 |
| Open-answer math: `solver_answers` present but entries carry `answer`/`temperature`, not `letter`/`confidence` (AIME/MATH-500-open panels have no MC letter pool to select over) | `aime_open_panel_cheap_seed42`, `math_open_panel_cheap_seed42`, `math_open_panel_seed42` | 3 |
| No `solver_answers` field at all (single-call baseline) | `aime_open_baseline_seed42`, `math_open_baseline_seed42` | 2 |
| Flat single-model row (`qwen38_baseline.py`), no panel | `qwen38_baseline_seed123` | 1 |
| Gate-replay analysis artifact, different schema entirely (`was_unanimous_correct`/`gate_doubt`/`gate_cost_usd`), no fresh solver pool | `lever_gate_replay` | 1 |

The 61 used files fall into three row-wrapping conventions, all handled: flat
(`self_consistency5`-style, not applicable here), `engine`-wrapped (`lever_*` and
combo pilot files), and `result`-wrapped (`moo_m1_eval.jsonl`, 827 rows across 4
buckets × 7 profiles — the single largest contributor). **Total: 5,451 usable
candidate pools**, spanning 3–5 seats each (most panels run 3 seats;
`lever_five_seed42.jsonl` runs 5). All pools are 4-choice MC (verified: every one of
the 5,451 pools' `item.choices` has length exactly 4). 17 of 16,297 individual
seat-answers (0.1%) carry an empty-string `letter` (a solver parse failure) — handled
correctly (never matches the gold letter, never wins a tie) rather than crashing.

**Data caveat, disclosed rather than silently absorbed:** 390/16,297 seat-answers
(2.4%) carry an empty `reasoning` string, spread thinly across ~30 files (max
concentration `lever_control_lexam_seed42.jsonl` at 45/270 = 16.7%) — not
concentrated in one bad file. This directly affects the longest-reasoning junk
selector's tie-break on those specific rows (falls back to first-seat order).

## 2. Per-benchmark results

McNemar notation (standard, **not** the same as selector labels (b)/(c) above):
`b` = rows where the alt selector is right and plurality is wrong (**selector
gain**); `c` = rows where plurality is right and the alt selector is wrong
(**selector loss**); `net = b − c`; exact two-sided p-value via
`scipy.stats.binomtest(b, b+c, 0.5, alternative="two-sided")`.

**Pre-registered bar (task spec, applied identically everywhere):** a selector WINS
iff `n_discordant = b+c ≥ 12` **AND** `net ≥ 5` **AND** `p < 0.05`. ORACLE is exempt
from the bar — it is a coverage ceiling, not a deployable selector (it cheats by
knowing the gold letter).

| Benchmark | n | plurality acc | oracle coverage | headroom (oracle−plurality) |
|---|---:|---:|---:|---:|
| GPQA-Diamond | 2,601 | 72.82% | 85.97% | **+13.15pp (+342 items)** |
| SuperGPQA-hard | 1,842 | 59.45% | 74.16% | **+14.71pp (+271 items)** |
| MMLU-Pro | 369 | 88.35% | 91.33% | +2.98pp (+11 items) |
| MedQA | 260 | 94.23% | 96.15% | +1.92pp (+5 items) |
| LEXam | 280 | 68.57% | 76.43% | +7.86pp (+22 items) |
| MATH-500-MC | 49 | 89.80% | 93.88% | +4.08pp (+2 items) |
| GSM8K | 50 | 94.00% | 96.00% | +2.00pp (+1 item) |
| **OVERALL** | **5,451** | **70.50%** | **82.50%** | **+12.00pp (+654 items)** |

Selector results (accuracy, McNemar b/c/net/p, bar verdict):

**GPQA-Diamond (n=2,601):**

| Selector | acc | Δ vs plurality | b | c | n_disc | net | p (two-sided) | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| confidence-weighted | 73.66% | +0.85pp | 29 | 7 | 36 | +22 | 0.0003 | **WINS** |
| max-single-confidence | 74.93% | +2.11pp | 141 | 86 | 227 | +55 | 0.0003 | **WINS** |
| longest-reasoning (junk) | 66.05% | −6.77pp | 73 | 249 | 322 | −176 | <0.0001 | loses (correctly rejected) |

**SuperGPQA-hard (n=1,842):**

| Selector | acc | Δ vs plurality | b | c | n_disc | net | p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| confidence-weighted | 60.80% | +1.36pp | 33 | 8 | 41 | +25 | 0.0001 | **WINS** |
| max-single-confidence | 63.57% | +4.13pp | 137 | 61 | 198 | +76 | <0.0001 | **WINS** |
| longest-reasoning (junk) | 54.07% | −5.37pp | 64 | 163 | 227 | −99 | <0.0001 | loses (correctly rejected) |

**OVERALL, pooled (n=5,451):**

| Selector | acc | Δ vs plurality | b | c | n_disc | net | p | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| confidence-weighted | 71.40% | +0.90pp | 65 | 16 | 81 | +49 | <0.0001 | **WINS** |
| max-single-confidence | 72.72% | +2.22pp | 294 | 173 | 467 | +121 | <0.0001 | **WINS** |
| longest-reasoning (junk) | 64.74% | −5.76pp | 148 | 462 | 610 | −314 | <0.0001 | loses (correctly rejected) |

**MMLU-Pro, MedQA, LEXam, MATH-500-MC, GSM8K:** thin discordant volume everywhere
(n_disc ranges 0–27), no selector clears `n_disc ≥ 12` **and** `net ≥ 5` **and**
`p<0.05` simultaneously on any of these five benchmarks. Full per-benchmark tables
(all 5 selectors × all 7 benchmarks) are in `selector_audit_summary.json`.

## 3. Which selectors clear the bar

**CLEAR THE BAR:** `confidence_weighted` and `max_single_confidence`, but **only** on
GPQA-Diamond, SuperGPQA-hard, and the pooled OVERALL figure. Both are driven almost
entirely by those two large-n, large-gap benchmarks — the five smaller/saturated
benchmarks (MMLU-Pro, MedQA, LEXam, MATH-500-MC, GSM8K) never accumulate 12
discordant items for any selector, so no verdict is reachable there regardless of the
true effect size (an honest power limitation, not a null result).

**DOES NOT CLEAR THE BAR anywhere:** `longest_reasoning`. It loses to plain
plurality on every single benchmark where it's measurable, most severely on
GPQA-Diamond (net −176) and SuperGPQA-hard (net −99), with p < 0.0001 in both cases.
**This is the report's cleanest finding: the junk selector loses badly and
consistently, which means confidence signals are NOT noise** — if verbosity had been
as good a proxy as (or better than) the shipped confidence field, that would have
been a serious indictment of the whole confidence-weighting premise. It is the
opposite: `max_single_confidence` (net +121 overall, the single strongest result in
this audit) and `confidence_weighted` (net +49) both clear the bar decisively, while
the structurally-similar-looking junk selector fails just as decisively.

## 4. The most important number: ORACLE coverage headroom

Oracle coverage (was the gold letter proposed by *any* seat) exceeds plurality
accuracy by **+12.00pp / +654 items overall**, concentrated almost entirely in
GPQA-Diamond (+13.15pp / +342 items) and SuperGPQA-hard (+14.71pp / +271 items) — the
same two benchmarks where the winning selectors clear the bar. This matches
`docs/experiment-spec-book.md` §3's S2 framing exactly: the generation side of these
pools already contains the right answer far more often than the shipped
letter-plurality selector surfaces it. **`max_single_confidence` closes 55/342
(16.1%) of GPQA-Diamond's oracle-plurality gap and 76/271 (28.0%) of SuperGPQA-hard's
gap** (net gain ÷ headroom items) — real, measured, and still leaving most of the
oracle headroom on the table for a smarter selector (verifier-selected, S5; held-out
confirmation, S7).

## 5. Decision consequences

- **`max_single_confidence` is the strongest zero-token selector improvement found
  in this repo to date.** It is trivially cheap to ship (no new tokens, no new
  calls — it only changes which already-computed letter gets reported) and clears
  the pre-registered bar with the largest margin of any candidate (net +121, p <
  0.0001 overall). Recommend it as the new default selector ahead of plain
  plurality, pending S7's held-out confirmation on fresh, disjoint seeds/pools (a
  selector chosen on the pool it was scored against is fitted to that pool — this
  audit is exactly the S1/S3 zero-token screen S7 exists to confirm, not a
  substitute for it).
- **`confidence_weighted` also clears the bar** but with a smaller, though still
  significant, margin (net +49 overall vs +121) — a reasonable second candidate,
  useful if `max_single_confidence`'s single-seat dependence turns out to be
  fragile under S7's held-out test.
- **The junk-selector control worked as designed and returned a clean, confidence-affirming
  null**: reasoning length is not standing in for confidence, and confidence is not
  standing in for noise.
- **Oracle coverage headroom (+12pp overall, +342/+271 items on GPQA/SuperGPQA-hard)
  is larger than what either winning selector currently captures** — this is the
  number that should drive the SEL-family's S2 generation-vs-selection ROI decision
  (`docs/experiment-spec-book.md` §3): a smarter selector (verifier-gated, S5) or a
  bigger pool (S2/S6) both have real, measured headroom to chase here, on exactly
  the two benchmarks where this project already has the most logged data.
- **MMLU-Pro/MedQA/LEXam/MATH-500-MC/GSM8K are underpowered for this question with
  currently-logged data** (discordant counts too thin to clear the bar in either
  direction) — not evidence of "no selector effect there," just evidence that more
  logged pools would be needed before a verdict is reachable on those five surfaces.
