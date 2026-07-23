# R2 disputed-step recursion: Bet-2 findings

The first RECURSIVE retrieval step (docs/recursive-rag-plan.md §2 R2,
§5 Bet-2). Lever `rag_recursive` = R1 pre-solve retrieval PLUS, on
escalation only, a second sharper retrieval from the Skeptic's named
disputed step, injected as grounding for the Verifier. Seed 42,
SuperGPQA-hard, n=90, RAG-ON (same pre-embedded corpus).

## Bet-2: NOT met — recursion does not beat one-shot R1

Apples-to-apples on 85 common items:

| SuperGPQA-hard, seed 42 | Accuracy |
|---|---|
| cheap-panel (no RAG) | 67.1% |
| rag_presolve (R1, one-shot) | 71.8% |
| rag_recursive (R1 + R2) | 70.6% |

**−1.2 vs R1 (within noise at n=85, 1 seed) — no accuracy improvement,
if anything slightly worse.** R1 already captured the retrieval gain; the
second retrieval at the tribunal added nothing to accuracy.

## Why — and it is a clean structural reason, not just noise

**R2 fires only on escalation, so it structurally cannot touch the
unanimous-wrong floor** — which is exactly where R1's accuracy gain lives.
Unanimous-wrong count is identical (14) for R1 and recursive, because
those questions never split, so the disputed-step retrieval never fires
on them. The dominant failure mode is only reachable by PRE-solve
retrieval (R1), never by tribunal-stage retrieval (R2). This is the deep
reason recursion can't beat R1 on this benchmark: it targets the wrong
stage for where the accuracy is.

What R2 *did* change, at the tribunal it does reach:

| | Escalated | Overturns | Overturn-correct | False-escalations |
|---|---|---|---|---|
| R1 | 38 | 18 | 13 (72%) | 20 |
| recursive (R1+R2) | 38 | 24 | 15 (62.5%) | 14 |

The extra evidence made the judge MORE interventionist (18→24 overturns)
and cut false-escalations (20→14, good), but the extra overturns were
LOWER quality (72%→62.5% correct) — some overturned a correct plurality.
More activity, not better calibration. Net neutral-to-slightly-negative.

## The lesson (reinforces a recurring project finding)

The binding constraint is upstream **solver knowledge, not tribunal
capability.** R2 feeds evidence to the tribunal, which was already the
strong part of the system (78-85% overturn-correct everywhere measured);
more evidence there makes it busier without making it righter. This is
the same lesson the qwen38_judge null result taught (a stronger judge
moved nothing) — the deliberation/adjudication machinery is not where the
gains are. **R1 pre-solve retrieval is the retrieval lever that matters;
R2 disputed-step retrieval is a documented no-gain on this benchmark.**

## Important: the LEXam retry is a DIFFERENT test, still live

R2 was also designed for the measured LEXam diagnosis (7/9 escalations
produced ZERO verifier findings because the tools were science-only). On
SuperGPQA-hard, R2 competes with an already-strong verifier/tribunal and
loses. On LEXam, the situation is opposite: the verifier is DEAD (no
findings at all), so retrieved statute-like passages would be its FIRST
evidence, not extra evidence competing with good evidence. This
SuperGPQA negative does NOT refute the LEXam hypothesis — the mechanism
is different (revive a dead verifier vs. augment a strong one). G3
(rag_recursive on LEXam) is still worth running and is queued.

## Caveats
- n=85, 1 seed; the −1.2 accuracy delta is within noise, so the honest
  claim is "no improvement over R1," not "R2 is harmful."
- k=3 for the disputed-step query, unchanged verifier prompt otherwise.
- 1 drop (Engineering), excluded by intersection.
