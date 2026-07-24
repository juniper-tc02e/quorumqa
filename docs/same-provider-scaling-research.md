# Scaling QuorumQA with Same-Provider (Qwen-Only) Agents — The Decision Document

*Synthesis of 5 research angles (sampling-decoding, prompt-role diversity, topology-pipelines, provider-internal variants, scaling-laws-limits) over the validated record in `benchmark/results/reasoning_arc_synthesis.md` and `docs/reasoning-supercharge-plan.md` (v2). Nothing here contradicts a committed finding. Paid work is quota-blocked until 2026-07-28 03:32 UTC; everything below is sequenced FREE-NOW → riders-on-week-1-paid → week-2+. Cost is measured in tokens, never dollars (Token Plan logs cost_usd=0.0); the free token-audit (plan §2 item 0) prices every run below before anything fires.*

---

## 1. The reframe: we have been doing same-provider scaling all along

Track B ("Ultra Agentic Scaling, Qwen edition") is not a new program. Every validated result in this repo is already a measurement of how far a Qwen-only society can go, because every seat ever run was a Qwen model. The question was never "should we scale within one provider" — it was "which within-provider diversity axes actually decorrelate errors." The record answers for three axes, the plan bets on four more, and the five angles surveyed here add a third tranche.

**Axes already VALIDATED (3-seed bar unless noted):**

| Axis | Configs | Result |
|---|---|---|
| **Tier gap** (flash ↔ 3.7-max) | thinking_gate; chem_thinking_gate; flagship_panel; shipped engine | thinking_gate mean ~+1.1 on GPQA; chem_thinking_gate **90.9%** (best validated); flagship_panel **+4.1** mean on SuperGPQA-hard (per-seed 83.3/81.7/82.7, mean ~82.6%); shipped 78.9% @ −11% cost vs flagship-solo 84.4% |
| **Thinking mode** (on/off, same model) | flash thinking-OFF solvers; thinking seat in gate configs | Thinking-off *creates* the gap (seats genuinely disagree → escalation fires, commit 82f7ab8); thinking-on *closes* it (flash-with-thinking = flagship 96.6% on MATH-500). One axis doing double duty. |
| **Retrieval context** (evidence-conditioned vs bare seat) | rag_presolve; rag_thinking_gate | +4.7/+6.9/+8.0/−5.6 (mean +3.5, validated-with-variance); reasoning-gated variant never negative (+0.0/+4.6/+4.5) |

**Axes already FALSIFIED (equally load-bearing):** same-model sampling diversity at equal strength (qwen38_panel 0% escalation *with* temperature variation; all-flagship math panel; 55/59 unanimous on MATH-500 MC); weak-seat-as-voter (the mixed-panel drag failure); cheap deliberation on saturated surfaces (−4.0/−6.1 on GSM8K/MATH-500 distractor-MC, −12 on MMLU-Pro full).

**Axes PLANNED, not yet run (reasoning-supercharge-plan.md — referenced, not re-planned here):** verification framing on unanimous answers (W1-A flaw-finder), sound computational checks (W1-B sympy/substitution), presentation permutation (W2 arm 0), procedure/method prompts (W2 arm 1), within-model sampling + equivalence clustering + cluster-margin escalation (W3), trace-feature wrongness prediction (W5); conditional: debate (W4), R3 retrieval (W6), routing v2 (W7).

**Axes NEWLY IDENTIFIED by this synthesis (section 3 owns these):** sequential-vs-parallel compute allocation as the unifying frame; distribution-derived confidence features (agreement margin, semantic entropy, permutation instability); adaptive early-stopping sampling; paraphrase/format perturbation for open-answer surfaces; verifier-*selection* (not just verifier-triggering) over sample pools; qwen3.7-plus as a non-voting verification-tier seat; cross-lineage flagship mixing (3.7-max + 3.8-max-preview); cross-lingual (Chinese-CoT) seat; thinking-budget asymmetry; reverse tier ladder (strong draft → cheap checkers); synthesis-framed aggregation over unanimous panels; and a ceiling-measurement suite (pass@k coverage audit, family blind-spot intersection, self-preference audit, qwen3.8-solo paired baselines).

**External confirmation worth recording once:** Self-MoA (Li et al. 2025, ICML) independently validates the whole same-provider thesis — repeated sampling of the *best* model + aggregation beats mixing in weaker models in the large majority of settings, because member quality dominates diversity. Our flagship_panel (+4.1) is approximately Self-MoA with a disagreement-gated tribunal, and our mixed-panel weak-seat failure is their quality-sensitivity finding verbatim. Their stated limit condition — mixing wins only with near-equal quality AND high cross-model diversity — is exactly the parked cross-provider track's rationale, and within one provider it leaves exactly one legal mixing candidate: 3.7-max + 3.8-preview (§3, P9).

