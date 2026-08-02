# Negative results: a catalogue of what did not work, and why

*Every claim below is traced to a committed result file — a `.jsonl` run log,
a `_findings.md` write-up, or an offline analysis script's output. Numbers
were spot-checked directly against the raw JSONL where the write-up did not
already show the arithmetic (see the "Verified directly" markers and §6).
Where a claim could not be traced to a committed file, it was omitted rather
than asserted from memory.*

---

## 1. Why these negative results matter

> **Scope correction, 2026-07-30.** This section previously argued that these
> nulls "have no published prior to compete with," citing a research pass over
> frontier open-weight model reports. **That inference does not hold**, and the
> correction is recorded here rather than quietly deleted. The review's actual
> finding was narrow and correctly stated at its source: no *surviving claim in
> that report corpus* addressed orchestration. The corpus was frontier-lab
> technical reports about **building single models** — it was never a review of
> the multi-agent systems literature. Absence of orchestration claims from that
> source set is a limitation of the review corpus, not evidence about the
> field.
>
> The claim is in fact **self-refuting from this repository's own files**: the
> repo cites Self-MoA (Li et al., "Rethinking Mixture-of-Agents", arXiv
> 2502.00674, 2025-02-02) in eleven places — including as the source of the
> *prediction* that this project's homogeneity trap would occur — and cites Sea
> AI Lab (arXiv 2503.20783) as an external refutation of its own reflection-
> token null. A project that cites external orchestration literature to
> corroborate its findings cannot also claim that literature does not exist.
> `docs/frontier-oss-model-research.md` even rated its own orchestration
> synthesis *"inferential and rated low"*; downstream documents quoted it as
> established fact. See `docs/prior-art-and-positioning.md` for the full
> component-level prior-art map.
>
> **The corrected thesis:** these results are valuable because they are measured
> under one reproducible orchestration stack and traced to committed artifacts.
> They show how homogeneity, escalation coverage, saturation, corpus mismatch,
> judge access, and cost interact in QuorumQA's specific setting. They should
> **not** be read as the field's first negative results.

The original argument is preserved below for audit. Read it as the reasoning
that was corrected, not as current positioning.

A verified, cited research pass over the frontier open-weight literature
(`docs/frontier-oss-model-research.md`, 104 agents, ~15 primary sources,
3-vote adversarial verification per claim) found a specific, named gap:

> **MAJOR GAP: No surviving claim addresses the entire multi-agent section of
> the brief — ensembling, mixture-of-agents (Self-MoA vs mixed-MoA), model
> routing, LLM-as-judge, self-preference bias, or debate/deliberation, nor
> the conditions under which combining models helps vs hurts.**
> (`docs/frontier-oss-model-research.md`, "Caveats (verification harness)")

Every frontier lab publication the harness could find and verify — Kimi K2,
DeepSeek-V3/R1/V3.2, DAPO, GSPO, VAPO, Lite-PPO — is about **building a
single model**: architecture, training stability, RL reward shaping. None of
it is about **orchestrating panels of already-built models**: when does a
second opinion help, when does a judge add value over the panel it judges,
when does retrieval help a panel that is already confident and wrong. The
harness's own synthesis states this plainly: *"the leap to multi-agent/
ensemble design is unvalidated by the surviving evidence set"* (finding 14).

~~This means the null results in this project have no published prior to
compete with, agree with, or be refuted by.~~ **[RETRACTED 2026-07-30 — see the
scope correction above. The reviewed corpus contained no orchestration claims;
the broader literature does. Corrected reading: no *frontier-lab technical
report in that corpus* provides a prior for these nulls.]** Two consequences
follow, and both are the actual point of this document:

1. **There is little frontier-lab validation to fall back on.** Every claim
   below stands or falls on this project's own 3-seed empirical record. That is
   why the tone throughout is source-traced rather than argued. *(Corrected:
   the original read "there is no literature to argue with" — there is, and
   this repo cites some of it. What is genuinely absent is a same-stack,
   same-harness, cost-accounted comparison to argue against.)*
2. **The nulls are the most exportable thing this project has produced.**
   A positive result on a resource-limited hackathon build is, at best, a
   3-seed replication of an effect a bigger lab could reproduce with more
   compute. A negative result that pins down *why* three structurally
   different levers (a stronger judge, a bigger panel, a smarter selector)
   all failed in the *same mechanistic way* is not compute-limited — it is a
   fact about the shape of multi-agent deliberation ~~and it is currently
   unpublished anywhere else~~ **[RETRACTED: no exhaustive search supports
   "unpublished anywhere else". The defensible version is that this particular
   set of mechanisms, measured on one stack with one cost model and traced to
   committed artifacts, is not something we found published in that form.]**
   `docs/capability-roadmap.md` names this item directly as **F10,
   "Null-harvest writeup (S5)"** — whose own rationale carried the same
   over-generalization and is corrected in that file.

This document is that writeup.

---

## 2. The one law that organizes every null

**Deliberation pays if and only if (a) the cheap and flagship tiers'
errors decorrelate into visible disagreement, and (b) the escalation
mechanism actually fires on that disagreement.** What predicts whether those
conditions can be met is the **cheap-to-flagship gap**, operationalized as the
**unanimous-wrong rate** (how often the cheap panel confidently agrees on a wrong
answer) — not subject difficulty, not benchmark prestige, and not how high the
flagship's own baseline sits.

