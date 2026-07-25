# Stability audit, repaired (F1) — offline log-mining

Implements `docs/capability-roadmap.md` section 4 FREE-tier item **F1**: "Stability
audit, repaired: re-key on choice TEXT (`load_gpqa._shuffle_choices` reshuffles per
seed), score at item level via text-majority, report lift vs a permutation null
preserving each item's replicate-answer multiset — Whether the instability signal
survives its own mechanical floor; gates every stability lever and CAL-2." Pure
offline JSONL mining, zero API calls, zero cost. Script:
`benchmark/analyze_stability_repaired.py`. Reproduce:

```
.venv/Scripts/python.exe benchmark/analyze_stability_repaired.py
```

Writes `benchmark/results/stability_audit_items.csv` (every multi-replicate item:
k/r/w, stability, majority verdict, contributing configs) and
`benchmark/results/stability_audit_summary.json` (full per-benchmark and overall
real + null aggregates) — every number below is traceable to one of those two files.
Both stdout and the CSV/JSON outputs were verified byte-for-byte identical across two
consecutive runs (deterministic given the fixed permutation-null seed).

## 0. What "repaired" means here

Three corrections applied, exactly as specified:

1. **Key on choice TEXT, never letter.** `load_gpqa._shuffle_choices` reshuffles the
   A–D↔choice-text mapping independently per seed. Every replicate's chosen letter is
   mapped back to its own choice-text via **that row's own** `item.choices` list
   before any cross-row comparison — never via another row's shuffle. Choice text is
   whitespace-normalized (collapse runs of whitespace, strip) first: raw text
   otherwise disagreed on trailing-newline artifacts alone in 12 GPQA items and the
   gold-text cross-check (below) initially showed 12 false "disagreements" that
   vanished entirely once normalized.
2. **Score at ITEM level via text-majority.** An item's verdict is the plurality
   vote (`Counter.most_common`, first-seen tie-break) of its replicates' chosen
   TEXTS, not any single replicate's answer.
3. **Permutation null.** Holds each item's real right/wrong replicate COUNT fixed
   (`r` correct, `w` wrong — "the replicate-answer multiset") and randomly
   reassigns, independently per Monte Carlo draw, which of the item's *observed*
   wrong choice-texts each wrong replicate lands on. Correct replicates are always
   the single correct text (nothing to shuffle there). NDRAWS=5,000, fixed seed
   **20260725**, ties in the per-draw plurality broken uniformly at random (a
   first-seen rule has no meaning inside a synthetic draw).

## 1. Inventory — what's usable and what isn't

**74 committed files. 67 contributed ≥1 observation, 7 excluded entirely:**

| Reason | Files |
|---|---|
| Flat row, no `item`/`choices` field to map a letter to text | `aime_open_baseline_seed42`, `math_open_baseline_seed42`, `qwen38_baseline_seed123`, `lever_gate_replay` |
| Open-answer schema (`answer`/`temperature`, no letter+choices) | `aime_open_panel_cheap_seed42`, `math_open_panel_cheap_seed42`, `math_open_panel_seed42` |

`qwen38_baseline_seed123.jsonl` is a **notable, disclosed loss**: its rows carry only
`{question_id, subject, answer_letter, correct_letter, correct, usage, latency_s}` —
no `choices` field at all, anywhere in the file — so its (family-best-model) answers
cannot be re-keyed to text and are absent from this analysis, unlike the family-floor
analysis which could use it (that script only needed the `correct` boolean, not text).