---

## 2. The technique map

Every technique from the 5 angles, deduplicated (28 rows from 49 raw entries). "Trap?" = does it dodge the homogeneity trap (identical-strength seats stop disagreeing → 0% escalation, proven twice). Status: **VAL** = validated in-repo, **PLAN** = already in reasoning-supercharge-plan.md (do not re-plan; reference), **NEW-F** = new, free-offline, **NEW-P** = new, paid, **NO** = do-not-run (pre-registered warn-off).

| # | Technique (angle sources) | Mechanism | Key evidence | Trap? | Composes with | Cost | EV / Status |
|---|---|---|---|---|---|---|---|
| 1 | Tier-gap cascade w/ disagreement gate | Cheap seats disagree where weaker than flagship → escalate | Repo 3-seed record; FrugalGPT (Chen et al. 2023) | Yes (unequal tiers by construction) | Everything | free (done) | **VAL** |
| 2 | Flagship panel + tribunal (≈ Self-MoA-with-gate) | 3× 3.7-max independent samples, tribunal on disagreement | +4.1 mean, 3 seeds; Self-MoA (Li et al. 2025) | Partly (escalation only 8–12%) | W1, P9 | free (done) | **VAL** |
| 3 | Thinking on/off mode axis | Off creates disagreement, on closes the gap | Commit 82f7ab8; MATH-500 96.6% both tiers | Yes (mode ≠ copy) | All gate configs | free (done) | **VAL** |
| 4 | Retrieval-context seat | Evidence-conditioned vs bare seat decorrelates where knowledge is the gap | rag mean +3.5; gated variant never negative | Yes (different effective input) | thinking_gate | free (done) | **VAL** |
| 5 | Non-monotonicity guard / routing on saturated surfaces | More calls can HARM easy items; route saturated → single-call | Repo −4.0/−6.1/−12; Chen et al. 2024 "Are More LLM Calls All You Need?" | n/a (guard) | W5→W7 | free (done) | **VAL** |
| 6 | Adversarial flaw-finder on unanimous answers (cross-tier critique, backward-verification framing) | Verifying a fixed candidate ≠ generating; task-framing decorrelation; covers 100% of MC | CoVe (Dhuliawala et al. 2023); Weng et al. 2023; null guard: Huang et al. 2024, Stechly et al. 2024 | Partly (framing shift; self-preference risk → P4) | Everything; the only conceptual-MC ceiling lever | cheap-pilot | **PLAN — W1-A** |
| 7 | Sound sympy/substitution check | Extraction call → deterministic local check; check has zero correlation with generator | Cobbe et al. 2021; Kirchner et al. 2024; LLM-Modulo | Yes (check side fully decorrelated) | W1, W3, P2 | cheap-pilot | **PLAN — W1-B** |
| 8 | MC option-order permutation per seat | Removes shared position/first-plausible bias; per-seat accuracy cannot degrade (task-invariant) | MedPrompt +2.1 MedQA (Nori et al. 2023); Zheng et al. 2024; Pezeshkpour & Hruschka 2023 | Yes (perturbs shared bias) | W1 control, W5 feature (row 17) | ~zero marginal | **PLAN — W2-0** |
| 9 | Method-diversity prompts (solve-forward / verify-backward / estimate-first) | Different procedures traverse different error surfaces | DiVeRSe (Li et al. 2022); persona-null contrast | Yes (computation changes) | Gated behind W2-0 | cheap-pilot | **PLAN — W2-1** |
| 10 | SC@N + equivalence clustering + cluster-margin escalation | Cluster by math_grade equivalence; margin = continuous escalation dial | Wang et al. 2022; USC (Chen et al. 2023); "More Agents" (Li et al. 2024) | No — exploits residual within-model variance; targets the gap regime (AIME), not the ceiling | W1-B, P2, P7 | cheap-pilot | **PLAN — W3** |
| 11 | Coverage-vs-selection (pass@N) logging inside W3 | Log any-cluster-correct alongside selected accuracy; gap = selection loss | Brown et al. 2024 (Monkeys) | n/a (metric) | W3, §4.2 | zero extra calls | **PLAN — W3 logged add** |
| 12 | Trace-feature wrongness predictor + logprobs check | P(unanimous-wrong) from logged traces; leave-one-benchmark-out AUC | Kadavath et al. 2022; pre-registered controls | n/a (signal reaches unanimous-wrong without disagreement) | smart_gate_v2, W7 | free | **PLAN — W5** |
| 13 | Escalation-only debate round | Structured rebuttal on frozen escalated set | Du et al. 2023 vs Smit et al. 2024 (MAD), sycophancy-collapse line | No (conversational form of the trap) | Only if W1/W2 enlarge pool | moderate | **PLAN — W4 conditional; do not promote** |
| 14 | Compute-allocation frontier (sequential thinking vs parallel seats vs single call) | Treat thinking-tokens and parallel calls as substitutable; per-item allocation policy | Snell et al. 2024; s1 (Muennighoff et al. 2025); repo: MATH-500 sequential-closed-the-gap, thinking_gate = targeted sequential spend | n/a (frame) | Reframes W5/W7 as compute-allocator | free-offline | **NEW-F, high** |
| 15 | Family blind-spot intersection + 3.8-deficit decomposition | Intersect wrong-sets across all logged Qwen configs = measured family floor; 3.8-right-society-wrong set = the exact Track-B deficit | Krogh & Vedelsby 1995; Goel et al. 2025 "Great Models Think Alike" | n/a (measurement) | Caps every claim; arbitrates Track A/B | free-offline | **NEW-F, high** |
| 16 | Distribution-feature upgrade for W5 (agreement rate, cluster margin, semantic entropy) | Consistency statistics are the strongest zero-training correctness estimator — strictly above verbalized confidence | Xiong et al. 2024; Kuhn et al. 2023; Farquhar et al. 2024 (Nature) | n/a | W5 (reprioritizes its feature list) | free-offline | **NEW-F, high** |
| 17 | Permutation-instability as W5 feature + W1 trigger | Seat flips under reordering = confidence is presentation artifact → prime unanimous-wrong suspect | Zheng et al. 2024 (PriDe) | n/a (signal) | W2 logs → W5, W1 | free (log mining) | **NEW-F, high** |
| 18 | Adaptive early-stopping sampling | Stop drawing when margin clears threshold; 2–4× fewer calls at unchanged accuracy | Adaptive-Consistency (Aggarwal et al. 2023); ESC (Li et al. 2024) | n/a (budget allocator) | W3, flagship_panel; attacks constraint #9 (quota) | free build + replay | **NEW-F, high** |
| 19 | Difficulty-conditional non-monotonicity map | Per-difficulty-bin help/hurt table from logs → predictive boundary, not anecdote | Chen et al. 2024; repo's own nulls | n/a (measurement) | W5, W7 no-harm guarantee | free-offline | **NEW-F, medium** |
| 20 | Rigor wiring: seed param, thinking_budget param, decode-profile spread inside W3, tool-checkable-fraction classification | Deterministic replicates shrink the ±2.5pt noise floor; budget param enables row 27; classification = the Arm-B cap | DashScope docs; Nguyen et al. 2024 (min-p) | n/a | Every future paired pilot | free-offline | **NEW-F, rigor** |
| 21 | qwen3.8-solo paired baselines (SuperGPQA-hard, AIME) | The family's BEST single model is the honest Track-B bar; unmeasured on both surfaces | Repo: 3.8 GPQA solo 93.6% vs best society 90.9%; 13/14 timeout drops were 3.8 calls | n/a (baseline) | Prerequisite for every Track-B claim | cheapest paid run in portfolio | **NEW-P, high** |
| 22 | Coverage pass@k audit of the unanimous-wrong pool | k=10–50 flash samples on ~30 pool items: recoverable-by-decorrelation vs irreducible blind spot | Brown et al. 2024; Goel et al. 2025 (expect flatter same-family curve) | n/a (measures whether the trap is escapable at all) | Sizes W1/W2 max upside before spending on them | fraction of one pilot | **NEW-P, high** |
| 23 | Self-preference audit of the same-family flaw-finder | Verbatim vs paraphrased vs known-wrong-fluent inputs; detects recall-suppressing self-recognition | Panickssery et al. 2024; 9/9 overturns ≠ Qwen-overrules-unanimous-Qwen | n/a (audit) | Recall-side control W1 lacks | ~90 flagship calls | **NEW-P, high** |
| 24 | Verifier-selected best-of-N over the SC pool | Prefer check-passing cluster over plurality; only lever with a mechanism against MAJORITY-wrong on quantitative items | Monkeys; Lightman et al. 2023; DiVeRSe | Yes (selection decorrelated from generation where checkable) | Rider on W3 logs + W1-B tools | near-free after W3 | **NEW-P, high** |
| 25 | qwen3.7-plus as verification-tier seat (never solver) | Non-voting roles can't drag plurality; verification is easier than generation → middle tier may suffice | Burns et al. 2023 (weak-to-strong); repo: doubt-gate works with a cheap model, plus-as-judge ruled out (9/9) | Yes (third tier, non-voting) | Cost-ablation rider on W1-A | cheap-pilot | **NEW-P, high** |
| 26 | Paraphrase/format perturbation panel (open-answer W2 analogue) | Perturb the CONDITIONING (variable names, given-order, units), not decode noise; only presentation lever available on AIME | FormatSpread (Sclar et al. 2024); Mizrahi et al. 2024 | Yes (different effective question surface) | W3 (diversify inputs AND samples, cluster once) | cheap-pilot | **NEW-P, high** |
| 27 | Thinking-budget asymmetry / budget ladder | Shallow vs deep budgets err differently; ladder = within-model escalation for W1/W5 triggers | Snell et al. 2024; s1; "Do Not Think That Much" (Chen et al. 2024) | Yes (compute-depth regimes) | W1/W5 triggers; needs row 20 wiring | cheap-pilot | **NEW-P, medium** |
| 28 | Reverse tier ladder: 3.7-max draft → 3 permuted flash checkers → 3.8 escalation | Weak models AUDIT a strong draft (verification asymmetry); 3.8 spent only on flagged items — attacks coverage, not adjudication | Generation-verification gap line; sandwiching (Bowman et al. 2022) | Yes, twice (tier gap both directions + verify-vs-generate) | Rider on W1's logged flagship answers | cheap-pilot | **NEW-P, medium** |
| 29 | Heterogeneous flagship panel: 2×3.7-max + 1×3.8-preview seat | Different lineages within one provider = partially decorrelated errors at comparable strength — the one panel composition the homogeneity trap forbids and the weak-seat failure doesn't apply to | Deep ensembles (Lakshminarayanan et al. 2017); repo: 3×3.8 = 0% escalation, 3×3.7-max = 8–12% | Yes (lineage decorrelation at equal strength) | flagship_panel; plan §5b week-2 hook | moderate (quota-limited 3.8: one seat/item max) | **NEW-P, high** |
| 30 | Cross-lingual seat (Chinese CoT) | Activates a different slice of Qwen's training distribution + tokenization path; uniquely-Qwen axis | CLP (Qin et al. 2023); Qwen bilingual strength | Yes (distribution shift; NOT invariant by construction → kill rule applies) | Extra W2 arm | cheap-pilot | **NEW-P, medium** |
| 31 | Always-on synthesis aggregator over unanimous panels (synthesis-framing vs verification-framing) | Traces diverge in method even when letters agree; aggregator reads all traces every item — no disagreement gate needed | Self-MoA gains accrue without any gate; MoA (Wang et al. 2024) with anchoring caveat | Partly (mines trace diversity under agreement) | Prompt-condition rider inside W1-A | same cost profile as W1-A | **NEW-P, medium** |
| 32 | Persona/expert prompting | Identity labels shift style, not computation | Zheng et al. EMNLP 2024 Findings: 162 personas, no accuracy gain; PRISM 2026: personas damage objective accuracy; our lens-named seats still homogenized | No (cosmetic) | — | — | **NO** |
| 33 | Same-model intrinsic Self-Refine | Same weights critique same weights, no escalation target | Huang et al. 2024; Stechly et al. 2024 | No | — | — | **NO** |
| 34 | ToT/GoT search with self-evaluated states | Same-model value function shares the searcher's blind spots; MC science lacks checkable intermediate states | Yao et al. 2023 gains confined to crisp-check tasks; CoT+SC matches at equal compute | No ("the trap in a tree costume") | — | 10–100× calls — worst tok/q vs a ~3-pilot weekly quota | **NO** |
| 35 | Temperature/top-p/top-k ladder as standalone diversity | Decode noise only surfaces variance the distribution contains; peaked wrong modes survive all temperatures | Falsified in-repo: qwen38_panel homogenized WITH temp variation | No | Fold decode spread into W3 seats free (row 20) | — | **NO (standalone)** |
| 36 | Logprob/perplexity-ranked selection | Model likelihood is a poor correctness proxy on reasoning | Monkeys: barely beats majority vote; Cobbe et al. 2021's original motivation | No | Logprobs → W5 features ONLY (already planned) | — | **NO (as selection)** |
| 37 | Plan-then-solve decomposition as pipeline | A shared wrong belief decomposes into subquestions answered with the same wrong belief | Zhou et al. 2023 gains confined to compositional tasks | Weak on conceptual MC (our pool) | One W2-1 method prompt on AIME only | — | **NO (as pipeline)** |

