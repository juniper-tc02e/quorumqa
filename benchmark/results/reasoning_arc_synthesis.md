# When does multi-agent deliberation help? — the reasoning-lever synthesis

One question drove the whole reasoning investigation: *when* does QuorumQA's
deliberation (multiple solvers → escalate disagreements to a stronger
tribunal) beat simply running the best single model? Across ~a dozen pilots on
five benchmarks, the answer is consistent and mechanistic.

## The one predictor: the cheap-to-flagship gap (unanimous-wrong rate)

Deliberation helps **if and only if** the cheap solver tier is meaningfully
worse than the flagship on the task — i.e. the "unanimous-wrong rate" (how
often the cheap solvers confidently agree on a wrong answer) is high. It is
**not** predicted by benchmark difficulty, baseline height, or answer format.

| Benchmark | Cheap→flagship gap | Deliberation result |
|---|---|---|
| GPQA-Diamond (MC) | large | **+20.0** shipped engine win (frozen n=90) |
| SuperGPQA-hard (MC) | large | **flagship_panel +4.1 mean, 3 seeds** (validated) |
| Organic-chem slice | very large | **chem_thinking_gate 90.9%** (validated) |
| MMLU-Pro STEM (4-way) | ~0 (saturated) | **+0.0** — predicted null, escalation 3% |
| MATH-500 L5 (open-answer) | ~0 (both tiers 96.6%) | **+0.0** — inert, escalation 0% |

The wins cluster where the gap is large; the nulls cluster where it is ~0 —
exactly and only as the predictor says.

## Two failure modes that look different but are the same

1. **Saturation** (MMLU-Pro STEM, MATH-500 L5): the *cheap* tier is already
   near-ceiling, so there's no gap. qwen3.6-flash-with-thinking scores 96.6% on
   MATH-500 L5 — identical to the flagship — and 3 flash solvers agree
   unanimously 55/59 times. Nothing to escalate, nothing to fix.
2. **Homogeneous strength** (qwen38_panel on hard STEM; the all-flagship math
   panel): make every solver equally strong and they stop disagreeing →
   escalation never fires → you pay for self-consistency with no adjudication.

Both reduce to: *no productive disagreement → no deliberation → no gain.* The
lever is disagreement between diverse, unequal solvers, never raw per-seat
strength.

## What deliberation cannot fix, by construction

When all solvers agree on a *wrong* answer (high unanimous-wrong), no
disagreement-triggered escalation can catch it — the tribunal never fires.
This is the irreducible ceiling on the whole approach, and it is why the
predictor is the unanimous-wrong rate specifically.

## The MoO corollary (routing)

Because a strong flagship panel is both accurate and *cheap* (it rarely
escalates), routing across specialized orchestrations does **not** beat
running that one panel everywhere on a balanced blend (−1.8pt). Routing's real
win is **cost on realistic easy-skewed traffic**: it matches flagship accuracy
within noise at 28–50% lower cost by not paying flagship compute for questions
a cheap call answers identically. A cost play, not an accuracy play.

## Tooling delivered (reusable, offline-tested)

- Open-answer math engine (flagship + cheap tiers, judge-on-split) — makes
  hard math gradable without distractor-MC saturation.
- Equivalence grader (`math_grade.py`): LaTeX/fractions/radicals/intervals/
  `\pm`/sets, **0/4000 false-positives**, fails closed. Caught a 7-point
  grader-artifact "headroom" on MATH-500 before it became a recorded finding.
- Recursive RAG stack (hybrid BM25+dense) with a contamination firewall.

## Open thread (blocked on quota until 2026-07-28)

The one regime the predictor says deliberation *should* help on open-answer
math — where the cheap tier is genuinely weak — is **AIME/Olympiad**. The
fixed cheap-tier AIME pilot (flash solvers thinking-off so they actually
disagree, flagship judge on escalation, retry-with-backoff) is built and
offline-tested, queued for the token-plan quota reset. That run is the direct
test of whether the shipped cheap-solver + flagship-escalation design
generalizes to hard open-answer math. Its result — win or honest null — will
close this arc.

*Every number above is reproducible from the committed `*_findings.md` and the
result JSONL. Nothing here is folded into the submitted n=90.*
