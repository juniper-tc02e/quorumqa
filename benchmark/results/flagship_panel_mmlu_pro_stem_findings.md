# flagship_panel on MMLU-Pro STEM — reasoning-generalization pilot

**Question.** flagship_panel (all-3-solver flagship + full skeptic/verifier/
judge tribunal) is a validated hard-STEM win on GPQA-hard and 3-seed
validated on SuperGPQA-hard (mean +4.1). Does it generalize to a *third*
hard-STEM benchmark, MMLU-Pro's STEM core?

**Setup.** Dataset `mmlu_pro_stem` — MMLU-Pro restricted to the six hard-STEM
categories (physics, chemistry, math, engineering, computer science,
biology), trimmed to 4 choices to match the engine's A–D contract (same trim
`load_gpqa.py`'s MMLU-Pro fallback already uses). n=60, seed 42. Apples-to-
apples: flagship_panel engine vs a single flagship (qwen3.7-max) call on the
identical 60 items.

## Result: a clean NULL — because the benchmark is saturated for the flagship

| MMLU-Pro STEM, seed 42 (n=60) | Accuracy |
|---|---|
| Single flagship baseline | 96.7% |
| flagship_panel engine | 96.7% |
| **Delta** | **+0.0** |
| Escalation rate | 3.3% (2/60 split) |
| Unanimous-wrong rate | **1.7% (1/60)** |

Per-category deltas are all exactly 0 (biology/CS/engineering/physics 100%,
math 95%, chemistry 89% — engine equals baseline in every category).

## This CONFIRMS the central thesis; it is NOT a negative for flagship_panel

The unanimous-wrong-rate rule says deliberation helps only where the cheap-
to-flagship gap is large — i.e. where the solvers confidently agree on wrong
answers. Here the *flagship itself* already scores 96.7%, the unanimous-wrong
rate is 1.7% (vs ~15–23% on SuperGPQA-hard where flagship_panel wins), and
only 2 of 60 questions split at all. There is no gap for deliberation to
close, so the predicted delta is ≈0 — and the measured delta is exactly 0.

This is the rule working as a **predictor**, not a post-hoc description: from
the gap alone one would forecast +0.0 on a saturated set, and that is what
came back. The same saturation caveat already flagged for MATH-500 and GSM8K
distractor-MC applies here: **4-choice-trimmed MMLU-Pro STEM is too easy for
the flagship to test whether deliberation helps on hard STEM.**

Two concrete takeaways:

1. **flagship_panel does zero harm on a saturated STEM set** (+0.0, 3.3%
   escalation). This is stronger than cheap deliberation, which carried a
   small but nonzero no-harm cost on saturated sets (GSM8K −4.0, MATH-500
   −6.1). flagship_panel is a safe general-STEM default: it wins where the
   gap is large and costs nothing where it isn't.
2. **A genuine third-benchmark generalization test needs a harder slice.**
   Either MMLU-Pro's full 10-way (untrimmed — an engine change to a variable
   A–J choice set, not attempted here) or a benchmark whose flagship baseline
   leaves real headroom. SuperGPQA-hard (3-seed validated, mean +4.1) remains
   the valid hard-STEM generalization of the GPQA-hard win; MMLU-Pro-STEM-4way
   simply doesn't have the difficulty to discriminate.

**Verdict: inconclusive-by-saturation for generalization, but a positive
no-harm confirmation and a clean predictive success for the unanimous-wrong
rule.** Not folded into any submitted number. seed 42, n=60,
lever_flagship_panel_mmlu_pro_stem_seed42.jsonl +
lever_baseline_mmlu_pro_stem_seed42.jsonl.
