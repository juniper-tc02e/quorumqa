# QuorumQA capability roadmap

## 1. The strategic frame

### 1.1 The axis label does not predict value — the cheap-to-flagship gap does

Every benchmark axis in this roadmap was originally chosen by *subject label* (science, math, medicine, law). That taxonomy has zero predictive power over whether orchestration pays. The measured record sorts cleanly on a different variable entirely:

| Surface | Flagship single call | Cheap-tier unanimous-wrong | Best lever result |
|---|---|---|---|
| SuperGPQA-hard | ~79.5% | 23% | flagship_panel **+4.1** mean (3 seeds) |
| Organic chem slice | matched flagship | large | chem_thinking_gate **+4.4** vs matched flagship |
| GPQA-Diamond | 84.4% | 11% | thinking_gate **+1.1** (inside noise) |
| MedQA | 94% | 4% | tie (+2 = one item of 50) |
| MMLU-Pro STEM 4-way | 96.7% | 1.7% | flagship_panel **+0.0**, escalation 3.3% |
| MATH-500 L5 open | 96.6% (cheap tier *also* 96.6%) | 0% escalation at both tiers | inert |
| LEXam | 86.0% (seed 42, n=50) | 15.6% cheap-panel | engine **−14** (cheap tier) |

Wins cluster where the gap is large. Nulls cluster where it is ~0. Medicine and science are both "knowledge-and-reasoning MC benchmarks" and they sit at opposite ends of this table — the label told us nothing, the gap told us everything.

The law has a **precondition that is easy to forget**: a large gap only pays if the resulting errors *decorrelate into disagreement that an escalation trigger can see*. That gives two distinct inert regimes, not one:

- **Ceiling saturation** — both tiers succeed, nothing to deliberate about. Measured on MMLU-Pro, MATH-500, GSM8K, MedQA.
- **Floor saturation** — both tiers fail, and fail the same way. Predicted (never yet measured) for any surface where the flagship is near-chance. This is the mirror-image null and it is currently an *unfilled row* in our ledger; recording it costs one cheap probe and would be a genuinely new finding.

### 1.2 Reframing: three classes of structural advantage

Where a multi-agent system can beat a single call is not a subject-matter question. It is a question of what *structure* the surface hands us.

**Class A — programmatic verifiability.** A non-fallible arbiter exists at inference time: a sandbox exit code, a unit test, a CAS equivalence check, a Python predicate over the output string. This is the strongest class we have, because it is the only one where escalation *coverage* is 100% by construction rather than contingent on solvers happening to disagree. Every internal null in the record (qwen38_judge, N=5, qwen38_panel) is a coverage failure; Class A surfaces cannot have one. External support is unambiguous: verifiable/rule-based rewards are the field's reliable arbiter across all frontier RL work.

**Class B — decorrelation headroom.** No external arbiter exists, so the arbiter is agreement itself. Value requires (i) a large cheap-to-flagship gap and (ii) errors that decorrelate. This is where our two validated wins live (SuperGPQA-hard, chem) and where the **unanimous-wrong ceiling** binds hardest: 61.6% of wrong rows are unanimous, and a disagreement-triggered escalation cannot see them by construction.

**Class C — architectural impossibility for a single call.** The single call cannot perform the task at all, or cannot produce the output type. Long-context map-reduce (each chunk sits at position 0 of its own window), sample-based confidence (one sample cannot produce a distribution), search-with-a-verifier (one call cannot search). Here we are not competing on quality; we are competing on capability. The honest caveat is that a Class C "win" is a capability claim, not a benchmark delta, unless a single-call baseline actually exists to beat.

