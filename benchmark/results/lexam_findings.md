# LEXam pilot findings

The first non-GPQA benchmark this engine has been pointed at. Exploratory,
n=50, English-language `mcq_4_choices` config, seed 42. Small pilot on
purpose -- no published baseline numbers exist for this model pair
(`qwen3.6-flash`/`qwen3.7-max`) on LEXam, so this is deliberately sized to
find out whether it's even worth a full run before committing to one.

**Headline: on this pilot, the single-flagship baseline (86.0%) beats
QuorumQA (72.0%) by 14 points -- a much larger gap in the same direction
than GPQA-Diamond's 5.5 points, not a smaller one.** This is a real,
honestly-reported negative result, not noise dressed up: n=50 is small
enough that some of the 14-point gap could shrink with a larger sample,
but a gap this size at this n is unlikely to fully vanish.

## What's actually going wrong

**Most errors never reach escalation at all.** 11 of the engine's 14 wrong
answers were unanimous -- all three solver seats confidently agreed on the
same wrong letter, so nothing ever triggered the tribunal. This is the
identical failure mode GPQA-Diamond's diagnosis found in Organic Chemistry
(a shared blind spot across three seats running the same base model), but
here it isn't confined to one subject -- 42 of the 50 pilot questions are
tagged "Interdisciplinary" (LEXam's own area label), and the unanimous-wrong
rate across that slice is high enough to dominate the result.

**The escalation mechanism itself looks close to a wash here, not clearly
value-additive.** 9/50 questions escalated (18%). Of those, 7 were
overturned (the Judge changed the final answer away from the plurality) --
and only 4 of those 7 overturns were correct (57%). On GPQA-Diamond's
frozen run, overturns were right 11/14 times (78.6%). A 57% overturn-correct
rate is barely better than a coin flip on a 4-option question where guessing
alone would be right 25% of the time picking among the remaining 3 -- it is
not the clean "adjudication beats plurality" signal GPQA showed.

**Mechanistic diagnosis: the Verifier's tools don't apply to this domain.**
Checked directly: of the 9 escalated questions, **7 (78%) produced zero
Verifier findings** -- the Verifier's tool set (`lookup_constant`,
`safe_calculate`) exists to ground numeric and physical-constant claims,
which is exactly what a physics or chemistry question has and a
statement-based legal MCQ ("which combination of these numbered statements
is true?") mostly does not. On LEXam, escalation effectively degrades to
Skeptic-plus-Judge, missing a third of the evidence sources the architecture
was designed around. This is a plausible, mechanistically clean explanation
for why overturns land close to a coin flip here: the Judge is ruling on
argument quality alone, with no independent tool-grounded check to break
ties the way it can on GPQA.

## Caveats, stated plainly

- n=50 is a pilot, not a claim. 42/50 questions share one area tag
  (Interdisciplinary) -- this is not yet a broad, balanced sample across
  LEXam's four areas (Private/Interdisciplinary/Criminal/Public).
- Single seed (42). No replication yet, unlike the GPQA-Diamond thinking_gate
  result which was validated across three independent seeds before being
  reported as solid.
- This does NOT mean the "vote cheap, escalate on disagreement" *shape*
  fails on law -- it means the *current* Verifier's tools are a science-
  specific instrument that doesn't transfer, and the panel's shared-model
  blind-spot problem (already diagnosed on GPQA) shows up here too, possibly
  worse. A domain-appropriate Verifier (statute/case lookup instead of
  constant/calculator lookup) is an untested, obvious next lever -- not
  built here, flagged as the clear next step if this benchmark gets
  revisited.

## What this would take to pursue further

- A larger, area-balanced sample (drawing evenly across all four LEXam
  areas, not letting one area dominate by chance of the random seed) before
  trusting the exact 72%/86% numbers as representative of the whole
  benchmark.
- A second, independent seed -- same rigor bar as GPQA-Diamond's levers.
- If revisited: a legal-domain Verifier tool (e.g. statute-text lookup)
  instead of reusing the science-domain `lookup_constant`/`safe_calculate`
  tools unchanged, to test whether the escalation mechanism's value returns
  once it has domain-appropriate grounding.
