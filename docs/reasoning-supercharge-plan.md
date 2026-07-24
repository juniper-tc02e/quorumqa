# Supercharging QuorumQA's Reasoning — the evidence-grounded plan (v2)

*Drafted 2026-07-24; revised the same day after a 4-lens adversarial review
(fact-check vs committed findings, build feasibility vs actual repo code,
experimental rigor, completeness). The review's 2 blockers and ~8 majors are
incorporated below. Paid work is quota-blocked until 2026-07-28 03:32 UTC, so
the plan is sequenced FREE-NOW → WEEK-1 PAID → WEEK-2+.*

## 0. What the evidence already proved (the design constraints)

Every validated win and honest null from ~a dozen pilots reduces to one
mechanism:

> **Deliberation pays exactly when (a) solver errors are decorrelated enough
> to produce disagreement, and (b) the disagreement actually triggers
> escalation to something stronger.**

Constraints any new lever must respect (numbers = the validated record, not
best seeds):

1. **The binding loss is unanimous-wrong** (all solvers agree on a wrong
   answer). GPQA diagnosis: 80% of the shipped engine's net loss never
   escalated. Measured pools differ by surface: ~10/90 on GPQA cheap-tier
   (~11%), ~20/86 on SuperGPQA-hard cheap panel (23%). Disagreement-triggered
   escalation *structurally cannot catch it*.
2. **Escalation coverage, not judge quality, is the bottleneck** — proven by
   qwen38_judge (stronger judge: 9/9 overturns right, zero net gain; it never
   saw the failures).
3. **Homogeneous strength kills the signal** — qwen38_panel and the
   all-flagship math panel both ran 0%-escalation. Model-family mixing also
   failed earlier (weakest seat + JSON breakage). Diversity must come from
   *method/presentation*, not just model choice.
4. **Wins live where the cheap→flagship gap is large.** Validated:
   thinking_gate matches-or-beats the flagship on GPQA at 3 seeds
   (+2.3 / tie / +1.1, mean ~+1.1); chem_thinking_gate 90.9% mean at 3 seeds
   (+4.4 over the matched same-seed flagship baseline, ~+5 cross-seed) — the
   project's best validated GPQA config; flagship_panel on SuperGPQA-hard
   +4.1 mean delta at 3 seeds (per-seed accuracies 83.3/81.7/82.7, mean
   ~82.6%).
5. **Saturated surfaces can only be tied, and CHEAP deliberation is not
   harmless there** (−4.0/−6.1 measured on GSM8K/MATH-500 distractor-MC;
   MMLU-Pro full −12). Demonstrated no-harm comes from routing to
   single-call, or from flagship_panel (+0.0 on MMLU-Pro-STEM); MedQA is the
   one cheap-tie case (+2, tie).
