# MoO M1: the router eval — the honest verdict on the thesis

The make-or-break test (docs/mixture-of-orchestrations-plan.md M1, "ceiling
analysis discipline"). Blended workload: 120 questions, 4 buckets × 30
(GPQA-hard, SuperGPQA-hard, MedQA, saturated-easy MMLU-Pro), every one run
through all 7 registry profiles + the R1 heuristic router (balanced budget).
Scored on the 111 questions present for all profiles.

## The three numbers

| | Accuracy | Cost (tok/q) |
|---|---|---|
| flat-best (flagship_panel) | **92.8%** | 6625 |
| ROUTED (R1 heuristic, balanced) | 90.1% | 7826 |
| oracle (per-question best) | 96.4% | — |

**As configured, the router LOSES: −2.7 pts vs the best single profile,
AND costs more.** Per the plan's own criterion (oracle−flat = 3.6 pts,
routed captured none of it), the R1 heuristic router does not justify its
complexity on this blend. Reported straight — this is the project's most
important honesty checkpoint, and the answer is "not yet."

## But the per-bucket breakdown diagnoses exactly why — and it's fixable

| bucket | flagship_panel | routed choice | verdict |
|---|---|---|---|
| gpqa_hard | 93% @ 12248 tok | stem-max 85% @ 14426 | router WORSE + costlier |
| supergpqa_hard | 84% @ 8633 | rag_thinking_gate 80% @ 15935 | router WORSE + ~2× cost |
| medqa | 97% @ 3367 | standard-tribunal 97% @ 1683 | **router TIES acc, HALF cost** |
| saturated_easy | 97% @ 3028 | single-call 97% @ 852 | **router TIES acc, ¼ cost** |

Two clean halves:
- **On easy/competent domains the router WORKS** — it matched flagship
  accuracy at ½ to ¼ the cost. Routing genuinely pays where the tiers
  separate (a cheap profile suffices, so don't pay flagship).
- **On hard STEM the router FAILS** — it routed to the retrieval/thinking
  stacks, which were both less accurate AND more expensive than
  flagship_panel.

## The wrong assumption the eval killed (the real finding)

The router's cost model assumed "flagship_panel = expensive, avoid on hard
STEM, use the cheap-tier robust profiles instead." **That assumption is
false, and the eval proved it:** flagship_panel rarely escalates (~8-12%
→ 3 solver calls, ~8-12k tok), while rag_thinking_gate escalates 55-69%
→ full tribunal → ~16k tok. **The escalation-heavy "cheap" stacks are the
EXPENSIVE ones on hard STEM; flagship_panel is both more accurate AND
cheaper there.** Cost cannot be inferred from solver tier — it is
dominated by escalation rate, which must be measured per-profile-per-domain
(exactly what the calibration memory, plan §5.1, is for).

## The corrected router (projected) DOES beat flat-best — on cost

Route flagship_panel for hard STEM (where it's the accuracy AND cost
winner) and single-call/standard-tribunal for easy/competent domains
(where they tie accuracy at ¼-½ cost). That router ties flat-best's 92.8%
accuracy while spending far less than flagship-everywhere (flagship wastes
~2200 tok/q on saturated questions a single call answers identically). The
MoO win on this blend is a COST win at equal accuracy, not an accuracy win
— because a strong generalist (flagship_panel) already captures most of the
accuracy, and the mixture's job is to not overpay for it where a cheap
profile ties.

## Verdict and next step
- **R1 heuristic router as shipped: does not beat flat-best. Honest
  negative.** The oracle gap (3.6pts) is real but per-question, not
  per-domain — beyond heuristic routing's reach; capturing it needs the
  calibrated R2 router (per-question gap estimate).
- **The fixable, validated-in-the-data insight:** correct the hard-STEM
  rule to flagship_panel and drive routing off MEASURED per-profile-
  per-domain cost (calibration memory), not tier assumptions. The
  corrected router is a cost win at flat-best accuracy — the honest,
  defensible MoO claim on this workload.
- Next: re-run the router with the corrected hard-STEM rule + a measured
  cost model, and report cost-at-equal-accuracy as the metric MoO actually
  wins on. Do NOT claim an accuracy win the data doesn't support.
