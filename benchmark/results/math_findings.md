# Math (MATH-500 level-5, distractor-MC) pilot findings

Fifth non-GPQA benchmark, math domain. n=49/50, seed 42, MATH-500 level-5
(hardest), each open-answer converted to 4-option via distractor synthesis
(see load_math.py — NOT comparable to published open-answer MATH scores).

## Headline: the benchmark saturated the flagship, so it can't test us

| MATH-500 L5 distractor-MC, n=49 | Accuracy |
|---|---|
| Single flagship baseline | **100.0%** |
| QuorumQA engine | 93.9% |

The flagship got a **perfect 100%**. This is the distractor-eliminability
caveat (flagged when the loader was built) biting exactly as predicted:
the synthetic distractors (order-of-magnitude slip, sign flip, ±5-30%
near-miss) are trivially eliminable by a model that simply *computes* the
answer and matches it — no reasoning about the distractors needed. So a
strong model saturates, and the "multiple choice" framing removes the
difficulty that makes open-answer MATH hard.

**Consequence: this pilot cannot tell us whether deliberation helps on
hard math.** With the baseline at 100% there is zero headroom; the engine
can only tie or lose, and it lost 6.1 points (3 questions) because the
cheap panel occasionally picks an eliminable distractor the flagship never
would. That is a fact about distractor-MC, not about math reasoning.

## What it does tell us (two real things)

1. **Distractor-MC is the wrong instrument for math.** A genuine test of
   QuorumQA on hard math needs open-answer numeric-equivalence grading (a
   SymPy-backed checker comparing the model's final answer to the gold
   answer), which is an ENGINE change — the current engine only compares
   an A-D letter. This is the `math-verified` profile's real prerequisite,
   and it's now concretely scoped: not "add a SymPy verifier tool" but
   "add an open-answer grading path," a bigger change. Recorded as the
   honest blocker rather than pretending the distractor pilot stood in for
   it.
2. **A small no-harm cost even on saturated benchmarks.** The engine lost
   6 points on a benchmark the flagship aced — because the cheap panel
   trips on eliminable distractors the flagship ignores. For the Mixture
   of Orchestrations router this reinforces the `single-call` route:
   saturated/easy domains should bypass the cheap panel entirely, since
   cheap deliberation is not free of downside even when the task is easy
   for a strong model. (Consistent with LEXam/MMLU-Pro losing at high
   baselines; MedQA tied only because its unanimous-wrong rate was
   genuinely tiny.)

## Gap-lens row

| Benchmark | Flagship baseline | Unanimous-wrong | Engine vs baseline | Read |
|---|---|---|---|---|
| MATH-500 L5 (distractor-MC) | 100% | 6% | −6.1 | saturated → single-call; benchmark can't test us |

## Caveats

- The 100% baseline is the whole story — this is a saturated benchmark
  under the distractor-MC framing, so treat the −6.1 as "mild no-harm
  cost on a saturated set," not "the engine is bad at math."
- n=49, single seed. Given saturation, more seeds would not change the
  conclusion (a 100% ceiling leaves no room for a different verdict).
- Real hard-math evaluation is deferred to the open-answer-grading engine
  change, not attempted via distractor-MC again.

## GSM8K (easy math, distractor-MC) — the no-harm confirmation

Ran GSM8K (grade-school word problems, the easy end) the same way. n=50,
seed 42. Result: baseline 100%, engine 96.0%, −4.0 (2 questions).

Identical shape to MATH-500 L5: the flagship saturates the distractor-MC
framing (100% at BOTH easy and hard math, because distractors are
computed-away regardless of problem difficulty), and the engine carries a
small no-harm cost (−4 to −6) from the cheap panel occasionally tripping
on an eliminable distractor. Two saturated math pilots, one conclusion:
**distractor-MC cannot evaluate math deliberation for this model pair,
and saturated domains are single-call routes.** The no-harm cost is
consistently small (4-6 pts) but non-zero, which is the concrete argument
for the router bypassing the cheap panel on saturated/easy traffic rather
than always deliberating.
