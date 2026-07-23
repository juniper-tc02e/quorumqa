# Open-answer hard-math deliberation pilot (MATH-500 L5)

**Question.** Does QuorumQA's multi-solver deliberation beat a single flagship
call on genuinely hard OPEN-ANSWER math — the surface the shipped engine's
distractor-MC framing couldn't test (it saturated the flagship at 100%,
`math500_hard_pilot_seed42.log`)? This is the reasoning-emphasis lever built
on the new open-answer engine (`math_open_engine.py`) + grader (`math_grade.py`).

**Setup.** MATH-500 level 5 (hardest tier), n=60 seed 42, open answers kept
(no MC). Panel = 3 flagship (qwen3.7-max, thinking) solvers → union-find
cluster by `grade()` equivalence → plurality wins, 3-way mutual split
escalates to a judge. Baseline = single flagship call. Both arms extracted
(`extract_boxed`) and graded (`grade`) identically. 1 item dropped
(unrecoverable error) from each arm; n=59 common.

## Result (corrected — see the grader caveat, it is the headline finding)

| MATH-500 L5, seed 42 (n=59) | Accuracy |
|---|---|
| Single flagship baseline | **96.6%** (57/59) |
| Panel (deliberation) | **98.3%** (58/59) |
| **Delta** | **+1.7 pp (one question)** |
| **Escalation rate** | **0.0% (0/59)** |

## Two honest findings

### 1. The deliberation mechanism is INERT on hard math (the real result)

Escalation was **0%** — not once did the three flagship solvers produce a
3-way mutual disagreement, so the judge never fired. Cluster shapes: 57/59
all-three-agree, 2/59 two-agree, **0/59 three-way split**. The +1.7 (a single
question) is therefore pure self-consistency@3 voting, comfortably inside
noise — *not* deliberation. Three strong, homogeneous solvers on math almost
always converge, so a disagreement-triggered tribunal has nothing to trigger
on. This is the **same mechanism as the qwen38_panel negative** on hard STEM
(a too-strong homogeneous panel never disagrees → tribunal idle → expensive
self-consistency). And the failure it *cannot* fix — all three agreeing on a
wrong answer — is the project's central unanimous-wrong mode, which no
disagreement-based escalation can catch by construction.

### 2. MATH-500 L5 is near-saturated for the flagship even open-answer

The open-answer framing did NOT reveal the large headroom it first appeared
to. Corrected baseline is **96.6%**, not the 89.8% the first grader reported
(see caveat). Combined with the MC framing's 100%, MATH-500 L5 leaves a strong
flagship only ~3% room — too little for deliberation to matter even if it
fired. Testing math deliberation needs a genuinely sub-90% surface for the
flagship (AIME/Olympiad tier) AND a weaker/ more diverse solver pool that
actually disagrees. That is the concrete next direction, not another
MATH-500 seed.

## Grader caveat — the methodological finding, caught before it became a lie

The FIRST run reported baseline 89.8% / panel 91.5%. Dissecting the six
baseline "errors" showed **four were grader false-negatives** on interval,
`\pm`, and set answers (`(3, 4]` vs gold `(3,4]`; `1 + \sqrt{19}, 1 -
\sqrt{19}` vs `1 \pm \sqrt{19}`; `\{-2, 1-\sqrt5, 1+\sqrt5\}` vs
`\{1\pm\sqrt5,-2\}`; a `\left(\tfrac35,\tfrac83\right]` interval) — exactly
the shapes the coverage note flagged as fail-closed. The grader was upgraded
to model intervals/±/sets (commit 40372fb: 0/4000 false-positives, L5 coverage
96→97%, suite 378), and the pilot answers were **re-graded for free** (the
answer strings are stored) to the 96.6/98.3 above. A naive equivalence grader
undercounts hard-math accuracy by ~7 points and manufactures illusory
headroom; the delta survives (both arms re-graded identically) but the
absolute numbers and the "headroom" story do not. Verified, not assumed.

## Verdict

**No math-deliberation win, and an honest reason why.** Deliberation neither
helped (escalation never fired) nor hurt (+1 item, noise) on MATH-500 L5,
because (a) the flagship is near-saturated there and (b) — the durable point —
strong homogeneous solvers don't generate the disagreement the tribunal needs.
The reusable assets are real: an open-answer math engine and a
false-positive-free equivalence grader, both offline-tested, that make hard
open-answer math *evaluable* at all. Not folded into any submitted number.
seed 42, n=59; math_open_baseline_seed42.jsonl / math_open_panel_seed42.jsonl.
