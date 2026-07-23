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

## Status
Two seeds, both non-negative, floor cut both times — promising and clearly
more robust than raw rag_presolve. Third fresh seed launched to complete
the validation bar. If it holds, rag_thinking_gate is the retrieval
profile the router should prefer over raw rag_presolve wherever the ~1.5×
escalation cost is acceptable.