6. **Verification-by-computation is decorrelated from generation** — but
   only *partially* reachable: turning a question+answer into a checkable
   relation needs a model call (only the check itself is deterministic), and
   CAS-style checks apply only to quantitative items. The unanimous-wrong
   pool is largely conceptual MC — a computational check alone cannot cover
   it (this bounded W1's design below).
7. **Retrieval helps only where knowledge is the gap.** Full 4-seed record
   for rag_presolve: +4.7/+6.9/+8.0/−5.6, mean +3.5, status
   **validated-with-variance** (one evidence-misled negative seed). The
   robustly-validated profile is rag_thinking_gate (3 seeds, +0.0/+4.6/+4.5,
   never negative). GPQA tripwire −4.7; law (LEXam) null. Score-gating cannot
   filter bad evidence; the reasoning-based gate can.
8. **Escalation rates vary hugely by config** — flagship_panel 8-12%,
   chem stacks 34-43%, thinking_gate 52-54%, rag stacks 55-79%. Any
   "escalation-only" lever must name its base config; its cost and sample
   size both depend on it.
9. **Cost is measured in TOKENS, not dollars** — the Token Plan endpoint
   logs cost_usd=0.0; the only meters are tok/q (logged) and the weekly
   quota, whose recorded size is ~3 two-arm pilot runs (the MATH-500 pair +
   partial AIME run exhausted a full week). Every cost bar below is in tok/q.

## 1. The portfolio (ranked by information-per-quota-token)

Each: mechanism → build → bar → kill. **The kill always dominates the bar**
(pre-registered precedence — a run that passes its bar while tripping its
kill is a kill).

### W1. Unanimity red-team — attack unanimous-wrong head-on  [WEEK-1 PAID]

**Mechanism.** Stop treating three agreeing opinions as settled. Two arms,
in priority order:

- **Arm A — flaw-finder (primary).** On every unanimous plurality, one
  flagship-with-thinking call framed as *verification, not solving*: "here is
  the panel's answer and reasoning; find the specific error, or confirm."
  Escalate on found-flaw. Verifying a fixed candidate is a different task
  than generating an answer, so its errors partially decorrelate from the
  seats' shared blind spot — and it covers **100% of MC items**, including
  the conceptual bio/org-chem/qualitative-physics questions where the
  unanimous-wrong pool actually lives. This is the stronger sibling of the
  validated doubt-gate (which used a cheap model and opinion-only framing).
- **Arm B — computational check (quantitative items only).** One
  MECHANICAL_MODEL extraction call (mirroring the shipped verifier's
  extract→tool→finalize pattern in `engine/verifier.py`) produces
  `{relation, candidate_expr}`; then a **deterministic** local
  `sympy_check`/`substitute_check` (new MCP tools; sympy already a dep)
  validates it. Escalate on check-fail. Honestly labeled *partially*
  decorrelated: the extraction is model-generated; only the check is
  deterministic. Fires only where an expression exists to check.

**Build (free now).** `verified_gate` lever with both arms +
`sympy_check`/`substitute_check` in `tools/mcp_server.py`; the lever must
**log the pre-gate panel vote per item with byte-identical shipped seat
prompts** (this logged pre-gate plurality is W2's paired control — see W2).
Offline tests with a fake client.

**Pilot (paid, week 1).** ONE surface first (SuperGPQA-hard — larger pool:
~20 unanimous-wrong per 86), one fresh seed, arm A before arm B if quota
forces a choice. Cost accounting: arm A adds ~1 flagship call on the ~50-90%
of items that are unanimous (config-dependent, constraint #8) — priced in
tok/q, not escalation-%.
**Bar (screen):** net paired item delta (recoveries − new breaks) **≥ +3 per
90** on the same-seed paired set.
**Kill (dominates):** net ≤ 0, **or** red-team precision < 20% (fires on
correct answers ≥ 4× as often as on wrong ones). Same discipline that killed
score-gating. Validation to the 3-seed bar only after the screen passes.

### W2. Decorrelation by construction  [WEEK-1 PAID, arm 0 first]

**Mechanism.** The seats currently differ only by lens+temperature — same
method, same choice ordering → correlated errors, and shared position/
first-plausible-option bias is a direct unanimous-wrong contributor.

- **Arm 0 — permuted panel (run first; ~zero marginal cost).** Shuffle MC
  option order independently per seat (map letters back afterward). The task
  is unchanged, so per-seat accuracy cannot degrade by construction — it
  directly tests whether unanimity survives a presentation-invariance
  perturbation.
- **Arm 1 — method-diversity prompts (conditional).** Re-specify seats as
  different *procedures*: solve-forward / verify-by-candidate (work backward
  from each option) / estimate-first (order-of-magnitude, limiting cases).
  **Run only if arm 0 fails to move the unanimous-wrong rate** — if
  permutation alone gets there, the prompt engineering is unnecessary.

**Build (free now).** `permuted_panel` + `method_panel` levers.
**Pilot (paid, week 1).** SuperGPQA-hard, same fresh seeds as W1; the paired
control is W1's logged pre-gate plurality (identical shipped prompts —
provenance pre-registered in W1's build). This is a **directional screen**,
not validation: n=90×2 seeds cannot detect a 5pt rate change with power
(binomial SE ≈ 4pt), so:
**Bar (screen):** unanimous-wrong rate drops at BOTH seeds in the same
direction (any magnitude) AND net accuracy not worse than control by >2.5pt.
**Kill:** rate rises at both seeds, or net accuracy drops >2.5pt at both.
3-seed validation (and pooled discordant-count stats) only if the screen
passes.

### W3. Own hard math: AIME + grader-clustered self-consistency  [WEEK-1 PAID]

**Mechanism.** AIME is the *predicted* gap regime on math — unmeasured (run
#1 was invalidated for survivorship bias; the queued pilot IS the
measurement). MATH-500 has no gap (measured, both tiers 96.6%). Beyond the
queued pilot: **self-consistency@N with equivalence clustering** — sample N
cheap solutions, cluster with `math_grade.grade` (exact mathematical
equivalence beats string-majority), use **cluster margin** (top − runner-up)
as a *continuous* escalation dial: big margin → accept cheaply; small margin
→ flagship judge over the clusters.

**Build (free now).** `solve_selfconsistency_math(client, item, n, margin)`
in `math_open_engine.py` (clustering already proven: `_cluster_answers`).
**Pilot (paid, week 1).** ① The queued fixed AIME cheap-tier pilot, run
as-is. ② SC@5 / SC@9 on the same 60 items. **Paired same-items design,
pre-registered:** AIME is the full 60-problem population (seed = fixed item
set + declared sampling temperature, not item selection); deltas are quoted
ONLY on items completed in both arms, and a run with drops must be fully
retried before any number is quoted (run #1's lesson).
**Bar:** net ≥ **+4 items on the 60 shared problems** vs the single-flagship
arm, at ≤ flagship-baseline tok/q — or a tie in items at materially lower
tok/q.
**Kill:** flash AIME accuracy < 15% → cheap-tier clusters are noise; record
it and move SC@N to the flagship tier (AIME headroom exists there, unlike
MATH-500).

### W5. Wrongness-predictor from existing logs  [FREE — do first]

**Mechanism.** Thousands of logged solver traces with ground-truth labels
sit in committed JSONLs. Mine features (verbalized confidence, reasoning
length, hedge-rate, answer-switching, inter-seat agreement pattern, subject,
retrieval score where present) → small calibrated logistic model for
P(unanimous-wrong). If it separates, it becomes (a) a zero-cost smarter
gate, (b) the per-question gap-estimator the MoO router lacks.

**Leakage + power controls (pre-registered).** Unanimous-wrong base rates
span 1.7%–23% across benchmarks, so pooled AUC can be inflated by simply
predicting the benchmark. Therefore: leave-one-benchmark-out, AUC computed
**within** each held-out benchmark, bootstrap CIs, and the decision rule:
- **Bar:** median per-benchmark AUC ≥ 0.70 with no benchmark < 0.60 →
  wire as `smart_gate_v2` + W7 input.
- **0.60–0.69 band (defined):** usable ONLY as a cost-router input (W7),
  never as an accuracy claim.
- **Kill:** median < 0.60 → record honestly as "*verbalized trace features*
  don't separate" (NOT "no cheap signal exists").

**Free sub-task:** check whether the DashScope/Token-Plan endpoints return
answer-token logprobs; if yes, wire logging now so every post-reset run
accumulates calibrated confidence for a v2 predictor.

### W4. Escalation-only debate round  [CONDITIONAL — week 2+]

Demoted by the review, and rightly: constraint #2 says adjudication on
escalated items is already near-perfect (9/9), so deepening it attacks
neither the ceiling nor coverage. **Run only if W1/W2 succeed** — converting
unanimous-wrong into disagreement enlarges and *toughens* the escalated
pool, at which point adjudication depth becomes newly relevant.
Pre-registered design when it runs: base config = thinking_gate (52-54%
escalation → 45+ escalated items/90); the escalated item set is **frozen
from a base run** and both arms (one-shot tribunal vs one structured
rebuttal round) run on that identical frozen set, same seed.
**Bar:** net discordant advantage ≥ +4 on the frozen set, replicated at a
2nd seed, at ≤1.5× one-shot-tribunal tok/q on that set.
**Kill:** concession-rate > 90% AND zero minority arguments change the
judge's ruling (sycophancy, not debate).

### W6. Targeted escalation-stage retrieval (R3)  [CONDITIONAL — week 2+]

The R2 null is the caution: tribunal-stage retrieval structurally can't
touch unanimous-wrong, and escalated items are already well-handled. The
surviving distinction: R2 re-retrieved generically on solver disagreement;
R3 retrieves on the **skeptic's specific disputed claim** and feeds the
passage to the verifier via its existing `evidence_block` parameter (already
plumbed) — new *information*, not more deliberation. Still bounded by the
same structural cap, hence conditional and cheap.
Precondition: corpus contains the knowledge (SuperGPQA yes, law no).
**Bar:** net discordant ≥ +4 on the frozen escalated set vs rag_thinking_gate.
**Kill:** > 50% of R3 queries judged off-topic by a pre-committed rubric
(blinded fixed-prompt LLM check, majority-of-3, run on every query).

### W7. Per-question MoO routing v2  [CONDITIONAL on W5]

W5's predictor upgrades the router from domain rules to per-question
routing: predicted-easy → single-call; predicted-hard-STEM →
flagship_panel; predicted-knowledge-gap → rag_thinking_gate. Chases the
3.6pt oracle gap.
**Bar:** routed within 0.5pt of flat-best on the balanced blend at ≥15%
tok/q saving (or any accuracy gain over flat-best).
**Kill:** routed still ≥1.5pt below flat-best → the already-recorded
cost-win verdict stands as MoO's final word.

## 2. Sequencing

### Now → 07-28 (FREE, no quota)
| # | Item | Output |
|---|---|---|
| 0 | **Quota token-audit**: sum logged tokens of the runs that exhausted the week (MATH-500 ×2 + AIME partial) → weekly allowance in tokens; re-express every planned run in measured tok/q before anything fires | The real budget |
| 1 | **W5 predictor mining** (leave-one-benchmark-out, within-benchmark AUC) + logprobs availability check | AUC report, committed |
| 2 | W1 build: flaw-finder + extraction→sympy check arms, pre-gate vote logging, offline tests | Ready-to-fire |
| 3 | W2 build: `permuted_panel` + `method_panel` levers, offline tests | Ready-to-fire |
| 4 | W3 build: SC@N + margin escalation, offline tests | Ready-to-fire |
| 5 | W4/W6 builds (debate round; R3 skeptic-claim hop + relevance rubric) — build only, conditional runs | Shelf-ready |

### Week 1 after reset (PAID — only what one week measurably holds)
Per the token-audit (#0), schedule **at most ~3 pilot-equivalents** and
re-check quota headroom after each:
1. **AIME pilot ①** (queued, fixed, paired design) — always first.
2. **W1 on SuperGPQA-hard** (flaw-finder arm first), one fresh seed —
   includes the logged pre-gate control W2 needs.
3. **W2 arm 0 (permuted panel)** at the same seeds — near-free riding on
   W1's control; W3's SC@N only if headroom remains.

### Week 2+ (PAID, gated)
- W1/W2 second seed + 3-seed validation of whatever screened positive.
- W3 SC@N (if not run week 1), flagship-tier fallback if the kill fired.
- W4/W6 only if W1/W2 enlarged the escalated pool; W7 only if W5 hit its bar.
- Section-3 stacked-config validation (below) is explicitly **multi-week**.

## 3. Success criteria for the whole push (pre-registered, noise-cleared)

The repo's own calibration: paired n=90 deltas inside ±2.5pt (~2 items) are
noise. So every criterion is a discordant-item count or a 3-seed mean:

- **GPQA-Diamond: ≥ 92% at the 3-seed bar** (current validated best:
  chem_thinking_gate **90.9%** mean — the baseline to beat, not 86.7%), via
  W1/W2 stacked on the chem_thinking_gate config; equivalently net ≥ +4
  discordant items vs chem_thinking_gate at shared fresh seeds.
- **SuperGPQA-hard: raise the validated mean delta from +4.1 to ≥ +6** over
  the single-flagship baseline at 3 seeds.
- **AIME: net ≥ +4 items over single-flagship on the 60 shared problems**
  (or tie at materially lower tok/q) — the first demonstrated
  math-deliberation value.
- **No-harm preserved via routing** on saturated surfaces (single-call or
  flagship_panel routes stay ±0; cheap deliberation is NOT the no-harm
  path — constraint #5).
- Every claim at the 3-seed bar before "validated"; every null recorded.

## 4. Non-goals (explicit, incl. considered-and-rejected)

- No model fine-tuning/training — wrong layer; the thesis is orchestration.
- No HLE (needs semantic-grading rebuild; previously closed).
- No leaderboard submissions without review (standing rule).
- No new benchmark families until the workstreams resolve — depth moved the
  numbers all session, surface-count didn't.
- **Pairwise/tournament adjudication: considered and rejected** — it
  multiplies calls on the escalated subset where adjudication is already
  9/9, adding no decorrelated information (recorded here so a future
  session doesn't re-derive it).

## 5b. The two-track product strategy (directive from Jun Kai, 2026-07-24)

QuorumQA runs two angles, and every lever above serves one or both:

**Track A — the price model (current portfolio).** Cheaper models organized
by QuorumQA match or beat a single flagship at lower cost. This is the
shipped engine's thesis (flash voters + routed flagship, 78.9% @ −11% cost),
the MoO cost win (28-50% cheaper at equal accuracy on realistic traffic),
and W1-W7's default framing. The claim is efficiency.

**Track B — Ultra Agentic Scaling, SAME-PROVIDER edition (cost-no-object).**
Redirected by Jun Kai 2026-07-24: scale using agents of ONE provider only
(the Qwen family). The research question: how far can manufactured
within-provider diversity (tiers, thinking modes, sampling, prompts,
permutation, pipeline topology) push a Qwen-only society past the best
single Qwen model (qwen3.8-max-preview solo, 93.6%)? Research doc:
`docs/same-provider-scaling-research.md`. The claim is absolute capability
within one ecosystem — measured as "beats the best participating single
model, apples-to-apples, 3-seed bar."

**CONSIDERED — PARKED (cross-vendor collaboration).** The earlier Track-B
concept (GPT 5.6 Sol Ultra + Kimi K3 + Qwen + Claude deliberating together)
is recorded as considered, not active. The evidence logic stands — our
homogeneity failures were same-model copies, and cross-lab lineages would
be engineered decorrelation at the top tier — but it needs a
provider-agnostic client plus cross-vendor keys (none in this repo), and
Jun Kai has directed the effort at same-provider scaling first. If revived:
the preconditions and honesty rules (measured claims only, per-model
diversity accounting) recorded in the git history of this section apply.

**Considered-and-recorded config (from Jun Kai, 2026-07-24):** all-qwen3.7
seats (solvers + skeptic + verifier + gate) with a qwen3.8-max-preview
judge. Never run. Prediction from the validated record: the 3.8-judge half
is marginal (judge quality is not the bottleneck — 9/9 overturns already);
the genuinely untested half is flagship-tier skeptic/verifier/gate, which
is what W1's flaw-finder tests in targeted form. If W1's screen passes, a
Track-B variant of this config (cross-lab judge over flagship seats) enters
the week-2+ queue rather than being re-derived.

## 5. Kill-discipline

Half this session's value was honest negatives (R2, score-gating,
qwen38_panel, MATH-500 saturation). Precedence is pre-registered globally:
**the kill dominates the bar** in every workstream. A killed workstream gets
a findings doc, not a silent burial. The ceiling on the whole program
remains the unanimous-wrong rate — W1 (flaw-finder) and W2 (permutation
first, method prompts second) are the only levers pointed at the ceiling
itself, which is why they own week 1.
