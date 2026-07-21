# MMLU-Pro pilot findings

Second non-GPQA benchmark. n=50, seed 42, trimmed to 4 choices per question
(see load_mmlu_pro.py for why -- the engine is hardcoded to A-D, MMLU-Pro
questions carry up to 10 options natively). Small pilot, same reasoning as
LEXam: no baseline numbers exist for this exact model pair on this exact
benchmark, so size it to find out whether a full run is worth running
before committing to one.

**Headline: single-flagship baseline (94.0%) beats QuorumQA (82.0%) by 12
points.** Same direction, similar scale to the LEXam pilot's 14-point gap.
This is now two out of two non-GPQA benchmarks where the engine
underperforms the plain flagship, not one.

## What's driving it

Same dominant failure mode as every prior diagnosis this session: **7 of
50 wrong answers were unanimous** -- all three solvers confidently agreed
on the same wrong letter, no escalation possible. Unlike LEXam, the
escalation mechanism itself looks reasonably healthy here when it does
fire: 4 overturns, 3 correct (75%), close to GPQA-Diamond's own overturn
quality (78.6%), not LEXam's near-coin-flip 57%. The problem on this
benchmark isn't a broken tribunal -- it's that too many wrong answers never
reach one.

Per-category breakdown (14 MMLU-Pro categories spread across 50 questions,
so most categories have n=1-8 -- too small individually to trust, but the
aggregate pattern is informative): most categories show baseline=engine at
100% (math, economics, business, physics, biology, health, psychology,
computer science, philosophy all unanimous-and-correct in this sample).
The gap concentrates in a few categories where the baseline was already
strong and the engine specifically missed: engineering (baseline 86% ->
engine 43%, n=7), chemistry (100% -> 75%, n=4), law (67% -> 33%, n=3).

## The cross-benchmark pattern worth naming

Both non-GPQA pilots so far show the flagship baseline landing very high
(94% here, 86% on LEXam) with QuorumQA underperforming it by a double-digit
margin. GPQA-Diamond is the opposite: the flagship baseline itself only
hits 84-86%, and QuorumQA closes most (not all) of the gap to it while
beating the same-tier self-consistency ensemble by 20 points.

The plausible mechanism: **QuorumQA's escalation value depends on the
question set being hard enough that the flagship itself has real headroom
for error.** GPQA-Diamond is explicitly constructed to be "Google-proof" --
hard even for the strongest available model -- which means the cheap panel
disagrees often enough to generate real, catchable signal, and there's
enough genuine baseline error for adjudication to meaningfully recover.
When the flagship is already near-ceiling (as it was on both pilots here),
most of the engine's remaining errors are the one failure mode this
architecture cannot catch by construction -- confident unanimous agreement
on a wrong answer -- and there are too few total mistakes for the
escalation mechanism's real, positive contribution to outweigh that blind
spot in the total tally.

**A real confound in this specific pilot, stated plainly:** trimming
MMLU-Pro to 4 choices (from its native up to 10) likely made this sample
easier than the benchmark's own published difficulty, since fewer
distractors is mechanically easier to reason through correctly. The 94%
baseline here may partly reflect that trimming, not just this particular
random sample being easy. This pilot is not a clean read on "true"
MMLU-Pro difficulty for this model pair -- it's a read on QuorumQA's
4-choice-trimmed variant of it, which is a different, easier benchmark
than the one any published MMLU-Pro number refers to.

## Caveats, stated plainly

- n=50, single seed, no replication.
- Category sample sizes (n=1-8) are too small individually to trust; only
  the aggregate gap and the unanimous-wrong-dominant diagnosis are
  reasonably solid at this n.
- The 4-choice trim is a real, disclosed methodological choice that likely
  biases this pilot toward being easier than untrimmed MMLU-Pro -- see
  above.

## What this suggests for benchmark strategy going forward

If the "needs real flagship headroom" hypothesis above holds, the
practical selection criterion for the next benchmark isn't just "not yet
saturated by frontier models in general" (the criterion used to shortlist
LEXam, MMLU-Pro, SuperGPQA, MedQA originally) -- it's "the specific sample
drawn is hard enough that the flagship itself gets a meaningful fraction
wrong," which can only really be confirmed by running the pilot, not
predicted from a benchmark's published aggregate difficulty alone (LEXam's
own leaderboard showed real headroom at scale; this 50-question pilot
still landed the baseline at 86%). Worth deliberately oversampling from a
benchmark's hardest-rated subset (where one exists) rather than a flat
random sample, on any future pilot.
