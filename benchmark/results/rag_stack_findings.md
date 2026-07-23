# rag_thinking_gate: the robust retrieval profile

Stacks the two cheap-tier retrieval/reasoning ideas: R1 pre-solve retrieval
(evidence to all 3 seats) + thinking_gate's panel (seat 3 thinking=True) +
the universal doubt gate. Tests whether reasoning-about-evidence fixes raw
rag_presolve's tail risk (it went −5.6 at seed 271, evidence-misled false
consensus). SuperGPQA-hard, RAG-ON, three-way same-seed comparison.

## Two seeds: the stack is never negative, and cuts the floor hard

| | control | rag_presolve | rag_thinking_gate (stack) |
|---|---|---|---|
| seed 271 acc | 66.3% | 60.7% (**−5.6**) | 66.3% (+0.0 vs ctrl, **+5.6 vs R1**) |
| seed 271 floor | 22 | 25 | **9** |
| seed 606 acc | 69.0% | 73.6% (+4.6) | 73.6% (+4.6 vs ctrl, +0.0 vs R1) |
| seed 606 floor | 15 | 13 | **5** |

**The pattern is the finding.** Where raw rag_presolve is volatile
(+4.7/+6.9/+8.0/−5.6, mean +3.5, one bad seed), the stack:
- is **never negative vs control** (+0.0, +4.6);
- **rescues rag_presolve's failure**: at the bad-retrieval seed 271, R1
  lost −5.6 but the stack held even with control (+5.6 over R1);
- **matches R1's upside** when retrieval is good (+4.6, seed 606);
- **cuts the unanimous-wrong floor dramatically and consistently** (to 9,
  then 5) — the mechanism: the thinking seat reasons past a misleading
  passage rather than trusting it, and the doubt gate catches residual
  false consensus. This is exactly the mitigation the score-gating
  analysis (rag_gating_analysis.md) said was needed — reasoning about
  evidence, not filtering it by retrieval score.

## The tradeoff, stated

The stack escalates much more (62% seed 271, 69% seed 606, vs control's
~47%): the thinking seat surfaces more productive splits and the gate
fires on unanimity. More escalation = more tribunal cost. So the stack
buys robustness (no negative seeds, hard floor cuts) with higher average
cost. For the MoO router this is a distinct profile from raw rag_presolve:
choose the stack when robustness matters and budget allows; raw R1 when
cheapest-possible and the domain's retrieval is reliable.

## VALIDATED (3 seeds)

| Stack vs control | s271 | s606 | s838 | mean |
|---|---|---|---|---|
| Accuracy delta | +0.0 | +4.6 | +4.5 | **+3.0** |
| Floor (control→stack) | 22→9 | 15→5 | 17→6 | — |
| Escalation | 62% | 69% | 55% | ~62% |

**rag_thinking_gate is VALIDATED as the robust retrieval profile** — three
seeds, never negative, unanimous-wrong floor cut to 5-9 every time. On the
one seed shared with raw rag_presolve (271), the stack (+0.0) dominated
raw R1 (−5.6). It trades a small mean vs raw rag_presolve (+3.0 vs R1's
+3.5, different seed sets) for eliminating the negative tail and much
harder floor cuts, at ~1.5× escalation cost. **Router rule: prefer
rag_thinking_gate over raw rag_presolve wherever the escalation budget
allows; it is the retrieval profile that does not blow up on a bad
retrieval draw.** Fifth validated profile.