---

## 3. The NEW test ladder

Only techniques NOT in reasoning-supercharge-plan.md. House rules apply globally: **the kill dominates the bar**; paired n=90 deltas inside ±2.5pt (~2 items) are noise, so bars are discordant-item counts ≥ +3 per 90 (≥ +3 per 60 on AIME, where ±2.5pt ≈ 1.5 items); screens (1–2 seeds) before 3-seed validation; every run priced in tok/q against the token-audit (plan §2 item 0) before firing; a run with unretried drops is rerun before any number is quoted (run-#1 lesson). Free rungs first — their info-per-quota-token is infinite.

### Free rungs (now → 07-28, no quota)

**F1. Family blind-spot intersection + 3.8-deficit decomposition** (map row 15).
*Build:* offline script over committed result JSONLs: per benchmark, (a) items wrong under EVERY logged Qwen config = measured family floor; (b) on GPQA, items 3.8-solo (93.6%) got right that the best society (90.9%) missed, decomposed into never-escalated (blind spot) vs escalated-and-lost (selection).
*Decision rule (pre-registered):* the intersection is subtracted from every lever's addressable pool — bars in this ladder and in W1/W2 are hereafter quoted against the addressable pool, not raw n. The deficit decomposition arbitrates where Track-B effort goes (coverage levers vs selection levers).
*Kill:* n/a (measurement). Honest-null form pre-committed: "X% of GPQA is unsolved by every Qwen config ever run."

**F2. Compute-allocation frontier from logs** (row 14).
*Build:* per benchmark, accuracy-per-token frontier over {flash-thinking, 3.7-max-no-thinking, 3.7-max-thinking, flagship_panel} from committed JSONLs.
*Decision rule:* crossovers exist → W7's router is reframed as a compute-allocator (predicted-easy → 1 flash call; predicted-medium → 1 max-thinking call; predicted-hard → panel) and W7's existing bar/kill carry over unchanged. No crossovers → record the dominant config per surface; W7 scope shrinks to the recorded cost-win.
*Kill:* n/a (measurement).

**F3. W5 distribution-feature upgrade + permutation-instability feature** (rows 16–17).
*Build:* add agreement rate, top-cluster share, cluster margin (via math_grade on math logs), vote entropy, answer-switching to W5's feature set; add permutation-instability once W2 arm-0 logs exist. Same leave-one-benchmark-out, within-benchmark AUC protocol — inherits W5's bar (median AUC ≥ 0.70, none < 0.60), band (0.60–0.69 router-only), and kill (< 0.60 → recorded as "these features don't separate") verbatim.
*New pre-registration:* report ΔAUC of distribution features over verbalized features, and note the structural limit up front: on unanimous items agreement features are maximal-and-useless — only crossed with instability features (F3's permutation term, P6's paraphrase term) can any W5 signal touch the ceiling.

**F4. Adaptive early-stop build + replay** (row 18).
*Build:* margin-threshold stopping inside W3's SC@N lever; validate by REPLAY on logged multi-sample runs (no new calls).
*Bar (replay):* ≥ 30% mean call reduction at ≤ 1 discordant item vs fixed-N on the replayed set.
*Kill:* replay accuracy drop > 2 items/90-equivalent → keep fixed N; record.

**F5. Difficulty-conditional non-monotonicity map** (row 19). Same log-mining pass as F3; output per-difficulty-bin help/hurt table per benchmark; locks the routing no-harm rule as a predictive boundary. No bar/kill (measurement).

**F6. Rigor wiring** (row 20): `seed`, `thinking_budget` params in `qwen_client.py`; decode-profile spread across W3 seats (read seat-level disagreement from logs — never a standalone pilot, per map row 35); tool-checkable-fraction classification of the unanimous-wrong pools (~10/90 GPQA, ~20/86 SuperGPQA-hard) — this fraction IS the W1-B cap, committed before W1 runs; offline paraphrase-fidelity checker for P6.

### Paid rungs (ranked by information-per-quota-token; riders on already-scheduled runs first)

**P1. qwen3.8-solo paired baselines — SuperGPQA-hard (n=86) + AIME (n=60)** (row 21). *Always the first new-paid spend.*
*Cost:* ~1 preview call/q — the cheapest paid run in the portfolio. 3.8 fragility is recorded (13/14 timeout drops were 3.8 calls): retry-with-backoff, paced, full-retry before quoting.
*Decision rule (pre-registered):* this run SETS the Track-B bar per surface (§5). If 3.8-solo ≥ flagship_panel's 82.6% mean on SuperGPQA-hard, the +4.1 claim is re-labeled "beats 3.7-max solo, not family-best" everywhere it appears. If below, flagship_panel already clears the family bar on one surface — promoted to 3-seed paired validation immediately.
*Kill (data quality):* any unretried drop when quoting → rerun.

**P2. Verifier-selected best-of-N ablation** (row 24). *Rider on W3's logged samples.*
*Cost:* extraction calls only (the check is local sympy via W1-B's tools); selection re-scored offline over the logged SC pool.
*Bar:* net ≥ +3 on the 60 shared AIME problems vs cluster-margin selection alone.
*Kill (dominates):* the check passes a known-wrong cluster in > 10% of audit cases → selection stays vote-based, the check stays trigger-only (its W1-B role). Inherits Arm B's honest bound: quantitative items only, extraction is model-generated.

**P3. Coverage pass@k audit of the unanimous-wrong pool** (row 22).
*Cost:* ~30 pooled items (≈20 SuperGPQA-hard + ≈10 GPQA) × k ≤ 50 flash thinking-off samples ≈ a fraction of one pilot.
*Decision rule:* coverage < 1/3 of the pool → W1/W2's +3-per-90 bar is near the theoretical max — expectations set, no bar-raising later. Coverage > 2/3 → decorrelation headroom is real; W2 arms get priority in week 2. MC reporting uses cluster margins, not raw pass@k (4-option guessing inflates coverage).
*Kill:* n/a (measurement); sampling params logged for reproducibility (F6's seed wiring).

**P4. Self-preference audit of the flaw-finder** (row 23).
*Cost:* ~30 unanimous items × 3 conditions ≈ 90 flagship-thinking calls. Conditions: (a) verbatim panel reasoning, (b) same content paraphrased to strip stylistic self-recognition cues, (c) known-wrong answers with fluent Qwen-style justifications.
*Decision rules (pre-registered):* (a)-vs-(b) flaw-detection gap ≥ 10pt → self-preference confirmed → W1 must paraphrase panel reasoning before the flaw-finder sees it (free fix, then re-screen). Detection on (c) < 30% even under (b) → recall ceiling recorded: same-family red-teaming is bounded, and flaw-finding is promoted to the parked cross-provider track's evidence file.
*Precedence:* W1's screen may run first, but W1 does NOT advance to 3-seed validation until this audit passes — the audit catches the failure shape W1's precision-kill is blind to (high precision, near-zero recall: it just confirms everything).

**P5. qwen3.7-plus as flaw-finder** (row 25). *Config-change rider on W1-A: same lever, same items, same seed.*
*Bar:* retains ≥ 2/3 of the 3.7-max arm's net discordant gain at materially lower tok/q.
*Kill (inherited from W1, dominates):* precision < 20%, or net ≤ 0. Note the standing constraint: plus never votes, never judges (9/9 ruled judge quality out) — gate/skeptic/flaw-finder is its only principled slot.

**P6. Paraphrase/format-perturbation panel** (row 26). *Third arm on the queued AIME paired design if headroom; else week 2.*
*Build (free, done under F6):* conservative perturbations only — variable renaming, given-order shuffling, unit restatement; no free rewording. Offline fidelity check first.
*Bar (screen):* top-cluster-wrong rate drops at both seeds in the same direction AND net accuracy within noise (≤ 1.5 items/60) of the plain SC@N arm.
*Kill (dominates):* fidelity checker flags > 5% of perturbations as problem-changing (fix before ANY paid run), or net accuracy drops beyond noise at both seeds.

**P7. Synthesis-framing condition inside W1 arm A** (row 31). *Prompt-condition rider on W1's unanimous pool — not a new workstream.* "Write the best answer from these three traces" vs W1's "find the specific error."
*Bar/kill:* inherit W1 verbatim (net ≥ +3/90; precision < 20% kill). Output: which framing wins on the same logged pool; if neither passes, both are recorded and W1's verdict stands.

**P8. Reverse tier ladder screen** (row 28). *Drafts = W1's logged flagship answers (free); new calls = 3 permuted flash checkers/q + 3.8 escalation on any confident objection.*
*Bar:* net ≥ +3/90 vs 3.7-max solo on the same items, checker precision ≥ 20%.
*Kill (dominates):* checker precision < 20% (objections fire mostly on correct drafts — W1's kill mirrored; the recorded risk is flash being too weak to audit 3.7-max on hard STEM), or 3.8-escalation volume > 20% of items (quota guard on the limited endpoint).

**P9. Heterogeneous flagship panel: 2×3.7-max + 1×3.8-preview seat** (row 29). *The within-provider miniature of the parked cross-provider track; plan §5b's week-2 hook.*
*Cost:* moderate — flagship-tier ×3/q; the 3.8 endpoint is quota-limited and fragile, so exactly one preview seat per item, never a full 3.8 panel (homogeneity null + fragility both already recorded).
*Bar (screen, then 3-seed):* productive-disagreement (escalation) rate > flagship_panel's 8–12% at the same seed AND unanimous-wrong rate lower; then net ≥ +3/90 vs flagship_panel at 2 seeds before validation. Diversity accounting mandatory: per-seat disagreement + unanimous-wrong rates logged — decorrelation proven, not asserted.
*Kill (dominates):* unanimous-wrong rate not lower at both seeds → lineage mixing adds no decorrelation within this provider (a load-bearing Track-B ceiling finding — see §5).

**P10. Cross-lingual seat** (row 30). *Extra W2 arm; inherits W2's screen bar/kill verbatim* (unanimous-wrong drops at both seeds same direction; net within 2.5pt).
*Extra kill:* the Chinese-CoT seat's own accuracy drops > 2.5pt vs its English twin at both seeds — unlike permutation this axis is NOT invariant by construction. Demo value for the hackathon narrative noted; it buys no bar relief.

**P11. Thinking-budget asymmetry** (row 27). *After F6 wiring; SuperGPQA-hard or AIME only (inert on saturated surfaces like everything else).* One arm: seats at (low, high) thinking_budget vs shipped config. W2-style screen bar/kill. The budget-LADDER variant (rerun flagged items at higher budget instead of a different model) runs only once W1 or W5 provides a non-disagreement trigger.

### Do-not-spend list (pre-registered, with reasons — so no future session burns a pilot rediscovering them)

Personas (persona-null + our lens-seats homogenized anyway); same-tier intrinsic Self-Refine (self-correction null; no escalation target); ToT/GoT (same-model value function; worst tok/q against a ~3-pilot weekly quota); standalone temperature/sampling-param diversity (falsified in-repo — decode spread rides W3 free); logprob-ranked selection (Monkeys null — logprobs are W5 features, never a selection rule); promoting W4 debate (conformity/sycophancy literature independently reproduces both our failure modes; stays conditional); plan-then-solve as a pipeline (one W2-1 method prompt on AIME only).

---

## 4. The ceiling: honest limits of same-provider scaling, and the cheap measurements that locate ours

Same-provider scaling has a floor it cannot dig below, and the program's credibility rests on measuring it rather than discovering it by attrition. Five limits, each with its in-repo evidence and its measurement:

**4.1 The correlated-error floor.** Ensemble error is lower-bounded by the correlated component (Krogh & Vedelsby 1995), and same-family models correlate MORE than cross-family (Goel et al. 2025, "Great Models Think Alike and This Undermines AI Oversight"). Our measured pools: ~10/90 unanimous-wrong on GPQA cheap-tier (~11%), ~20/86 on SuperGPQA-hard (23%). Disagreement-triggered escalation structurally cannot reach them; 80% of the shipped engine's GPQA net loss never escalated. *Measurement:* **F1** (free — the exact per-benchmark floor: items no logged Qwen config ever solved) and **P3** (small paid — what fraction of the pool ANY flash sample ever gets right). P3 < 1/3 means W1+W2's +3/90 bars are already near the theoretical max.

**4.2 The coverage-vs-selection (verifier) gap.** Coverage grows log-linearly with samples while selection plateaus (Brown et al. 2024); whoever can CHECK candidates captures the gap. In math, math_grade (0/4000 false positives, fails closed) makes selection fully decorrelated from generation — the one domain where repeated same-model sampling has the least-capped upside. In conceptual MC, selection needs a model and is therefore bounded by 4.3. *Measurement:* W3's logged pass@N-vs-selected metric (zero extra calls) + **P2**'s selection ablation. Pre-registered reading: high coverage + failed selection → fix the selector, not the sampler.

**4.3 Self-preference bias.** LLM evaluators recognize and favor their own generations (Panickssery et al. 2024). Our 9/9-overturn result proves adjudication-after-disagreement is unbiased enough; nobody has tested Qwen overruling *unanimous* Qwen — exactly W1's job. The dangerous failure shape is high-precision/near-zero-recall (confirm everything), which W1's precision kill cannot see. *Measurement:* **P4** (~90 calls). A large verbatim-vs-paraphrase gap is fixable free (paraphrase-wrap); low known-wrong detection even paraphrased is a genuine same-provider bound and promotes flaw-finding to the parked cross-provider track.

**4.4 Presentation artifact vs genuine blind spot.** Part of the unanimous-wrong pool is shared position/format bias (recoverable in-provider, at zero accuracy risk — permutation is task-invariant); the remainder is genuine knowledge/reasoning deficit (the hard cap). *Measurement:* W2 arm 0 (planned) + P6's paraphrase-invariance on the ~20-30 pool items: flip-under-perturbation fraction = artifact floor; the invariant remainder = the cap. F3's instability features carry the same signal into W5 per-item.

**4.5 The tool-checkable cap.** Deterministic checks are the only FULLY decorrelated channel same-provider scaling can add (external-feedback literature: Huang et al. 2024, Stechly et al.; in-repo replication: LEXam — 7/9 escalations produced zero verifier findings and overturn quality fell to 67% without tool-grounded evidence). But they cover only items where a checkable relation exists, and the unanimous-wrong pool is largely conceptual MC. *Measurement:* **F6**'s quantitative-vs-conceptual classification of the pool — committed before W1 runs, as Arm B's cap.

**4.6 Saturation and non-monotonicity.** More calls are not merely useless on easy surfaces — they harm: −4.0/−6.1 on GSM8K/MATH-500 distractor-MC, −12 on MMLU-Pro full, MATH-500 saturated at both tiers (96.6% = 96.6%). Chen et al. 2024 generalizes the mechanism. The only safe posture is routing (single-call or flagship_panel), and **F5** turns the recorded nulls into a predictive boundary.

**Per-benchmark ceiling-location ledger (all cheap):**

| Benchmark | Floor measurement | Cost | What it bounds |
|---|---|---|---|
| GPQA-Diamond | F1 intersection (logs incl. 3.8-solo 93.6% baseline) + P3 on ~10-item pool | free + small | Max W1/W2 recovery; the 2.7pt society-to-3.8 deficit's composition |
| SuperGPQA-hard | F1 + P3 on ~20/86 pool + P1 (3.8-solo unmeasured) | free + cheapest paid | The real Track-B bar; addressable pool for the +4.1→+6 goal |
| AIME-60 | W3's logged coverage-vs-selection + P2 + P1 arm | ~zero extra + small | Whether math headroom is coverage or selection; kill: flash < 15% |
| MATH-500 / MMLU-STEM | F5 map (already measured saturated) | free | Nothing to scale; routing-only, no-harm |

---

## 5. Track B restated for one provider: "Ultra Agentic Scaling, Qwen edition"

**The measurable claim (the only form that counts):**

> On surface S, a Qwen-only society beats **qwen3.8-max-preview solo** — the family's best single model, not qwen3.7-max — on the same items and seeds, by a net discordant margin ≥ +3 per 90 (≥ +4 per 60 on AIME), at the 3-seed bar, with per-seat diversity accounting (disagreement + unanimous-wrong rates) proving decorrelation rather than asserting it.

Everything short of that is Track A (the price claim: match flagship cheaper), which is already validated and needs no new evidence.

**Honest per-surface status against that bar:**

| Surface | Family-best bar | Best society today | Gap |
|---|---|---|---|
| GPQA-Diamond | **93.6%** (3.8-solo, measured) | chem_thinking_gate **90.9%** (3 seeds) | **−2.7pt — currently UNDER the bar.** The hardest surface; ~2.5 discordant items of ground to make up before any claim. |
| SuperGPQA-hard | **unmeasured** (P1 measures it) | flagship_panel mean ~82.6% (+4.1 over 3.7-max solo, 3 seeds) | Unknown — possibly already cleared if 3.8's edge there is small; possibly entirely inside it. P1 is therefore the first paid spend. |
| AIME-60 | unmeasured (P1 arm) | unmeasured (queued pilot IS the measurement) | Open — the predicted gap regime. |

**The dependency chain (each stage gates the next; kill dominates bar throughout):**

- **Free now (pre-reset):** F1 (deficit decomposition on GPQA — which items 3.8 wins that the society loses, and why), F2–F6. These are Track-B intelligence at zero quota.
- **Week 1 (unchanged from the plan — Track B adds only riders):** AIME pilot ① first; W1 flaw-finder + W2 arm 0 on SuperGPQA-hard; riders **P1** (cheapest paid — sets the bar), **P7** (prompt condition inside W1), **P2/P6** only if headroom after the token audit.
- **Week 2:** **P3 + P4** (is the ceiling attackable same-provider, and can Qwen honestly police Qwen?) → go/no-go on the ceiling attack; **P9** heterogeneous-panel screen (the one legal flagship-mixing config); W1/W2 second seeds; P5/P8 as budget allows.
- **Week 3+:** stack whatever screened positive onto the best validated base per surface — chem_thinking_gate for GPQA (the §3 goal: ≥ 92% at 3 seeds, i.e. net ≥ +4 discordant vs the 90.9% config), flagship_panel for SuperGPQA-hard (+4.1 → ≥ +6 goal, now also referenced to P1's bar), the W3 winner for AIME — then the full 3-seed paired validation against 3.8-solo on shared items/seeds. Only then is the Track-B sentence utterable. The §5b recorded config (all-3.7 seats + 3.8 judge) enters this queue only if W1 screens positive, exactly as the plan states — its judge half is predicted marginal (9/9), its seat half is what W1 tests.

**Standing constraints:** the 3.8 endpoint is quota-limited and timeout-fragile (13/14 dropped calls in the invalidated AIME run were 3.8) — one preview seat or one escalation target per item, retry-with-backoff, paced against the weekly token quota; never a 3-copy 3.8 panel (0% escalation, proven).

**Failure semantics — pre-registered, because a bounded null is also a Track-B result:** if P9 cannot lower the unanimous-wrong rate, W2's arms cannot shrink it, P3 shows low pool coverage, and P4 shows recall-suppressed self-verification, then the finding is: *the same-provider ceiling on GPQA sits below the family's best solo model, and the residual floor is family-correlated error that no within-provider diversity axis reaches.* That is the strongest evidence-grade justification the parked cross-provider track could ever receive — engineered decorrelation at the top tier as the only remaining lever — and it would be recorded as a findings doc, not a silent burial, per the kill-discipline that produced half this project's value.