**Replicate definition (broader than the selector audit's within-row pools):**
every graded top-level answer this repo has ever logged for an item counts as one
replicate — bare `baseline_3.7max` single calls, the shipped `engine` under every
lever, `self_consistency5`, and `moo_m1_eval`'s 7 profiles all count, because they
are independent "solves" of the same underlying item, which is exactly the axis F1
asks about ("solved by multiple configs/seeds"). 6,644 observations extracted →
1,043 distinct (benchmark, question_id) items.

**Gold-text consistency check (load-bearing — an item is only a valid replicate set
if every replicate agrees on what "correct" even means):** after whitespace
normalization, **0/1,039 multi-replicate items show gold-text disagreement across
replicates** — full agreement, methodology validated.

**Sanity check:** recomputed correctness (`chosen_text == gold_text`) vs each row's
own logged `correct` field — **6,644/6,644 observations checked, 0 mismatches.**

**Disclosed data-quality finding, not asked for but worth flagging:** for MMLU-Pro
(26/83 items) and SuperGPQA-hard (15/522 items), the union of observed wrong
choice-texts across an item's replicates exceeds 3 distinct strings — i.e. the
loader is **resampling which distractors appear**, not just reshuffling their order,
for some items across different runs. The permutation null uses the union of
*actually observed* wrong texts per item as its redraw pool (a disclosed, minor
approximation — a hypothetical extra replicate could in principle see a distractor
never yet observed for that item; the null cannot sample from what was never logged).

**Items with ≥2 replicate observations (the analysis pool): 1,039** — mean
replicates/item ranges from 2.0 (GSM8K, MATH-500-MC — only `baseline`/`engine`
pairs logged) to 16.5 (GPQA-Diamond, thanks to its large number of distinct lever
configs).

## 2. Real (observed) results, per benchmark

| Benchmark | n items | mean replicates/item | instability rate | P(wrong\|stable) | P(wrong\|unstable) | LIFT |
|---|---:|---:|---:|---:|---:|---:|
| GPQA-Diamond | 195 | 16.5 | 41.0% | 1.7% (2/115) | 20.0% (16/80) | **+18.3pp** |
| SuperGPQA-hard | 522 | 4.0 | 31.2% | 17.3% (62/359) | 39.3% (64/163) | **+22.0pp** |
| LEXam | 90 | 3.7 | 27.8% | 9.2% (6/65) | 52.0% (13/25) | **+42.8pp** |
| MMLU-Pro | 83 | 5.8 | 12.0% | 2.7% (2/73) | 30.0% (3/10) | +27.3pp |
| MedQA | 50 | 6.2 | 2.0% | 4.1% (2/49) | 100.0% (1/1) | +95.9pp (n=1 unstable, unreliable) |
| GSM8K | 50 | 2.0 | 4.0% | 0.0% (0/48) | 0.0% (0/2) | +0.0pp |
| MATH-500-MC | 49 | 2.0 | 6.1% | 0.0% (0/46) | 0.0% (0/3) | +0.0pp |
| **OVERALL** | **1,039** | **6.4** | **27.3%** | **9.8% (74/755)** | **34.2% (97/284)** | **+24.4pp** |

At face value, every benchmark with a usable unstable pool shows a large, positive
lift — the raw signal every prior write-up in this repo has already quoted
(unanimous-wrong rates of similar magnitude appear throughout `improvement-loop-state.md`
and the roadmap). **This is exactly the number the permutation null exists to
interrogate.**

## 3. Does it survive the permutation null?

| Benchmark | observed lift | null lift mean | null 95% CI | empirical p(null ≥ observed) | Verdict |
|---|---:|---:|---:|---:|---|
| GPQA-Diamond | +18.3pp | +17.5pp | [+15.8, +19.5]pp | 0.4186 | **DOES NOT SURVIVE** |
| SuperGPQA-hard | +22.0pp | +20.7pp | [+16.4, +24.6]pp | 0.3194 | **DOES NOT SURVIVE** |
| LEXam | +42.8pp | +42.9pp | [+30.8, +54.8]pp | 0.6412 | **DOES NOT SURVIVE** |
| MMLU-Pro | +27.3pp | +27.3pp | [+27.3, +27.3]pp (degenerate — see note) | 1.0000 | **DOES NOT SURVIVE** |
| MedQA | +95.9pp | +46.1pp | [−4.1, +95.9]pp | 0.5014 | **DOES NOT SURVIVE** (n=1, uninformative) |
| GSM8K | +0.0pp | +50.0pp | [+0.0, +100.0]pp | 1.0000 | n too small to be informative (2 unstable items) |
| MATH-500-MC | +0.0pp | +49.8pp | [+0.0, +100.0]pp | 1.0000 | n too small to be informative (3 unstable items) |
| **OVERALL** | **+24.4pp** | **+24.1pp** | **[+21.5, +26.9]pp** | **0.4774** | **DOES NOT SURVIVE** |

**On every benchmark where the null is well-powered (GPQA-Diamond, SuperGPQA-hard,
LEXam, and the pooled OVERALL), the observed lift lands almost exactly on the null
mean** — GPQA-Diamond's +18.3pp observed vs +17.5pp null mean; SuperGPQA-hard's
+22.0pp vs +20.7pp; LEXam's +42.8pp vs +42.9pp (essentially identical); overall
+24.4pp vs +24.1pp. Empirical p-values (fraction of 5,000 null draws at or above the
observed lift) sit at 0.32–0.64 everywhere — nowhere close to a one-tailed 0.05
significance threshold in the direction that would indicate a genuine
above-mechanical-floor signal.

**MMLU-Pro's degenerate, exactly-flat null CI is not a bug** (verified directly by
re-running the per-item simulator standalone): every one of MMLU-Pro's 10 real
unstable items has either only 1 distinct observed wrong text (`m=1`, meaning the
null has literally nothing to randomize — every wrong replicate is forced onto the
same single bin) or a replicate-count profile where the majority outcome is
arithmetically fixed regardless of how the wrong votes are distributed among 2 wrong
bins. The null therefore reproduces the real value in all 5,000 draws — the
strongest possible "does not survive" result: this benchmark's instability-wrongness
correlation has **zero degrees of freedom** to be anything other than what the
mechanical floor already dictates.

