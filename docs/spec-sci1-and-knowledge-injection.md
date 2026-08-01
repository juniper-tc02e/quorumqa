# SCI-1 and the Knowledge-Injection family — final, reviewed specs

**Authored 2026-08-01. Adversarially reviewed the same day by an independent pass. Revised against that review.**

Two verdicts up front, so nothing below reads as a build-up:

- **SCI-1 (`restate_probe`): DO NOT RUN.** Killed three times over — by its own pre-registration, by an unreachable bar, and by an invalid test.
- **Knowledge injection: one arm survives, and it is not the one the draft led with.** The family's fire-first item is a **~0.58M-token offline replay**; the only live run funded is **`universal_gate` on GPQA-Diamond at two fresh seeds**, which the review showed is a *transfer replication of an already-shipped result*, not a knowledge-injection test at all.

Proposed family budget: 15.0M tokens. **Funded: ≈4.4M.**

---

# Section 0 — Provenance and method

## 0.1 Why these specs did not exist

`docs/experiment-spec-book.md` references SCI-1 in **fifteen** places — its seed block, its build item (F11), its fidelity gate, its firing-order slot (§7 items 4 and 7, 3.20M + 8.30M), its decision points (§8), the SCI-2 gating clause, and the SCI-6 drop rationale. It has **no spec section.** Verified:

```
$ grep -n "^#.*SCI" docs/experiment-spec-book.md
330:### SCI-2 — `backward_check`: blinded per-choice consistency scoring (CONDITIONAL, week 2+)
360:### SCI-3 — `step_audit_replay`: does process-level checking see what answer-voting cannot?
390:### SCI-5 — `gap_gate`: does the chemistry win's mechanism transfer, or is it a chemistry artifact?
```

SCI-2, SCI-3 and SCI-5 have headings. SCI-1 does not. Two other specs were **gated on it** (SCI-2 fires only in the branch where SCI-1 clears coverage but fails net; SCI-4 is chained behind both), and 11.5M tokens of firing order were reserved for it. A spec that gates 11.5M and does not exist is a hole in the record, not a rounding error.

Knowledge injection is worse. It appears **twice**, both times as a forward-pointer inside someone else's kill clause:

> `experiment-spec-book.md:503` — "…the calibration thesis is dead and effort moves to knowledge injection."
> `experiment-spec-book.md:745` — "If neither logged features (META-1) nor instability (META-2) can see inside the unanimous pool, the thesis is dead and effort moves to knowledge injection."

META-2 fired on 2026-08-01. The clause fired. Effort was supposed to move to a destination that had never been written down.

Both specs were therefore authored on 2026-08-01, after the results that make them decidable existed — which is itself a hazard, and is why the adversarial pass was run before anything was committed.

## 0.2 What the review was, and what it changed

An independent adversarial pass reviewed both drafts against the repo, not against the drafts' own prose. **The review was treated as authoritative.** Where it found a fatal flaw, the spec is rejected here or genuinely repaired — not waved through with a caveat. Specifically:

**On SCI-1, the review rejected the draft's own reasoning as insufficient.** The draft argued DO-NOT-RUN from power on the *contrast* statistic. The review agreed with the verdict and then demonstrated that the draft never checked whether the **shippable** bar was reachable at all — and it is not, by roughly 10×, *for any effect size including a perfect oracle*. It further found that the statistical test named in that bar (exact McNemar, a paired test) does not apply to the quantity it was pointed at (a difference of two deltas on non-identical item supports). Both findings are load-bearing and are reproduced in full in §2.

**On knowledge injection, the review reordered the entire family and killed four of five specs.**

| Draft | Draft verdict | Review verdict | Reason |
|---|---|---|---|
| KI-0 strict checkability | P0, fire first, 0 tokens | **REJECTED as written** | Measures whether *choice strings* parse; the lever parses a *model-written relation*. Cannot gate KI-1. Command also does not exist. |
| KI-1 Arm A `verified_gate_cas` | P0 | **DO-NOT-RUN pending a real gate** | +6.8 net is a product of two self-declared ceilings × an invented 0.50 |
| KI-1 Arm B `universal_gate` | "attribution control" | **RUN — but it is not a control** | It is a transfer replication of a shipped +9 result; it dominates Arm A by set inclusion, before any run |
| KI-2 `verified_discriminator` | P1, "highest EV" | **DO-NOT-RUN** | Cites the N=15 oracle figure to motivate an N=3 run; the gap does not exist in the arm being run |
| KI-3 `verified_gate_flaw` | P2 | **DO-NOT-RUN** | Spec concedes "What is NEW: nothing" |
| KI-4 `rag_candidate_discriminate` | P3 | **DO-NOT-RUN** | ±6pt per-seed RAG swing swamps a +5 bar |

Three claims in the drafts were **verified as false against the source** and are corrected below:

1. `benchmark/classify_pool_checkability.py` has **zero** `add_argument` calls and a `main()` that takes no arguments. `--strict` is not a flag to add; argparse does not exist in that file.
2. `pre_gate_votes` is logged **only** for `verified_gate_flaw` and `verified_gate_cas` (`lever_experiments.py:1944-1945`). `universal_gate` is excluded. Its counterfactual is recoverable, but from `plurality_letter`, as `verify_universal_gate.py` already does.
3. `--n-solvers` is documented `diversified_panel/cycled_panel only`. KI-2's N=15 framing has no command that can express it.

## 0.3 One correction the review itself needed

The review is authoritative but not infallible, and one inconsistency between its two halves is decisive for the single run that survives.

In the **SCI-1** review the author correctly used the *dataset-specific* conversion rate from `unanimous_gate_headroom.md` §5 — SuperGPQA-hard, 21 unanimous-wrong → 2 recovered = **9.5%**, **24.0 escalations per net item**. In the **knowledge-injection** review the same author accepted the draft's "Arm B expected net = 33.8 × 0.476 ≈ **+15.5**, genuinely powered" — which uses the **pooled** 47.6%, on **SuperGPQA-hard**, the one surface where that table says the rate is 9.5%.

Applying the review's own number: **33.8 × 0.095 = +3.2 net at n=180 — below the +5 bar, at ~2.73M tokens.** Arm B as specified is *not* powered on SuperGPQA-hard. The same code on GPQA-Diamond converts at 55.1–75.0% and costs 4.2 escalations per net item. `docs/FINDINGS.md` and the strategic assessment reached this independently ("same code, 1/3 the cost, 6× the conversion").

**KI-1 Arm B is therefore re-pointed from SuperGPQA-hard n=180 to GPQA-Diamond n=90.** This is the only place where the final spec departs from the review, and it departs by *applying the review's own arithmetic more consistently than the review did.* It makes the run cheaper (1.22M vs 2.73M per seed, both **measured**) and roughly doubles its expected effect.

## 0.4 Contamination firewall

No answer key was retrieved or inspected in authoring these specs. Where a spec below selects items by known-wrongness (KI-0R), it reads **this repo's own logged `correct` field from committed run files** — our own past grading, not a key lookup. That distinction is stated at each use.

---

# Section 1 — Strategic position

## 1.1 Where the measurements actually stand

**GPQA-Diamond** (n≈90/seed; `qwen3.7-max` solo = 84.4%; shipped cheap engine = 78.9%)

