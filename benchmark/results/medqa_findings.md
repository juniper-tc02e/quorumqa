# MedQA (biology/medicine) pilot findings

Fourth non-GPQA benchmark, first in the biology/medicine domain. n=50,
seed 42, USMLE-style native 4-option (no trimming — see load_medqa.py).

## Headline: a tie, and that is itself the finding

| MedQA, n=50, seed 42 | Accuracy |
|---|---|
| Single flagship baseline | 94.0% |
| QuorumQA engine | 96.0% |

**+2.0 points = one question out of 50. This is a tie, not a win** —
squarely inside the noise floor, and reported as such. No overturn drove
it (0 overturns on 3 escalations); the 1-question edge is the cheap panel's
majority vote beating a single flagship call on one item, which is exactly
what self-consistency does by chance at this n. Do not cite MedQA as a
QuorumQA win.

## Why the tie matters: it confirms the refined gap-lens

MedQA is the control case the SuperGPQA finding predicted. The refined
hypothesis (from supergpqa_findings.md) says the engine's outcome is
governed by the cheap-tier-to-flagship GAP, best measured by the
unanimous-wrong rate:

| Benchmark | Flagship baseline | Unanimous-wrong | Engine vs baseline |
|---|---|---|---|
| GPQA-Diamond | 84-86% | ~11% | −5.5 (closes most of it) |
| LEXam | 86% | elevated | **−14** |
| MMLU-Pro | 94% | ~14% | **−12** |
| SuperGPQA-hard | 79% | **23%** | **−11.6** |
| **MedQA** | 94% | **4%** | **+2 (tie)** |

MedQA and MMLU-Pro have the SAME near-ceiling baseline (94%), yet MedQA
ties while MMLU-Pro lost 12 points. The single thing that differs is the
unanimous-wrong rate: 4% vs 14%. On MedQA the cheap tier (`qwen3.6-flash`)
genuinely knows medicine — it rarely agrees confidently on a wrong answer
— so the uncatchable floor is tiny and deliberation does no harm. This is
direct confirmation that **unanimous-wrong rate, not baseline height, is
the predictor** of whether QuorumQA helps, ties, or hurts.

## What it means for Mixture of Orchestrations

MedQA is a `single-call`-or-`standard-tribunal` domain, NOT a
`flagship_panel` domain. The router's decision rule sharpens:

- **Low unanimous-wrong (cheap tier competent, e.g. medicine):** cheap
  deliberation is safe — it ties the flagship at a fraction of the cost.
  The escalation machinery adds little here (6% escalation, 0 overturns)
  but does no harm, and the cheap panel's cost is far below a flagship
  call. This is arguably QuorumQA's *ideal* economic case: flagship-level
  accuracy, cheap-tier cost.
- **High unanimous-wrong (cheap tier out of depth, e.g. hard STEM):**
  route the panel to the flagship tier (`flagship_panel`, validated to
  generalize on SuperGPQA-hard) or to `single-call`.

The practical problem the router still has to solve: unanimous-wrong rate
is only knowable with the answer key, which product traffic doesn't have.
The calibration memory (MoO plan §5.1) is the answer — accumulate
per-domain unanimous-wrong statistics from every run, so the router
learns "medicine is a low-gap domain, hard-chemistry is a high-gap
domain" from history rather than needing the current question's label.
MedQA + SuperGPQA are the first two real rows of that table.

## Caveats

- n=50, single seed, +2 = 1 question. The TIE is the finding; the sign of
  the delta is not meaningful.
- The 4% unanimous-wrong (2 questions) is itself a small-sample estimate;
  a larger MedQA run would firm up the "cheap tier is competent at
  medicine" claim, but the contrast with SuperGPQA's 23% is stark enough
  to trust the direction.
- Native 4-option, no trimming, so unlike the SuperGPQA/MMLU-Pro pilots
  these absolute numbers ARE comparable to other 4-option MedQA reports
  (modulo the specific 50-question sample).