**Not a class — saturated recall.** Where the base model already knows the answer (MMLU-Pro, MedQA, GSM8K) or structurally does not (LEXam's Swiss statutes absent from a STEM/US-law corpus), orchestration adds tokens and subtracts accuracy. The required fix is a better base model, better pretraining data, or a different corpus. Not a better tribunal.

### 1.3 The cost frontier is part of the verdict

F2 (offline, 73 result files) is the most uncomfortable finding in the record: **on 6 of 9 benchmarks a bare single flagship call Pareto-dominates every lever we ever logged** — more tokens, equal-or-worse accuracy. Levers clear the frontier on exactly two surfaces plus the chem slice.

That converts "winnable" into a two-part test. A lever is winnable only if it beats the baseline **at matched or lower tokens**. Consequences applied throughout this roadmap:

- Every whole-pipeline swap (panels, councils, replicated ensembles) must carry a **compute-matched control** — the same base config sampled the same number of times, aggregated by majority. Without it, a gain is indistinguishable from plain self-consistency, which Self-MoA (ICML 2025) predicts will dominate and which this repo has already reproduced twice.
- Every **gate-shaped lever** (fires only on a subset, logs the pre-gate vote) gets its control for free inside the same run, byte-identically paired on identical items. This is a real economic advantage of gates over swaps and it drives the funding order in §2.

### 1.4 The twelve axes

| # | Axis | Structural class | Verdict | Gate before spend |
|---|---|---|---|---|
| 3.1 | Science (GPQA / SuperGPQA-hard / chem) | B (+ partial A) | **Winnable** — the only validated accuracy surface | Free union + instability audits |
| 3.2 | General knowledge (MMLU-Pro, BBH) | — | **Not winnable** (MMLU-Pro saturated); BBH unmeasured | R6 probe |
| 3.3 | Math | A (equivalence checking) | **Not winnable on absolute SOTA** — measurement-blocked; every reachable surface saturated | M0 probe |
| 3.4 | Coding (SWE-bench class) | A in principle | **Not winnable** — ~50pt base gap, no scaffold | Dropped this window |
| 3.5 | Agentic tool use (Terminal-Bench) | **A** | **Winnable as relative lift only** — never absolute | Oracle-gap measurement |
| 3.6 | Medicine | B (MedXpertQA) / none (MedQA) | MedQA **cost-only**; MedXpertQA **unproven, screen first** | 60-item probe + A–J refactor |
| 3.7 | Law | none measured | Probe-only; panel run dropped — see §3.7 |
| 3.8 | Factuality | B (unbounded answer space) | Structurally favourable, ceiling-capped — see §3.8 |
| 3.9 | Instruction following | **A** | Blocked on porting the official scorer — see §3.9 |
| 3.10 | Long context | **C** | Blocked on an unmeasured transport cap — see §3.10 |
| 3.11 | Calibration / selective prediction | **C** | Not an accuracy lever; a capability claim — see §3.11 |
| 3.12 | Multimodal | — | Not a lever; architectural project — see §3.12 |

### 1.5 House statistical standard (applied uniformly below)

Three corrections adopted for this roadmap, all forced by the adversarial review.

1. **The "+3 net discordant per 90" bar is retired.** It cannot reach significance under the paired test this roadmap mandates. McNemar exact, one-sided: with zero losses, +4 gives p = 0.0625 and +5 gives p = 0.03125 — so **+5 is the minimum single-seat net gain that can clear p < 0.05**, and any realistic discordant volume (e.g. 6 gains / 3 losses) lands at p ≈ 0.5. Replacement rule, used everywhere below: **net ≥ +5 discordant at one seed with McNemar exact p < 0.05, OR net ≥ +3 at 2 of 3 seeds with the POOLED McNemar (n = 270) clearing p < 0.05.**
2. **GPQA answers are keyed on choice TEXT, never letter.** `load_gpqa._shuffle_choices` reshuffles options per seed, so letters are not comparable across runs. Any cross-seed or cross-config join keyed on letters is noise. This is a latent hazard in the repo and should be written into the loader docstring.
3. **Seed hygiene.** seed42 appears in 50 result files, seed7 in 17, seed123 in 16. Screens that gate spend run on **unburned** seeds, and a seed used for a go/no-go decision is excluded from the validation seeds.

Kill dominates bar, without exception. A lever that passes its bar and fires a kill is killed.

---

## 2. Reasoning: the deep plan

### 2.1 The organizing law: decorrelation must be injected at the CONDITIONING, not the sampler

Four approaches have failed, and they failed for one reason.

| Failed approach | Measured result | What was varied |
|---|---|---|
| More solvers (N=5) | 81.1% vs 84.4% at higher cost | sampler |
| Stronger same-lineage solvers (qwen38_panel) | ties baseline, trails flagship_panel, **0% escalation**, 30% drops | sampler |
| Stronger judge (qwen38_judge) | 9/9 overturns correct, **zero net gain** | neither — same candidates, same information |
| Temperature/persona lenses | capped; the residual is unanimous-wrong | sampler |

Every one of them held the model's *input* fixed and varied the *noise*. Same conditioning plus different noise yields correlated errors — that is the homogeneity trap, measured three separate ways, and Self-MoA independently predicts it (repeated sampling of one strong model beats mixing, unless members are near-equal quality *and* highly diverse).

Every approach that ever produced signal changed what the model was conditioned on: thinking on/off, retrieval evidence, subject priming, method priors. **This is the design constraint for every lever below.**

### 2.2 The ceiling test: does the mechanism produce a bit that no logged run contains?

61.6% of wrong rows are unanimous. A disagreement-triggered escalation cannot see them, by construction — they are unanimous precisely because every channel the engine currently runs agreed. This gives a sharp, mechanical test for whether a proposed lever is a real attack or the ceiling in a new costume:

> **Does the mechanism take a NEW ACTION that produces an observation absent from every existing log, or does it merely re-weight information already there?**

Re-weighting is the costume. W5's trace features (LOBO AUC 0.625, a BAND) re-read existing traces and failed; F3's re-engineering of the same quantities was *negative* (dAUC −0.026); qwen38_judge re-scored existing candidates and gained nothing; the Sea AI Lab result independently confirms that reflection tokens do not track correctness. Three internal nulls and one external refutation, all of the same shape.

The escapes are exactly two:

- **A new observation** — perturb the input and re-observe; execute the answer; retrieve on a single claim; solve without the options.
- **A non-fallible or de-anchored arbiter** — a deterministic checker, or a judge that structurally cannot see the consensus it is supposed to audit.

Anything else is renaming.

### 2.3 Where the headroom actually is (and where it is not)

Two offline findings converge and they point in *opposite* directions on our two science surfaces.

- **F1(a) family floor.** On GPQA, only 4 of 192 multi-config items (2.1%) are wrong under *every* config ever logged, against 90.9% for the best single config — roughly **7pt of answers the family already produces and then discards**. On SuperGPQA-hard the floor is 16.1%, so the cross-config oracle is 83.9% against flagship_panel's 82.6% mean — roughly **1.3pt**, inside the ±2.5pt noise floor at n=90.
- **F1(b) deficit decomposition.** On GPQA items where qwen3.8-solo beat our best society, the split was **0 never-escalated / 2 escalated-and-lost** — 100% one-sided but **n = 2**. Directionally unambiguous, statistically thin. The *strong* evidence for selection levers on GPQA is F1(a)'s union headroom, not F1(b).

Sequencing consequence, applied throughout:

- **GPQA is the SELECTION surface and the harvesting surface.** Coverage levers have no logged target there.
- **SuperGPQA-hard is the COVERAGE surface and the SCREENING surface.** Its 23% unanimous-wrong pool gives the statistical power to detect whether a coverage mechanism moves the rate at all; its selection headroom is exhausted, so no second-order arbitration lever runs there.

One honest bound on F1(a): the 2.1% floor is **inflated**, because a config is credited correct if it was *ever* correct across seed repeats. Part of that 7pt is resampling luck. De-inflating it costs zero tokens and is the first item below.

### 2.4 Ranked plan

Ranking rule: free before cheap, cheap before expensive, gates before swaps, and — per §1.3 — a lever whose control is free inside its own run outranks an equally promising lever that must buy a matched-compute control.

---

#### Rung 0 — free, mandatory, zero tokens

**D1. Corrected instability audit** *(repairs the reasoning-depth planner's headline finding, which does not survive review)*

The proposed 6.2x wrongness lift (P(wrong | stable) = 6.2% vs P(wrong | unstable) = 38.5%, n = 77 pooled GPQA items) is **largely an arithmetic artifact of the definition**. An item is "unstable" iff its K = 3 replicate answers disagree; if they disagree, at most one distinct answer can be correct, so the run-level wrongness rate among unstable item-runs has a hard mechanical floor of 33.3% (A,A,B with A correct) rising to 66.7% for any other split. The measured 38.5% sits **5.2pt above a guaranteed floor**. Meanwhile stable items are all-right-or-all-wrong by construction, so the denominator term is free to be tiny. A "lift ≥ 3x" bar is therefore satisfied by construction on any surface above roughly 80% accuracy, and the "< 2x" kill can essentially never fire.

*Corrected mechanism.* Extend `benchmark/analyze_family_floor.py`. (a) Re-key every run's final answer on **choice text**, not letter. (b) Score at the **item** level using the text-majority-over-replicates answer, which removes the mechanical floor. (c) Report the lift against a **permutation null** that preserves each item's replicate-answer multiset while shuffling correctness, and derive the bar from that null distribution rather than asserting 3x. (d) Report the same quantities restricted to items that were *unanimous within each run* — the first direct measurement of P(wrong | unanimous), flagged UNMEASURED by W5. (e) Report the lift separately for **within-config cross-seed** pairs versus **cross-config** pairs, because the pooled 6.2x conflates option-order change, temperature resampling, *and* configuration change, while the lever it is supposed to price (D5) implements permutation-only within one config.

*Ceiling test.* This is a measurement, not a lever. It prices D5 and nothing else.

*Bar.* Item-level lift ≥ 2x against the permutation null, with pooled n_unstable ≥ 20, reproduced deterministically on two runs.
*Kill.* Item-level lift < 2x against the null, or within-config lift materially below pooled lift → **D5 loses its measured prior and does not run.**
*Cost.* 0 tokens. Build ~3h.

---

**D2. De-inflated cross-config union (the free half of the council lever)**

*Mechanism.* On GPQA items covered by ≥ 3 distinct configs, recompute the union crediting each config **once** — single repeat, no ever-correct-across-seeds crediting — with the repeat-selection rule (lowest seed value) **pre-registered before computing**, since that choice bears directly on the quantity being de-inflated. Join on choice text. Build the agreement/disagreement contingency table. Report the coverage-selected item set's baseline accuracy against full-GPQA baseline, so the non-random selection (items are present because runs happened to cover them) is visible rather than laundered.

*Ceiling test.* Measurement. It prices D4 and can kill it for zero tokens.

*Bar.* De-inflated cross-config plurality beats the best single config by ≥ +5 discordant on that item set.
*Kill.* Plurality ≤ best single config → **the 7pt union was seed luck, D4 dies free.**
*Cost.* 0 tokens.

---

**D3. Confidence-estimator head-to-head** *(the genuinely free half of the calibration rider)*

The proposed instability-calibration rider was labelled "P0, 0 tokens" but its permutation-flip half requires a **W2 permuted_panel run that has never been executed** — a paid multi-million-token dependency. Split it. Part B is free today: over the existing 5,597 logged rows, compute within-benchmark AUC of single-seat verbalized confidence alone versus panel agreement alone. That comparison is the entire empirical basis for the claim that orchestration produces a better confidence signal than one call can, and it has never been run. Part A becomes a rider on W2, priced at W2's cost, conditional on W2 being funded.

*Cost.* 0 tokens.

---

#### Rung 1 — cheap paid (funded)

**D0. Repair the family-best bar** *(measurement integrity; prerequisite for any GPQA claim)*

The qwen3.8-solo GPQA bar of 93.6% is **73/78 with 12 timeout/429 drops**. That is the identical survivorship contamination the repo's own F2 review used to disqualify qwen38_panel's 87.3% (n=63 after ~30% drops) and the invalidated AIME baseline's 100% (n=48) — the rule was simply never applied to this row. Drops are timeouts, timeouts correlate with long/hard items, so the bar is upper-biased in the direction that most disadvantages every society claim.

*Corrected mechanism.* Re-invoke `benchmark/qwen38_baseline.py` against the existing output file using **its own resume path** (`done_ids = {r["question_id"] for r in existing}` at line 115), with paced retry-and-backoff. The originally proposed route via `retry_dropped.py` **does not work**: verified, that script builds its done-set from `json.loads(line)["engine"]["item"]["question_id"]` (line 26) — the combo baseline+engine schema — and would KeyError on every flat qwen38 row, and it re-runs `run_question` (the qwen3.7-max engine), not the 3.8 baseline. Publish the repaired full-90 number **and** the survivor-only 78-item number side by side. Drop the claim that the F6 seed parameter makes the arm deterministic — a seed on a hosted endpoint is a best-effort hint and nothing in the record verifies run-to-run identity under it.

*Bar.* 90/90 completed with zero unretried drops; both numbers published together.
*Residual band (1–5 items still failing — the most probable outcome given 3.8's fragility).* Publish with stated n **plus best-case/worst-case imputation bounds** (all-dropped-correct and all-dropped-wrong), so the repaired figure is reported as an interval rather than a point.
*Kill.* > 5 items still failing after 3 paced retries, **or** spend exceeding 3x the estimate → retire 3.8 to a footnote and quote qwen3.7-max solo (86.7%, n = 451, the deepest baseline in the repo) as the bar.
*Cost.* ~0.05M expected (12 items × 4,229 tok/item), **hard cap 1.2M**. Build: already-built.

---

**D6. Merged claim audit — routed, de-anchored premise verification** *(merges the two duplicate proposals)*

Two clusters independently proposed the same lever (blind premise audit; claim audit). Both fire only on unanimous panels, both extract 3–5 atomic claims from the seats' shared reasoning, both escalate on a contradicted claim. They differ only in the adjudicator. Build **one** lever with a shared extractor and a routing switch.

*Mechanism, concretely.*
1. **Extract** (1 cheap `qwen3.6-flash` call, unanimous items only): convert the seats' joint reasoning into 3–5 atomic, **load-bearing** propositions, each rewritten to stand alone — without the question, without the options, without the candidate answer. ("A suprafacial-suprafacial [4+2] is thermally allowed.")
2. **Route by type** using the already-committed pool classifier:
   - *Quantitative/algebraic* → deterministic `sympy_check` / `substitute_check` via the existing MCP server. Verified in repo: `src/quorumqa/tools/mcp_server.py` exposes exactly five tools (`lookup_constant`, `safe_calculate`, `sympy_check`, `substitute_check`, `search_corpus`) — all constrained evaluators, fail-safe.
   - *Factual/definitional* → retrieval on **that claim alone** (reuse `r3_extract_disputed_claim` / `retrieve_r3_evidence`), judged by a reasoning gate, never by score. Score-gating failed: wins and regressions have statistically identical retrieval scores (0.0288 vs 0.0290).
   - *Neither* → **blind flagship-with-thinking proposition judgment**: the bare proposition, no question, no options, no candidate answer, returning true/false/uncertain plus a stated ground.
   - *Unclassifiable* → marked UNVERIFIABLE, given no vote.
3. **Escalate** iff any proposition is CONTRADICTED, seeding it as the skeptic's opening claim.
4. **Log** the pre-gate vote for every item, so the control arm is byte-identical within the same run.

*Ceiling test — REAL attack, on both escapes.* It fires on unanimous items (coverage the engine currently has none of), and it produces observations no logged run contains: a CAS verdict, a claim-scoped retrieval, and a judgment rendered without the conclusion in context. The naive form of this idea — show a critic the trace and ask which step is wrong — is predicted to fail by every anchored-critique null in the record and by the self-preference literature. **Blinding, not step-granularity, is the load-bearing part**, and the design tests exactly that distinction: the anchored condition (W1-A's flaw-finder) and the blind condition run over the same items in one run, giving the paired head-to-head the portfolio is missing.

*Coverage bound, stated honestly.* The CAS arm is capped by the committed pre-run classifier at 18/34 (53%) on GPQA and 96/110 (87%) on SuperGPQA-hard, and that figure is the **regex heuristic's ceiling, not a floor** — alphanumeric codes count as quantitative where a CAS cannot evaluate them. Roughly half the GPQA unanimous-wrong pool is conceptual and reachable only by the blind-proposition arm.

*Pre-screen (mandatory, before the full run).* A frozen diagnostic set of **40 known-unanimous-wrong and 40 known-unanimous-right items**, ids committed before the run. The originally proposed 15/15 cannot resolve its own thresholds — at 15/15 the stated bar is Fisher-exact p ≈ 0.13 even if hit exactly, and the bar/kill pair leaves 1.5–2.5:1 discrimination undefined, which is the most likely landing zone. Report **two** metrics, not one: firing rate (does it trigger) and **recovery rate** (of the fired wrong items, what fraction end at the correct answer after escalation). A lever can fire on half the wrong pool and recover none of it.

*Bar.* Discrimination ≥ 2.5:1 on the frozen set **and** recovery > 0 on the wrong set; then, on the full run, net ≥ +5 discordant with McNemar p < 0.05 at one seed, or net ≥ +3 at 2 of 3 seeds with pooled McNemar clearing.
*Kill (dominates).* Discrimination < 1.5:1 — it fires as often on correct answers as wrong ones, the precision failure that killed score-gating. **Independent kill:** extraction fidelity < 90% on a blinded spot-check of 30 extracted propositions against their source traces, or a blinded majority-of-3 judgment that the extracted claims are not load-bearing. **Independent kill:** the frozen relevance rubric (`benchmark/r3_relevance_rubric.md`, committed pre-run) returns > 50% off-topic on the claim-level retrievals. 1.5–2.5:1 is pre-registered as **re-screen at larger n, do not run the full pilot**.
*Cost.* Pre-screen ~0.5M. Full run ~+2k tok/q on top of the base config; on SuperGPQA-hard at n=90 with the within-run control, **~1.6M per seed**.
*Build.* Small-build (extractor + router; both adjudicator arms reuse built components).
*Base config note.* Must run on a config whose seats emit a real derivation — the shipped seats emit ≤ 3 sentences, and there is no process to audit in three sentences. Run on the thinking-seat base.

---

**D7. Advocate gate — contrastive red-team on the runner-up** *(rides D6's run)*

*Mechanism.* On a unanimous plurality, identify the strongest non-chosen option deterministically (highest mention frequency across the seats' reasoning, tie-broken by option index — no extra call). One flagship-with-thinking call is ordered to **build the strongest case for that option**, then answer explicitly: does this case defeat the panel's answer, yes/no, on what specific ground. Escalate iff "defeats". Ships as arm B of the same W1 pilot as the existing flaw-finder, paired on identical items and identical pre-gate votes.

*Ceiling test — REAL attack.* W1's arm A asks the model to find a flaw in a stated answer, which is a confirmation-shaped task whose most likely failure mode is "the reasoning holds up". Asking for generative work in the *opposite* direction breaks the anchor: the model must produce content, not endorse it. It fires on unanimous items, so it is coverage, not adjudication quality — the bottleneck qwen38_judge proved is binding. It covers 100% of MC items including the conceptual ones the CAS arm structurally cannot reach.

*Bar.* Net ≥ +5 discordant at one seed with McNemar p < 0.05 (or +3 at 2 of 3 with pooled), **and** red-team precision ≥ 25% (fires on correct answers ≤ 3x as often as on wrong ones).
*Kill (dominates).* Precision < 20%, or "defeats" rate > 60% of unanimous items (indiscriminate advocacy).
*Cost.* ~+3k tok/q on the unanimous subset → **~+0.3M** riding D6's run.
*Build.* Small-build.

---

#### Rung 2 — one expensive selection lever (conditional on D2)

**D4. Merged council-of-configs adjudicator** *(merges the two duplicate second-order proposals; the only lever aimed at the ~7pt union)*

Two clusters proposed this idea at ~10.5M and ~6M — a 16.5M double-spend on one mechanism — and they **contradict each other on the load-bearing detail**. One shows the arbiter each config's answer plus its distinguishing artifact (majority visible); the other's central claim is that vote counts must be hidden or the judge anchors on argument count, with "judge matches raw majority > 90%" pre-registered as a kill. Merge, keeping the de-anchoring.

*Mechanism.*
- **Candidates (K = 5), from genuinely different conditionings, not temperatures**: evidence-on (rag_thinking_gate seat), thinking-on, permuted-options, method-constrained (verify-by-candidate), plain. Retrieval-vs-no-retrieval is a real information difference, which is Self-MoA's stated exception condition (near-equal quality *and* highly diverse).
- **Presentation**: anonymised, identity cues stripped, **vote counts withheld**, presentation order shuffled per item. The judge (flagship-with-thinking) rules on the merits and must name the specific argument it found decisive.
- **Second judge call on the identical candidate set with vote counts SHOWN** (~+3k tok/q). This is the arm that identifies the mechanism. Without it, a pass conflates two changes — a more diverse candidate set and a de-anchored presentation — and the novel claim is specifically the de-anchoring one.
- **Option-elimination arm** (the third de-anchoring proposal, folded in rather than separately funded): for each option A–D, one bounded reasoning block producing accept/reject plus the disqualifying fact, options in randomized order, plurality withheld until all four verdicts are written. Exactly one survivor → answer; zero or ≥ 2 → second pass on the tied set, then plurality as tiebreaker. **Log the survivor-count distribution per item** — a free per-item calibration signal no run in this repo produces.
- **Compute-matched control (mandatory).** The portfolio arm is ~25k tok/q against chem_thinking_gate's ~13.6k. The control is **2× chem_thinking_gate aggregated by text-majority** at ~27k tok/q — same tokens, same vote count, no cross-config structure. The bar is stated against *that*, not against a single 13.6k run. Without this control, a pass is indistinguishable from plain self-consistency, which is precisely the outcome Self-MoA predicts and which this repo has reproduced twice.

*Ceiling test — REAL attack, but on the SELECTION side only.* Cross-config disagreement fires on items where each individual config is internally unanimous, which is a trigger the current engine structurally cannot see. But it does **not** attack the unanimous-wrong pool where *every* config is wrong — that is the 2.1% family floor, and nothing here reaches it. Stated plainly so the claim is not overread.

*Not run on SuperGPQA-hard.* Union headroom there is ~1.3pt, inside noise. Pre-registered.

*Bar.* Net ≥ +5 discordant vs the **compute-matched control** at one seed with McNemar p < 0.05, **and** the hidden-vote judge beats the shown-vote judge on the same candidate sets (the de-anchoring claim), **and** judge ruling differs from the raw hidden majority on ≥ 10% of items with those overrides net-positive.
*Kill (dominates, scoped per arm).* Cross-config disagreement < 10% (the configs have homogenized — the trap in a new costume). Judge matches raw majority > 90% (anchoring on argument count; the lever failed even if accuracy ties). Survivor count exactly 1 on > 95% of items (the elimination arm is cosmetically restructured and behaviourally identical). **Arm-scoped:** if the plurality-of-configs rule clears while the arbiter's overturns are < 50% correct, ship the plurality arm and drop the arbiter — do not destroy a lever whose winning arm passed. The run logs both selection rules per item precisely so the arms can be judged separately.
*Cost.* ~5.0M for a **single-seed screen** at n = 90 (portfolio ~2.25M + shown-vote judge ~0.27M + matched control ~2.45M). **3-seed validation (~10M further) is explicitly UNFUNDED this window** and is scheduled only if the screen clears.
*Build.* Medium-build (candidate orchestration + blinded presentation harness; the elimination arm and the frozen-set replay machinery already exist).

---

#### Conditional and deferred (recorded with reasons, not scheduled)

**D5. Stability gate — permutation-replicated panel.** Conditional on D1 surviving the permutation null. Two defects forced the demotion: (a) its live gate condition is the same mechanically-guaranteed quantity D1 exposes, so an entirely inert gate passes it; (b) it has no compute-matched control — at ~24k tok/q against chem_thinking_gate's ~13.6k, with a text-majority over K×3 votes, it *is* 3x self-consistency with an escalation relabel bolted on, and comparing it to a single run attributes the sampling gain to the trigger. It is also not a fresh medium-build: `_permute_choices` and `solve_all_permuted_panel` already exist (W2 permuted_panel, built, offline-tested, suite 473 green). If D1 clears, run it as **the built W2 lever plus the instability trigger plus a matched K=3-with-unchanged-trigger control**, at ~1.2M for the cheap-panel variant — not as a 6.5M new build.

**D8. Blind-solve / no-match gate.** One seat solves open-ended with the options hidden; a constrained cheap matcher maps the free-text answer onto the option set returning `{index | NO_MATCH}`; matches plurality → confirm, matches a different option → escalate, matches nothing → escalate as the strongest signal. **REAL attack**: MC distractors are adversarially built around named misconceptions, so showing them conditions the derivation toward the trap all three seats then share — removing them is a conditioning change, and NO_MATCH is a third state agreement features cannot produce by construction. Ranked immediately behind D6 as the natural replacement if D6's pre-screen fails. ~1.2M/seed. **Unfunded-pending.**

**D9. Program-of-thought executable seat — DROPPED this window (fatal).** The mechanism claims execution "in the sandbox/MCP tooling already built and hardened". **Verified false.** `mcp_server.py` exposes five constrained evaluators and no code execution; `safe_math.py`'s own header states it is deliberately not a general eval because the Verifier tool must never become an arbitrary code execution path reachable from model-generated arguments; the only `exec` path in the repo is `environment.exec(...)` in `agents/terminal_agent.py`, a Harbor per-task Docker container instantiated by the Terminal-Bench harness and not callable from the QA benchmark path. This is therefore **not a small-build riding existing tooling — it is a new resource-capped, network-denied untrusted-code executor**, and its stated kill ("any observed sandbox escape") is vacuous against a sandbox that does not exist. Two further defects: its health bar compares PoT accuracy *conditioned on non-abstention* against a prose seat measured over all items (the same drop-conditioning class that disqualified qwen38_panel and the AIME baseline), and its non-determinism kill is undecidable because each program is executed once with no replay. **Re-labelled large-build, unfunded.** If revived: abstention-matched paired scoring, a determinism replicate (re-execute, compare stdout byte-for-byte), and escape defined as a concrete logged predicate. W1-B remains the deterministic-check channel this window.

**D10. Signal-driven refinement.** Strictly a multiplier on a firing parent (D6's contradicted claim, D7's defeating counter-argument, D8's NO_MATCH). Never a generic "please reconsider" — intrinsic self-refine without an external signal is a known null, and qwen38_judge showed more capability on the same information gains nothing. Runs only if a parent clears. ~+1–2k tok/q amortised.

**D11. Adversarial restatement.** A second perturbation arm inside D5, not a standalone lever. Its failure mode is specific: restatement can silently drop a constraint, producing a *different problem* and a false instability flag, which is how score-gating died. Needs a faithfulness checker (extra call, extra failure surface). Runs only if D5's permutation arm shows real signal but under-fires.

**Dropped outright, with reasons.** Naive step-critic (show the trace, ask which step is wrong — anchored, pre-refuted). More seats / stronger same-lineage seats / stronger judge (measured negative or null, three ways). Trace-feature and hedge-word gates (W5 BAND, F3 negative, externally refuted). ARC-AGI program search this window — it inherits D9's missing executor, needs ~1,600 untrusted executions in the 30-task micro-screen alone with no loader and no harness, compares 16x compute against a 1x arm, and validates "search with a perfect verifier beats one call" rather than anything about deliberation. Its one cheap, genuinely novel idea — floor saturation as the twin of ceiling saturation — is recorded in the null ledger for free.

### 2.5 What the reasoning plan is honestly worth

- **Achievable target.** GPQA-Diamond ≥ 92% at the 3-seed bar against chem_thinking_gate's validated 90.9%, with D0's repaired qwen3.8-solo number as the family bar. Stretch is that repaired number.
- **Not achievable, and no sentence in this roadmap will claim it.** A cross-lab "QuorumQA tops frontier models" claim on GPQA. Our unit is a reseeded 90-item subsample (each seed draws a *different* 90 from ~198, which is why qwen3.8-solo and chem_thinking_gate share only 68 items), our noise floor is ±2.5pt ≈ 2 items, and published frontier numbers use the full 198-item set with different prompting and grading conventions. A 1–3pt margin against a leaderboard number is inside our noise *and* inside a protocol difference we do not control. Only same-items, same-seed, within-family comparisons are defensible.
- **The hard ceiling.** 4/197 GPQA items and 84/522 SuperGPQA-hard items are wrong under every config ever logged. No orchestration of this model family reaches them: ~97.9% and ~83.9% respectively. Note this also shrinks the addressable base of a 90-item SuperGPQA run to ~75–76, so a "+3/90" bar is really +3/~76.

---

## 3. Per-axis plans — part 1 of 2

### 3.1 Science

**Verdict: WINNABLE.** The only axis with validated accuracy wins, and the only one where levers clear the F2 compute frontier.

**Numbers to beat.**

| Surface | Baseline | Best society | Family bar |
|---|---|---|---|
| SuperGPQA-hard | ~79.5% single flagship | flagship_panel 83.3 / 81.7 / 82.7 (**+4.1** mean, 3 seeds, never negative) | — |
| GPQA-Diamond | 84.4% single flagship | chem_thinking_gate 90.9% mean | qwen3.8-solo 93.6% — **contaminated**, n = 78 with 12 drops; repaired by D0 |
| Organic chem slice | matched flagship | chem_thinking_gate **+4.4** vs matched flagship, **+7.9** on chem | — |

**Funded levers (this window).**

| Lever | Target | Bar | Kill (dominates) | Cost | Build |
|---|---|---|---|---|---|
| **D0** bar repair | GPQA family bar | 90/90, zero unretried drops; both repaired and survivor-only numbers published | > 5 items failing after 3 paced retries **or** spend > 3x estimate → retire 3.8, quote qwen3.7-max solo 86.7% (n=451) | ~0.05M, cap 1.2M | already-built |
| **D6** claim audit + **D7** advocate gate (one run) | SuperGPQA-hard screen (23% pool = power), harvest on GPQA | pre-screen ≥ 2.5:1 discrimination on frozen 40/40 with recovery > 0; then net ≥ +5 discordant, McNemar p < 0.05 (or +3 at 2/3 seeds pooled) | discrimination < 1.5:1; extraction fidelity < 90% on blinded audit; frozen rubric > 50% off-topic; advocate precision < 20% | 0.5M pre-screen + ~1.6M/seed (control free, within-run) | small-build |
| **D4** council adjudicator | GPQA-Diamond ≥ 92% | net ≥ +5 vs **compute-matched** control, p < 0.05; hidden-vote beats shown-vote; judge diverges from hidden majority ≥ 10% with net-positive overrides | disagreement < 10%; judge matches majority > 90%; survivor count = 1 on > 95%; arbiter overturns < 50% correct (arm-scoped) | ~5.0M, **1 seed only**; 3-seed unfunded | medium-build |

Gated behind the free rungs: D4 does not run unless **D2** clears; D5 does not run unless **D1** clears against the permutation null.

**Dropped, and why.**
- **PoT executable seat** — no sandbox exists (verified: five constrained MCP tools, `safe_math.py` explicitly forbids being an exec path, the only `exec` is Harbor inside the agent track). Re-labelled large-build, unfunded.
- **Council-of-configs as a separate 10.5M lever** — merged into D4; the two proposals were one idea costed twice and contradicted each other on whether the arbiter sees vote counts.
- **Blind premise audit as a separate lever** — merged into D6; near-duplicate extractor, trigger and escalation path.
- **Option elimination as a separate build** — folded into D4 as an arm; its n=2 evidential base cannot support an independent budget line, though its survivor-count logging is a free calibration signal worth keeping.
- **More coverage on GPQA** — F1(b) gives coverage levers no logged target there (0 never-escalated). Coverage work screens on SuperGPQA-hard only.
- **Second-order selection on SuperGPQA-hard** — ~1.3pt union headroom, inside noise. Pre-registered not to run.

**Axis subtotal:** ~2.15M base (cap 3.3M) + ~5.0M conditional.

---

### 3.2 General knowledge

**Verdict: NOT WINNABLE BY ORCHESTRATION on MMLU-Pro. UNMEASURED on BBH.**

MMLU-Pro is the cleanest saturation null in the record and orchestration does not merely fail there, it subtracts: flagship 96.7% on STEM 4-way, flagship_panel **+0.0**, escalation 3.3%, unanimous-wrong 1.7%, full MMLU-Pro with the shipped engine **−12**, and F2 puts a bare single call **alone** on the Pareto frontier at 96.7% for 919 tok/q, dominating all 11 configs ever logged against it. There is no gap for deliberation to exploit. The only correct engineering action is a router that recognises saturation and spends one call — which is already the recorded MoO result, not a new lever.

BBH is entirely unmeasured in this repo: no loader, no baseline, no result file. It will not be claimed in either direction. The **registered prediction, committed in advance: flagship ≥ 92%, BBH is saturated, BBH gets no levers.**

**Funded lever: the standing gap probe (first application, BBH).**

*Mechanism.* Two arms on the same items: arm A single flagship call, arm B the three cheap seats only with no tribunal. Log the cheap-to-flagship gap and the unanimous-wrong rate. Items sampled across both the symbolic subtask family (dyck languages, boolean expressions, tracking shuffled objects, word sorting) and the natural-language family, since these plausibly have different gap profiles and a pooled number would hide it.

*Two corrections forced by review.*
1. **Sizing.** At n = 60, unanimous-wrong 5% vs 15% is 3 items vs 9 items with SE ≈ 4.6pt — the two routing branches sit inside each other's noise. The cheap arm runs at **n = 120** (~0.3M extra) so the split is resolvable.
2. **The decision table must be exhaustive.** As proposed it left the common case (unanimous-wrong 5–15% with flagship 85–92%) undefined — precisely the band the surfaces this protocol exists to adjudicate will land in.

| Flagship | Unanimous-wrong | Route |
|---|---|---|
| ≥ 92% | any | SATURATED — single call, build nothing |
| < 92% | < 5% | No coverage headroom — selection levers only |
| < 90% | > 15% | Full lever programme authorised |
| **85–92%** | **5–15%** | **DEFER — run one cheap already-built lever, build nothing new** |

*Falsifiability, and the one thing that makes this a predictor rather than a spending policy.* As proposed, the protocol was **unfalsifiable by construction**: any surface it labels SATURATED is routed to "build nothing", so no full-run outcome is ever generated for exactly the predictions that could refute it — the same self-sealing structure the plan correctly criticises elsewhere. Fix: **pre-commit ~0.5M for one audit run.** Take the next surface the probe condemns and run one cheap already-built lever on it, pre-registered before the probe fires.

*Bar.* The protocol's own forecast must match the eventual full-run outcome on ≥ 2 of the next 3 surfaces probed. Per-surface the output is a routing decision, not a win.
*Kill.* If the audit run shows a lever clearing +5 discordant on a surface the probe called SATURATED, the predictor is incomplete — record it, revise the law, do not defend it.
*Cost.* ~0.8M (60 flagship + 120 cheap) + 0.5M audit reserve.
*Build.* Small-build (BBH loader + 2-arm harness).

**Dropped.** Any MMLU-Pro lever. Any BBH lever built before the probe returns — that is exactly the mistake that cost full pilots on MMLU-Pro, GSM8K and MATH-500-MC.

**Axis subtotal:** ~1.3M.

---

### 3.3 Math

**Verdict: NOT WINNABLE ON ABSOLUTE SOTA — and on the reachable surfaces, not winnable at all.** One cheap measurement is worth making; everything downstream of it is conditional.

**Three independent blockers, all measured.**

1. **Measurement.** AIME-2026 has GLM-5.2 at 0.992 on **n = 30**. One item is 3.3 points. A flawless 30/30 run cannot be statistically distinguished from the leader. This is a stronger objection than the capability gap and it holds even if headroom exists.
2. **Saturation at both tiers.** MATH-500 L5 open-answer: flagship 96.6% **and** cheap flash-with-thinking 96.6%, 0% escalation at both tiers, 55/59 unanimous, 46 literally identical answer strings. GSM8K and MATH-500-MC: 100% baseline at both tiers, cheap deliberation costs −4.0/−6.1.
3. **Cost.** The externally validated mechanism is unaffordable at the N that produced it. `aime_open_panel_cheap` logged 2,050,542 tokens for 28 items = 73.2k tok/row across 3 solvers, i.e. **~24.4k tokens per sample**. DeepSeek R1-Zero's cons@64 (AIME 71.0 → 86.7) would cost ~1.5M tokens *per item* and ~75M for one 48-item seed — **1.7x the entire weekly quota**. Even N = 8 is ~9.4M = 21% of the week for a single seed, on a surface our own data says cheap deliberation loses on. cons@64 validates the mechanism; our token audit proves we cannot buy it.

Additionally: AIME-2024/25 is unusable on two independent grounds — our pilot is invalidated for survivorship bias (12/60 and 32/60 drops on 429s; the n=26 survivors are a biased easy subset that produced a spurious flash "100%" with 0% escalation), and both sets predate the models. FrontierMath, the one math surface with genuine headroom (~88–89%), is an Epoch AI holdout with no public access — recorded so the headroom is not mistaken for an opportunity.

**Funded lever: the AIME-2026 headroom probe (M0), with three corrections.**

*Mechanism.* Single qwen3.7-max call (thinking on), 4 runs per problem to match MathArena's reported protocol, over MathArena/aime_2026 (30 problems, integer answers 000–999, ungated). Graded by the existing `benchmark/math_grade.py::grade` (0/4000 false positives on real MATH-500, fails closed; integer answers carry zero interval/set/± edge-case risk) through `run_math_open.py`. New code is a ~30-line loader mirroring `load_aime.py`.

*Corrections.*
1. **The metric was undecidable.** The protocol runs 4 attempts but stated the bar in items ("≤ 24/30"), with no rule for collapsing 4 runs into an item verdict — mean, any-correct and majority give materially different numbers. **Pre-registered: mean over 4 runs, thresholds restated as accuracies.**
2. **The 25–26/30 band was undefined.** Exhaustive table below.
3. **Contamination is asserted, not measured.** No training cutoff for qwen3.7-max or qwen3.8-max-preview is established anywhere in this repo, and a February 2026 competition is well within reach of a current-generation model. A flagship at ceiling would then be read as saturation when it could be memorization. **Fix, free: include 5 AIME-2025 items as a contamination control inside the same probe.** If 2025 scores at ceiling and 2026 does not, the cutoff is bracketed and the 2026 number is interpretable; if both are at ceiling, record "saturation vs memorization unresolved" rather than closing the axis on an unverified premise.

| Flagship (mean of 4) | Cheap arm | Route |
|---|---|---|
| ≥ 90% (27/30) | any | CLOSED — third measured math saturation null; M1 cancelled unrun |
| 83–90% (25–26/30) | any | DEFER — insufficient headroom to distinguish a lever at n=30; no build |
| ≤ 80% (24/30) | ≤ 70% (21/30) | M1 authorised, **flagship tier only** |
| ≤ 80% | > 70% | No cheap-to-flagship gap — no lever |

*Second, independent kill.* Even with headroom: if our gap to 0.992 is ≥ 5 items, no lift in our record (max +4.1pp) or the literature closes it at n = 30. The axis is unwinnable by measurement and the honest move is to say so rather than run a lever that cannot produce a distinguishable claim.

*Cost.* ~0.25M (30 × 4 × 5,327 tok/item measured from `aime_open_baseline_seed42`, plus the 2025 control). The cheap arm is priced honestly at **73k tok/item for flash-with-thinking — flash is NOT the cheap option on math** and must never be scheduled as one; if run it adds ~0.5M.
*Build.* Small-build.

**Conditional, unfunded: SC@N with margin escalation (M1).** The built `solve_selfconsistency_math` (grade-equivalence clustering, cluster-margin dial at threshold 2, F4 adaptive early-stop verified offline to stop at sample 6 not 5). Two resolutions forced by review:

- **The conflicting instruction.** One cluster says "do not run this on MATH-500/AIME as built"; another schedules it on AIME-2026. **Resolution: the blanket verdict stands for MATH-500 and AIME-2024/25; it is superseded only for AIME-2026, and only because that surface is genuinely unmeasured — and only if M0's dual condition fires, at the flagship tier.** The proposed SuperGPQA re-target is deleted; it is a third competing use of the same code.
- **The bar and kill were simultaneously satisfiable at the most likely outcome.** Bar included "a tie at ≤ 50% of flagship tokens"; kill was "net ≤ 0". A tie satisfies both, and under kill-dominates the cost win the lever itself calls likeliest was pre-registered to be killed. **Split into two mutually exclusive pre-registered claims, named before the run.** *Accuracy claim:* bar net ≥ +5 items with McNemar p < 0.05, kill net < 0. *Cost claim:* bar net ≥ −1 (inside the noise band) at ≤ 50% of flagship tokens, kill net < −1 or tokens > 50%.
- *Third kill, retained.* Escalation rate = 0%. A third measured instance of the inert-tribunal mode on math permanently closes SC-with-escalation for this domain, leaving plain SC@N voting as the only surviving form.

**Dropped.** CAS tiebreak on AIME (answers are bare integers — the answer is not checkable, only a back-substitutable intermediate relation is, and the 53%/87% checkability figures are the regex heuristic's ceiling; expected coverage on competition math is low, recorded so it is not re-derived as promising). All MATH-500 and GSM8K spend. All AIME-2024/25 spend.

**Axis subtotal:** ~0.25M.

---

### 3.4 Coding

**Verdict: NOT WINNABLE BY ORCHESTRATION. No spend this window.**

**SWE-Bench Pro is blocked twice over, independently.** (1) Architectural: it needs the SWE-agent scaffold plus per-repo Docker evaluation environments with fail-to-pass/pass-to-pass tests, none of which exists here — rated multi-day to multi-week. (2) Capability: frontier is 59.1% on Scale's standardized public split and up to 80.3% in vendor aggregates, against a base model roughly 50 points behind. **Fixing (1) does not touch (2).** Our best validated orchestration lift anywhere is +4.1pp; the only published work on this technique class caps at +8–12pp. Orchestration is off by 4–6x.

**One honest correction to our own story.** The coding result on the record — QuorumQAAgent hardening taking Terminal-Bench **graded coverage** from 36% to 86% on a seed-7 sample — is a *harness* result for a **single non-deliberating agent**, not evidence that deliberation helps on code. It measures how many attempts survived to be graded, not how many were correct. It must never be quoted as an orchestration win, and the seed-7 sample it was tuned on must never be used as an evaluation set (see §3.5).

**Consequence.** There is no separate coding axis this window. The one place where code-shaped work has a measurable, verifiable arbiter is the agentic loop, and it is funded there — see §3.5. A deliberating code tribunal is explicitly *not* proposed: our measured failure taxonomy is dominated by timeouts, stalls and premature-done, not by bad candidate solutions, and the propose-run-observe loop already has a non-fallible arbiter in the sandbox.

**Axis subtotal:** 0M.

---

### 3.5 Agentic tool use

**Verdict: WINNABLE AS RELATIVE LIFT ONLY.** Never as an absolute number, and every writeup must say so in the same breath.

**The gap that cannot be closed.** Terminal-Bench 2.1 leaderboard-reported (tbench.ai / Artificial Analysis, 2026-07-21, not independently verified by us): GPT-5.6 Sol Ultra 91.9%, GPT-5.6 Sol 88.8%, Kimi K3 88.3%. Our hardened QuorumQAAgent measures 37.5% (9/24 graded). That is a ~50-point base-model gap against a max orchestration lift of +4.1pp in our record.

**The gap that can be claimed.** This is the one cluster where the ceiling that caps every QA lever disappears. Our binding constraint everywhere else is escalation **coverage** — 61.6% of wrong rows unanimous, qwen38_judge proving a better judge never sees them. In an agentic setting there is no answer to be unanimous *about*: three independent 30-turn trajectories in an open action space essentially never coincide, so coverage is ~100% by construction and the constraint relocates to **selection**, which is exactly where an execution-graded benchmark hands us a **non-fallible arbiter** for the first time in this project. That is Class A, and it is real.

**Four fatal defects in the proposed plan, all repaired below.**

1. **Cost.** ~11M for A0 alone is 25% of the measured weekly quota, on a self-described ESTIMATE with no surviving agent-run token log. A second 11M run (method-prior rollouts) would take the cluster to 50%.
2. **Survivorship.** pass@1 = 9/24 is computed "at ~86% grading coverage" — the denominator already excludes tasks that died before grading — and no rule was pre-registered for scoring an ungraded *attempt* inside pass@3. Under "any-attempt-solves", k=3 gives three independent chances to survive to grading at all, so the oracle gap is inflated by **grading survival, not solution diversity**. This is the same drop-conditioning class the F2 review already ruled fatal for qwen38_panel and the AIME baseline.
3. **Tuned-on evaluation.** The frozen 24-task sample pools two 14-task samples, one of them the **seed-7 sample the agent hardening was developed against** (36% → 86%). Using it as the frozen evaluation set for pass@1, pass@3, the self-check gate, the stall detector and the doubt trigger is evaluating on tuned-on data.
4. **A miscategorised kill.** A0's kill was declared to cancel A1a unrun. That is a category error: A0 bounds **selection** levers; A1a is a **coverage** lever operating inside a single rollout whose target is pass@1 itself. A zero oracle gap makes single-rollout improvements *more* valuable, not less.

**Funded plan.**

| # | Item | Mechanism | Bar | Kill (dominates) | Cost |
|---|---|---|---|---|---|
| **A0′** | Token calibration | 4 tasks, k=1, measure real tok/task | Replaces the ESTIMATE with a measurement | If measured cost > 1.5x the derivation, the 12-task sample is permanent and 24 is never scheduled | ~0.5M |
| **A0** | Oracle gap, **fresh sample** | 12 tasks drawn from the **65 unused** Terminal-Bench 2.1 tasks (the 24 become a development set, labelled as such); `harbor run -k 3`; the three rollouts carry **method priors from the start** (explore-first / minimal-diff / test-first), so one run measures both temperature-only and method-prior diversity; **ungraded = FAIL pre-registered for both pass@1 and pass@3**; grading coverage logged per attempt; gap reported **twice** (ungraded-as-fail and graded-only) so bias direction is visible | Oracle gap ≥ 3 tasks, reported as a paired discordant count with an exact binomial | Gap = 0 → selection levers dead by construction; written up as a first-class negative beside score-gating and qwen38_panel. **Gap 1–3 → INCONCLUSIVE: cluster DEFERRED, not killed** | ~5.5M |
| **A1a** | Self-check gate | `NextAction` gains a required `acceptance_check` (shell command + expected observable) whenever `done=true`; the loop refuses the first `done`, executes the check via `environment.exec`, feeds stdout/stderr/rc back as an observation, allows ≤ 5 repair turns inside the existing 30-turn cap. **Independent of A0's kill** | Net ≥ +3 tasks over same-sample pass@1 at ≤ 1.25x tokens | **Discrimination test, replacing the rubber-stamp threshold:** first-attempt check-pass rate on verifier-SOLVED vs verifier-FAILED tasks must be ≥ 1.5:1. A flat ">85% pass" threshold measures the expected value of the quantity, not a red flag, and would kill a working lever | ~0.6M (rides a k=1 pass) |

**Conditional, unfunded.**
- **A1b cross-verification (N×N).** Restore each candidate's artifact into a fresh container, run all N acceptance checks, exclude a rollout's own check from its own score (a structural control for self-preference). Runs **only if A0's gap ≥ 5**. Its bar must be stated **purely as a fraction of the measured gap (≥ 60%)** — the proposed "≥ 60% AND net ≥ +3 tasks" is unsatisfiable at the minimum authorised gap of 3, where it demands a perfect selector. Must ride A0's artifacts (~0.5M); ~11M standalone, which is why it is never scheduled independently.
- **A2 stall restart.** Detect 3 consecutive identical commands or nonzero/TIMEOUT returns with no new state evidence; one flagship call distils what was attempted and ruled out; restart with that summary; at most one restart inside the unchanged 30-turn cap. Economics run the right way (transcript reset makes remaining turns cheaper). **Citation flag:** the supporting result (arXiv 2604.16529, RTV+PDR, Claude-4.5-Opus 46.9 → 59.1 on Terminal-Bench v2.0; RTV alone +8–12pp) **is not on this session's verified-research list** and must be marked UNCONFIRMED until the primary source, arXiv id, benchmark version and both numbers are checked. The +8–12pp figure is removed as a stated comparator from A1b until then. ~1.5M.
- **A4 doubt trigger.** Escalate to N=3 only on execution facts — `done` reached with no goal-related command transitioning nonzero → zero; ≥ 2 TIMEOUT/ERROR observations; turn count within 3 of the cap; A1a needed repair turns. Deliberately built from execution facts, never from anything the model says about its own confidence (W5 AUC 0.625; the reflection-token null externally confirmed). **Must be fitted and scored under leave-one-task-out**, or with thresholds pre-registered before inspecting A0's rewards — four binary features on ~12 data points will look good in-sample by construction, which is exactly why F3's in-sample-looking upgrade was negative out of sample. Report in-sample and held-out separately; gate any paid run on the held-out number only. ~0M to fit.

**Dropped.** Method-prior rollouts as a separate ~11M line item — folded into A0's rollout definitions. Step-level review of every proposed action — our failure taxonomy is timeouts, stalls and premature-done, not destructive commands, so a per-turn reviewer guards a failure mode we have not observed. Subgoal-decomposition-with-acceptance-commands as a separate large-build — it is A1a's construction at 4x the cost with a weaker kill; build A1a only, and if it clears, subgoal-boundary deliberation becomes a follow-on with a measured base rate.

**Axis subtotal:** ~6.6M.

---

### 3.6 Medicine

**Verdict: MedQA is CLOSED (cost-only). MedXpertQA is UNPROVEN — screen only, and the build is larger than advertised.**

**MedQA is permanently closed as an accuracy axis.** Flagship 94%, engine ties (+2 = one question of 50), unanimous-wrong 4%. The cheap tier is already competent, so by the central law deliberation has no target. It remains a genuine **cost** story — flagship-level accuracy at cheap-tier price — and nothing else. No future medical accuracy claim may be sourced from MedQA.

**MedXpertQA-Text is the correct substitute, and the case for it is structural.** TsinghuaC3I/MedXpertQA, MIT, ungated, 2,450 test items, structured 10-option MC with a clean single-letter label — which avoids the free-text-option parsing that killed the HLE loader. Published Text-subset scores put the frontier at o1 44.67%, DeepSeek-R1 37.76%, o3-mini 37.30%, GPT-4o 30.37%, Claude-3.5-Sonnet 21.31%. Two structural arguments: the headroom is the largest of any benchmark we can actually reach, and **10 options drop chance-agreement from 25% to 10%**, which mechanically converts correlated-lens coincidence into escalation-visible disagreement — the ingredient qwen38_panel (0% escalation) and MATH-500 L5 (0% escalation) both lacked.

**Two corrections forced by review.**

1. **The A–J generalization is not "exactly 5 call sites".** Verified by grep: `ABCD` appears **34 times across 7 files** — `src/quorumqa/baseline.py` (2), `engine/judge.py` (2), `engine/skeptic.py` (1), `engine/solver.py` (2), `benchmark/qwen38_baseline.py` (2), `tests/test_lever_permuted_panel_offline.py` (3), and **`benchmark/lever_experiments.py` (22)**. That last file is where flagship_panel, chem_thinking_gate and rag_thinking_gate actually live — i.e. exactly the profiles a MedXpert panel run would use. Left unfixed, a 10-option item would be presented to those panels as four options with the gold answer possibly absent. Note also that the house pattern is currently the *opposite* of what this lever assumes: `load_supergpqa.py` **down-samples** native >4-option rows to 4. **Re-labelled medium-build**, and the byte-identical fingerprint-equivalence proof (the method that shipped MoO M0) must cover `lever_experiments.py`, not just the shipped engine.
2. **Seed contamination and an undefined decision band.** The screen was proposed at seed 42 — the most burned seed in the repo (50 files) — with the panel then reusing that same seed-42 baseline while claiming "3 fresh seeds". The go/no-go and a third of the validation would come from the same seed. And the GO/KILL pair left flagship 66–84% or unanimous-wrong 5–15% entirely undefined, which is where published Text scores of 20–45% make our own harness most likely to land.

**Funded lever: MedXpertQA gap screen (repriced to the standing protocol).**

*Mechanism.* Build `benchmark/load_medxpertqa.py` mirroring `load_mmlu_pro.py`'s discipline (options dict → `choices` ordered by key, `label` → `correct_letter`, `body_system` → `subject`). Run the standing 2-arm probe from §3.2 — 60 items flagship, 120 items cheap panel — on an **unburned seed**, excluded from any later validation seeds. Report flagship accuracy, cheap accuracy, unanimous-wrong rate, escalation rate.

| Flagship | Unanimous-wrong | Route |
|---|---|---|
| ≥ 85% | any | KILL — saturated; MedQA/MMLU-Pro repeat, medicine closed |
| any | ≤ 5% | KILL — cheap tier already competent; MedQA repeat |
| ≤ 65% | ≥ 15% | GO to a **1-seed** panel screen (not a 3-seed programme) |
| 66–84% or 5–15% | — | **DEFER — 1-seed screen only, no 3-seed commitment, no new build** |

*Additional kill.* If the A–J generalization fails its fingerprint-equivalence proof across all 6 files, the refactor has touched engine behaviour and the axis stops there — no number is quoted.

*Cost.* ~0.4M.
*Build.* Loader small; the A–J refactor is **medium-build** and is a prerequisite for any panel run, not for the screen.

**Unfunded, conditional on the screen.** flagship_panel and a thinking-gate-stacked arm on MedXpertQA-Text, targeting > 44.67% (o1) and beating our own paired flagship on the same items — with the external comparison reported as a **separate, clearly-caveated headline** (different sample of the 2,450-item split, our harness, our prompt), never as the validation bar. Bar: net ≥ +5 discordant with McNemar p < 0.05 at one seed, or +3 at 2 of 3 with pooled McNemar. Kills: escalation < 15% at 2 of 3 seeds (homogeneity trap); net ≤ 0 at 2 of 3; and an honesty kill — if two disjoint n=150 samples' flagship baselines differ by more than 8pt, the sample is unrepresentative and no external comparison is made at all. ~6M.

**Dropped this window.** The RAG rider on the existing STEM corpus — it is a P3 whose entire value is testing whether a field-of-science Wikipedia subset happens to cover medicine, and it cannot be scheduled before the axis has a measured gap. Recorded, not funded.

**Axis subtotal:** ~0.4M.

---

**Running total for §3.1–3.6:** ~10.8M base + ~5.0M conditional (D4's single-seed screen) ≈ **15.8M**, against a funded envelope of ≤ 35M with a 20% reserve intact. Roughly 45% of the funded envelope for six axes, leaving room for §3.7–3.12 — which is the intended shape, because five of those six axes are gated on a probe or a port rather than ready to spend.

---

### 3.7 Law (LEXam)

**Verdict: NOT winnable by orchestration in this quota window. Law routes permanently to a single flagship call until a flagship-tier gap probe says otherwise.**

**What the record actually says.** The headline "-14 on law" describes the *cheap* engine, and that framing was too crude — but the correction does not rescue the axis. Re-scoring `benchmark/results/lever_thinking_gate_lexam_seed42.jsonl` against `benchmark/results/lexam_pilot_seed42.jsonl` on the identical 50 items gives thinking_gate 80.0% vs single-flagship 86.0%, a paired split of 5 flagship-only / 2 gate-only — **net −3 items**. That is not "inside the noise floor": ±2.5pt is our *n=90* floor, and at n=50 the honest statement is that we have exactly one paired deliberation-vs-flagship measurement on law and **it lost**. Add F2 (a bare single flagship call Pareto-dominates every lever ever logged on LEXam), RAG moving nothing (+2.2, noise), and 2/30 retrievals on-topic, and the axis has no positive evidence at any tier.

**DROPPED (fatal):**
- **`lexam_flagship_panel` — dropped.** 2.4M screen / 7.2M full (16% of quota) on the one surface where every paired measurement is negative and F2 already shows single-call dominance. Its predictor was also read off the wrong tier: the 15.6% unanimous-wrong (14/90, `lever_control_lexam_seed42.jsonl`) is the **cheap** panel's rate, but flagship_panel *replaces* the cheap seats — three qwen3.7-max seats' unanimous-wrong rate on LEXam is unmeasured. And the S4 dominance gate proposed in the same portfolio would block this run.
- **`swiss_law_corpus` paid run — dropped.** It was gated on `lexam_flagship_panel` (now dropped), and its load-bearing premise — that the 207 English acts in `rcds/swiss_legislation` are the Fedlex translations of the Constitution / Civil Code / Code of Obligations / Criminal Code — is an *unverified inference*, not a measurement. The largest headroom in LEXam is on German-language Swiss-law items (de 1,036 vs en 619), which 207 English documents structurally cannot reach.

**What survives — one FREE check and one conditional probe.**

| | Lever | Cost | Build |
|---|---|---|---|
| LAW-0 | **Swiss corpus title dump.** List the 207 English `rcds/swiss_legislation` titles and compute topic overlap against LEXam's English `mcq_4` items. Zero API calls. This either resurrects the corpus arm or kills it before a single token is spent. | **0 tokens** | small-build |
| LAW-1 *(conditional on LAW-0 showing real overlap)* | **Flagship-tier gap probe**, R6 protocol: 60 LEXam English items, arm A = single qwen3.7-max, arm B = 3 **flagship** seats with no tribunal. Measures the *flagship-tier* unanimous-wrong rate — the number every law lever was mis-priced against. | **~0.4M** | already-built |

**Benchmark target with the number to beat:** LEXam `mcq_4`, English subset — our own paired qwen3.7-max single call, **86.0% at seed 42, n=50**. The external LEXam leaderboard figure (Gemini-2.5-Pro / Claude-3.7-Sonnet are named as leaders in arXiv 2505.12864) is **UNVERIFIED in-session — the abstract page carries no results table**. It must be pulled from the paper's MCQ table and pre-registered before any external comparison is made, or the external comparison is not made at all.

**Pre-registered bar:** LAW-0 must show ≥30% topical overlap between the 207 English acts and LEXam English item subjects before LAW-1 is funded. LAW-1 reopens the axis only if flagship-tier unanimous-wrong ≥15% at n=60.

**Kill (dominates):** flagship-tier unanimous-wrong <15% → **law is recorded permanently as a single-call surface**, the Swiss corpus is never built, and no further law tokens are spent. Independent kill: LAW-0 overlap thin → the English arm is dead before the index exists, and the multilingual (BGE-M3) arm is re-classified from "nearly drop-in" to an infrastructure project, not a lever.

**Structural note for the record:** a beat-the-flagship claim on law is not demonstrable at n≤90 regardless of lever. On the n=50 seed-42 sample only 7/50 items were flagship-wrong — the entire addressable pool. Any delta at that n is a 2-3 item swing. This retroactively explains why *both* the "−14" and the "+2.2" LEXam numbers on our record were over-interpreted.

---

### 3.8 Calibration

**Verdict: NOT an accuracy axis — measured and closed. It survives in exactly two honest forms: a zero-token comparative capability claim, and one untried feature family that must first be re-derived because its headline statistic is an artifact.**

**Why the accuracy framing is closed:** W5's leave-one-benchmark-out median AUC is **0.625 (BAND)** over 5,597 rows; F3's distribution-feature upgrade was **negative (dAUC −0.026)**; 61.6% of wrong rows are unanimous, which agreement features structurally cannot see; and the external record independently refutes reflection-token features (Sea AI Lab — "wait" tokens do not track correctness). Re-engineering features over the same logged quantities is exhausted.

**FATAL CORRECTION APPLIED — the 6.2x instability lift is mostly definitional.** The offline audit reports P(wrong|stable) = 6.2% vs P(wrong|unstable) = 38.5% on n=77 pooled GPQA items (n_unstable = 13). But an item is "unstable" *iff* its K=3 replicate answers disagree, and if they disagree at most one distinct answer can be correct — so the **run-level** wrongness rate among unstable item-runs has a hard mechanical floor of 33.3% (A,A,B with A correct) rising to 66.7% for any other split. The measured 38.5% sits **5.2pt above a floor that is guaranteed by the definition**. Meanwhile stable items are all-right-or-all-wrong by construction, so P(wrong|stable) is free to be tiny. Consequences: the "lift ≥3x" bar is satisfied by construction on any surface above ~80% baseline accuracy, and the "lift <2x" kill can essentially never fire. **Any lever resting on the 6.2x prior loses that prior until it is re-derived correctly.**

**DROPPED / RESTRUCTURED:**
- **`instability_calibration_rider`'s "P0, 0 tokens" label — dropped.** Part (A), the permutation-flip features, requires a `permuted_panel` run joined to a matched-seed control. W2 permuted_panel is **built but not yet run**, so those logs do not exist. Zero *marginal* cost on a run that is itself paid is not zero cost. Only part (B) is genuinely free.
- **`L7` and `selective_abstention_riskcoverage` — merged.** Same mechanism, same benchmarks, same motivating findings, two different comparators and two different thresholds. Whichever shipped first would have retroactively set the bar. One deliverable, one comparator.

**The two surviving levers:**

| | Lever | Cost | Build |
|---|---|---|---|
| CAL-1 *(FREE, run now)* | **Confidence head-to-head + risk-coverage, as one deliverable.** On the existing 5,597 rows under W5's unchanged LOBO protocol: AUC of panel agreement alone vs AUC of single-seat verbalized confidence alone, within-benchmark; then risk-coverage curves and AURC ordered by the panel signal, against the single-flagship verbalized-confidence curve on the **same items**. Report accuracy@90/80/70% coverage. | **0 tokens** offline + **~0.3M** for the one flagship verbalized-confidence baseline pass | small-build |
| CAL-2 *(rider on W2, NOT free)* | **Permutation-flip features, correctly scored.** Join W2 permuted_panel to its matched-seed control by `question_id`; derive `n_seats_flipped`, `any_flip`, `flip_rate`, `flipped_while_panel_unanimous`. **Score at the ITEM level** using the text-majority-over-replicates answer (removes the mechanical floor), and report the lift against a **permutation null** that preserves each item's replicate-answer multiset while shuffling correctness. Refit W5's predictor under LOBO and report AUC on the **unanimous-only** subpopulation — the first direct measurement of P(wrong \| unanimous). | 0 marginal, **conditional on W2 being funded** | small-build |

**Benchmark targets with numbers to beat:**
- CAL-1: the panel curve must sit at or above the single-flagship verbalized-confidence curve at 90%, 80% and 70% coverage on ≥2 surfaces (GPQA-Diamond, SuperGPQA-hard). This is the *comparative* claim, and it is the only one our evidence supports — a single call cannot produce a sample-based confidence at all, because there is only one sample.
- CAL-2: W5's own unchanged bar — median LOBO AUC **≥0.70** (from 0.625) — or unanimous-only AUC **≥0.65**.

**Pre-registered bar:** CAL-1 — 6 of 6 coverage comparisons non-negative with ≥4 clearly positive (bootstrap CI excluding the flagship curve), reported alongside accuracy@80% coverage. CAL-2 — item-level lift ≥2x **against the permutation null**, not against the raw 6.2x.

**Kill (dominates):** CAL-1 — verbalized confidence alone matches or beats the panel curve → the multi-agent confidence signal adds nothing; drop the capability claim entirely *and* record that the same finding invalidates the trust story the escalation architecture rests on. CAL-2 — item-level lift <2x against the null → **record permanently that instability features do not separate either**, close calibration-as-a-gate for good, and keep calibration only as a cost-router input (its one validated role: MoO matches flagship accuracy within noise at 28-50% lower cost on easy-skewed traffic).

---

### 3.9 Long context

**Verdict: UNRESOLVED, and the honest move is to resolve it for 0.2M rather than fund an 8-14M lever against an unmeasured baseline. Everything except the transport pre-flight is cut this window.**

**DROPPED:**
- **`longctx_mapreduce` — dropped this window.** Self-costed at 24M (55% of quota), scoped down to 8-14M (18-32%). Large-build, no measured baseline, and its only external prior is labelled UNCONFIRMED by its own author with an instruction not to cite it. Worse, its **control arm may not be executable**: `QwenClient.chat` posts one non-streaming request with `max_tokens: int = 1024` (qwen_client.py:96) and `timeout=300` (qwen_client.py:160), and nothing in the repo has exercised it near any context limit. The lever concedes this in its own kill (c) and then downgrades the outcome to "a capability claim" — a capability claim is not a benchmark win and does not justify a fifth of the week.
- **`longctx_degradation_screen` as specced — dropped.** ~40 items across three task families is ~13 items/family. The bar (≥10pt drop 4K→64K on one family) is **1.3 items**; the kill (<5pt on all three) is **0.65 items**. At n=13 the paired band is roughly ±14pt, so both thresholds are inside noise, the 5-10pt band is undefined, and the depth sweep splits each cell to 2-3 items. As designed it would authorize or kill an 8-14M lever on a one-item difference.

**What survives:**

| | Lever | Cost | Build |
|---|---|---|---|
| LC-0 | **Transport pre-flight.** One 64K and one 128K single call through the actual Token Plan endpoint. Record: accepted / rejected / timed out, the observed input cap, and the billed input tokens. Nothing else. | **~0.2M** | small-build |

**Benchmark target:** none, and deliberately so. LC-0 produces a **hard constraint**, not an accuracy number: the maximum context length at which any long-context claim of ours is even meaningful.

**Pre-registered bar:** a committed one-page record stating the observed cap with live evidence, in the format `hle_feasibility.md` uses — what is measured, what is unmeasured, which ground is decisive.

**Kill (dominates):** the transport caps below 64K → **the long-context axis closes for ~0.2M**, re-scoping every long-context statement we would ever make, instead of discovering it after a 3.6-4M screen. If the cap is ≥64K, the *rescoped* screen (40 items **per family**, n=120, two lengths, no depth sweep) becomes a candidate for a future week — it is explicitly **not funded now**.

**Recorded in advance, so it is not re-derived later:** even a successful map-reduce lever cannot claim general long-context reasoning. If a fact in chunk 3 must be combined with a fact in chunk 17, no map agent sees both; the targeted re-read mitigates but does not solve it. That is the honest boundary of the win and it is pre-registered as the kill, not discovered as a caveat.

---

### 3.10 Multimodal

**Verdict: NOT winnable by orchestration. This is an architectural project and the worst available use of the quota. One <10k-token feasibility GET is the entire funded scope.**

**Measured state:** zero matches for `image_url|qwen-vl|vision|multimodal` anywhere in `src/`; `GPQAItem` has no image field (`schemas.py:10` still documents `correct_letter: str  # "A" | "B" | "C" | "D"`); solver / skeptic / verifier / judge all call `chat_json(user=<str>)`. The **only** multimodal-ready layer is the transport — `qwen_client.chat` passes messages through untouched and already parses content blocks filtering `type=="text"`. Everything above it assumes text. And the gating fact is not knowable today: a read-only GET on the Token Plan `/v1/models` endpoint returned **429 Throttling.AllocationQuota** (resets 07-28 03:32 UTC), so VL availability is **unmeasured, not unfavorable**.

**DROPPED:**
- **`M1` perception-vote panel — dropped, converted to a design note.** ~9M for 3 seeds (21% of quota) on an "architectural" build for an axis with **no measured cheap-to-flagship gap on any vision surface** — which the lever itself concedes ("nothing here predicts value"). Its token estimate is self-labelled honestly uncertain and could move several-fold. A P3 line item consuming a fifth of the week is not a priority ranking; it is an unfunded aspiration parked where it can be picked up mid-week. **The idea is preserved, not the budget:** the naive "describe-then-reason" decomposition is *predicted-negative* by our own law — a single transcription makes every text solver inherit an identical wrong premise (perfectly correlated error → unanimous-wrong → tribunal idle), which is the qwen38_panel homogeneity trap (0% escalation) and the LEXam poisoned-input failure (2/30 on-topic) fused into one design. If vision is ever built, **voting must happen at the perception layer**, not after it.
- **`M2` mixed vision+text seat panel — already a committed rejection.** Seats with unequal evidence access give the tribunal no shared record to arbitrate on; Self-MoA (ICML 2025) says mixing loses unless models are near-equal quality *and* highly diverse; and we already reproduced that in-house — the original Heter-MAD mixed panel's weakest seat scored 54.1% against flash's 66-72% and was dropped for it (`config.py` `SOLVER_MODELS` comment).

**What survives:**

| | Lever | Cost | Build |
|---|---|---|---|
| MM-0 | **Feasibility gate.** After the reset: one GET on `{TOKEN_PLAN_BASE_URL}/v1/models`; if any `qwen-vl` / `qwen*-omni` id appears, 2-3 single-image probes with content blocks through the existing `qwen_client.chat()`. Record (1) does the id resolve, (2) does an image block 400/401/succeed, (3) **measured input tokens billed per image**. | **<10k tokens** (~0.02% of the week) | small-build |

**Benchmark target:** none. Binary outcome plus one measured cost number.

**Pre-registered bar:** a committed feasibility doc stating served VL ids (or none), whether image blocks are accepted, and the measured per-image input billing, with unknowns labelled unknown.

**Kill (dominates), with the token threshold re-specified:** (a) no VL model served on the Token Plan endpoint → **the multimodal axis closes permanently, in writing**; the only alternative is pay-as-you-go DashScope, which is real money and therefore a hard stop requiring Jun Kai's explicit approval, never an autonomous decision. (b) The original kill — "one image bills >2x a typical text item" — is **replaced**: at any current VL serving path an image bills on the order of 1,000+ input tokens against a few-hundred-token stem, so that threshold was pre-decided by arithmetic rather than measured. The correct kill is on the quantity that matters: **projected cost of a 90-item 3-seed vision study >20% of the weekly quota**, computed from the measured per-image billing. The 2x figure is reported as a diagnostic, not a gate.

**Stated plainly:** "beat frontier models on MMMU" is unachievable. Frontier MMMU is a base-VLM perception problem, and orchestration cannot close a perception gap in a model we do not have.

---

### 3.11 IFEval (instruction following)

**Verdict: The strongest *structural* case in the portfolio — and NOT fundable as written. Two independent fatals. It becomes a three-stage gated program whose paid stages are explicitly UNFUNDED this window.**

**Why the structural case is real.** Every negative result we have traces to one root cause: no oracle, therefore escalation *coverage* is the bottleneck (qwen38_judge — 9/9 overturns correct, zero net gain, because a better judge never sees the failures; 61.6% of wrong rows unanimous and structurally invisible to agreement features). On IFEval that root cause disappears: constraint compliance is decidable by a Python predicate, so detection coverage is 100% by construction, and the residual failures are the mechanical-counting kind an LLM provably cannot self-check ("at least 300 words", "no commas", "end with this exact phrase"). This does not violate the gap law — it **sidesteps its precondition**, because the trigger is a deterministic check rather than solver disagreement. External support is direct: verifiable/rule-based rewards are the field's one reliable arbiter across all frontier RL work.

**FATAL 1 — no gap probe.** The lever was scheduled P0 at 5-7M (12-16% of quota) with **zero measurement** of our own IFEval baseline. That is precisely the mistake the same portfolio's R6 lever declares mandatory to prevent. Published frontier strict-prompt sits ~85-92% (band **unverified in-session** — must be pulled from a primary model card before quoting); if qwen3.7-max sits there, the surface is in the MMLU-Pro saturation regime and the lever's two targets (≥90% absolute **and** ≥+5pt over our single call) are jointly near-infeasible by arithmetic. A plan cannot make gap probes mandatory and exempt its own most expensive P0 from them.

**FATAL 2 — the grader does not exist in this repo.** Verified: **zero** matches for `ifeval|instruction_following|instruction_id` anywhere outside this roadmap document. No `benchmark/load_ifeval.py`, no scorer module, and `requirements.txt` carries none of its dependencies. Every one of the nine existing surfaces has a committed `benchmark/load_*.py`; IFEval has none. The primary metric **and both kill criteria** (extractor-recall audit against `instruction_id` metadata; loose-prompt scoring) come from a harness we do not possess.

**MAJOR 3 — the "held-out" verifier is not independent of the optimization target.** The ~20 predicate types are drawn from IFEval's own instruction families, so the repair loop optimizes against a reimplementation of the grader. The design controls for *label* leakage ("the extractor reads ONLY the prompt text") but not for **vocabulary** leakage: the predicate vocabulary *is* the metadata taxonomy.

**The restructured program:**

| Stage | Content | Cost | Status |
|---|---|---|---|
| **IF-1** *(FREE, buildable now)* | Port and pin the official IFEval scorer + a `load_ifeval.py`; **validate it reproduces a published strict-prompt number on a public reference output** before any paid generation. Hold out ~1/3 of instruction types from the predicate vocabulary and **pre-register which**. | **0 tokens** | medium-build |
| **IF-2** *(PAID, gate)* | R6 protocol: 60 prompts, single qwen3.7-max call, measure strict-prompt accuracy **and** the violation rate the deterministic checker can actually see. | **~0.1M** | small-build |
| **IF-3** *(PAID, UNFUNDED this window)* | The generate → extract → check → repair loop, plus the all-flash `ifeval_cheap_tier_arm` rider (~0.4-0.6M). | **~5-7M** | medium-build |

**Benchmark target with the number to beat:** IFEval **strict-prompt** on the full 541-prompt set, against **our own matched-seed qwen3.7-max single call on the same prompts** (house rule: never a published number as the bar). Absolute stretch ≥90% strict-prompt; the *headline* metric is the held-out-constraint-type subset, with the full-vocabulary number reported as the in-domain ceiling.

**Pre-registered bar (IF-3, if it is ever funded):** 3 seeds, paired same-prompt — mean ≥+3.0pt strict-prompt, **positive on all 3 seeds**, net discordant ≥+20 with **pooled McNemar p<0.05**, and the held-out-constraint-type lift reported separately as the claim. Strict-instruction reported alongside strict-prompt.

**Kill (dominates):**
1. **IF-1 fails to reproduce a published number** → we have no trustworthy grader, no number is quotable from this surface at all, and the program stops. This kill fires *before* any token is spent.
2. **IF-2 returns single-call strict-prompt ≥90%** → record IFEval as the **fourth measured saturation null** beside MMLU-Pro, MATH-500 and MedQA, and drop the axis.
3. Extractor recall <70% on the post-hoc `instruction_id` audit (we cannot see the constraints, so the mechanism is fictional).
4. The repair loop **lowers** strict-prompt accuracy on any seed (the emit-best-candidate logic is broken).
5. The win exists on strict-prompt but **vanishes on loose-prompt** → we are gaming formatting tolerance, not following instructions. Record as a null; do not ship the claim.

**The cheap-tier arm is the real prize and should be stated as such:** if flash generation + deterministic repair ties or beats a bare flagship call at strictly fewer tokens, that is the cleanest demonstration of the project's thesis any benchmark can produce — and the exact mirror of our best-established null. qwen38_panel and qwen38_judge showed that adding model *strength* to an architecture with no detection coverage buys nothing; the deterministic-oracle case predicts the opposite, that **architecture substitutes for strength**. It also finally clears the F2 compute frontier, because a tie at lower cost is a win there.

---

### 3.12 Factuality (SimpleQA-Verified)

**Verdict: WINNABLE against our own flagship, and the structurally cleanest fit we have. NOT promisable against the published SOTA — that ceiling is arithmetic, not engineering, and must be measured before the run rather than explained away after it.**

**Why the architecture fits by construction.** On free-form short-answer the wrong-answer space is unbounded, so two hallucinating seats essentially never coincide: unanimity becomes a near-sufficient correctness signal and nearly every error surfaces as a split an abstention gate can catch. That is the exact inverse of MC, where 4 options manufacture agreement by chance and produce the 61.6%-of-wrong-rows-are-unanimous ceiling W5 measured. It is also the first surface on which **P(wrong \| unanimous)** — flagged UNMEASURED in W5 — can be measured directly. And the scoring function rewards the behaviour the tribunal already produces: F1 = harmonic mean of accuracy and correct-given-attempted, so a calibrated abstention raises the second term without new knowledge. External corroboration for aggregation over high-entropy outputs: DeepSeek R1-Zero's cons@64 (AIME 71.0 → 86.7).

**The hard ceiling, stated before the run.** Abstention *reallocates* knowledge; it cannot create it. F1 ≤ **2k/(1+k)** where k is the fraction of facts the base model actually knows. Beating Gemini 2.5 Pro's **55.6 F1** therefore requires qwen3.7-max's parametric k ≥ **~38%**, and k is unmeasured. If the probe returns k<38%, **the frontier-topping claim is dropped before the run**, not defended after it.

**CRITIQUE APPLIED — the missing comparator.** As originally specced, our arm gets a new ABSTAIN terminal state while the single-flagship comparator does not. Any F1 gain would then be attributable to *being permitted to abstain*, not to deliberation — and the bar's mechanistic clause does not fix this, because a single call permitted to say "I don't know" moves the same two numbers. **Three arms, not two.**

**Build honesty.** This is not an extension of the shipped engine; it **forks a second engine path**. `schemas.py` defines `final_letter: str` as required on both `JudgeVerdict` (line 36) and `QuestionResult` (line 59) with no abstain sentinel, and every engine module formats choices with `zip("ABCD", …)`. `math_open_engine.py` gives a real head start, which is why this is medium-build rather than large — but the claim "small change" would be false. **Loader gotcha, verified live:** the `answer` column is double-encoded UTF-8 ("JÃ³hanna SigurÃ°ardÃ³ttir" where "Jóhanna Sigurðardóttir" belongs) — normalize on load or every accented gold answer silently fails grading. The `urls` column is **never** read into any index (§4 firewall).

**The levers:**

| | Lever | Arms | Cost | Build |
|---|---|---|---|---|
| FA-0 | **k-probe + comparator baseline** (1 seed, n=300): arm (i) single flagship, no abstain; arm (ii) single flagship, **abstain-permitted** under the identical official grader. Arm (ii) is the real comparator for every downstream F1 claim; arm (i) is the reference. | 2 | **~0.5M** | medium-build |
| FA-1 | **`simpleqa_abstain`**: 3 solvers emit `{answer, confidence}`; cluster by normalized string equivalence; unanimous → emit; split → **ABSTAIN** (arm A) or escalate to flagship judge (arm B). Official CORRECT / INCORRECT / NOT_ATTEMPTED grader on qwen3.7-max, run identically on every arm. 3 seeds. | 2 | **~4.5M** | medium-build |
| FA-2 | **`factuality_verified_gate`** (within-run rider on FA-1's seeds): W1-A flaw-finder on unanimous answers — one flagship pass interrogating the specific claim ("is this the right person / date / number for this question, and what would make it wrong?"); flagged answers demoted to escalation or abstention. Pre-gate votes logged so the control path is byte-identical. | 1 | **~1.5M** | small-build |

**Benchmark target with the number to beat:** SimpleQA-Verified F1 (`google/simpleqa-verified`, MIT, 1,000 items, `eval` split) — **F1 > FA-0 arm (ii)**, the abstain-permitted single-flagship F1 on the same items. Stretch/headline **F1 > 55.6** (Gemini 2.5 Pro), gated on k ≥ ~38% and reported with the harness/prompt caveat.

**Pre-registered bar:** F1 **+5 over FA-0 arm (ii)** at 3 seeds, with the gain mechanistically attributable — correct-given-attempted must **rise** while attempt rate stays ≥50%; plus net discordant ≥+5 with pooled McNemar p<0.05. A gain produced by abstaining on everything is not a gain. FA-2's own bar: net ≥+3 discordant **on the unanimous subset alone**, paired within-run, at 3 seeds, with demotions scored separately for correct-demotion vs false alarm.

**Kill (dominates):**
1. **Unanimous-and-wrong >20% of unanimous items** → agreement is not a correctness signal even in an unbounded answer space; that **falsifies the entire structural argument** for this axis and the abstention gate with it.
2. F1 rises while raw correct-count falls by >10 points → the system is buying score with silence; not reported as a win.
3. **k < 38%** → the frontier claim is dropped *before* the run (honesty gate, not a kill of the lever).
4. FA-2, re-specified: the original kill mixed a rate ("false-alarm >30%") with a count comparison ("demotes more correct than wrong") — at a ~90%-correct unanimous base rate those fire at completely different points, leaving the analyst to choose after seeing the data. **Replaced by one decidable ratio: kill if correct-demotions / wrong-demotions ≥ 3:1** (mirrors W1's precision kill).
5. FA-2 also dies if FA-1 measures the unanimous-wrong pool at <5% of items — nothing to catch, pure cost.

---

## 4. The ranked roadmap

**Constraints this table respects:** quota measured at **~43.8M tokens/week**, exhausted until **2026-07-28 03:32 UTC**; funded set capped at **≤35.0M** (43.8M minus the 20% reserve the ledger pre-registers as mandatory); the already-built, offline-tested **W1-W6 shelf (suite 473 green)** is referenced, not re-planned; everything below the line is marked **UNFUNDED**, not "P1 later".

**Governance fix applied before anything else.** The portfolio as submitted was priced at roughly **2.5-3x** the quota (P0 minima alone ≈ 36.8M = 84% of the week; full portfolio >100M). Two P0 governance levers also cancelled each other: **S1**'s allowlist assertion (paid tokens only on GPQA-Diamond / SuperGPQA-hard / chem) would have blocked six other P0 levers, and its re-entry rule (≥15% unanimous-wrong **in existing logs**) is structurally unreachable for any surface with no logs — making **R6**'s gap-probe protocol unrunnable. **Resolution: S1 ships as a spend cap plus an exploration lane, not a runner assertion** — ≥60% of paid tokens on validated surfaces, and a surface is admitted the moment an R6 probe clears. **S4 ships in WARN mode** with logged would-have-blocked decisions and an explicit exemption for (benchmark, lever) pairs with zero logged rows, because a hard block can never generate the counterfactual its own kill requires.

### FREE — executable now, during the quota block

| # | Item | Axis | What it decides | Tokens | Cum. paid | Build |
|---|---|---|---|---|---|---|
| F1 | **Stability audit, repaired**: re-key on choice TEXT (`load_gpqa/_shuffle_choices` reshuffles per seed), score at **item level** via text-majority, report lift vs a **permutation null** preserving each item's replicate-answer multiset | reasoning / calibration | Whether the instability signal survives its own mechanical floor; gates every stability lever and CAL-2 | 0 | — | small |
| F2 | **Council Gate-1**: de-inflated cross-config union keyed on choice text, pre-registered repeat-selection rule (lowest seed), contingency table, plus the coverage-selected set's baseline vs full-GPQA baseline so selection bias is visible | reasoning | Whether the ~7pt GPQA union is structure or seed-luck; gates the entire council lever | 0 | — | small |
| F3 | **Ledger + governance rewrite**: rank every lever by (measured-gap evidence / token cost), draw the line at 35.0M, name the CUT set; S1→spend-cap, S4→WARN mode | scope | Prevents the audited week's failure mode repeating by default | 0 | — | small |
| F4 | **Bar restatement**: every bar re-expressed as net-discordant with McNemar. Net +3 at one seed is p=0.125 best-case (b=3,c=0) and p=0.508 at b=6,c=3; **minimum clearing p<0.05 one-sided with zero losses is +5** | all | Stops seven levers from being pre-registered to declare success on evidence their own analysis plan rejects | 0 | — | small |
| F5 | **CAL-1 offline half**: panel-agreement AUC vs verbalized-confidence AUC on the 5,597 rows under LOBO | calibration | Whether our confidence signal is comparatively better at all | 0 | — | small |
| F6 | **IF-1**: port + pin the official IFEval scorer and loader; reproduce a published strict-prompt number on a public reference output; pre-register the held-out constraint-type split | IFEval | Whether IFEval is gradeable here at all | 0 | — | medium |
| F7 | **A-J option generalization**: ~28 call sites across 6 files **including `lever_experiments.py`** (where flagship_panel / chem_thinking_gate / rag_thinking_gate actually live), with byte-identical full-call-fingerprint proof on all 4-choice items | medicine | Unblocks any >4-option surface without touching frozen behaviour | 0 | — | medium |
| F8 | **SimpleQA build**: loader (double-encoded-UTF-8 fix), free-text panel path, ABSTAIN terminal state, official grader prompt | factuality | Makes FA-0/FA-1 runnable at the reset | 0 | — | medium |
| F9 | **LAW-0**: dump the 207 English `rcds/swiss_legislation` titles, overlap against LEXam English items | law | Kills or resurrects the corpus arm for zero tokens | 0 | — | small |
| F10 | **Null-harvest writeup (S5)**: homogeneity trap, coverage-not-judge-quality, saturation-kills-deliberation, LEXam corpus diagnosis, score-gating (0.0288 vs 0.0290), AUC-0.625 band, F2 dominance frontier — every claim traced to a committed result file | output | The scarcest artifact we own: no frontier lab publishes on multi-agent ensembling, so there are no published nulls to compete with | 0 | — | small |

### PAID — after 2026-07-28 03:32 UTC, ordered by information per token

| # | Item | Axis | Tokens | Cum. | Build | Gate |
|---|---|---|---|---|---|---|
| P1 | **R0 — repair the GPQA family-best bar.** Re-invoke `qwen38_baseline.py` against its existing output using its **built-in resume** (`done_ids`, line 115) with paced backoff — *not* `retry_dropped.py`, which builds its done-set from `["engine"]["item"]["question_id"]` and would KeyError on flat qwen38 rows. Publish repaired **and** survivor-only numbers together; report the 1-5-residual case as an interval with all-correct/all-wrong imputation bounds. Hard spend cap at 3x estimate. | reasoning | 0.4M | 0.4M | built | — |
| P2 | **MM-0** VL feasibility GET + image probes | multimodal | 0.01M | 0.41M | small | — |
| P3 | **LC-0** transport pre-flight at 64K/128K | long ctx | 0.2M | 0.61M | small | — |
| P4 | **IF-2** IFEval 60-prompt gap probe | IFEval | 0.1M | 0.71M | small | F6 |
| P5 | **FA-0** SimpleQA k-probe + abstain-permitted comparator baseline | factuality | 0.5M | 1.21M | medium | F8 |
| P6 | **MedXpertQA gap screen**, repriced to R6's protocol, on an **unburned seed** (seed42 appears in 50 result files, seed7 in 17, seed123 in 16) and excluded from the later validation seeds | medicine | 0.4M | 1.61M | small | F7 |
| P7 | **AIME-2026 M0 probe**, mean-over-4-runs pre-registered as the metric, **+5 AIME-2025 items as a contamination control** (no training cutoff for either Qwen model is established anywhere in this repo) | math | 0.25M | 1.86M | small | — |
| P8 | **R6 BBH probe** — flagship arm n=60, cheap arm **n=120** so the 5%/15% routing split is actually resolvable (at n=60 those branches sit inside each other's noise) | reasoning | 0.8M | 2.66M | small | — |
| P9 | **W1 verified_gate** (shelf, suite 473) — 3 paired seeds, SuperGPQA-hard | reasoning | 6.0M | 8.66M | **built** | — |
| P10 | **W2 permuted_panel** (shelf) — 3 paired seeds + **CAL-2 instability rider** (item-level, permutation null) | reasoning / calibration | 6.0M | 14.66M | **built** | F1 |
| P11 | **Council, merged** — R1's mechanism with **L3's blinded, vote-count-hidden presentation** (the two were the same lever proposed twice at 16.5M combined), **plus the compute-matched control** (3× chem_thinking_gate + text-majority at equal tokens) and a second judge call with vote counts **shown** to identify which factor pays. 2-seed screen. | reasoning | 5.0M | 19.66M | medium | F2 |
| P12 | **Claim audit, merged** — one extractor with a routing switch: quantitative → `sympy_check`/`substitute_check`, conceptual → blind proposition judgment (R2 and L6 were near-duplicates at P0 and P2). 40/40 frozen pre-screen (0.2M) then 2 seeds. | reasoning | 1.4M | 21.06M | medium | — |
| P13 | **A1a agent self-check gate** on a **fresh, disjoint** Terminal-Bench sample (the 24-task set is the sample the agent was *hardened against*, 36%→86%), preceded by a 4-task cost calibration run to replace the unverifiable ~150k tok/task estimate. **Decoupled from A0's kill** — A0 bounds *selection* levers; A1a is a coverage lever targeting pass@1 itself. | agentic | 1.1M | 22.16M | small | — |
| P14 | **FA-1 + FA-2** SimpleQA panel, 3 seeds, + verified-gate rider | factuality | 6.0M | 28.16M | medium | P5 |
| P15 | **A0 Batch-1** oracle gap, 12 fresh tasks, **ungraded = FAIL pre-registered** for both pass@1 and pass@3 (the 37.5% is computed among graded tasks only; k=3 gives three chances to survive to grading, which inflates the gap by survival rather than diversity) | agentic | 5.5M | 33.66M | built | P13 |
| P16 | **LAW-1** flagship-tier unanimous-wrong probe | law | 0.4M | **34.06M** | built | F9 |

**Funded total 34.06M / 43.8M — reserve 9.74M (22%), above the pre-registered 20% floor.**

### Below the line — UNFUNDED this window, named so they are not quietly picked up

`IF-3` IFEval verify-repair (5-7M) · `longctx_mapreduce` (8-14M) · `medxpert_flagship_panel` (6.0M) · council at full 3 seeds (+5M) · `A3` method rollouts (11M) · `A1b` cross-verification (11M, only viable riding A0's artifacts) · `R4` ARC-AGI beyond the 30-task micro-screen · `R5` HLE (external dependency — a HuggingFace access-agreement click only the account owner can make; **zero engineering spend until granted**, and its probe bar must be a **band** — 25-55% flagship with 20-60% cheap-tier unanimous-wrong — because >60% unanimous-wrong is floor saturation, not headroom) · `swiss_law_corpus` run (3.8M) · `M1` perception panel (9M) · **shelf items W2 method_panel, W3 SC@N, W4 tribunal_debate, W6 rag_r3_targeted** remain built-and-shelved.

**Two unresolved contradictions that must be settled before the reset, not during:** (a) **S3 says "do not run `solve_selfconsistency_math` on MATH-500/AIME as built"** while **M1 (sc_margin_aime2026)** points that exact code at AIME-2026 — resolution: M0's probe runs, and SC@N runs **only** at the flagship tier and **only** if M0's dual condition fires; S3's SuperGPQA re-target is deleted as a third competing use of the same code. (b) **R3's program-of-thought seat is not a small-build riding existing tooling** — `mcp_server.py` exposes exactly five constrained tools (`lookup_constant`, `safe_calculate`, `sympy_check`, `substitute_check`, `search_corpus`), `safe_math.py`'s own header states it must never become an arbitrary-execution path, and the only `exec` in the repo is Harbor's per-task container in `agents/terminal_agent.py`. R3 and R4 both require a sandbox that does not exist; both are unfunded until it does, and R3's kill ("any observed sandbox escape") is vacuous until then.

---

## 5. What we will deliberately NOT chase

This section exists so the roadmap cannot drift into a wishlist. Each row: the axis, the **measured** reason, and what would actually be required — which in every case is a better base model, more data, fine-tuning, or an architectural addition, **not a better tribunal**.

| Axis | Measured reason we stop | What would actually be required |
|---|---|---|
| **MMLU-Pro / general knowledge** | Flagship 94-96%, engine **−12**. STEM 4-way: flagship 96.7%, flagship_panel **+0.0**, escalation 3.3%, unanimous-wrong 1.7%. F2 puts `moo:single-call` **alone** on the Pareto frontier at 919 tok/q, dominating all 11 configs logged against it. | Broader/better pretraining knowledge. The only correct engineering action is a router that recognizes saturation and spends one call — already the recorded MoO result. |
| **GSM8K / MATH-500 (L5 open-answer and MC)** | Saturated at **both** tiers: 96.6% flagship **and** 96.6% cheap-flash-with-thinking, 0% escalation at both, 55/59 unanimous, 46 identical answer strings. Cheap deliberation costs −4.0/−6.1. | Harder items. Deliberation is provably inert, not merely unhelpful. |
| **MedQA** | Flagship 94%, unanimous-wrong **4%**, engine ties (+2 = one question of 50). | A harder medical benchmark before any accuracy claim is meaningful. MedQA stays a **cost** story only. |
| **AIME / competition math, absolute SOTA** | Unwinnable **by measurement**, independent of capability: GLM-5.2 at 0.992 on n=30 means one item is 3.3pt, so a flawless 30/30 cannot be statistically distinguished from the leader. | Nothing orchestration can supply. A larger evaluation set would be required before the claim is even expressible. |
| **cons@N at published scale on math** | Measured unaffordable: `aime_open_panel_cheap` logged 2,050,542 tok / 28 items = 73.2k tok/row ≈ **24.4k tokens per sample**. cons@64 ⇒ ~1.5M tok/item, ~75M for one 48-item seed = **1.7× the entire weekly quota**. Even N=8 is ~9.4M (21% of the week). | ~10x the quota, or a materially cheaper-per-sample model. The mechanism is externally validated; we cannot buy it. |
| **AIME 2024 / 2025 as a measurement surface** | Unusable twice over: our pilot is **invalidated** for survivorship bias (12/60 and 32/60 drops on 429s), and both sets predate the models. | A post-cutoff surface *and* verified training-cutoff evidence. |
| **FrontierMath** | The one math surface with genuine headroom (~88-89%) is an **Epoch AI holdout** — no public access, no path. | Access we do not have. Recorded so the headroom is not mistaken for an opportunity. |
| **LEXam as an accuracy axis** | Engine −14; the only paired flagship comparison we have is **80.0% vs 86.0%, net −3 items**; 2/30 retrievals on-topic; RAG +2.2 (noise); F2 single-call dominance. | A jurisdiction-specific corpus **and** a multilingual encoder (63% of `mcq_4` is German; the Swiss corpus is 17,559 de / 207 en against English-only indexed encoders). That is a data + infrastructure project. |
| **SWE-Bench Pro / Terminal-Bench absolute SOTA** | Base-model gap, not an orchestration gap. Terminal-Bench: ours 37.5% (9/24 graded) vs leaderboard-reported 88.8 / 91.9 / 88.3 — **~50pt**. Our best validated lift anywhere is **+4.1pp**; the only published work on this technique class caps at +8-12pp (**arXiv 2604.16529 — UNVERIFIED in-session; must be confirmed or the figure withdrawn from A1b's comparator**). Orchestration is off by 4-6x. | A frontier-class base model. SWE-Bench Pro additionally needs the SWE-agent scaffold and per-repo Docker eval environments — neither exists here. |
| **tau-bench / tau2-bench** | No loader, no scaffold, no measured number of ours, no frontier figure researched. | Recorded explicitly so nobody later quotes a number this plan did not produce. |
| **OSWorld and any GUI/vision agentic surface** | Engine is text-only; zero `vision|qwen-vl|multimodal` matches in `src/`. | A VLM plus a second engine mode (image-bearing schema, VL client, non-letter grading). Architectural addition, not a lever. |
| **MMMU / ChartQA / DocVQA** | Same, plus VL availability on our endpoint is **unmeasured** (live 429), and the obvious decomposition is predicted-negative (shared transcription ⇒ identical solver errors ⇒ the homogeneity trap at the perception layer). | A frontier-class VLM we do not have. |
| **Cross-lab "QuorumQA tops frontier models" on GPQA-Diamond** | Not establishable with our instruments: our unit is a **reseeded 90-item subsample** (qwen3.8-solo and chem_thinking_gate share only 68 items), our noise floor is ±2.5pt ≈ 2 items, and published numbers use the full 198-item set with different prompting and grading. A 1-3pt margin is inside our noise **and** inside a protocol difference we do not control. | A full-set, protocol-matched evaluation. Only same-items/same-seed within-family comparisons are defensible. |
| **Closing GPQA's residual deficit with more COVERAGE** | F1(b): the deficit set is **0 never-escalated / 2 escalated-and-lost** — every item the family-best model won and the society lost *did* escalate. More seats, more permutations, better flaw-finder recall have nothing to catch there. | Selection-side work only (and W1/W2 remain justified on SuperGPQA-hard's 23% pool). |
| **Cross-config selection on SuperGPQA-hard** | Family floor 84/522 = 16.1% ⇒ cross-config union ceiling ~83.9% against flagship_panel's ~82.6% best-society mean. **~1.3pt**, inside noise at n=90. | A genuinely new answer source (coverage), not better arbitration. |
| **The hard family floor** | 84/522 SuperGPQA-hard and 4/197 GPQA items are wrong under **every** config ever logged, including qwen3.8-solo. Caps any lever at ~97.9% (GPQA) / ~83.9% (SuperGPQA-hard). Also shrinks a 90-item SuperGPQA run's addressable base to ~75-76, so "+3/90" is really +3/~76. | A different model family. |
| **Better judges, bigger panels, stronger same-family seats** | All measured negative or null: qwen38_judge zero net gain despite 9/9 correct overturns; N=5 solvers 81.1% vs 84.4% at higher cost; qwen38_panel ties baseline, trails flagship_panel, 0% escalation, 30% timeout drops. | New sources of **decorrelation** at the conditioning level — never more compute on the same lens. |
| **Score- or confidence-based accuracy gating** | Score-gating retrieval failed on statistically identical scores (0.0288 vs 0.0290); W5 AUC 0.625 = BAND; F3 −0.026; reflection tokens externally refuted (Sea AI Lab). | Nothing available. Instability features are the last untried family and are a band-improvement bet, never a gate. |
| **Retrieval-boosted SimpleQA** | Blocked twice: (a) protocol — the benchmark measures **parametric** knowledge, so a RAG score is not comparable to the leaderboard; (b) feasibility — general English Wikipedia at ~50M passages × 1024 dims × float32 ≈ **200GB**, and indexing the dataset's own `urls` column is barred by our §4 firewall. | A lead-paragraph-only full-coverage index (~6.9M passages, ~28GB) — architectural, not a lever. |
| **Cross-vendor seats (Kimi K2 / DeepSeek)** | No provider-agnostic client (not built), no keys (not provisioned, outside the Token Plan = real money = hard stop needing explicit approval). Kimi K2 GPQA-Diamond 75.1 is ~10pt below our flagship; Self-MoA says mixing loses unless models are near-equal quality **and** highly diverse. "Kimi K3" is UNCONFIRMED. | Keys, a client, and a near-equal-quality partner model. A legitimate research bet; not a lever for this window. |
| **A coding tribunal / deliberation on agentic coding** | Our coding win (36%→86% graded coverage) came from **harness hardening of a single non-deliberating agent**, not voting. The propose-run-observe loop already has a verifiable arbiter. Step-level review of every action is also rejected on measured grounds: our failure taxonomy is timeouts, stalls and premature-done, **not** destructive commands. | More loop and tool discipline — which is what already worked. |
| **Fine-tuning / training anything** | Explicit non-goal. The thesis is orchestration. | — |

---

## 6. Success criteria — pre-registered

**The statistical standard, stated once and applied everywhere.** Every claim is a **paired discordant-item count on shared items**, never a raw accuracy delta. The house noise floor is ±2.5pt at n=90 ≈ 2.25 items. Because net +3 at a single seed cannot reach significance under the test we ourselves mandate (McNemar exact, one-sided: b=3/c=0 ⇒ p=0.125; b=6/c=3 ⇒ p=0.508; the minimum net clearing p<0.05 with zero losses is **+5**), the portfolio-wide bar is:

> **"We topped it" = net ≥+5 discordant at a single seed with McNemar exact p<0.05, OR net ≥+3 at 2 of 3 seeds with the pooled McNemar (n=270) clearing p<0.05 — and never negative at any seed.**

Any lever that cannot state its bar in that form is not validated, whatever its headline percentage says.

**Three claim-shape rules that bind every axis:**
1. **Within-family only.** The comparator is always the best single model *we* can run, on the *same items and seeds*. No leaderboard-topping sentence is written on any reseeded subsample.
2. **Compute-matched or it does not count.** F2 showed a bare single flagship call Pareto-dominates every lever we ever logged on 6 of 9 benchmarks, precisely because our comparisons were not token-matched. Any lever spending Nx tokens must beat an Nx-token control of its own base config, not a 1x control.
3. **Kill dominates bar.** If a kill and a bar fire together, the kill wins — with one repair: where a lever has two separable arms (e.g. plurality vs arbiter, accuracy vs cost), each arm carries its own bar and kill, so a winning arm is not destroyed by a losing sibling.

**Per-axis definitions of "we topped it":**

| Axis | Number to beat | "Topped it" at the 3-seed bar |
|---|---|---|
| **Reasoning — GPQA-Diamond** | chem_thinking_gate **90.9%** (validated best); **R0-repaired** qwen3.8-solo bar (currently 93.6% at n=78 with 12 drops — upper-biased, unusable until repaired) | ≥92% mean with net ≥+5 discordant vs same-seed chem_thinking_gate at ≥2 of 3 seeds, pooled McNemar p<0.05, **against a compute-matched control** |
| **Reasoning — SuperGPQA-hard** | flagship_panel **83.3/81.7/82.7** (mean +4.1 vs ~79.5) | Net ≥+5 discordant vs same-seed flagship_panel, never negative. Note the ceiling: family floor 16.1% ⇒ union ~83.9%, so only **coverage** levers (a genuinely new answer source) can clear this; arbitration levers cannot and are pre-registered not to run here |
| **Chemistry slice** | chem_thinking_gate **90.9%**, +4.4 over matched same-seed flagship | Maintained at 3 seeds; any new lever must add net ≥+5 discordant on top |
| **Law** | our paired flagship **86.0%** (n=50, seed 42) | **Not claimable at n≤90** — only 7/50 items were flagship-wrong. Success this window = a probe result recorded honestly, in either direction, and the axis routed on the evidence |
| **Calibration** | W5 median LOBO AUC **0.625**; flagship verbalized-confidence risk-coverage curve | Median LOBO AUC ≥0.70 **or** unanimous-only AUC ≥0.65; **and** the panel curve at or above the flagship verbalized-confidence curve at 90/80/70% coverage on ≥2 surfaces (6/6 non-negative, ≥4 with bootstrap CI excluding it). This is a **capability** win, explicitly not an accuracy win |
| **Long context** | none — no baseline exists | Success = a committed, evidence-backed transport cap. If the endpoint caps below 64K, that **is** the result and it closes the axis for 0.2M |
| **Multimodal** | none | Success = a committed feasibility record with served VL ids (or none) and measured per-image billing. No accuracy claim is available on this axis and none will be made |
| **IFEval** | our own matched-seed qwen3.7-max single call on the same 541 prompts (frontier band ~85-92% **unverified**, not the bar) | Mean ≥+3.0pt strict-prompt, positive on all 3 seeds, net discordant ≥+20 with pooled McNemar p<0.05, **headlined on the held-out constraint-type subset**; loose-prompt must move in the same direction. Separately, the cheap-tier arm "tops it" by **tying flagship at strictly fewer tokens** — a cost win is a legitimate result here and on this evidence the likelier one |
| **Factuality** | our own **abstain-permitted** single-flagship F1 on the same items; stretch 55.6 (Gemini 2.5 Pro), gated on k ≥ ~38% | F1 +5 over the abstain-permitted comparator at 3 seeds, with correct-given-attempted rising and attempt rate ≥50%, net discordant ≥+5 pooled p<0.05. The stretch claim is dropped **before the run** if k<38% |
| **Agentic coding** | our own pass@1 **37.5%** (9/24 graded) on the development sample; every bar computed on a **fresh disjoint sample** | Relative-lift claim only: an orchestration lift over our own single-agent baseline exceeding the published frontier-model lift for this technique class — with that published figure verified first, or the comparator withdrawn. **Never an absolute-SOTA claim**; the base gap is ~50pt |
| **Medicine** | MedXpertQA-Text: o1 **44.67%** (published Text-subset leader) and our own paired flagship | Net ≥+5 discordant vs same-seed flagship on ≥150 shared items at 3 seeds. Beating 44.67% is reported as a **separate, caveated headline** (different sample of the 2,450-item split, our harness, our prompt) — never as the validation bar |
| **Math** | AIME-2026: our own flagship probe number (does not yet exist) | The axis "tops it" only if M0's dual condition fires. Otherwise the honest outcome is the third measured saturation null — and a null recorded at 0.2M is a better result than a lever run at 2M into a saturated surface |

**Finally, the criterion that is not a benchmark.** Our external research pass found that **no frontier lab publishes on multi-agent ensembling, mixture-of-agents, LLM-as-judge, or self-preference bias**. That means our null ledger — the homogeneity trap, escalation-coverage-not-judge-quality, saturation-kills-deliberation, the corpus-coverage diagnosis, the identical-score failure of score-gating, the AUC-0.625 band, and the F2 dominance frontier — is a scarce artifact with two independent external corroborations (Self-MoA predicting the homogeneity trap; Sea AI Lab confirming the reflection-token null). It costs **zero tokens**, it is already measured, and it outcompetes any lever bidding for the same week. A roadmap that ends the window with that written up and every number traced to a committed result file has succeeded even if every paid lever returns null.