| lever | result | comparator | status |
|---|---|---|---|
| `chem_thinking_gate` | **90.9% mean, 3 seeds**, pooled b=16 c=4, **net +12, p=0.0059**, n=259 | matched same-seed flagship | The only 3-seed, McNemar-clearing, flagship-comparator result in the repo. Composition is thin and honest: **+9 (p=0.0020) / +4 (p=0.145) / −1** |
| `universal_gate` | **78.9% → 88.9%, net +9, p=0.00195**, seed 1001 | the cheap panel, paired in-run | Strongest p-value in the repo. **One seed.** 9/12 unanimous-wrong recovered (75.0%), 0/36 unanimous-right broken |
| `thinking_gate` | +2.3 / tie / +1.1 | flagship | Inside the ±2.5pt noise floor |

**SuperGPQA-hard** (flagship 79.5 / 79.3 / 76.5): `flagship_panel` 83.3 / 81.7 / 82.7, **+4.1 mean, pooled net +10, p=0.0032, n=241, at 3.0× tokens.** Arithmetic intact; **mechanism retracted.** The compute-matched control decomposes it into **+9 from 3× self-consistency (p=0.0245, n=251)** and **+2 from the tribunal (p=0.344, n=237)**.

Everything else is a null, a cost story, or uncontrolled. RAG's +3.5 mean is against a *cheap* control and loses to the flagship on every seed where the comparison exists (−7.0 / −2.4 / −4.7); no RAG delta has ever been McNemar-tested. MedQA / MMLU-Pro-STEM / MATH-500 / GSM8K are saturated or negative. LEXam −14. Coding is a *coverage* number (5/14 → 12/14 graded) with solved moving 2/14 → 4/14.

**Retracted this session:** deliberation as `flagship_panel`'s mechanism; the D0 `qwen3.8`-solo point estimate (93.6% → interval **[83.3%, 94.4%]**, so our 90.9% sits *inside* the bar and the sign is undetermined); confidence-based selection (+76 in-sample, **−4 held out**, sign-reversed on 2/3 fresh seeds); permutation instability (42.4% instability, contrast +7.1pp, **Fisher p=0.4552**) — which by its own kill clause also finishes META-1 and the calibration thesis; and the "no published prior" claim.

## 1.2 What "beating frontier models" can and cannot mean here

**Measurable, in exactly one form.** A Qwen society versus the best single Qwen call *we can actually run*, on identical items, identical seeds, paired McNemar. Even that is currently half-blind: `qwen3.8-max-preview` solo is an interval on GPQA and **unmeasured on SuperGPQA-hard**.

**Not measurable at any budget in this repo.** Fable 5, GPT 5.6, or any other lab's model. No client, no keys, outside the Token Plan. Access would not fix it: our unit is a reseeded 90-item subsample of ~198 (the `qwen3.8`-solo and `chem_thinking_gate` runs share only 68 items), the noise floor is ±2.5pt ≈ 2 items, and published numbers use the full set with different prompting and grading. A 1–3pt margin is inside our noise *and* inside a protocol difference we do not control. On Terminal-Bench the gap is arithmetic rather than methodological: 37.5% vs 88.3–91.9%, ~50pt, against a best-ever orchestration lift of +4.1pp.

**Claimable, and nearly in hand:** *"orchestration of cheap Qwen seats beats a single call of a stronger Qwen, on identical items, paired."*
**Not expressible with these instruments:** *"QuorumQA beats \<any other lab's model\>."* Do not write that sentence.

## 1.3 The synthesis that constrains everything below

Every mechanism that merely **re-reads what the model already generated** has now failed: verbalized confidence, reasoning length, resample instability, permutation instability, logged features, trace/hedge heuristics, logprob ranking, and stronger judges (9/9 correct overturns, zero net). Six independent nulls with one shape.

The remaining class is **knowledge injection** — an observation the panel did not produce. Section 3 tests that class honestly, including admitting where a proposed "injection" is a re-read wearing a new hat.

One narrative in the record must also be retired here, because two of the drafts lean on it. **The oracle/plurality gap is not a 40-point opportunity.** At N=15 with ~47%-accurate seats, 90.8% oracle coverage is *below* the **98.7%** that 15 uniformly random 4-choice guesses would produce. Most of that "coverage" is guessing entropy, not harvestable signal. Five selectors have now died against it. It does not size an opportunity and must not be cited as though it does.

---

# Section 2 — SCI-1 `restate_probe`, FINAL

### VERDICT: **DO NOT RUN.** Not in week 1, not in week 2, not in the extension branch.

Written as a **post-mortem of a design that was never written down**, so the record shows what it would have been and exactly why it dies.

## 2.1 The design, stated once, in full

**Hypothesis (falsifiable).** Among items where the shipped cheap panel is unanimous, items whose unanimity **breaks** when the question stem is restated (meaning-preserving rewrite; choice strings and order untouched) are wrong at ≥25pt higher rate than items whose unanimity survives — and escalating on that trigger beats escalating the same number of *random* unanimous items.

**Arms.** (A) CONTROL — shipped 3-seat cheap panel, original stems. (B) `restate_probe` — one `ORCHESTRATOR_MODEL` rewrite call per item (thinking=True, T=0.3, `restate_question()`), then the byte-identical panel re-run on the restated stem; flip = unanimity broken or canonical letter changed; trigger → shipped tribunal. (C) PLACEBO — seeded-random escalation of the same **per-seed count** from the same unanimous pool. Headline = (corrections − breakages)_B − (corrections − breakages)_C, never B alone.

**Dataset.** SuperGPQA-hard, n=90, 3 seeds.

The placebo arm is the design's best feature and is the right instinct. At META-2's measured enrichment the trigger set was 19/59 = 32.2% wrong against a 28.8% base rate — **3.4pp** of enrichment. Random escalation of the same count recovers nearly the same items.

## 2.2 Kill #1 — it is already dead by its own pre-registration

META-2's kill clause (`experiment-spec-book.md:503`), written **before** the data existed:

> "Contrast gap < 10pt **or** p > 0.2 → … do not build the paraphrase arm…"

Measured 2026-08-01: contrast **+7.1pp** (< 10pt) **and** Fisher **p = 0.4552** (> 0.2). **Both disjuncts fired.** Funding SCI-1 now means overriding our own pre-registration after an unfavourable result — the precise failure mode this spec-book exists to prevent.

## 2.3 Kill #2 — the shippable bar is arithmetically impossible, for *any* effect size

**This is the review's finding and it is the strongest argument against the spec.** The draft argued power on the *contrast*; it never checked the *shippable* bar.

Using this repo's measured tribunal behaviour on the SuperGPQA-hard unanimous pool (`benchmark/results/unanimous_gate_headroom.md`: 21 unanimous-wrong → 2 recovered = **9.5%**; 27 unanimous-right → 0 broken; **24.0 escalations per net item** — verified in the file):

| trigger quality | escalations/seed | enrichment | net_B/seed | net_B − net_C /seed | 3-seed (B − C) |
|---|---|---|---|---|---|
| permutation's measured +7.1pt | 19.7 | 32.2% | 0.60 | **0.06** | 0.2 |
| bar (b)'s +25pt | 22.1 | 39.5% | 0.83 | **0.23** | 0.7 |
| **perfect oracle** (every wrong item flips) | 26.7 | 50.0% | 1.27 | **0.54** | **1.6** |

The bar demands **≥ +5 net discordant at one seed**. A *perfect* trigger delivers **0.54/seed**. Reaching +5 needs:

- **837 items/seed** with a perfect oracle,
- **1,995 items/seed** at the spec's own +25pt bar,
- **543 items/seed** even if the placebo arm is deleted entirely.