**That gap is necessary, not sufficient — and this project's own figure caught us
overstating it.** Plotting the gap against the best paired lever delta puts
SuperGPQA-hard (23%, +4.1) in "large gap → deliberation pays", but LEXam (22%,
**−6.0**) and MMLU-Pro (14%, **−2.0**) land in a quadrant the figure labels "large
gap, lever still lost" — two of five plotted points. A large gap pays only when
the missing ingredient is *decorrelation*. Where it is missing *knowledge or
corpus* (§3.5, LEXam's Swiss law against a STEM/US-law index) the gap is real, the
escalation fires, and the answer is still wrong.

![The law, and where it breaks](figures/f05_unanimous_wrong_vs_lever_delta.png)

The table below is the single strongest piece of evidence for this law,
because medicine and hard science are *both* "knowledge-and-reasoning
multiple-choice benchmarks" by any subject-matter taxonomy, and they sit at
opposite ends of it:

| Surface | Flagship baseline | Unanimous-wrong rate | Lever outcome | Source |
|---|---|---|---|---|
| SuperGPQA-hard | ~79.3–79.5% (3 seeds) | 23% (20/86, seed 42) | `flagship_panel` **+4.1 mean** (3 seeds, never negative) — but it **fails its compute-matched SC@3 control** (tribunal leg net +2, p=0.344; the panel vs the control is net +1, p=0.50). The gain is sampling, not deliberation | `benchmark/results/supergpqa_findings.md` |
| GPQA Organic Chemistry slice | matched flagship (83.3–86.5%) | 18.9% (37 questions, seed 42) — 0% on every physics subject in the same set | `chem_thinking_gate` **+4.4** vs matched flagship (3-seed mean 90.9%, spread 0.2pt) | `benchmark/results/lever_findings.md` |
| GPQA-Diamond (full) | 84.4–86.5% (3 seeds) | ~11% | `thinking_gate` **+1.1 to +2.3** (3-seed replicated, one seed a tie) | `benchmark/results/lever_findings.md` |
| MedQA | 94.0% | **4%** (2/50) | tie, **+2 = one item of 50** | `benchmark/results/medqa_findings.md` |
| MMLU-Pro (4-choice trim, full) | 94.0% | ~14% (7/50) | shipped engine **−12** | `benchmark/results/mmlu_pro_findings.md` |
| MMLU-Pro STEM (4-choice, 6 hard categories) | 96.7% | **1.7%** (1/60) | `flagship_panel` **+0.0**, escalation 3.3% | `benchmark/results/flagship_panel_mmlu_pro_stem_findings.md` |
| MATH-500 L5 (open-answer) | 96.6% (cheap tier also 96.6%) | **0%** escalation at both tiers | inert | `benchmark/results/math_open_pilot_findings.md` |
| GSM8K / MATH-500-MC (distractor) | 100% (both) | ~4–6% | **−4.0 / −6.1** | `benchmark/results/math_findings.md` |
| LEXam (English, `mcq_4`) | 86.0% (seed 42, n=50) | 22% (11/14 wrong rows unanimous) | engine **−14** | `benchmark/results/lexam_findings.md` |

Wins cluster exactly where the unanimous-wrong rate is large (SuperGPQA-hard
23%, Organic Chemistry 18.9%). Nulls and losses cluster exactly where it is
near zero (MMLU-Pro STEM 1.7%, MedQA 4%, MATH-500 L5 0%) *or* where it is
elevated but the flagship's own baseline is already very high, so a loss
still reads as a loss on the shipped cheap-tier engine (MMLU-Pro full,
LEXam). MedQA and MMLU-Pro-full share the *same* 94% flagship baseline and
land on opposite sides of the ledger (+2 tie vs −12 loss) purely because
their unanimous-wrong rates differ by 3.5x (4% vs 14%) — this is the
cleanest isolation of "baseline height doesn't predict the outcome, the gap
does" the project's own data produces
(`docs/capability-roadmap.md` §1.1, `benchmark/results/medqa_findings.md`).

The law has a precondition worth stating precisely, because it produces two
*different* inert regimes rather than one: **ceiling saturation** (both
tiers succeed — MMLU-Pro STEM, MATH-500, GSM8K, MedQA) and **floor
saturation** (both tiers fail the same way — predicted by the roadmap,
never yet measured in this project's logged data; recording it is listed as
an open, zero-token opportunity in `docs/capability-roadmap.md` §2.4's
"Dropped outright" list). Every catalogued saturation null below is a
ceiling case.

---

## 3. The catalogue

Twenty-three distinct measured nulls, grouped by mechanism.

### 3.1 Saturation nulls — the benchmark ran out of headroom before the lever could be tested

**A1. MMLU-Pro (full, 4-choice trim) — shipped engine −12**

- *Hypothesis.* The shipped 3-cheap-solver + escalation engine beats a
  single flagship call, generalizing the GPQA-Diamond win.
- *Config.* Shipped engine vs single `qwen3.7-max` baseline, n=50, seed 42,
  MMLU-Pro trimmed from its native up-to-10 options to 4 (engine's
  hardcoded A–D contract).
- *Measured.* Baseline 94.0%, engine 82.0%, delta **−12**. 7/50 wrong
  answers were unanimous (all three cheap seats agreed, confidently, on the
  same wrong letter).
- *Mechanism.* The flagship baseline is already near-ceiling on this
  trimmed sample; the cheap panel's remaining errors are almost entirely
  the unanimous-wrong failure mode escalation cannot see by construction.
  A disclosed confound: 4-choice trimming (from native up to 10) likely
  makes this sample mechanically easier than the benchmark's published
  difficulty, inflating the 94% baseline itself.
- *Source.* `benchmark/results/mmlu_pro_findings.md`.

**A2. MMLU-Pro STEM (4-choice, 6 hard categories) — flagship_panel +0.0**

- *Hypothesis.* `flagship_panel` (the lever validated +4.1 mean on
  SuperGPQA-hard) generalizes to a third hard-STEM benchmark.
- *Config.* `flagship_panel` engine vs single flagship, n=60, seed 42.
- *Measured (verified directly against `lever_baseline_mmlu_pro_stem_seed42.jsonl`
  and `lever_flagship_panel_mmlu_pro_stem_seed42.jsonl`).* Both 96.7%
  (58/60), delta **+0.0**. Escalation 3.3% (2/60). Unanimous-wrong 1.7%
  (1/60).
- *Mechanism.* Not a negative for the lever — a **predictive confirmation**
  of the law in §2. The flagship already scores 96.7%, so the unanimous-
  wrong rate is 1.7% (vs 23% on SuperGPQA-hard, where the same lever wins
  +4.1); the law forecasts ≈0 lift from the gap alone, and 0.0 is what came
  back.
- *Source.* `benchmark/results/flagship_panel_mmlu_pro_stem_findings.md`.

**A3. MATH-500 L5 open-answer — 96.6% at both tiers, 0% escalation**

- *Hypothesis.* Flagship-panel deliberation beats a single flagship call on
  genuinely hard open-answer math (the surface distractor-MC couldn't test,
  since it saturated the flagship at 100%).
- *Config.* Two pilots, n=59 (1 drop/arm), seed 42: (i) 3-flagship-solver
  panel with judge-on-3-way-split vs single flagship; (ii) shipped-design
  cheap panel (3 `qwen3.6-flash` solvers + flagship judge) vs the same
  baseline.
- *Measured.* Flagship panel: baseline 96.6% (57/59), panel 98.3% (58/59),
  **+1.7pp (one question), 0.0% escalation** (57/59 all-three-agree, 0/59
  three-way split). Cheap panel: baseline 96.6%, cheap panel 96.6%, **+0.0,
  0.0% escalation** (55/59 unanimous, 46 literally identical answer
  strings).
- *Mechanism.* Two independent findings stack: (1) three homogeneous strong
  solvers on math converge almost every time, so the disagreement-triggered
  tribunal has nothing to trigger on — the same mechanism as the
  `qwen38_panel` negative (B1 below); (2) `qwen3.6-flash`-with-thinking
  scores 96.6% on this slice, identical to the flagship, so even the
  shipped cheap-tier design finds no gap to exploit. The +1.7 is pure
  self-consistency@3 noise, not deliberation.
- *Corrected number, disclosed.* The first grading pass reported 89.8%/91.5%
  before a grader bug was fixed; see §4 — the 96.6%/98.3% figures above are
  the corrected, re-graded numbers and are the authoritative ones.
- *Source.* `benchmark/results/math_open_pilot_findings.md`.

**A4. GSM8K (distractor-MC) — shipped engine −4.0**

- *Hypothesis.* Same shipped engine, tested on easy grade-school math.
- *Config.* Shipped engine vs single flagship, n=50, seed 42, distractor-MC
  synthesis (open-answer converted to 4-option; **not** comparable to
  published open-answer GSM8K numbers).
- *Measured.* Baseline 100.0%, engine 96.0% (2 wrong), delta **−4.0**.
- *Mechanism.* Flagship saturates the distractor-MC framing entirely
  (numeric distractors are trivially eliminable by computing the answer);
  the cheap panel occasionally trips on an eliminable distractor the
  flagship never would. A small, consistent no-harm-but-not-zero cost on a
  fully saturated surface.
- *Source.* `benchmark/results/math_findings.md`.

**A5. MATH-500 level-5 distractor-MC — shipped engine −6.1**

- *Hypothesis/config.* Same shipped engine, hardest MATH-500 tier converted
  to distractor-MC, n=49, seed 42.
- *Measured.* Baseline 100.0% (perfect), engine 93.9%, delta **−6.1** (3
  questions).
- *Mechanism.* Identical shape to A4 at higher stakes: distractor-MC
  removes the actual difficulty of hard math (synthetic distractors —
  order-of-magnitude slip, sign flip, ±5–30% near-miss — are eliminable by
  direct computation), so the flagship aces it and the cheap panel's rare
  distractor slip is pure downside. This result is superseded as a *math
  reasoning* test by A3 (open-answer), but stands as its own distinct
  finding about distractor-MC as an instrument.
- *Source.* `benchmark/results/math_findings.md`.

**A6. MedQA — tie, +2 (one item of 50), 4% unanimous-wrong**

- *Hypothesis.* Shipped engine on native 4-option USMLE-style medicine
  questions.
- *Config.* Shipped engine vs single flagship, n=50, seed 42, no trimming
  (native 4-option, so absolute numbers ARE comparable to other reports of
  this benchmark, unlike the trimmed surfaces above).
- *Measured.* Baseline 94.0%, engine 96.0%, delta **+2.0 (one question)** —
  reported explicitly as a tie, not a win. Zero overturns on 3 escalations;
  the one-point edge is self-consistency-by-chance at this n. Unanimous-
  wrong 4% (2/50).
- *Mechanism.* This is the clean control case for the law: MedQA and
  MMLU-Pro (A1) share the same 94% flagship baseline, but MedQA's cheap
  tier genuinely knows medicine (4% unanimous-wrong) where MMLU-Pro's
  cheap tier does not (14%) — the sole variable that predicts tie vs −12
  loss. `docs/capability-roadmap.md` states this explicitly as a closed
  axis: *"MedQA is permanently closed as an accuracy axis... No future
  medical accuracy claim may be sourced from MedQA."*
- *Source.* `benchmark/results/medqa_findings.md`.

### 3.2 Homogeneity-trap nulls — making solvers more similar (stronger, more numerous, more thoughtful) kills the disagreement the tribunal needs

**B1. qwen38_panel (SuperGPQA-hard) — 0% escalation, 30% timeout drops**

- *Hypothesis.* Swapping all three solver seats to the family's strongest
  single model (`qwen3.8-max-preview`, 93.8% survivor-only (upper-biased); honest interval **[83.3%, 94.4%]**, point estimate RETIRED 2026-07-30 by D0's own kill clause — solo on GPQA) beats
  `flagship_panel` (`qwen3.7-max`, validated +4.1 mean).
- *Config.* 3× `qwen3.8-max-preview` solver seats, SuperGPQA-hard, seed 42,
  concurrency 2.
- *Measured (verified directly against `lever_qwen38_panel_supergpqa_seed42.jsonl`).*
  63/90 items survived (27 dropped to 300s timeouts, concentrated in
  Science/Engineering — the hardest questions); escalation **0/63 (0%)**.
  On the 58 items common to all four systems tested (an easier tail: this
  subset's baseline reads 87.9% vs 79.5% on the full set), qwen38_panel
  scored 87.9% — tying the single-flagship baseline and **trailing**
  `flagship_panel`'s 89.7% on the same items.
- *Mechanism.* Three heavy-thinking 3.8 seats agree with each other so
  consistently that escalation never fires; the entire Skeptic/Verifier/
  Judge apparatus sits idle. `qwen38_panel` is not deliberation on a
  stronger tier — it is 3× self-consistency at premium cost. A stronger,
  more-homogeneous tier bought nothing and cost more; the survivorship-
  biased 30%-drop pool is also inconclusive on exactly the hardest
  questions where a stronger tier might have mattered most.
- *Source.* `benchmark/results/supergpqa_findings.md`.

**B2. All-flagship math panel (MATH-500 L5) — 0% escalation**

- Already detailed as part of A3 above (0/59 three-way splits, 57/59
  all-agree). Listed here separately because it is mechanistically the
  *same* homogeneity-trap finding as B1, independently reproduced on a
  different benchmark and a different model tier (flagship-vs-flagship
  rather than 3.8-vs-3.7): three strong, similarly-capable solvers on the
  same task converge, and convergence starves the tribunal.
- *Source.* `benchmark/results/math_open_pilot_findings.md`.

**B3. Five solvers (N=5) — 81.1% vs flagship 84.4%, confounded by lens-cycling**

- *Hypothesis.* More solver seats (`N_SOLVERS=5` vs the shipped 3) improves
  accuracy via more sampling.
- *Config.* GPQA-Diamond, seed 42, n=90, 5 solver seats instead of 3.
- *Measured.* 81.1%, above the shipped 3-solver engine's 78.9% but below
  the flagship's 84.4%, at higher cost (escalation 43.3%).
- *Mechanism — the confound, stated because it makes this a flawed test,
  not a clean negative.* `SOLVER_LENSES` defines only 3 distinct
  perspectives, and `_lenses_for()` cycles them while `solve_all()` cycles
  3 temperatures on the same period — so **seat 4 was a byte-identical
  config to seat 1, and seat 5 to seat 2** (verified from the code path;
  `docs/experiment-spec-book.md` §MATH-6/S1-S2). This tested more *copies*,
  not more *perspectives*. The result is real (81.1% is what was measured)
  but it does not test the hypothesis it was designed to test — the
  honest label is "confounded, not deliberation-tested," and the
  confound-controlled replacement (S1/S2's lens-cycled vs diversified N=15
  harvest, `docs/experiment-spec-book.md`) is designed but its paid run
  status is not confirmed in the committed record as of this writing.
- *Source.* `benchmark/results/lever_findings.md`; confound diagnosis in
  `docs/experiment-spec-book.md` §"MATH-6" and §1 (S1/S2).

**B4. Mixed-model weak seat (`qwen3.7-plus`, thinking off) — dropped for cause**

- *Hypothesis.* A structurally different model as a third seat increases
  panel diversity.
- *Measured.* 54.1% accuracy solo — the weakest seat tested, and the source
  of every JSON-malformation drop in that run. Removed from `config.py`
  before further use.
- *Mechanism.* Diversity from an under-capable seat is not free: a seat too
  weak to reliably even format its answer correctly degrades the panel
  rather than diversifying it. Diversity has to come from *conditioning*
  differences among capable seats, not from including an incapable one.
  Cited in `lever_findings.md`'s diagnosis section as the reason a "plain
  model swap" proposal would reproduce a known failure if re-tried without
  addressing why it failed the first time.
- *Source.* `benchmark/results/lever_findings.md` ("Diagnosis" section,
  referencing `config.py:29-32`).

**B5. thinking_all (all three seats thinking-enabled) — underperforms one thinking seat**

- *Hypothesis.* If one thinking-enabled seat helps (`thinking_gate`
  validated +1.1 to +2.3), all three thinking-enabled should help more.
- *Config.* GPQA-Diamond, seeds 42 and 7, all 3 solver seats `thinking=True`,
  cheap tier, still with the universal doubt-gate.
- *Measured.* 85.6% (seed 42) and 83.3% (seed 7) — below the single-
  thinking-seat lever's 86.7%/83.3% at the same seeds, while costing
  40–60% more. Escalation collapsed to 18.9–21.1%, vs 47.8–53.9% for the
  single-thinking-seat design.
- *Mechanism.* Making every seat "smarter" makes the seats agree with each
  other more, which starves the tribunal exactly as in B1/B2 — the same
  homogeneity trap at a smaller scale (cheap tier, added reasoning rather
  than added strength). The value was never raw capability; it was one
  differently-calibrated seat creating productive disagreement.
- *Source.* `benchmark/results/lever_findings.md`.

**B6. smart_gate (Organic-Chemistry-targeted thinking) — 83.1%, worse than baseline on chemistry itself**

- *Hypothesis.* Following the diagnosis that Organic Chemistry carries an
  18.9% unanimous-wrong rate (vs 0% for every physics subject in the same
  set), concentrate the expensive thinking-seat treatment specifically on
  that subject — capture most of `thinking_gate`'s gain at a fraction of
  the cost.
- *Config.* Seat 3 runs `thinking=True` only when `item.subject ==
  "Organic Chemistry"`; universal doubt-gate kept; GPQA-Diamond, seed 123,
  n=89.
- *Measured.* Overall 83.1% — below both `thinking_gate` (86.7%) and the
  plain flagship baseline (85.6%) at the same seed. Broken down: on
  Organic Chemistry itself, `smart_gate` scored **72.2%**, *below* the
  plain baseline's 77.8%, despite escalating 26/36 (72%) of those
  questions.
- *Mechanism.* The diagnosis that disagreement concentrates in Organic
  Chemistry was correct, but disagreement is a *symptom* of a knowledge
  gap, not a target fixable by pointing more reasoning time at the same
  base model. All three solver seats, the Skeptic, and the Verifier share
  one base model (`qwen3.6-flash`); a thinking-enabled seat running the
  same model tends to reproduce the same conceptual blind spot with more
  confident-sounding reasoning attached, and the tribunal it escalates to
  has no fundamentally new information to correct it with. This is a
  distinct, sharper mechanistic finding from B1/B5: it establishes that
  homogeneity isn't only about *how many* seats or *how hard* they think —
  it's about whether the added effort comes from the *same* model's
  knowledge or a *different* one's. (The follow-up, `chem_flagship_gate` —
  a genuinely different, stronger model on the same subject — is a
  validated **win**, +4.4 vs matched flagship, confirming the mechanism by
  contrast.)
- *Source.* `benchmark/results/lever_findings.md`.

### 3.3 Wrong-stage nulls — the fix targets adjudication quality, but the bottleneck is upstream of adjudication

**C1. qwen38_judge — 9/9 overturns correct, zero net gain**

- *Hypothesis.* Swapping the Judge role to `qwen3.8-max-preview` (93.8% survivor-only (upper-biased); honest interval **[83.3%, 94.4%]**, point estimate RETIRED 2026-07-30 by D0's own kill clause; formerly quoted as 93.6%
  solo vs `qwen3.7-max`'s 85.6%) lifts the engine, since the Judge rules on
  every escalation.
- *Config.* GPQA-Diamond, seed 42 (the frozen submission run's own
  questions, for a paired comparison), shipped engine otherwise unchanged.
- *Measured (verified directly against `lever_qwen38_judge_gpqa_seed42.jsonl`).*
  n=76/90 survived (14 dropped, 13/14 in Organic Chemistry — a
  survivorship pattern, disclosed rather than retried because the
  conclusion is robust without it). Headline 80.3%, capped at 83.3% even
  under a perfect-14/14 best case on the drops — still below the flagship
  baseline (84.4%). Paired against the frozen run on the 76 survivors:
  fixed 1, broke 3, net **−2**, inside the measured ±2.5pt noise floor.
  **The judge itself went 9/9 on overturns it made** (verified: 9 rows
  both escalated and had `final_letter != plurality_letter`, all 9
  correct) — strictly better than the frozen run's own judge (11/14 =
  78.6%).
- *Mechanism.* Judge quality was never the binding constraint. 14 of the
  surviving set's errors were unanimous-wrong — confident three-way
  agreement no judge, however good, ever gets a chance to see. A better
  adjudicator polishes a stage that was already performing well; it cannot
  reach the failure mode that actually dominates the error budget. This is
  the cleanest single demonstration in the whole record that **coverage
  (what reaches the tribunal), not tribunal quality (what happens there),
  is the ceiling.**
- *Source.* `benchmark/results/lever_findings.md`.

**C2. R2 disputed-step recursive retrieval (SuperGPQA-hard) — −1.2 vs R1, structurally can't touch the floor**

- *Hypothesis.* A second, sharper retrieval pass at the tribunal stage
  (grounded in the Skeptic's named disputed step) beats one-shot pre-solve
  retrieval (R1, validated +6.5 mean before its 4th-seed correction — see
  D4).
- *Config.* `rag_recursive` = R1 + a second retrieval fired only on
  escalation, feeding the Verifier. SuperGPQA-hard, seed 42, n=90.
- *Measured.* Apples-to-apples on 85 common items: cheap-panel (no RAG)
  67.1%, `rag_presolve` (R1 only) 71.8%, `rag_recursive` (R1+R2) 70.6% —
  **−1.2 vs R1** (within noise at this n, one seed). Unanimous-wrong count
  identical (14) between R1 and R1+R2. At the tribunal it does reach: 18→24
  overturns, but overturn-correct quality dropped 72%→62.5%.
- *Mechanism.* R2 fires only on escalation, so by construction it cannot
  touch the unanimous-wrong floor — exactly where R1's accuracy gain
  lives. More tribunal-stage evidence made the judge more interventionist
  without making it righter (more overturns, lower overturn quality): the
  same "wrong stage" lesson as C1, from the retrieval side. This
  SuperGPQA-hard negative does **not** generalize to LEXam, where the
  mechanism is different (reviving a *dead* verifier that produces zero
  findings, vs. adding evidence to an already-strong one) — see E1/G3.
- *Source.* `benchmark/results/rag_r2_findings.md`.

### 3.4 Signal-that-isn't nulls — a plausible proxy carries no real discriminating information

**D1. Retrieval score-gating — regressions and wins are statistically identical (0.0288 vs 0.0290)**

- *Hypothesis.* Gate retrieval injection on the top fused retrieval score,
  to suppress the seed-271 failure mode where misleading-but-confident
  passages create false unanimous consensus.
- *Config.* Offline calibration over all 4 logged `rag_presolve` seed runs
  (350 questions, `benchmark/results/rag_gating_calibration.csv`); no paid
  API call was spent because the offline data settles the question.
- *Measured (verified directly against the CSV).* Mean top retrieval score:
  regressions (RAG hurt) **0.0288** (n=30), helped (RAG rescued) **0.0290**
  (n=41), neutral 0.0286 (n=279) — statistically indistinguishable. A
  threshold sweep confirms no operating point suppresses regressions
  without discarding an equal number of wins; net recovered goes negative
  past T≈0.02.
- *Mechanism.* The fused score measures retrieval *confidence* (how
  strongly the index believes a passage matches the query text), not
  *correctness for this specific question*. A passage that is confidently,
  topically on-point but wrong for the exact question (a closely-related
  but distinct concept) scores identically to a passage that is right. A
  score threshold is structurally blind to that distinction — it cannot
  separate confidently-right from confidently-wrong. The real mitigation
  (already measured, not filtering by score) is `rag_thinking_gate`: a
  thinking seat plus the doubt-gate cut the same seed's unanimous-wrong
  floor 22→9, because reasoning *about* evidence catches what a number
  cannot.
- *Source.* `benchmark/results/rag_gating_analysis.md`.

**D2. W5 trace-feature wrongness predictor — AUC 0.625 band; F3's distribution-feature upgrade is NEGATIVE**

- *Hypothesis.* Verbalized confidence, trace-shape (reasoning length,
  hedge-word rate), and vote-distribution features (agreement rate,
  top-vote share, entropy) can predict, per-item, whether the engine's
  answer is wrong — a candidate cost-router or confidence gate.
- *Config.* 5,597 rows across 11 benchmarks, leave-one-benchmark-out
  logistic regression, bootstrapped 95% CI, primary label = engine/panel
  wrong.
- *Measured (verified from `wrongness_predictor_findings.md`'s own tables).*
  Median per-benchmark LOBO AUC, full feature set: **0.625** (BAND —
  usable only as a router input, never an accuracy claim). F3's
  pre-registered comparison, verbalized-only (0.647) vs
  verbalized+trace+distribution (0.621): **ΔAUC = −0.026**, i.e. adding
  trace and distribution features made the predictor *worse*.
- *Mechanism.* Two structural facts explain the ceiling. First, **61.6% of
  wrong panel rows are unanimous** (verified: 615/998 wrong rows), and on
  unanimous items the agreement/entropy features are maximal-and-useless
  by construction — they cannot distinguish a unanimous-correct item from
  a unanimous-wrong one. Second, the top standardized coefficient by
  magnitude is `is_unanimous` (−0.572, higher → more likely correct),
  meaning the model is substantially just learning "disagreement predicts
  wrongness," which is already known and does not need a trained model to
  state. This is an internal, independently-derived confirmation of the
  external frontier-research finding that reflective-token ("wait") counts
  do not track correctness (Sea AI Lab, cited in
  `docs/frontier-oss-model-research.md` finding 12) — two unrelated
  methods converge on "hedge/reflection-style trace features carry little
  signal beyond agreement itself."
- *Source.* `benchmark/results/wrongness_predictor_findings.md`.

**D3. Answer-instability — the +24.4pp lift lands on its own permutation-null mean (p=0.48)**

- *Hypothesis.* Items whose replicate answers disagree ("unstable") are
  more likely wrong than items whose replicates agree ("stable") — a
  genuine, buildable escalation-trigger signal.
- *Config.* 1,039 multi-replicate items across 8 benchmarks, re-keyed on
  choice TEXT (not letter, since `_shuffle_choices` reshuffles per seed),
  scored at item level via text-majority, compared against a permutation
  null that holds each item's real right/wrong replicate count fixed and
  randomly reassigns which observed wrong text each wrong replicate lands
  on (NDRAWS=5,000, fixed seed).
![Per-seed spread](figures/f06_per_seed_spread.png)

*Related, and the reason a mean is not a finding: `chem_thinking_gate` clusters
inside 0.2pt across three seeds while `rag_presolve` reads +4.7 / +6.9 / +8.0 and
then **−5.6**. Two mean-positive levers, entirely different confidence.*

- *Measured (verified from `stability_audit_summary.json` and the
  write-up's own tables).* Observed overall lift P(wrong|unstable) −
  P(wrong|stable) = **+24.4pp** (34.2% vs 9.8%). Permutation-null mean:
  **+24.1pp**, 95% CI [+21.5, +26.9]pp. Empirical p(null ≥ observed) =
  **0.48**. Per-benchmark: GPQA-Diamond +18.3pp observed vs +17.5pp null
  mean (p=0.42); SuperGPQA-hard +22.0pp vs +20.7pp (p=0.32); LEXam +42.8pp
  vs +42.9pp (essentially identical, p=0.64).
- *Mechanism.* An item whose replicates disagree is mechanically
  guaranteed to contain at least one wrong replicate (if all replicates
  agreed, they'd report the same, single correct text — disagreement is
  impossible among all-correct replicates). Whether an all-wrong item's
  votes happen to concentrate on one wrong text ("stable," i.e. all wrong
  the same way) or scatter across several ("unstable") is close to a coin
  flip once more than one wrong option exists to land on. The observed
  effect is therefore almost entirely this combinatorial floor, not a
  genuine wrongness signal — the null was built specifically to isolate
  and subtract exactly this artifact, and it accounts for essentially all
  of the raw lift.
- *Consequence.* This is a **kill** by the project's own house rule (kill
  dominates bar): no instability-fed router, no permutation/paraphrase
  escalation trigger built on raw agree/disagree, and the unanimous-wrong
  floor is not reducible by cheap resampling alone. It confirms, from
  independently-repaired logged data, the same conclusion the separate
  paid `permuted_panel` probe (META-2) was designed to test.
- *Source.* `benchmark/results/stability_audit.md`.

**D4. rag_presolve's negative tail (seed 271, −5.6) — retrieval manufacturing the exact failure mode it targets**

- *Hypothesis (implicit, discovered rather than pre-registered).* Does
  injected retrieval evidence ever *create* unanimous-wrong consensus
  rather than only preventing it?
- *Config.* `rag_presolve` on SuperGPQA-hard, seed 271 — the 4th seed in
  `rag_presolve`'s validation sequence, run as the control arm of an
  unrelated composition test; same corpus, same code as the immediately
  prior (positive) seed 123.
- *Measured.* cheap-panel (no RAG) 66.3%, cheap+RAG **60.7% (−5.6)**.
  Unanimous-wrong floor *rose* under RAG: 22 (control) → 25 (RAG). Of 13
  regressions (control-right → RAG-wrong), **10 were unanimous-wrong under
  RAG**.
- *Mechanism.* Retrieved passages that are plausible-but-wrong for the
  exact question can actively mislead a panel into confident false
  consensus — the identical mechanism D1's score-gating tried and failed
  to filter, discovered here as a live failure rather than an offline
  audit. This single negative seed is why `rag_presolve`'s status was
  downgraded from "validated, robust" (3 seeds, mean +6.5) to
  "validated-with-variance" (4 seeds, mean +3.5, 3 of 4 positive) — see
  §4's disagreement log. The mitigation that resisted this specific
  failure at the same seed, `rag_thinking_gate` (floor cut 22→9 at seed
  271, never negative across 3 seeds, mean +3.0), is documented in
  §3 nowhere else in this catalogue because it is a validated **win**, not
  a null — cited here only as the seed-271 counterfactual.
- *Source.* `benchmark/results/rag_r1_findings.md` ("Fourth seed (271)").

**D5. The unanimous-wrong rate does not predict whether a lever wins — it only bounds it (r=−0.216, p=0.73)**

- *Hypothesis.* Since the escalation gate fires on disagreement, an item
  where all three cheap solvers agree *and* are wrong is invisible to the
  cascade. The unanimous-wrong rate is therefore the pool any lever could
  recover, and README.md claimed it "predicts whether that is even
  possible." Does it?
- *Setup.* All 5 benchmarks with both numbers measured
  (`figure_f05_unanimous_wrong_vs_lever_delta.csv`). Threshold for
  "predictive" fixed at p<0.05 as a named constant *before* the statistic
  was computed, not chosen after seeing it.
- *Result.* **Two claims were hiding in that one word, and only one
  survives.**

  | | claim | verdict |
  |---|---|---|
  | **bound** | a lever cannot move more accuracy than there is unanimous-wrong to recover | **holds, 5 of 5** |
  | **prediction** | the rate tells you where in that range a lever lands, or its sign | **not supported** |

  Pearson **r = −0.216 (p = 0.7270)**, Spearman **ρ = +0.100 (p = 0.8729)** —
  the two do not agree on the **sign**, which is the clearest available
  evidence that neither is measuring anything. The decisive pair sits one
  point of headroom apart:

  | benchmark | unanimous-wrong | best lever | evidence |
  |---|---:|---:|---|
  | LEXam | 22.0% | **−6.0 pp** | 1 seed, screen |
  | SuperGPQA-hard | 23.0% | **+4.1 pp** | 3 seeds, validated |

  Levers convert between **−27.3% and +50.0%** of the available headroom, a
  range spanning zero. Only **1 of the 5** points is validated at 3 seeds.
- *Mechanism.* Headroom says an error pool exists; it says nothing about
  whether the pool is *reachable by re-reading the panel's own output*. On
  LEXam it is not — the missing ingredient there is knowledge, so a lever
  aimed at decorrelation moves accuracy the wrong way. This is the same
  boundary as the ten mechanism nulls in §5: a large gap is a large gap of
  *unanimous* error, and unanimity is exactly the condition under which the
  panel has no internal signal left to exploit.
- *Consequence.* README.md's "predicts" is retired in favour of "bounds",
  with the numbers shown at the point of correction rather than the verb
  quietly swapped. Note this also retires the temptation to use the rate to
  *choose* which benchmark to work on next — it cannot rank candidates.
- *Source.* `benchmark/results/headroom_rule_analysis.json`; reproduce with
  `python -m benchmark.analyze_headroom_rule`.

### 3.5 Domain/corpus nulls — the architecture is sound but the surface, or the data behind it, cannot support it

**E1. LEXam law — shipped engine −14**

- *Hypothesis.* Same shipped engine (validated on GPQA), tested on Swiss/
  international law MCQs.
- *Config.* Shipped engine vs single flagship, n=50, English `mcq_4`
  config, seed 42.
- *Measured (verified directly against `lexam_pilot_seed42.jsonl`).*
  Baseline 86.0% (43/50), engine 72.0% (36/50), delta **−14**. 11 of the
  engine's 14 wrong answers were unanimous. Escalation 18% (9/50); of 7
  overturns, only 4 correct (57% — barely better than the 3-of-remaining-
  options 33% a blind guess would get after eliminating the chosen wrong
  letter). 7 of 9 escalations (78%) produced **zero** Verifier findings.
- *Mechanism.* The Verifier's tools (`lookup_constant`, `safe_calculate`)
  exist to ground numeric/physical-constant claims — exactly what a
  physics or chemistry question has and a statement-based legal MCQ mostly
  does not. On LEXam, escalation effectively degrades to Skeptic-plus-
  Judge with no independent tool-grounded check to break ties, which is
  the mechanistically clean explanation for the near-coin-flip overturn
  rate.
- *Source.* `benchmark/results/lexam_findings.md`; corroborated by the
  full engine dominance table in `benchmark/results/family_floor_analysis.md`
  §F2 (LEXam: `baseline_3.7max` 86.0% @ 1,285 tok is the entire Pareto
  frontier — every lever tested against LEXam is dominated).

**E2. Swiss-law corpus (`rcds/swiss_legislation`) — LAW-0 does not clear the 30% overlap bar; 88% of the LEXam English pool is Interdisciplinary**

- *Hypothesis.* LEXam's −14 was a corpus-coverage problem (the existing
  STEM/US-law Wikipedia RAG index has no Swiss statute content); a real
  Swiss-law corpus would close most of the gap.
- *Config.* Live probe of `rcds/swiss_legislation`'s 207 English rows
  against the HuggingFace datasets-server, manual audit of the strongest
  automated keyword matches against the 90-item logged LEXam English pool.
- *Measured.* The corpus is real (207 English federal-legislation rows out
  of 35,698 total, verified via two independent HF endpoints). A naive
  keyword-overlap metric reads 98.9%/38.9% — both clear the pre-registered
  ≥30% bar — but a manual audit of every match ≥2 shared keywords found
  only **10/90 (11.1%) genuinely on-topic**, rising to **19/90 (21.1%)**
  under a generous "plausible" reading. **Both readings sit below the
  pre-registered 30% bar.** Subject breakdown of the 90-item logged pool:
  Interdisciplinary 79 (88%), Private 9, Public 2.
- *Mechanism.* The corpus itself is fine — it contains the Constitution,
  Civil Code, Code of Obligations, and Criminal Code exactly as inferred.
  The blocker is that **88% of LEXam's actual logged English item pool is
  legal history, theory, and comparative law** — content no statute-text
  corpus can serve, however good the retrieval, because the answers to
  those questions are not *in* any statute. This is a sharper, corrected
  diagnosis than the original "wrong jurisdiction" read: retrieval was
  never going to be the missing piece for this specific item pool, even
  with a perfect domain-correct corpus.
- *Source.* `benchmark/results/swiss_law_corpus_check.md`; the R2-recursion
  retry on the existing STEM-Wikipedia corpus (`benchmark/results/rag_lexam_findings.md`,
  "G3") independently corroborates from a different angle: +2.2 (noise-
  level at n=90), only 2/30 escalations produced verifier findings, and
  the retrieved titles ("Robot tax", "Predicate transformer semantics")
  show the mechanism firing correctly on a corpus with nothing relevant to
  return.

### 3.6 Cost/frontier nulls — the lever is real but not worth its tokens against the actual frontier

**F1. F2 compute frontier — a bare single flagship call Pareto-dominates every logged lever on 6 of 9 benchmarks**

![Accuracy vs tokens frontier](figures/f04_accuracy_vs_tokens_frontier.png)

*This null, drawn. Six panels render on a red "FLAGSHIP DOMINATES" ground; two on
green. Pooled-marginal provenance — the shape is the claim, not the gaps.*

- *Hypothesis (implicit — a portfolio-level audit, not a single pre-
  registered test).* Across the whole logged record, do multi-agent
  levers (panels, gates, RAG) ever lie off the accuracy/token Pareto
  frontier a bare flagship call defines?
- *Config.* Every (benchmark, config) pair across 73 usable committed
  result files (6,975 normalized records), pooled marginal accuracy vs
  mean tokens/question.
- *Measured.* On **6 of 9 benchmarks** — MMLU-Pro, MedQA (except a small
  `moo:single-call` improvement), LEXam, GSM8K, MATH-500-MC, MATH-500-open
  — a bare `baseline_3.7max` single call is the **entire** Pareto frontier;
  every multi-agent lever logged against that benchmark (shipped engine,
  `thinking_gate`, `flagship_panel`, RAG variants, `combined`, `five`,
  `smart_gate`, `subject`, `thinking_all`) is strictly dominated: more
  tokens for equal-or-worse accuracy. The shipped engine specifically is
  dominated everywhere it appears: GPQA 79.8%@8,620tok vs baseline
  86.7%@3,282tok; SuperGPQA-hard 67.4%@10,343tok vs baseline 77.3%@3,151tok;
  LEXam 72.0%@3,480tok vs baseline 86.0%@1,285tok; MMLU-Pro 82.0%@4,154tok
  vs baseline 95.5%@1,202tok.
- *Mechanism.* This is not a new mechanism — it is the portfolio-level
  aggregation of every saturation and homogeneity-trap null above, stated
  as an investment-allocation fact: on 6 of 9 benchmarks tested, there was
  no gap for any lever to exploit, so every additional call was pure
  overhead. The two places a config *does* clear the frontier are a tier
  swap (`qwen3.8_solo` on GPQA), not a lever, and `qwen38_panel`'s pooled
  87.3% on SuperGPQA-hard — flagged by the same document as survivorship-
  contaminated (B1 above; its paired, honest verdict is negative). With
  that row discounted, **no lever built purely from flagship+flash seats
  clears the Pareto frontier on any of the 9 benchmarks** in this
  analysis.
- *Correction, 2026-07-30.* The first of those two exceptions has since been
  **retracted**, which strengthens the conclusion rather than weakening it.
  `qwen3.8_solo`'s 93.6% was a *survivor-only* figure over 78 of 90 items.
  Three paced retries recovered 2 of the 12 drops (78 → 79 → 80) and then
  stalled on repeated 504s from Aliyun's own infrastructure — a structural
  property of those items' generation length, not transient load, so no
  client-side timeout could have fixed it. Per D0's own pre-registered kill
  clause the point estimate is retired; the honest figure is the interval
  **[83.3%, 94.4%]**, and `chem_thinking_gate`'s 90.9% sits *inside* it, so
  the sign of that gap is undetermined. It is therefore no longer a config
  that demonstrably clears the frontier, and it was suppressing five
  legitimate configs while it stood as the ceiling. `RETIRED_POINT_ESTIMATES`
  in `benchmark/figure_data.py` excludes it at source and the Pareto flags are
  recomputed rather than read from the stale CSV.
- *Source.* `benchmark/results/family_floor_analysis.md` §F2.

**F2. The MoO router does not beat flat-best on accuracy (91.0% vs 92.8%, corrected; 90.1% vs 92.8%, original)**

![MoO delta and escalation](figures/f07_moo_delta_escalation_heatmap.png)

*The mechanism, side by side: where escalation collapses, the delta collapses with
it. Note the hatching — **27 of 28 cells sit below the +5 net-discordant McNemar
floor**, so almost none of this grid is a real effect. Each cell prints its item
count for exactly that reason: at n=27, a single item is 3.7pp.*

- *Hypothesis.* A heuristic router that picks a per-domain profile (cheap
  single-call, standard tribunal, flagship panel, RAG stacks) beats always
  running the single best-known profile (`flagship_panel`) on a blended,
  realistic workload.
- *Config.* 120-question blended eval (4 buckets × 30: GPQA-hard,
  SuperGPQA-hard, MedQA, saturated-easy MMLU-Pro), all 7 registry profiles
  run on every question, scored on the 111 present for all profiles.
- *Measured.* flat-best (`flagship_panel`) **92.8%** @ 6,625 tok/q;
  original R1 heuristic router **90.1%** @ 7,826 tok/q (**−2.7pt, and
  costlier**); oracle (per-question best) 96.4%. After a diagnosed and
  corrected hard-STEM routing rule (calibrated offline, zero new paid
  calls): corrected router **91.0%** @ 6,208 tok/q — **+0.9pt over the old
  router and 20.7% cheaper, but still −1.8pt short of flat-best**, with the
  residual gap traced to two specific thin-sample buckets (a 14-question
  organic-chem draw protected by a stronger 3-seed validated rule, and a
  9–11-question heterogeneous "unknown" bucket) rather than the rule the
  correction targeted.
- *Mechanism.* The router's original cost model assumed
  "`flagship_panel` = expensive, avoid on hard STEM" — false, and
  disprovable directly from the same logs: `flagship_panel` escalates only
  ~8–12% of the time (rarely reaching the expensive tribunal), while the
  "cheap" retrieval/thinking stacks it was routed to instead escalate
  55–79% of the time into a full tribunal, making them *both* less
  accurate *and* more expensive on this bucket. Cost cannot be inferred
  from nominal solver tier; it is dominated by measured escalation rate.
- *The honest, defensible claim this null converts into.* Re-weighting the
  same logged data toward realistic easy-skewed traffic mixes (rather than
  the deliberately adversarial 50/50 hard/easy blend) shows the corrected
  router matching flat-best accuracy within noise (−0.2 to −0.7pt at
  80–95% easy) while cutting cost 28–50%. **This is a cost win at
  statistically-equal accuracy on realistic traffic, not an accuracy win
  on any traffic mix** — stated as such, without inflating it further.
- *Source.* `benchmark/results/moo_m1_findings.md`,
  `benchmark/results/moo_m1_corrected_findings.md`.

---

## 4. Methodological negatives — the errors caught in our own work

These are catalogued with the same weight as the experimental nulls above,
because each one describes a way this project's *own analysis process*
would have produced a false positive if a check had not existed. Stated
without defensiveness: catching them is the discipline that makes the
catalogue in §3 trustworthy in the first place.

**Grader false-negatives inflated a MATH-500 "headroom" finding by ~7 points
before it became a recorded result.** The first pass of
`benchmark/math_grade.py` fell back to fail-closed on interval, `\pm`, and
set-valued answers; on MATH-500 level-5, 4 of 6 apparent flagship "errors"
were exactly this grader gap (`(3, 4]` vs gold `(3,4]`; `1 \pm \sqrt{19}` vs
the expanded pair; a set answer with elements reordered). Left uncaught,
this would have shipped "MATH-500 L5 flagship baseline: 89.8%, real
headroom for deliberation" as a finding. The grader was upgraded to model
bracketed sequences, order-insensitive sets, and `\pm` expansions
explicitly (commit `40372fb`); re-grading the same stored answers for free
moved the baseline to **96.6%** and killed the headroom claim outright.
Verified: `0/4000` cross-false-positives on real distinct MATH-500 answers
both before and after the fix, so the correction added coverage without
introducing over-matching risk. — `benchmark/results/math_grade_coverage.md`,
`benchmark/results/math_open_pilot_findings.md`.

**The AIME cheap-tier pilot's first run was invalidated by survivorship
bias, not reported as a finding.** 32/60 panel items and 12/60 baseline
items dropped (ReadTimeout ×56, HTTP 429 ×30) — AIME thinking traces exceed
a 300s timeout and concurrency-6 tripped the rate limit, so the *hardest*
problems (longest traces, most likely to disagree or be wrong) were
disproportionately the ones that dropped. The n=26 survivors were a biased
easy subset that produced a spurious "flash 100%, 0% escalation" reading —
recognized as invalid and not reported as a result. Root causes (client
retries only JSON-parse failures, not transport errors; concurrency too
high) were fixed (retry-with-backoff, concurrency 2) before any subsequent
AIME run. — `docs/improvement-loop-state.md` ("AIME cheap-tier run #1 =
INVALID").

**A silent-degeneracy bug in the chemistry-routing levers would have bought
a mislabelled arm at flagship price on SuperGPQA.** `chem_flagship_gate` /
`chem_thinking_gate` / `smart_gate` branch on an **exact** string match
`subject == "Organic Chemistry"`, a label that exists only in GPQA's
fine-grained subject field. SuperGPQA stores `subject=discipline` (8 coarse
values), so on SuperGPQA the chemistry branch could **never** fire, and the
lever would silently degenerate byte-identically to `thinking_gate` while
still logging under the chemistry-specific lever name — i.e. a run
believed to be testing a chemistry-routing hypothesis would in fact have
tested a different, already-known lever and reported the result under the
wrong name. Caught before any SuperGPQA run of these levers was executed;
the code now fails loudly before any paid call rather than degenerating
silently. All committed chem results are `--dataset gpqa` (seeds
217/314/471) and are unaffected. — `docs/improvement-loop-state.md`
("BUG CAUGHT AND GUARDED").

**The `+3` net-discordant significance bar was retired as statistically
unreachable, and replaced with a derived minimum.** Under exact one-sided
McNemar with zero losses, net **+3** discordant items is **p = 0.125** best
case; **+4** is **p = 0.0625**; the minimum net that can clear p < 0.05 with
zero losses is **+5** (p = 0.03125). Any realistic discordant volume with a
few losses mixed in (e.g. 6 gains / 3 losses, net +3) lands around
**p ≈ 0.5** — no better than a coin flip. The house standard is now: net
≥ +5 at one seed clearing p < 0.05, **or** net ≥ +3 at 2 of 3 seeds with
the pooled McNemar (n=270) clearing p < 0.05. — `docs/capability-roadmap.md`
§1.5; independently re-derived and confirmed in the panel-scaling family's
own McNemar tests (`+3→0.125, +4→0.0625, +5→0.03125`).

**GPQA answer letters are not comparable across seeds.**
`load_gpqa._shuffle_choices` reshuffles the A–D↔choice-text mapping
independently per seed, so any cross-seed or cross-config analysis keyed on
letter rather than choice text is measuring shuffle noise, not a real
signal. This was a latent hazard until the family-floor and stability
analyses both explicitly re-keyed on whitespace-normalized choice text
before any cross-row comparison — normalizing whitespace alone resolved 12
items that otherwise looked like false disagreements purely from
trailing-newline artifacts. — `docs/capability-roadmap.md` §1.5;
`benchmark/results/family_floor_analysis.md` §0; `benchmark/results/stability_audit.md` §0.

**The "cheap tier is ~4x cheaper" assumption is refuted by the measured
token meter, and inverts entirely on one benchmark.** Under a token-plan
quota (no per-token USD meter), the pricing-table assumption that cheap
(`qwen3.6-flash`) calls cost roughly a quarter of flagship
(`qwen3.7-max`) calls does not hold. Measured per-solver-call tokens on
SuperGPQA-hard: cheap flash **2,009 tok** (1,341 logged calls) vs flagship
thinking **3,096 tok** (729 calls) — only **~35% cheaper**, not 4x, so 15
cheap seats cost roughly the same quota as 10 flagship seats. On AIME it
**inverts**: cheap flash averages **24,411 tok/call** vs flagship's
**5,327 tok/call** — the cheap model is **4.6x more expensive**, because
`max_tokens` is not capped in that run and the flash model, lacking the
flagship's concision, rambles at length under thinking mode (verified
directly against `aime_open_panel_cheap_seed42.jsonl` and
`aime_open_baseline_seed42.jsonl`: 84 flash-solver calls averaging
24,411.2 tokens vs 48 baseline calls averaging 5,327.0 tokens). —
`docs/improvement-loop-state.md` ("THE COST CORRECTION").

### Where two committed documents disagree with each other

**rag_presolve's own headline number was revised downward by its own
4th-seed run, and both numbers remain on the record.** Three seeds (42, 7,
123) gave a mean lift of **+6.5** and the write-up called it "VALIDATED at
the project's standard bar... robust." A 4th seed (271) then landed
**−5.6**, dropping the four-seed mean to **+3.5** and prompting an explicit
downgrade: *"`rag_presolve` is downgraded from 'validated, robust' to
'validated-with-variance'."* **The four-seed +3.5 mean is the authoritative
number**; the earlier +6.5 is not wrong, but it is an artifact of having
stopped measuring one seed early, and the write-up itself states this
plainly rather than quietly updating the number in place. This is stated
in the same document, sequentially, and is a model instance of a null
correcting itself in public. — `benchmark/results/rag_r1_findings.md`.

**The same F2 compute-frontier table contains a row its own authors flag as
not to be trusted, inside the same file.** The raw table in
`family_floor_analysis.md` §F2 lists `baseline_3.7max_open: 100% @
5,327tok (n=48)` as the AIME Pareto frontier entry. The same document's
"Orchestrator review annotations" section, several paragraphs later,
explicitly discounts this exact row: *"AIME `baseline_3.7max_open` 100%
(n=48) — survivors of the INVALIDATED run #1... AIME has no valid measured
numbers yet."* **The annotation is authoritative; the raw table row is
retained for transparency about what the mining script actually pooled,
not as a claim.** The same pattern applies to the `qwen38_panel` 87.3% row
in the identical table (see B1/F1 above): pooled-marginal figures from a
drop-contaminated run are mechanically correct arithmetic over a biased
survivor set, and the document is explicit that the paired, honest verdict
(negative, B1) is the one to cite, not the pooled figure. —
`benchmark/results/family_floor_analysis.md`.

**The GPQA "unanimous-wrong rate" means two different things in two places
in this project, and both are correct for their own scope.** Single-run
figures quoted throughout `improvement-loop-state.md` and
`capability-roadmap.md` (~10/90 ≈ 11% on GPQA cheap-tier) describe *one
config's* internal 3-seat disagreement on *one run*. The family-floor
analysis's cross-config floor (4/197 = **2.1%**) describes a categorically
stricter quantity: items wrong under *every config this project has ever
logged*, including the strongest single model (`qwen3.8-solo`) and the
best validated society (`chem_thinking_gate`). The 2.1% figure is smaller
by construction, not because it contradicts the 11% figure — an item only
counts toward the 2.1% floor if it defeated every one of ~24 distinct
configs, not just one gate's three cheap seats. **Both numbers are
authoritative for the question they answer**; conflating them (e.g.
treating the 2.1% floor as "how often the shipped gate will miss
something") would understate the shipped gate's blind spot by roughly 5x.
— `benchmark/results/family_floor_analysis.md` §F1(a) (explicit about the
distinction in its own text).

**The GPQA family-best bar (qwen3.8-solo, 93.6%) is itself flagged
elsewhere as likely contaminated, and — as of the material this document
was built from — has not yet been repaired.** `family_floor_analysis.md`
and multiple lever write-ups cite 93.6% (73/78) as "exact match to the
number already recorded in the repo history" and build on it directly
(e.g. the GPQA-deficit decomposition in F1(b)). `docs/capability-roadmap.md`
item **D0** states plainly that this bar is *"73/78 with 12 timeout/429
drops... the identical survivorship contamination the repo's own F2 review
used to disqualify qwen38_panel's 87.3%... the rule was simply never
applied to this row,"* and specifies a repair (paced retry via the
existing resume path) with a published side-by-side interval as the fix.
**Until D0 runs, 93.6% should be read as an upper-biased point estimate,
not a settled bar** — flagged here because several other committed
findings (the GPQA deficit split, the Track-B family-floor targets) are
built on it without that caveat attached at the point of use.

**Quantified 2026-07-26 (free, no new data).** Imputing the 12 missing
items at both extremes bounds the true value:

| Assumption about the 12 missing | True accuracy |
|---|---|
| all 12 wrong | 73/90 = **81.1%** |
| all 12 right | 85/90 = **94.4%** |
| missing behave like survivors | ≈ 93.6% (the published figure) |

The band is **13.3pt wide, and our own best society (chem_thinking_gate,
90.9%) sits inside it.** So the repeated claim that the society is
*"−2.7pt under the family bar"* silently selected the top of the interval:
the honest range runs from **9.8pt ahead** to **3.5pt behind**, and the
*sign of the gap is not established*. Corrected at the point of use in
`docs/same-provider-scaling-research.md` §5 and §4.6's ledger.

**A second, independent defect in the same comparison — NOT repaired by
D0.** The bar was measured at **seed 123**; chem_thinking_gate ran at
seeds **314/217/471**. GPQA reshuffles its item sample per seed, so this
was never a paired comparison, and cross-seed sampling error stacks on
top of the survivorship bias. Even a clean 90/90 repair leaves it
unpaired. Any "society vs family-best" sentence must therefore either
re-run 3.8-solo at our seeds or carry the cross-seed caveat inline.
Pre-registered analysis plan (written before the repair data exists):
`benchmark/results/qwen38_bar_repair_preregistration.md`.

---

## 5. What the nulls jointly imply

Two structural facts recur across nearly every entry in §3, and together
they define what would actually count as new evidence rather than a
repackaged version of an old null.

**61.6% of wrong panel rows are unanimous** (verified count: 615/998 wrong
rows with ≥2 solver seats, `wrongness_predictor_findings.md` §5). A
disagreement-triggered escalation mechanism cannot see this majority of the
error budget *by construction* — it is unanimous precisely because every
channel the engine currently runs agreed. Every catalogued null that
re-reads or re-weights the panel's *existing* outputs (a better judge, a
bigger homogeneous panel, trace/hedge features, permutation-based
instability) runs into this ceiling in some form, because none of them
introduces a new fact the panel did not already have when it produced its
unanimous, wrong answer.

`docs/capability-roadmap.md` §2.2 states the resulting test precisely, and
it is the load-bearing sentence for any future lever proposal in this
project:

> *Does the mechanism take a NEW ACTION that produces an observation
> absent from every existing log, or does it merely re-weight information
> already there?*

Re-weighting is the costume the ceiling wears when it looks like progress.
W5's trace features (D2) re-read existing traces and failed; F3's
re-engineering of the same quantities was *negative*; `qwen38_judge` (C1)
re-scored existing candidates with a better judge and gained nothing; the
external Sea AI Lab result independently confirms that reflection-token
counts specifically do not track correctness. Four independent
observations, one shape.

There are exactly two escapes from this ceiling, both already named in the
roadmap and both consistent with every validated win in this project's
record:

1. **A genuinely new observation.** Perturb the input and re-observe
   (paraphrase, permute); execute the answer rather than just reasoning
   about it; retrieve evidence on a specific disputed claim rather than
   trusting the panel's own memory; solve with the multiple-choice options
   hidden, forcing a different derivation path. `flagship_panel` and
   `rag_presolve` both work by this route — a stronger model, or injected
   external evidence, is literally new information the cheap panel did not
   have.
2. **A non-fallible or de-anchored arbiter.** A deterministic checker (CAS
   equivalence, unit test, computed value) that cannot be talked out of a
   correct verdict by confident-sounding consensus; or a judge that is
   structurally prevented from seeing the very consensus it is meant to
   audit (blind to vote counts, blind to the candidate answer, ruling on
   an isolated claim rather than the full trace).

Anything that does not fall into one of these two categories — however
elaborate the mechanism, however plausible the story about *why* it should
work — is, mechanically, the ceiling in a new costume, and the correct
default expectation is that it reproduces one of the nulls in §3 rather
than escaping them.

---

## 6. Reproducibility

Every headline number in this document was traced to one of the files
below. All scripts are pure offline log-mining unless noted (zero
additional API cost to reproduce).

**Offline analyses (re-run to regenerate the underlying data):**

```
.venv/Scripts/python.exe benchmark/analyze_family_floor.py        # F1/F2/F5 — §3.6 F1, §4 disagreements
.venv/Scripts/python.exe benchmark/analyze_stability_repaired.py  # §3.4 D3
.venv/Scripts/python.exe benchmark/audit_selectors.py             # selector oracle-headroom context for §5
.venv/Scripts/python.exe -m benchmark.build_wrongness_predictor --report benchmark/results/wrongness_predictor_findings.md  # §3.4 D2
.venv/Scripts/python.exe benchmark/check_swiss_law_corpus.py      # §3.5 E2 (requires live huggingface.co read, zero LLM tokens)
.venv/Scripts/python.exe benchmark/build_moo_calibration.py       # §3.6 F2 calibration table
.venv/Scripts/python.exe benchmark/rescore_moo_router.py          # §3.6 F2 corrected-router re-score
```

**Raw result files behind specific numbers cited above** (all under
`benchmark/results/`):

| Claim | File(s) |
|---|---|
| MMLU-Pro STEM 96.7%/96.7%, escalation 3.3%, unanimous-wrong 1.7% | `lever_baseline_mmlu_pro_stem_seed42.jsonl`, `lever_flagship_panel_mmlu_pro_stem_seed42.jsonl` |
| qwen38_judge 9/9 overturns correct | `lever_qwen38_judge_gpqa_seed42.jsonl` |
| Retrieval score-gating 0.0288 vs 0.0290 | `rag_gating_calibration.csv` |
| LEXam engine −14 (86.0% vs 72.0%) | `lexam_pilot_seed42.jsonl` |
| AIME token cost 24,411 vs 5,327 (4.6x) | `aime_open_panel_cheap_seed42.jsonl`, `aime_open_baseline_seed42.jsonl` |
| qwen38_panel 0% escalation, 63/90 survivors | `lever_qwen38_panel_supergpqa_seed42.jsonl` |
| GPQA family floor 4/197 (2.1%) | `family_floor_analysis_data.json` (`f1_floor`), `f1_family_floor_items.csv` |
| Stability-audit permutation null (+24.4 vs +24.1, p=0.48) | `stability_audit_summary.json`, `stability_audit_items.csv` |
| SuperGPQA-hard flagship_panel 3-seed (+3.8/+2.4/+6.2, mean +4.1; pooled b=11, c=1, net +10, McNemar p=0.0032) | `lever_flagship_panel_supergpqa_seed{42,7,123}.jsonl` + matched `lever_baseline_supergpqa_seed{7,123}.jsonl`; **seed 42's comparator is the `baseline` arm inside `supergpqa_hard_pilot_seed42.jsonl`** — there is no `lever_baseline_supergpqa_seed42.jsonl`, and this row previously implied one. Recompute with `python -m benchmark.verify_flagship_claim` |
| chem_thinking_gate 3-seed (90.9/91.0/90.8) | `lever_chem_thinking_gate_gpqa_seed{314,217,471}.jsonl` |
| rag_presolve 4-seed (+4.7/+6.9/+8.0/−5.6) | `lever_rag_presolve_supergpqa_seed{42,7,123,271}.jsonl` |
| MoO router (92.8 / 90.1 / 91.0 / 96.4) | `moo_m1_eval.jsonl`, `moo_calibration_table.csv` |
| MATH-500 grader correction (89.8%→96.6%) | `math_open_baseline_seed42.jsonl`, `math_open_panel_seed42.jsonl` + `math_grade.py`'s test suite |

Every `_findings.md` file cited by name throughout §3–§4 carries its own
per-seed source-file references inline; this table lists only the files
this document's author spot-checked directly (via `python -c` one-liners
against the raw JSONL/CSV/JSON) rather than trusting the write-up's
arithmetic on faith.

---

*Document scope note: this catalogue covers nulls with a committed result
file as of 2026-07-25. Runs described as "queued," "ready-to-fire," or
"conditional on quota reset" in `docs/improvement-loop-state.md` are not
included, since they have no result file yet to trace a number to — most
notably the fixed AIME cheap-tier pilot (the one benchmark this project's
own law predicts *should* show a deliberation win, given a genuinely weak
cheap tier against a strong flagship) and the W1/W2 verified-gate and
permuted-panel screens. If those land, they belong in a revision of this
document, not a retroactive edit of the nulls recorded here.*