**MedQA, GSM8K, MATH-500-MC are underpowered, not evidence either way** — 1–3
unstable items each is too few for the null (or the real lift) to mean anything;
GSM8K's and MATH-500-MC's own real lift is exactly 0.0pp because the handful of
unstable items happened to still land on the correct majority both times.

## 4. Verdict, stated plainly

**Instability does NOT survive its own mechanical floor, on every benchmark where
the question is answerable.** The observed P(wrong|unstable) > P(wrong|stable) gap
this repo has repeatedly quoted (and which motivated META-2's paid permutation-panel
probe) is, on the current logged data, **fully explained by the combinatorics of
one-correct-option-vs-several-wrong-options** — an item whose replicates disagree is
mechanically guaranteed to contain at least one wrong replicate (disagreement is
impossible if all replicates are correct, since they'd all report the identical
correct text), and whether an all-wrong item's votes happen to concentrate on one
wrong text (reading "stable") or scatter across several (reading "unstable") is
close to a coin flip once there is more than one available wrong option — exactly
the artifact F1 was built to isolate and, if present, subtract.

This is stated as a *repaired-log-mining* result, with the honest limits that come
with it: the null's wrong-text redraw pool is bounded by what was *actually
observed* for each item (never texts the loader could theoretically have produced
but didn't), and the largest, best-powered benchmarks (GPQA-Diamond, SuperGPQA-hard)
still show the effect landing on the null mean rather than merely "inside a wide CI"
— the strongest form this null result can take with the currently logged data.

## 5. Decision consequences

- **This is a KILL, and kill dominates bar per the house statistical standard
  (`docs/capability-roadmap.md` §1.5).** Per F1's own stated purpose ("gates every
  stability lever and CAL-2"): **do not build an instability-fed router, do not
  build a paraphrase/permutation escalation trigger on top of raw agree/disagree,
  and do not treat the unanimous-wrong floor as reducible by cheap resampling
  alone** — this repairs and confirms, on already-logged data, the same conclusion
  the roadmap's separate META-2 paid-probe kill criterion was designed to test
  (`docs/experiment-spec-book.md` §"META-2": "Contrast gap < 10pt or p > 0.2 →
  permutation instability is NOT a wrongness signal ... This kill also finishes
  META-1"). If META-2's paid permuted_panel probe has not yet been run, this F1
  result is a strong prior that it will land the same way, for zero tokens.
- **W5's "instability features are the last untried family" framing
  (`docs/capability-roadmap.md` §5, "Score- or confidence-based accuracy gating")
  should be downgraded further.** This result adds choice-text-repaired,
  permutation-null-corrected evidence to the existing AUC-0.625 BAND finding — two
  independent measurements now point the same direction on the same broad claim.
- **Positive, reusable output:** the (r, w, m)-parameterized permutation-null
  simulator (`simulate_item_draw` in `benchmark/analyze_stability_repaired.py`) is
  small, fast (5,000 draws × 1,039 items in under 5 seconds), and general — it can
  be reused as-is against the paid META-2 permuted_panel logs once/if they land, to
  give that probe the same mechanical-floor correction for free.
- **The MMLU-Pro finding (zero degrees of freedom, m=1 for every unstable item) is
  itself informative beyond the headline verdict**: it says MMLU-Pro's genuinely
  low instability rate (12.0%, the lowest of the well-covered benchmarks) rarely
  produces more than one distinct wrong answer among disagreeing replicates in the
  first place — a saturation signal consistent with `docs/capability-roadmap.md`
  §5's separate finding that MMLU-Pro is a saturated, single-call-dominant surface.