Exact one-sided McNemar needs ≥5 all-one-way discordant pairs just to touch p<0.05 (5-0 → p=0.03125). The design's ceiling for net_B alone across three seeds is **3.8**; for the headline quantity (B − C) it is **1.6**. **Bar (c) can never fire.** A pre-registered bar no outcome can satisfy makes the experiment unfalsifiable in the only direction that would justify paying for it.

## 2.4 Kill #3 — the named test does not apply to the named quantity

Bar (c) specifies **exact one-sided McNemar**, a **paired** test. Arms B and C escalate *different* item sets — partially overlapping, both drawn from the same unanimous pool, but not identical. `(trigger − placebo)` is a difference of two paired deltas on **non-identical supports**. McNemar's null is not that quantity's null and its p-value is not calibrated for it. The design's best feature has no valid test attached to it.

## 2.5 Four further defects, recorded so a revival cannot quietly inherit them

1. **Bar (b) and the fidelity gate are mutually inconsistent.** A 19.9%-non-equivalent audit *passes* the 20% gate, and broken rewrites enter the trigger set at roughly base wrongness, so observed contrast ≈ **0.80 × true**. A true **+25pt** effect reads **+20pt** and fails its own bar. Tolerance must be **≤5%** (a true +25 then reads +23.8) or the bar must be stated fidelity-adjusted.
2. **Undefined dead zone.** The kill fires below +10pt; the bar fires at +25pt. A **+18pt** result — the *most likely* non-null outcome, given the MDE below is +19.6pp — has no pre-registered disposition at all.
3. **The fidelity audit is neither blind nor validated.** (a) Pairs are presented as `(original, restatement)` in **fixed order**, in a repo that has *measured* 42.4% position sensitivity in these models. Order must be randomized and the judge must not be told which stem is the rewrite. (b) "Majority-of-3" is three calls to **one** model; Fleiss κ across three samples of one configuration measures **decoder determinism**, not inter-rater reliability. κ≥0.4 is trivially passable and is therefore not evidence the audit is informative. Needs ≥2 genuinely distinct judge configurations.
   **Credit where due:** the firewall question is answered correctly. E1–E5 judge the stem→answer-*set* mapping, never the gold letter, and the load-time key-excluding projection is the right mechanic. That part holds.
4. **Difficulty confound, bidirectional and unresolvable post hoc.** Rewrites broken at random dilute toward null (conservative). Rewrites that get *harder* preferentially on **marginal** items — which are also disproportionately wrong — inflate the contrast spuriously. The rubric scores each rewrite in isolation and cannot separate these. **The free detector the draft omitted:** compare cross-seat disagreement on **all** items (including originally-split ones) between original and restated stems. Global rise ⇒ difficulty moved; rise confined to the unanimous pool ⇒ the claimed signal. This costs nothing — it is already in the run — and would have to be mandatory before any contrast were reportable.

## 2.6 Power, for the record

Pooled n=139 unanimous (40 wrong / 99 right); base flip rate on right items 40.4%.

- **Minimum detectable effect.** The smallest contrast reaching one-sided Fisher p<0.05 at those cell counts is **24/40 (60.0%) vs 40/99 (40.4%) = +19.6pp** (p = 0.028). Any true effect below ~+19.6pp is **arithmetically unreachable** at this n, however real it is.
- **Power** (4,000 sims, n = 40/99, α = 0.05 one-sided): true +7.1pp → **0.14**; +15pt → 0.41; +20pt → 0.62; +25pt → **0.81**; +30pt → 0.93.
- To detect a **+10pt** effect at 80% power needs ~303 wrong / ~750 right ≈ **1,050 unanimous items ≈ 22 seeds ≈ >25M tokens** — the entire weekly cap, for one probe.

The design only works if restatement's true contrast is ≈ **3.5×** permutation's measured one.

## 2.7 Is restatement different in kind, or the same thesis in a third costume?

**Steelman for.** Permutation leaves every token unchanged and moves only positions, so a flip can only come from position sensitivity or decoder noise. Restatement perturbs the **lexical/syntactic encoding of the stem** while holding the referent fixed, and could in principle expose items whose answer is keyed to a *surface cue* — a memorised phrasing, a distractor-triggering word, a template match — rather than to content. That is a genuinely different failure mode.

**Steelman against.** The **readout is byte-identical**: cross-seat agreement, through the same aggregation. The explanation that killed both predecessors — unanimity among 3 cheap seats at T=0.3/0.6/0.9 is largely a *coincidence-of-modal-answer* event, and right and wrong modal answers are held with similar margins — is **axis-agnostic**. Restatement also carries a liability permutation did not: permutation is task-preserving **by construction**, restatement only **up to a rubric**, so some flips mean "the rewrite got harder" — noise pointing the wrong way, inseparable post hoc.

