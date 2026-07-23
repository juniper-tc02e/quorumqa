# Evidence-relevance gating: offline calibration verdict

Goal: fix the seed-271 failure mode (rag_presolve −5.6, with 19/30 hard-STEM
regressions being unanimous-wrong UNDER RAG — retrieved passages misleading
the panel into false consensus) by injecting retrieval evidence ONLY when it
looks relevant enough, gated on the top fused retrieval score.

**Calibrated offline against all 4 seed runs (350 questions,
benchmark/results/rag_gating_calibration.csv) — no paid API spent, because
the offline data settles it. No seed-271 pilot was run: the calibration
proves the gate cannot work, so spending on it would be waste.**

## Verdict: score-gating CANNOT fix this failure mode

Top retrieval score by outcome class is statistically indistinguishable:

| Outcome | n | top_score mean | median |
|---|---|---|---|
| REGRESSIONS (RAG hurt) | 30 | 0.0288 | 0.0303 |
| — of which unanimous-wrong-under-RAG | 19 | 0.0283 | 0.0298 |
| HELPED (RAG rescued) | 41 | 0.0290 | 0.0297 |
| NEUTRAL (no change) | 279 | 0.0286 | 0.0307 |

Regressions do **not** have lower retrieval scores than the questions RAG
helped. A threshold sweep confirms there is no operating point that
suppresses regressions without discarding an equal number of wins — net
questions-recovered is +0 up to T≈0.02 and goes NEGATIVE beyond it (T=0.030
suppresses 13 regressions but loses 21 wins, net −8).

## Why — and it names the real problem precisely

The RRF fused score measures **retrieval confidence** (how strongly the
index thinks a passage matches the query), NOT **correctness for this
specific question**. The failure mode is passages that score HIGH —
confidently retrieved, topically on-point — but are wrong for the exact
question being asked (a closely-related-but-distinct concept, a plausible
distractor from an adjacent article). A score threshold is structurally
blind to that: high-confidence-wrong and high-confidence-right passages sit
at the same score. Gating on the number the retriever is most sure about
cannot separate the cases where it is confidently misleading.

## The real mitigation already exists (and was already measured)

The failure is bad evidence trusted by the cheap panel. The fix is not
filtering evidence by retrieval score — it is having the panel REASON about
the evidence instead of trusting it. This is exactly what the composition
test already showed: `rag_thinking_gate` (retrieval + one thinking seat +
the doubt gate) cut the unanimous-wrong floor 22→9 on the SAME bad seed 271
— the strongest floor cut ever measured — because the thinking seat reasons
past a misleading passage and the gate catches residual false consensus.
**The mitigation for "retrieval can mislead" is the thinking-seat + gate
stack, not a score threshold.** The `rag_gated_presolve` lever is kept in
the harness (12 offline tests, documented) as a validated-ineffective
approach, not a shipped one.

## Concrete next levers this points to (in priority order)
1. **Finish validating `rag_thinking_gate`** (the real mitigation) — it
   resisted bad evidence at seed 271; run its remaining fresh seeds. If its
   floor-resistance holds while accuracy converts on other seeds, it is the
   robust retrieval profile, superseding raw `rag_presolve`.
2. **Cheap LLM relevance/consistency check** (not a score): a one-call
   flash judgment "does this passage actually bear on THIS question?" before
   injection — reasons about fit, which the score cannot. Costs a call;
   test only if #1 doesn't fully solve it.
3. Route retrieval to the Verifier/tribunal (evidence as something to
   adjudicate) rather than raw solver-prompt injection — but note R2 already
   showed tribunal-stage retrieval doesn't help on hard STEM, so this is
   lower priority.
