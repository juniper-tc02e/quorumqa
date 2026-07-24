# W6 R3 Relevance Rubric

This is the frozen kill-criterion instrument for the `rag_r3_targeted`
lever (`benchmark/lever_experiments.py`, `docs/reasoning-supercharge-plan.md`
section W6). It is committed here, before any W6 pilot run, so that a
post-hoc reading of the results can never quietly loosen or tighten the
check that decides whether W6 lives or dies.

## Why this exists

R3 (`_tribunal_r3` in `benchmark/lever_experiments.py`) retrieves passages
targeted at the Skeptic's specific disputed claim, rather than the raw
question (that was R1's job) or the general disputed step (R2's job, which
was a validated null). The R2 null's caution applies here too: retrieval
that *looks* targeted can still fetch a plausible-but-irrelevant passage,
which is worse than fetching nothing -- it can mislead the Verifier and the
Judge into false confidence. W6's kill criterion exists specifically to
catch that failure mode, independent of whether accuracy numbers look good:
a lever whose retrieval is mostly off-topic is not "working for the wrong
reason," it is not working, and any accuracy delta it produced should be
treated as noise or luck, not signal.

## The check

A **blinded** LLM call answering exactly one question: *is this passage
on-topic for this disputed claim?* It sees **ONLY** the disputed claim and
ONE retrieved passage -- never the original question, the answer choices,
the Skeptic's full rebuttal, the Verifier's findings, or any other
deliberation context. This blinding is deliberate and load-bearing: the
question being asked is "does this passage discuss the same subject matter
as the claim," not "does this passage help answer the exam question" --
conflating the two would let an irrelevant-but-lucky passage pass simply
because the underlying question is easy, or fail a genuinely on-topic
passage because it doesn't itself resolve the exam question. Relevance and
usefulness-for-the-exam are different properties; this rubric measures only
the former.

The prompt text below (between the `RUBRIC_PROMPT_START` /
`RUBRIC_PROMPT_END` markers) is the **exact, verbatim, frozen** instrument.
`benchmark/score_r3_relevance.py` reads this file at runtime and extracts
that exact block -- it must never hand-duplicate a copy that could drift
from what is committed here.

<!-- RUBRIC_PROMPT_START -->
SYSTEM:
You are checking whether a retrieved reference passage is on-topic for a disputed factual claim. You are given ONLY the claim and the passage -- you do not see the original exam question, the answer choices, the skeptic's full argument, or any other context, and you must not guess at or assume any of it. Judge relevance narrowly and literally: does this passage discuss the same subject matter, fact, mechanism, or relationship named in the claim, closely enough that it could plausibly help confirm or refute the claim itself? A passage about a related but distinct topic, a passage that is merely thematically nearby, or a passage that would only be useful if you already knew unstated context, is OFF-TOPIC. Do not reward a passage for being well-written, authoritative-sounding, or generally informative -- score ONLY topical relevance to the claim as stated.

USER:
Disputed claim: <<CLAIM>>

Retrieved passage: <<PASSAGE>>

JSON shape: {"on_topic": true|false, "reason": "one sentence, at most 25 words"}
<!-- RUBRIC_PROMPT_END -->

## Aggregation: majority-of-3

Run the check **3 times** per (disputed_claim, passage) pair, independently,
at **temperature 0**. (Temperature 0 does not guarantee a literally
deterministic response on this project's endpoint -- see
`quorumqa/qwen_client.py`'s notes on the Token Plan transport -- so 3
independent calls are used rather than trusting a single call.) The
aggregated verdict for that passage is the **majority** vote: `on_topic` if
at least 2 of the 3 calls returned `"on_topic": true`, `off_topic`
otherwise.

## Kill criterion

For a given `rag_r3_targeted` run, pool every passage retrieved across
every escalated question where R3 actually fired (`r3_query_fired: true`
in the row -- see `benchmark/lever_experiments.py`'s `_tribunal_r3`/
`_build_output_row`), score every (disputed_claim, passage) pair with the
majority-of-3 check above, and compute:

```
off_topic_rate = (# passages majority-voted off_topic) / (total passages scored)
```

Per `docs/reasoning-supercharge-plan.md` W6:

> **Kill:** > 50% of R3 queries judged off-topic by a pre-committed rubric
> (blinded fixed-prompt LLM check, majority-of-3, run on every query).

If `off_topic_rate > 0.50`, W6 is **killed** -- record the finding honestly
regardless of what the paired-item accuracy bar shows. Per the plan's
global kill-discipline (`docs/reasoning-supercharge-plan.md` section 5),
**the kill dominates the bar**: a run that clears its accuracy bar while
tripping this relevance kill is still a kill, not a partial win.

## Freeze notice

The prompt block between `RUBRIC_PROMPT_START` and `RUBRIC_PROMPT_END`
above is **FROZEN as of 2026-07-24**, prior to any live W6 pilot run. Any
edit to that block after this date invalidates the pre-registration -- W6's
kill criterion must be evaluated against the exact instrument committed
here, not a version tuned after looking at results. If the rubric text
genuinely needs to change (e.g. a real defect is found in the prompt), that
is a new pre-registration, not a silent edit: bump this notice with a new
date and explicitly record why, rather than editing in place.