**Ruling (the review's, adopted): the mechanistic difference is real but not load-bearing.** The design provides no channel to observe surface-cue keying *except* the statistic that has now nulled twice. A load-bearing version would measure the cue directly, not re-read agreement through a new input port.

## 2.8 Cost, corrected; and the registry conflict

The draft's **2.45M/seed** double-counts: the control arm's 0.95M/seed **is** the base panel run already consumed inside the restate arm's 1.37M. Either the panel runs twice at the same seed (waste) or the figure is inflated by ~0.95M. True cost ≈ **1.6M/seed ≈ 4.7M for three seeds.** This does not change the verdict.

**Registry.** Seeds 1607 / 2311 / 3407 are verified absent from `benchmark/data/seed_registry.json` and from every result filename. But the registry's `instability_merged` block **already binds SCI-1** to `{"screen": 909, "extension": [1313, 2027]}`. Reassignment would require a committed registry amendment, which the draft's "Build needed" omitted. Since SCI-1 is retired, **the correct registry action is to mark `instability_merged`'s SCI-1 membership RETIRED**, releasing nothing (909/1313/2027 stay burned by META-2) and freeing 1607/2311/3407, two of which §4 now claims.

## 2.9 Expected value

P(true contrast ≥ 25pt) ≤ ~**0.12** given permutation's measured +7.1pp; × 0.80 power ⇒ ~**0.10** chance of clearing bar (b). P(clearing bar (c)) ≈ **0** (§2.3). So **4.7–7.4M tokens buys a ~10% chance of an unshippable contrast finding and a ~90% chance of a third null we can already predict** — on a pool that is, additionally, orthogonal to the family's own stated target, since SCI-1 only ever touches *unanimous* panels.

## 2.10 On F11 (`restate_question()` + fidelity harness) — **DO NOT BUILD AS DRAFTED**

The draft proposed funding F11 alone at ~0.2M as a "cheap, reusable, self-killing asset." **Rejected.** With fixed-order presentation and a single-model κ, it manufactures *false assurance* about a primitive that SCI-6's demoted seat-dimension would then inherit. A broken audit that reports "gate passed" is worse than no audit.

F11 may be built **only** if all three hold: **(a)** pair order randomized and the judge blind to which stem is the rewrite; **(b)** ≥2 genuinely distinct judge configurations, with κ computed across configurations rather than across samples of one; **(c)** non-equivalence tolerance **≤5%**, not 20%. Note that its only downstream consumers are SCI-1 (retired), SCI-6 (dropped) and SCI-2 (gated on an SCI-1 branch that can no longer occur). **Priority: P4, unfunded.**

## 2.11 What would revive SCI-1

Only a **new premise**, not a better-powered version of this one: evidence from some *other* result that panel unanimity is surface-cue-driven — e.g. a direct measurement of cue keying that does not read cross-seat agreement. Absent that, a third perturbation axis is a third costume.

**If it had run and failed, we would have learned:** that the perturbation-instability family is closed across all three axes (resample, position, semantics) — *cross-seat agreement carries no wrongness signal under any cheap input perturbation.* That is worth saying. **Two nulls already say it, and the third costs 4.7M.**

---

# Section 3 — Knowledge-injection family, FINAL

Ordered by **expected value per token**, best first. "What is NEW" is stated for every spec, and where the answer is *nothing*, it says so.

### Measured constants (used throughout, no tier labels)

| quantity | value | source |
|---|---|---|
| cheap flash seat / flagship thinking seat | **2,009 / 3,096 tok/call** | `experiment-spec-book.md:47-48` (1,341 and 729 logged calls) |
| control run, SuperGPQA-hard | **10,505 tok/item** | `lever_control_supergpqa_seed7.jsonl`, recomputed |
| control run, **GPQA** | **9,145 tok/item** | `lever_control_seed7.jsonl`, recomputed |
| **`universal_gate` run, GPQA** | **13,541 tok/item (1,218,704 total at n=90)** | `lever_universal_gate_gpqa_seed1001.jsonl`, recomputed — **not an estimate, a measurement of the exact command below** |
| unanimity rate, SuperGPQA-hard | 374/713 = 52.5% | control jsonl recount |
| unanimous-**wrong**, SuperGPQA-hard | 134/713 = **18.8%** (≈16.9 per 90) | ” |
| unanimous-**wrong**, GPQA | **12/90 = 13.3%** | `full_run2.jsonl` and seed 1001, independently |
| tribunal recovery, **GPQA** | **55.1%** pooled (49→27); **75.0%** at seed 1001 (12→9) | `unanimous_gate_headroom.md` §5, §8 |
| tribunal recovery, **SuperGPQA-hard** | **9.5%** (21→2), **24.0 escalations/net item** | `unanimous_gate_headroom.md` §5 |
| breakage of escalated unanimous-right | **0.8%** pooled; **0/36** at GPQA seed 1001 | ” |
| CAS-checkable fraction (regex **ceiling**) | GPQA 18/34 = 52.9%; SuperGPQA 96/110 = **87.3%** | `pool_checkability.md` |

### The bar, and what it really requires

Repo bar: exact one-sided McNemar, **net ≥ +5 discordant at one seed with p<0.05**, OR **net ≥ +3 at 2-of-3 seeds with pooled p<0.05**. The review's arithmetic, which every spec below must respect:

| b–c | net | exact one-sided p | clears? |
|---|---|---|---|
| 5–0 | +5 | 0.03125 | ✓ |
| **6–1** | **+5** | **0.0625** | **✗** |
| 6–0 | +6 | 0.01563 | ✓ |
| 7–1 | +6 | 0.03516 | ✓ |
| **7–2** | **+5** | **0.0898** | **✗** |
| 9–0 | +9 | 0.00195 | ✓ |

**The +5 bar effectively requires zero losses.** Any spec projecting "+6.8 net, clears +5" is only correct if breakage is exactly 0. Every projection below states its breakage assumption explicitly.

---

## 3.1 KI-0R — CAS gate replay on the known-wrong pool ★ **FIRE FIRST**

### VERDICT: **RUN, FIRST, BEFORE ANY LIVE ARM.** ~0.58M tokens.

**This replaces the drafted KI-0, which is rejected.** The drafted KI-0 proposed `classify_pool_checkability --strict` to measure whether **choice strings** parse under sympy. `verified_gate_cas` **never parses choice strings** — it parses a **model-written relation** produced by `CAS_EXTRACT_SYSTEM` (`lever_experiments.py:828-841`). KI-0 as drafted would have returned a confident number about a quantity the lever does not use, and would have gated 2.30M on it. It also cannot run: `classify_pool_checkability.py` contains **zero `add_argument` calls** and a `main()` taking no arguments.

**Hypothesis.** The product `p_check × y_detect` — the fraction of *known-wrong unanimous items* on which `cas_gate_check` both emits a parseable relation **and** `sympy_check` returns `fail` — is materially below the 0.437 the KI-1A projection assumes.

**Why the drafted 0.437 is not credible.** It is `0.873 × 0.50`, where 0.873 is a number `pool_checkability.md` itself calls *"the CEILING the heuristic supports, not a validated floor"*, and 0.50 is invented. The file's own "checkable" exemplars are, verbatim:

- `$$\n0. 8 9 \times1 0^{-6} \mathbf{r}\mathrm{a d}/\mathbf{s}^{2}\n$$`
- `3<5<1<6<2<4`
- `c3`, `d2h`

None of these parse in `_parse_sympy_expr` (`src/quorumqa/tools/mcp_server.py:114`).

**And there is a structural argument that `y_detect` is small.** `CAS_EXTRACT_SYSTEM` asks the model to write "LHS = RHS **with the chosen answer's numeric value already substituted in**" — *from its own transcript*. A model reconstructing its own wrong chain writes a **self-consistent** equation, `sympy_check` returns `pass`, and nothing escalates. CAS can therefore only catch **arithmetic slips** — and three seats at T=0.3/0.6/0.9 agreeing unanimously actively selects *against* stochastic slips and *for* correlated conceptual/setup error. **Unanimity filters out precisely the error class CAS can see.**

**What is NEW:** nothing is injected — this is a diagnostic replay. Its value is that it measures the one unmeasured parameter on which 2.30M (KI-1A) and 2.76M (KI-2) both depend, for 1.5–4% of their cost.

**Arms / pools.** Replay `cas_gate_check` → local `sympy_check` over four committed pools, reading each item's already-logged `correct` field (our own past grading; **no answer key is retrieved**):

| pool | n | purpose |
|---|---|---|
| SuperGPQA-hard unanimous-**wrong** (deduped) | 110 | sensitivity — the exact pool KI-1A must convert |
| SuperGPQA-hard unanimous-**right**, seeded sample | 110 | specificity → cost-per-recovery |
| GPQA unanimous-**wrong** (deduped) | 34 | sensitivity on the surface KI-1B actually runs |
| GPQA unanimous-**right**, seeded sample | 34 | specificity, same |

The unanimous-right arms are an addition neither the draft nor the review specified, and they are necessary: **sensitivity alone gives you `b` but not `c`.** Without `c` you cannot compute a net, and the review's own recommendation — replace KI-1A's accuracy McNemar with a **cost-per-recovery non-inferiority test vs Arm B** — is not computable without a false-positive rate.

**Dataset / n / seeds.** Committed logs only. Sampling seed for the two unanimous-right samples: **`analysis:8419`** (fresh; verified absent from the registry and from all result filenames). No new benchmark items are drawn.

**Command.**

```bash
./.venv/Scripts/python.exe -m benchmark.replay_cas_gate_on_wrong_pool \
  --datasets gpqa,supergpqa \
  --match-right-sample-seed 8419 \
  --out benchmark/results/KI0R_cas_gate_replay.md
```

*(All flags are on a script that does not yet exist — see Build needed. Nothing above claims a flag on an existing script.)*

**Bar (pre-registered, descriptive + gating).** Report `p_check × y_detect` per dataset, with Wilson CIs, plus the false-positive rate on unanimous-right.

**Kill clause (dominates every downstream bar).** Gains ≥5 net at n=180 requires `p_check × y_detect ≥ 5 / (33.8 × 0.476) = **0.311**`.
- **`p_check × y_detect` < 0.311 on SuperGPQA-hard ⇒ KI-1 Arm A is dead.** Do not run it at n=180 or any n; the mechanical-verification branch of knowledge injection is closed for MC-science, and KI-2 (which depends on the same parseability) is closed with it.
- At a plausible **y_detect = 0.15**: 33.8 × 0.873 × 0.15 × 0.476 = **2.1 net — less than half the bar.** This is the expected outcome. State it now so a low number cannot be retro-spun.

**Token cost.** 288 items × 2,009 tok/call = **578,592 ≈ 0.58M.** (2.5% of the 15.0M the family proposed; 25% of KI-1A alone.) `sympy_check` is offline and free.

**Build needed.** Real but small: `benchmark/replay_cas_gate_on_wrong_pool.py`, ~120 lines — inventory the control-lever unanimous rows exactly as `classify_pool_checkability.py` already does (reuse its dedup and its control-lever-only scoping), call `cas_gate_check`, dispatch the returned `relation`/`candidate` to `sympy_check`, tabulate `checkable ∧ parseable ∧ status=="fail"` against the logged `correct` field. Plus ~8 offline tests. **This is not "add a flag"** — the drafted KI-0's script has no argparse at all.

**If it fails, we learn:** that the bottleneck is **extraction**, not verification — a model asked to write a check for its own answer writes one that passes. That is a real, publishable finding about tool-augmented self-verification, and it kills two levers for 0.58M instead of 5.06M.

**Priority: P0.** Highest EV/token in the repo by a wide margin.

---

## 3.2 KI-1 Arm B — `universal_gate` transfer, GPQA-Diamond, two fresh seeds

### VERDICT: **RUN. This is the only live arm funded.**

**It is not a knowledge-injection control, and it must not be labelled as one.** The draft cast it as the "escalate-everything null" against Arm A. The review established that it is something else and better: a **transfer replication of an already-shipped result**, and that it **dominates Arm A by set inclusion, before any run** — `verified_gate_cas` escalates a strict *subset* of the unanimous panels `universal_gate` escalates, and with breakage at 0.8%, Arm B's accuracy net is ≥ Arm A's by construction. KI-1's "attribution clause" was never a contingency; it was the pre-determined outcome.

**Re-pointed from SuperGPQA-hard n=180 to GPQA-Diamond n=90** (see §0.3). On SuperGPQA-hard the same command converts unanimous-wrong at **9.5%** and costs **24.0 escalations per net item**: 33.8 × 0.095 = **+3.2 net at ~2.73M — below the bar.** On GPQA it converts at **55.1–75.0%** and costs **4.2 escalations per net item**.

**Hypothesis.** The +9 (p=0.00195) measured at GPQA seed 1001 is a property of the lever on this surface, not of that seed — so the pre-registered **2-of-3-seed branch** clears with seed 1001 banked.

**What is NEW:** the *tribunal itself* is the injection — a flagship-with-thinking Judge plus a tool-using Verifier see items the cheap panel never showed anyone. That is a real tier-gap escape, and it is honestly weaker than "external computation": the Judge is still the same model family. What makes it fundable is not novelty of mechanism but that it is **built, fired once, and already clears the bar at p=0.00195.**

**Arms.**
- **(i) `universal_gate`** at each fresh seed.
- **(ii) shipped-panel-without-escalation**, derived **in-run and free** from each run's own logged `plurality_letter` on unanimous rows plus `final_letter` on split rows — exactly the pairing `benchmark/verify_universal_gate.py` already implements. **Not** from `pre_gate_votes`: that field is logged only for `verified_gate_flaw`/`verified_gate_cas` (`lever_experiments.py:1944-1945`) and `universal_gate` is excluded. The draft's pairing prose was wrong; the mechanism is fine.
- **(iii) compute-matched control, one seed only** — see §3.3.

**Dataset / n / seeds.** GPQA-Diamond, n=90, **fresh seeds 2311 and 3407** (verified absent from `benchmark/data/seed_registry.json` and from every filename in `benchmark/results/`; freed by SCI-1's retirement in §2.8). Seed **1001 is already banked at +9** and supplies the third seed of the 2-of-3 branch.

**Commands.**

```bash
./.venv/Scripts/python.exe -m benchmark.lever_experiments --lever universal_gate \
  --dataset gpqa --n 90 --seed 2311 --concurrency 6 \
  --out benchmark/results/lever_universal_gate_gpqa_seed2311.jsonl

./.venv/Scripts/python.exe -m benchmark.lever_experiments --lever universal_gate \
  --dataset gpqa --n 90 --seed 3407 --concurrency 6 \
  --out benchmark/results/lever_universal_gate_gpqa_seed3407.jsonl
```

Every flag verified present in `lever_experiments.py:2386-2422`; `universal_gate` and `gpqa` are both in `choices`.

**Power, honestly.** Expected unanimous-wrong per seed = 90 × 13.3% = **12.0**. At the pooled GPQA rate (55.1%): **6.6 recovered**. At seed 1001's rate (75.0%): **9.0**. Breakage: 0/36 observed at 1001; at the pooled 0.8% per escalated unanimous-right, P(zero broken among ~36) = 0.992³⁶ ≈ **0.75**.

- **Single-seed branch (+5, p<0.05):** needs 5-0, or 7-1 if one item breaks. Expected 6.6 recoveries → clears at ~55–65% per seed. **Not guaranteed. Do not present it as such.**
- **2-of-3 branch (+3 at 2 of 3, pooled p<0.05):** seed 1001 is already one of the two. Only **one** of the two fresh seeds needs ≥+3. Pooled projection b≈22, c≈1 → p = 24/2²³ ≈ **2.9 × 10⁻⁶**. This branch is the target and it is robust.

**Bar (pre-registered, one line).** Net ≥+3 at 2 of 3 seeds (1001 / 2311 / 3407) with pooled exact one-sided McNemar p<0.05; a fresh seed also clears standalone if it reaches +5 with zero losses (or +6 with one).

**Kill clauses (kill dominates the bar).**
1. If **both** fresh seeds land net ≤ +2, the seed-1001 +9 is seed luck and `universal_gate` is retracted as a claim, not softened. Written now, before the runs.
2. If the compute-matched control (§3.3) matches or beats `universal_gate`, the win is a **compute** effect and must be reported exactly as `flagship_panel`'s was — retracted mechanism, arithmetic intact.
3. **>9 item drops (10%) voids that seed.** Survivorship bias voided an earlier AIME run; this is not negotiable.

**Token cost.** **1.22M/seed measured** (1,218,704 tok at n=90, recomputed from `lever_universal_gate_gpqa_seed1001.jsonl`; 13,541 tok/item; role split: solver 1,745 × 3, skeptic 2,757, verifier 896 × 1.6, judge 4,116). **Two seeds = 2.44M.**

**Build needed.** **None for the runs.** One analysis change: extend `benchmark/verify_universal_gate.py`'s `SEEDS = (1001,)` tuple to `(1001, 2311, 3407)` and add the pooled McNemar — ~15 lines against a file that already computes the paired counterfactual correctly.

**Registry.** 2311 and 3407 must be committed to `benchmark/data/seed_registry.json` under the `universal_gate` block **before** the first run, and `instability_merged`'s SCI-1 membership marked RETIRED in the same commit.

**If it fails, we learn:** that unconditional escalation of unanimity does not survive reseeding, which retracts the repo's strongest p-value and closes gate-recall as a lever. That is a large, cheap, decisive thing to learn for 2.44M.

**Priority: P0.** This is the shortest path to the only claim §1.2 says is expressible.

---

## 3.3 KI-1B-C — compute-matched control for `universal_gate`, one seed

### VERDICT: **RUN, ONE SEED, ALONGSIDE §3.2.**

Not in either draft. Added because **the control that retracted the last headline was run late**, and the strategic assessment's explicit instruction is to run it **up front this time**. `flagship_panel`'s +10/p=0.0032 survived arithmetically and lost its mechanism to a compute-matched control fired afterwards. Repeating that sequence would be a choice, not an oversight.

**Hypothesis (expected to be a null, which is the point).** `universal_gate`'s gain is *not* reproduced by spending the same extra tokens on **more cheap seats**. If it is, the win is compute, not the tribunal.

**Arm.** `diversified_panel --n-solvers 9 --no-tribunal` at seed 2311 — vote-only, no skeptic/verifier/judge. 9 cheap seats ≈ 9 × 1,745 = **15,700 tok/item** vs `universal_gate`'s measured 13,541 — the control is *over*-matched on compute, which is the conservative direction.

**Command.**

```bash
./.venv/Scripts/python.exe -m benchmark.lever_experiments --lever diversified_panel \
  --dataset gpqa --n 90 --seed 2311 --n-solvers 9 --no-tribunal --concurrency 6 \
  --out benchmark/results/KI1BC_compute_matched_n9_gpqa_seed2311.jsonl
```

All flags verified; `--n-solvers` and `--no-tribunal` are documented `diversified_panel/cycled_panel only`, and this is `diversified_panel`.

**Honest limitation, stated because it constrains the reading.** `solve_all_diversified_panel` (`lever_experiments.py:1051`) builds seat *i* from `SOLVER_PROCEDURES[i%5] × SOLVER_TEMPERATURES[i%3]` with an independently permuted choice order — **this is not the shipped lens panel.** Its derived N=3 point is therefore a *within-arm* reference, not the shipped control. The shipped control for the headline comparison comes from `universal_gate`'s own logged `plurality_letter` at the same seed, which is free and correctly paired. N=3/5/7/9 are all derivable offline from the logged `seat_answers`, so the whole curve costs nothing extra.

**Bar (one line).** Report `universal_gate` net minus N=9-vote-only net at seed 2311, paired on `question_id`, with exact one-sided McNemar; **no bar to clear** — this is an attribution guard, and its output is a sentence in the write-up either way.

**Kill clause.** If N=9 vote-only matches or beats `universal_gate` at matched compute, **KI-1B's mechanism claim is retracted on the spot**, exactly as `flagship_panel`'s was. Arithmetic stands; mechanism does not.

**Why one seed suffices.** `panel_scaling_n15_seed19.md` already measured plurality accuracy **flat at ~47–51% from N=3 to N=15** on SuperGPQA-hard. The null is the strongly expected outcome; one seed is an attribution guard, not a headline, and three seeds would be paying for a result we can nearly predict.

**Token cost.** 90 × 15,700 ≈ **1.41M.**

**Build needed.** None. Offline scoring reuses `benchmark/analyze_panel_scaling.py`'s `mcnemar_exact_one_sided`.

**Priority: P0**, contemporaneous with §3.2.

---

## 3.4 KI-1 Arm A — `verified_gate_cas`

### VERDICT: **DO NOT RUN until KI-0R returns `p_check × y_detect ≥ 0.311`.** Built, 37 offline tests passing, still not fundable.

**What is NEW, stated precisely and with its asymmetry.** `sympy_check` runs offline sympy (1e-9 tolerance, 3s thread timeout) — a computation the panel never performed. But the *relation* is written by the model **from its own transcript** (`CAS_EXTRACT_SYSTEM`), so the **premise is a re-read**; only the **arithmetic verdict** is new. That asymmetry is the whole problem: §3.1 argues the premise is where it breaks.

**Why it is gated rather than killed.** The mechanism is the only genuinely external computation in the repo. If KI-0R shows the product clears 0.311, it deserves a run. If it does not — and 0.15 for `y_detect` gives **2.1 net, less than half the bar** — it is dead for 0.58M instead of 2.30M.

**If it ever fires, three pre-registered changes are mandatory:**
1. **Not an accuracy McNemar.** Against Arm B it loses by set inclusion, before any data. The correct instrument is **cost-per-recovery non-inferiority vs Arm B**, computable only with KI-0R's specificity arm.
2. **The zero-breakage requirement is stated in the spec, not discovered afterwards:** 6-1 (net +5) → p=0.0625, fails. The projection "+6.8 net clears +5" is true only at exactly zero losses.
3. **Registry.** Seeds 4409 / 4517 / 4621 remain reserved and unregistered; they are verified fresh but must not be claimed until the gate opens.

**Token cost if it fires (unchanged, for the record).** n=180 SuperGPQA-hard: 180 × 10,505 (1,890,900) + gate extraction 180 × 0.525 × 2,009 (189,850) + extra escalations at an assumed 25% fire rate (222,700) ≈ **2.30M.** At n=90 the same assumptions give **+3.4 — below bar**, so n=180 is the minimum powered size, not padding.

**Priority: P3, gated.**

---

## 3.5 KI-2 `verified_discriminator` — **DO NOT RUN**

**Fatal scoping mismatch.** The spec cites the **N=15** oracle-coverage figure (90.8%) to motivate a run of the **N=3** shipped panel. The command has no `--n-solvers`, and `--n-solvers` is documented `diversified_panel/cycled_panel only` — `verified_discriminator` could not accept it even if built. At N=3, coverage is **71.3%**: the advertised 40-point gap does not exist in the arm being run.

**And the gap it targets is not what it looks like.** At N=15 with ~47%-accurate seats, 90.8% oracle coverage is **below the 98.7%** that 15 uniformly random 4-choice guesses would give. Most of that coverage is guessing entropy. Five selectors have already died against it.

**Compounding:** it is the family's largest build (new lever + prompt + dispatch + ~25 offline tests) for a mechanism whose parse rate is governed by the same unmeasured sympy-parseability KI-0R has not yet answered. Strictly downstream of KI-0R, and downstream of a premise §1.3 retires.

**Revival condition.** Re-spec at `--n-solvers 15` on a lever that accepts it, **after** KI-0R clears — or drop. Not funded in week 1 or 2. **Priority: P4.**

---

## 3.6 KI-3 `verified_gate_flaw` — **DO NOT RUN**

The spec concedes it: **"What is NEW: nothing."** It is pure re-reading, proposed at **2.50M** as a diagnostic contrast. Its answer is already bounded twice: W5 self-evaluation AUC **0.625**, and `flaw_finder_gate_check` (`lever_experiments.py:803`) uses the **same model family auditing its own panel** — self-preference, not injection. Its stated kill clause ("clears while KI-1A fails ⇒ the re-read family is not exhausted") becomes near-vacuous once KI-1A is itself gated behind KI-0R.

§1.3's six nulls are the prior. Paying 2.50M to add a seventh is not diagnosis, it is confirmation.

**If ever revived,** run it at the *same* seed as an Arm B run so the escalation-subset relation is directly measurable. **Priority: P4.**

---

## 3.7 KI-4 `rag_candidate_discriminate` — **DO NOT RUN**

Highest cost (**4.6M**, no in-run pairing — retrieval changes solver prompts, so a paired control run must be bought separately), weakest prior.

**Its own recon is disqualifying.** Per-seed `rag_presolve` deltas: **+4.7 / +6.9 / +8.0 / −5.6** (mean +3.5). A **±6-point seed swing swamps a +5 bar.** A single screen seed cannot distinguish signal from that variance, so the spec actually lives in its 3-seed extension at **~13.8M** — 46% of the 30M week-1 cap, for the family's weakest prior. Additionally, RAG loses to the flagship on every seed where that comparison exists (−7.0 / −2.4 / −4.7), and **no RAG delta has ever been evaluated under the current McNemar bar** — every one is a raw accuracy delta at n≈86–90.

The idea itself is the family's most interesting: prior RAG arms queried the corpus with the **question**, which the solvers already read; this would query with each **candidate answer string**. That is genuinely new information. It is unaffordable at the variance it must overcome.

**Note for the record:** `rag_thinking_gate` cut the unanimous-wrong floor 22→9 and 15→5 — the largest floor cuts measured here, and often cited as a reason to fund retrieval. Before anyone does, run **its** net-vs-placebo arithmetic against the current bar: ~13 items on the same 24-escalations-per-net-item SuperGPQA pool, which is the same death SCI-1 dies. **Priority: P4.**

---

# Section 4 — Firing order

Every flag below is verified present in the named script. Every seed is verified fresh against `benchmark/data/seed_registry.json`, the burned list (7, 42, 123, 217, 271, 314, 471, 555, 606, 777, 838, 888) and this session's used list (19, 101, 411, 523, 631, 909, 1001, 1313, 2027), and absent from every filename in `benchmark/results/`.

### 0. Registry amendment — do this before any run, in one commit

Add to `benchmark/data/seed_registry.json`: `universal_gate` block gains **2311, 3407** (dataset GPQA-Diamond); a new `cas_replay` block claims **`analysis:8419`**; `instability_merged`'s SCI-1 membership is marked **RETIRED** with a pointer to §2 of this document. Reserved-but-unclaimed until their gates open: 4409 / 4517 / 4621. Released, unassigned: **1607**.
**Cost: 0 tokens.**

---

### 1. KI-0R — CAS gate replay ★ FIRE FIRST

```bash
./.venv/Scripts/python.exe -m benchmark.replay_cas_gate_on_wrong_pool \
  --datasets gpqa,supergpqa \
  --match-right-sample-seed 8419 \
  --out benchmark/results/KI0R_cas_gate_replay.md
```

- **Build first:** `benchmark/replay_cas_gate_on_wrong_pool.py` (~120 lines + ~8 offline tests). This script does not exist; nothing above claims a flag on an existing one.
- **Seeds:** `analysis:8419` (sampling the matched unanimous-right pools only; no new benchmark items drawn).
- **Cost: 0.58M** (288 items × 2,009 tok/call; `sympy_check` is offline).
- **Bar:** report `p_check × y_detect` with Wilson CIs per dataset; **< 0.311 on SuperGPQA-hard kills KI-1 Arm A and KI-2 outright.** Expected outcome is a fail — stated now so a low number cannot be retro-spun.

---

### 2. KI-1B — `universal_gate`, GPQA, seed 2311

```bash
./.venv/Scripts/python.exe -m benchmark.lever_experiments --lever universal_gate \
  --dataset gpqa --n 90 --seed 2311 --concurrency 6 \
  --out benchmark/results/lever_universal_gate_gpqa_seed2311.jsonl
```

- **Seed:** 2311 (fresh). **Cost: 1.22M** (measured, not estimated).
- **Bar:** net ≥+3 here contributes to the 2-of-3 branch with seed 1001 (+9) banked; ≥+5 with zero losses clears standalone at p<0.05. **>9 drops voids the seed.**

---

### 3. KI-1B-C — compute-matched control, same seed

```bash
./.venv/Scripts/python.exe -m benchmark.lever_experiments --lever diversified_panel \
  --dataset gpqa --n 90 --seed 2311 --n-solvers 9 --no-tribunal --concurrency 6 \
  --out benchmark/results/KI1BC_compute_matched_n9_gpqa_seed2311.jsonl
```

- **Seed:** 2311 (same items as step 2 — that pairing is the point). **Cost: 1.41M.**
- **Bar:** no bar to clear; **kill clause only** — if N=9 vote-only matches or beats `universal_gate` at matched compute, the mechanism claim is retracted on the spot, as `flagship_panel`'s was.

---

### 4. KI-1B — `universal_gate`, GPQA, seed 3407

```bash
./.venv/Scripts/python.exe -m benchmark.lever_experiments --lever universal_gate \
  --dataset gpqa --n 90 --seed 3407 --concurrency 6 \
  --out benchmark/results/lever_universal_gate_gpqa_seed3407.jsonl
```

- **Seed:** 3407 (fresh). **Cost: 1.22M.**
- **Bar:** completes the pre-registered 2-of-3 branch — net ≥+3 at 2 of {1001, 2311, 3407} with pooled exact one-sided McNemar p<0.05. **Both fresh seeds ≤+2 ⇒ retract the seed-1001 result.**

---

### 5. Analysis — free

```bash
./.venv/Scripts/python.exe -m benchmark.verify_universal_gate
```

- **Build first:** extend `SEEDS = (1001,)` → `(1001, 2311, 3407)` and add the pooled McNemar (~15 lines). The paired counterfactual from `plurality_letter` is already correct in that file.
- **Cost: 0 tokens.** Offline.
- **Bar:** restates the 2-of-3 verdict and the compute-matched attribution in one place.

---

### Budget

| step | tokens | cumulative | % of 30M week-1 cap |
|---|---|---|---|
| 0 registry | 0 | 0 | 0% |
| 1 KI-0R replay | 0.58M | 0.58M | 1.9% |
| 2 `universal_gate` s2311 | 1.22M | 1.80M | 6.0% |
| 3 compute-matched N=9 s2311 | 1.41M | 3.21M | 10.7% |
| 4 `universal_gate` s3407 | 1.22M | 4.43M | **14.8%** |
| 5 analysis | 0 | 4.43M | 14.8% |

**Funded: ≈4.43M.** Proposed across the two drafts: 15.0M (KI) + 4.7–7.4M (SCI-1) ≈ 20–22M. **Roughly 78% of the proposed spend is declined**, and the decline is where nearly all of the review's value lies.

**Conditional, not funded now:** KI-1 Arm A at 2.30M, **iff** step 1 returns ≥0.311 on SuperGPQA-hard, and then re-specified around cost-per-recovery non-inferiority rather than an accuracy McNemar.

**If steps 2–4 land**, the claim reads:

> *On GPQA-Diamond, three cheap `qwen3.6-flash` seats that escalate every unanimous answer to a tool-using tribunal with a `qwen3.7-max` judge score 88.9 / xx / xx% against 78.9 / xx / xx% for the byte-identical panel without escalation (pooled net +N, exact one-sided McNemar p<0.05, 3 seeds, paired in-run) — recovering R% of unanimous-wrong answers while breaking B% of unanimous-right ones, and beating a compute-matched 9-seat cheap panel that spends the same tokens on more votes instead of a tribunal.*

Paired, controlled, within-family, and — critically — it survives the control that killed the last headline, because that control is in the run rather than appended to it.

---

# Section 5 — What is abandoned, and why

Named explicitly so nothing returns in a new costume.

**1. The entire re-reading family.** Verbalized confidence and every confidence selector (+76 in-sample, **−4 held out**, sign-reversed 2/3 fresh seeds); resample instability (died against its own permutation null); permutation instability (42.4% flip rate, contrast +7.1pp, **Fisher p=0.4552**, n=139 pooled over 3 seeds); reasoning length, trace and hedge features; logprob ranking; stronger judges (9/9 correct overturns, **zero net**). Six independent nulls, one shape. **Any new proposal whose readout is cross-seat agreement or a property of the existing transcript is presumed dead and must argue past all six.**

**2. SCI-1 `restate_probe` and the third perturbation axis.** Killed by its own pre-registration (both disjuncts of META-2's clause fired), by an unreachable shippable bar (a **perfect oracle** yields **0.54 net/seed** against a **+5** requirement; **837 items/seed** would be needed), and by an invalid test (McNemar is paired; B−C is not). §2.

**3. F11 as drafted** — fixed-order pair presentation and a single-model κ manufacture false assurance about the primitive SCI-6's demoted seat-dimension would inherit. Buildable only under §2.10(a)(b)(c); all its downstream consumers are retired, dropped, or gated on a branch that can no longer occur.

**4. META-1 and the calibration thesis.** Finished by META-2's own kill clause. If neither logged features nor instability can see inside the unanimous pool, the thesis is dead. This also blocks META-6's panel arms.

**5. The oracle-coverage narrative as an opportunity size.** At N=15 with ~47% seats, 90.8% coverage is **below the 98.7%** that 15 random 4-choice guesses give. The "40-point gap" is mostly guessing entropy. Do not cite it to motivate anything, including KI-2.

**6. Bigger or stronger same-family panels.** Plurality accuracy is **flat N=3→15** (best +3 against a +5 bar); N=5 = 81.1%; `qwen38_panel` escalates 0% of items.

**7. SuperGPQA-hard as a gate surface.** 9.5% conversion, **24.0 escalations per net item**, 16.1% family floor, ~1.3pt union headroom. Every gate lever belongs on GPQA. This is the single fact that re-pointed the one funded live arm.

**8. Deliberation as `flagship_panel`'s mechanism.** Retracted. +9 of the +10 is 3× self-consistency (p=0.0245); the tribunal contributes **+2 (p=0.344, n.s.)**. The arithmetic stands; the story does not.

**9. The D0 `qwen3.8`-solo point estimate.** 93.6% retired to **[83.3%, 94.4%]** after three paced retries recovered 2 of 12 items lost to structural server-side 504s. Our 90.9% sits *inside* the interval; the sign is undetermined.

**10. Coding and agentic work as an accuracy axis,** including A0's 5.5M. ~50pt base gap (37.5% vs 88.3–91.9%) against a best-ever orchestration lift of +4.1pp, on a 24-task set we tuned on.

**11. RAG as an accuracy claim against the flagship.** ±6pt per-seed swing (+4.7/+6.9/+8.0/**−5.6**), loses to the flagship on every seed where the comparison exists, never McNemar-tested. Also abandoned: LEXam (−14), MMLU-Pro, MedQA, GSM8K/MATH-500, AIME, SimpleQA-RAG, multimodal, long-context — saturated, negative, or both.

**12. The 5.0M council** until its free gate (F2/D2 de-inflated union) actually clears; the 7pt GPQA union may be seed luck.

**13. Every cross-lab comparison sentence.** Not expressible with these instruments (§1.2). No client, no keys, no shared item set, no shared grading — and a 1–3pt margin would sit inside both our noise floor and a protocol difference we do not control.

---

## Appendix — verification log

Claims checked against the repo on 2026-08-01, in the order they became load-bearing.

| claim | method | result |
|---|---|---|
| SCI-1 has no spec section | `grep -n "^#.*SCI" docs/experiment-spec-book.md` | Only SCI-2 (330), SCI-3 (360), SCI-5 (390). **Confirmed** |
| "knowledge injection" never specified | `grep -n "knowledge.injection" docs/*.md` | Two hits, both forward-pointers inside kill clauses (503, 745). **Confirmed** |
| `classify_pool_checkability --strict` does not exist | `grep -c add_argument` | **0** `add_argument`; `main()` at line 462 takes no args. **Confirmed** |
| `pre_gate_votes` excludes `universal_gate` | `lever_experiments.py:1944-1945` | `if lever in ("verified_gate_flaw", "verified_gate_cas")`. **Confirmed** |
| `--n-solvers` is not available to a new lever | argparse help, `lever_experiments.py` | "diversified_panel/cycled_panel only". **Confirmed** |
| `verified_discriminator`, `rag_candidate_discriminate` do not exist | `--lever` `choices` list | Absent. **Confirmed** |
| CAS extractor writes the check from its own transcript | `lever_experiments.py:828-841` | "with the chosen answer's numeric value already substituted in". **Confirmed** |
| 87.3% is a ceiling, not a floor | `pool_checkability.md` | "Treat these numbers as the CEILING the heuristic supports, not a validated floor." **Confirmed**; unparseable exemplars quoted verbatim |
| 47.6% is an upper estimate | `unanimous_gate_headroom.md` §6 limit 2 | "**Treat 47.6% as an upper estimate.**" **Confirmed** |
| SuperGPQA gate conversion 9.5% / 24.0 escalations | `unanimous_gate_headroom.md` §5 table | 21 → 2; 24.0. **Confirmed** |
| GPQA gate conversion 55.1% / 75.0%, 4.2 escalations | same table + §8 | **Confirmed** |
| `universal_gate` GPQA seed 1001 = net +9, p=0.00195 | `FINDINGS.md:89`, headroom §8 | 78.9%→88.9%, 9/12 recovered, 0/36 broken. **Confirmed** |
| `universal_gate` GPQA cost | recomputed from `lever_universal_gate_gpqa_seed1001.jsonl` | 1,218,704 tok / 90 = **13,541 tok/item**. **Measured** |
| GPQA / SuperGPQA control cost | recomputed from `lever_control_seed7.jsonl`, `lever_control_supergpqa_seed7.jsonl` | 9,145 / 10,505 tok/item. **Confirmed** |
| `diversified_panel` N=3 ≠ shipped panel | `lever_experiments.py:1051` | Seats are procedure × temperature × permutation. **Confirmed** — limitation stated in §3.3 |
| `run_compute_matched_control.py` cannot take a fresh seed | line 114 | `choices=list(CLAIM_SEEDS)`, `CLAIM_SEEDS = (42, 7, 123)`. **Confirmed** — which is why §3.3 uses `diversified_panel` instead of that script |
| seeds 2311, 3407, 8419, 1607, 4409, 4517, 4621, 5711, 5813, 6203, 6311, 6427, 7717, 7823, 7919 are fresh | registry grep + `benchmark/results/` filename scan | 0 hits each. **Confirmed** |
| registry binds SCI-1 to 909/1313/2027 | `seed_registry.json` → `instability_merged` | `"spec_ids": ["META-2", "SCI-1"]`. **Confirmed** — amendment required, §4 step 0 |
| `sympy_check` / `_parse_sympy_expr` exist | `src/quorumqa/tools/mcp_server.py:114, 192` | **Confirmed** |
| McNemar 6-1 fails at +5 | exact binomial | P(X≥6 \| n=7) = 8/128 = 0.0625. **Confirmed** |

**No answer key was retrieved or inspected at any point.**
