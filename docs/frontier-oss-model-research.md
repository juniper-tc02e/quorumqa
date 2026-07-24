# Frontier open-source LLM research — findings digest (2026-07-24)

*Produced by the deep-research harness: 5 search angles, ~15 primary sources
fetched, 3-vote adversarial verification per claim (2/3 refutes kills), cited
synthesis. 104 agents, 6.3M tokens. Confidence tags are the harness's.*

## Executive summary

As of mid-2026 the strongest documented open-weight frontier models are Moonshot's Kimi K2 (1T-total / 32B-active MoE, positioned as an agentic "non-thinking" tool-use solver) and DeepSeek's V3 line, now extended to V3.2 / V3.2-Speciale (685B MoE with DeepSeek Sparse Attention and RL-scaled reasoning the lab reports as GPT-5-class). The most transferable cross-lab thread is reinforcement learning with verifiable / rule-based rewards: DeepSeek-R1-Zero showed reasoning and self-correction emerge from pure RL on a base model with NO supervised fine-tuning (AIME-2024 pass@1 15.6%→71.0%, and 86.7% with cons@64 majority voting), and a wave of open GRPO successors — DAPO, GSPO, VAPO, and the minimalist "Lite PPO" — refined the recipe while proving these techniques are strongly setup-dependent, not universally beneficial. Concrete, primary-sourced systems findings round it out: MuonClip/QK-clip training stability, DSA sparse attention for long-context/KV efficiency, and GSPO's fix for MoE routing-induced RL instability. The single biggest gap for the orchestration use-case is that NONE of the verified claims cover multi-agent ensembling, mixture-of-agents, LLM-as-judge, or self-preference bias — so the orchestration implications (final finding) are inferred from single-model results, chiefly that verifiable-reward verification tools and majority-vote self-consistency are well-supported while reflective-token counts are NOT a reliable correctness signal.

## Verified findings

### 1. [HIGH] Kimi K2 (Moonshot AI, July 2025) is a 1T-total / 32B-active-parameter Mixture-of-Experts model: 384 experts (8 routed + 1 shared), 61 layers (incl. 1 dense), Multi-head Latent Attention (MLA), SwiGLU, 64 heads, 160k vocab, 128k context via YaRN — the largest open-weight MoE at release, exceeding DeepSeek-V3's 671B total; architecturally a scaled DeepSeek-V3-family design (experts 256→384).

**Evidence.** Two primary sources agree verbatim (report: 1.04T total / 32B active, rounded to '1 trillion'; card: 384 experts, 8+1, 61 layers, MLA, SwiGLU). Architecture specs, not benchmarks. Modified-MIT license.

**Sources:**
- Kimi K2: Open Agentic Intelligence, Kimi Team/Moonshot AI, Jul 2025 — https://arxiv.org/pdf/2507.20534
- Official model card — https://github.com/moonshotai/kimi-k2 (mirror: huggingface.co/moonshotai/Kimi-K2-Instruct)

*Verification vote: 3-0 (merged claims 0 and 3)*

### 2. [HIGH] Kimi K2 was pre-trained on 15.5T tokens with zero loss spikes using the MuonClip optimizer — Muon plus a novel QK-clip technique that rescales query/key projection matrices after optimizer steps to bound attention-logit explosion, the instability plain Muon caused at scale. A concrete, transferable training-stability recipe.

**Evidence.** Abstract and README verbatim; report Fig. 3 shows an unsmoothed, non-subsampled loss curve with no spikes across the full run. Caveat: 'zero loss spike' is a first-party self-report (not independently reproducible); the QK-clip mechanism itself is genuinely described and portable to other training stacks.

**Sources:**
- Kimi K2 Technical Report, Moonshot AI, Jul 2025 — https://arxiv.org/pdf/2507.20534
- Model card — https://github.com/moonshotai/kimi-k2

*Verification vote: 3-0 (merged claims 1 and 4)*

### 3. [HIGH] K2 is post-trained via a large-scale agentic data-synthesis pipeline plus a joint RL stage over real and synthetic environments, positioned as a 'non-thinking' agentic tool-use solver (not a long-CoT reasoner); ships Base + Instruct; reports SOTA among open-source non-thinking models — SWE-bench Verified 65.8, Tau2-Bench 66.1, GPQA-Diamond 75.1, AIME-2025 49.5, all without extended thinking.

**Evidence.** Near-verbatim from abstract/model card; 'SOTA among non-thinking models' is a correctly-scoped self-report, not overall SOTA. A later long-CoT variant, Kimi-K2-Thinking, appears only in verifier notes (Reported, not primary-confirmed here). No surviving primary claim confirms any 'Kimi K3'.

**Sources:**
- Kimi K2: Open Agentic Intelligence, Kimi Team, Jul 2025 — https://arxiv.org/pdf/2507.20534
- Hugging Face moonshotai/Kimi-K2-Instruct and Kimi-K2-Base cards

*Verification vote: 3-0 (merged claims 2 and 5)*

### 4. [HIGH] DeepSeek-R1-Zero acquires strong reasoning by applying GRPO RL directly to DeepSeek-V3-Base with NO supervised fine-tuning — establishing that verifiable-reward RL alone can incentivize reasoning and self-correction. AIME-2024 pass@1 rose 15.6%→71.0% over training, and cons@64 majority voting lifted it further to 86.7% (a direct primary datapoint that sampling-based aggregation substantially beats single-sample accuracy). 'No SFT' is scoped to R1-Zero; full R1 uses cold-start SFT.

**Evidence.** Both 3-0; top-tier (peer-reviewed Nature) primary source. Table 2 gives 15.6→71.0 pass@1 and 86.7 cons@64 verbatim; 'we bypass the conventional SFT phase before RL training' quoted. Debate exists on HOW emergent the reasoning is (some latent in base), not on the no-SFT mechanism.

**Sources:**
- DeepSeek-R1 incentivizes reasoning in LLMs through RL, Nature s41586-025-09422-z, 17 Sep 2025 (peer-reviewed) — https://www.nature.com/articles/s41586-025-09422-z
- DeepSeek-R1, arXiv 2501.12948, Guo et al., Jan 2025 — https://arxiv.org/pdf/2501.12948

*Verification vote: 3-0 (merged claims 6 and 9)*

### 5. [HIGH] DeepSeek-V3.2 (2 Dec 2025; 685B MoE; MIT) introduces DeepSeek Sparse Attention (DSA) — a lightning-indexer plus fine-grained top-k token selection that cuts attention complexity from O(L^2) to O(Lk) while preserving long-context performance. It is implemented on top of MLA (it succeeds MLA chronologically in the V3 line rather than replacing it).

**Evidence.** 3-0; abstract near-verbatim, corroborated by model card and multiple secondary tours. Mechanism confirmed; the efficiency magnitude is Reported (not independently benchmarked in the abstract). Directly relevant to KV-cache compression / long-context serving.

**Sources:**
- DeepSeek-V3.2: Pushing the Frontier of Open LLMs, DeepSeek-AI, 2 Dec 2025 — https://arxiv.org/abs/2512.02556
- HF deepseek-ai/DeepSeek-V3.2-Exp card; S. Raschka V3→V3.2 tour

*Verification vote: 3-0 (claim 10)*

### 6. [HIGH] DAPO (ByteDance Seed + Tsinghua, Mar 2025; NeurIPS 2025) is a fully open-sourced at-scale RL system reaching 50 points on AIME-2024 with a Qwen2.5-32B base (beating R1-Zero-Qwen-32B's 47 with ~50% fewer steps), and — unlike OpenAI o1 / DeepSeek R1, which withheld details — discloses four techniques: Clip-Higher, Dynamic Sampling, Token-Level Policy-Gradient Loss, and Overlong Reward Shaping. A reproducible open RL recipe (code on verl + curated dataset).

**Evidence.** 3-0; primary + peer-reviewed + open code/dataset. All elements map to abstract text; explicitly targets the o1/R1 reproducibility gap.

**Sources:**
- DAPO: An Open-Source LLM RL System at Scale, arXiv 2503.14476, Mar 2025 — https://arxiv.org/abs/2503.14476
- Repo BytedTsinghua-SIA/DAPO; NeurIPS 2025 poster

*Verification vote: 3-0 (merged claims 13 and 14)*

### 7. [HIGH] GSPO (Qwen/Alibaba, Jul 2025) defines the importance ratio at the sequence level (length-normalized) and clips/rewards/optimizes whole sequences instead of GRPO's per-token weights — fixing GRPO's high-variance gradient noise that accumulates over long sequences. It also stabilizes RL of MoE models, eliminating the Routing Replay workaround: after each gradient update ~10% of activated experts differ between old and new policy (measured on Qwen3-30B-A3B), which destabilizes token-level GRPO but not GSPO's sequence-level ratios.

**Evidence.** 3-0; both the mechanism and the exact ~10% figure are verbatim in §5.3. Highly relevant to RL-tuning MoE models, the dominant open-weight architecture.

**Sources:**
- Group Sequence Policy Optimization, Qwen team (Zheng et al.), arXiv 2507.18071v2, Jul 2025 — https://arxiv.org/html/2507.18071v2
- Qwen blog — qwenlm.github.io/blog/gspo

*Verification vote: 3-0 (merged claims 15 and 16)*

### 8. [HIGH] VAPO (ByteDance Seed, Apr 2025), a value-based (PPO-derived) framework, reaches SOTA AIME-2024 = 60.4 on a Qwen2.5-32B base, beating value-free R1-Zero-Qwen-32B (47) and DAPO (50) by >10 points, by targeting three failure modes of value-based long-CoT RL: value-model bias, heterogeneous sequence lengths, and sparse rewards — arguing value-based RL can beat critic-free GRPO/DAPO in this regime.

**Evidence.** 3-0; abstract verbatim; arithmetic checks (gaps 13.4 and 10.4); apples-to-apples Qwen2.5-32B base; DAPO=50 baseline corroborated by the DAPO paper. 'SOTA' is scope-bounded (value-based paradigm / Qwen-32B) self-report.

**Sources:**
- VAPO: Efficient and Reliable RL for Advanced Reasoning Tasks, ByteDance Seed, arXiv 2504.05118, Apr 2025 — https://arxiv.org/abs/2504.05118

*Verification vote: 3-0 (merged claims 17 and 18)*

### 9. [HIGH] A minimalist critic-free 'Lite PPO' — just two tricks on vanilla PPO loss (advantage normalization using group-level mean + batch-level std, plus token-level loss aggregation) — consistently beats the more elaborate GRPO and DAPO on Qwen3-4B/8B base + math benchmarks. The paper's broader thesis ('Tricks or Traps?'): most RL techniques are strongly sensitive to setup (model type, data distribution, reward mechanism) and must be conditioned on it, not applied by default — challenging over-engineered RL pipelines.

**Evidence.** 3-0 across three underlying claims; empirical anti-over-engineering study. Group-mean/batch-std reduces gradient magnitudes, preventing excessive policy updates (the paper's own stated mechanism). Scope caveat: Qwen base models on math benchmarks; 'conclusions may vary across LLM families' and token-level loss helps base but not aligned models.

**Sources:**
- Part I: Tricks or Traps? A Deep Dive into RL for LLM Reasoning, Alibaba/ROLL-Qwen, arXiv 2508.08221, Aug 2025 — https://arxiv.org/pdf/2508.08221
- OpenReview (peer-reviewed)

*Verification vote: 3-0 (merged claims 19, 20, 21)*

### 10. [HIGH] Theoretically, GRPO with verifiable rewards is equivalent to a KL-regularized contrastive loss (contrastive samples drawn from the old policy) with asymmetric weighting: when old-policy success p>0.5 it penalizes wrong answers more than it rewards correct ones; when p<0.5 the reverse. And GRPO provably amplifies success — at the fixed point p*>p_ref for all beta>0 when base success <=0.5, and only under a specific beta condition when base success already >0.5.

**Evidence.** 3-0; Theorem 3 verbatim, standardized-advantage algebra verified (A=+sqrt((1-p)/p) for correct, -sqrt(p/(1-p)) for wrong). Idealized mean-field fixed-point model; Thm 4 gives only local convergence. Explains WHY verifiable-reward RL reliably works.

**Sources:**
- RL with Verifiable Rewards: GRPO's Effective Loss, Dynamics, and Success Amplification, Y. Mroueh, IBM Research, arXiv 2503.06639, Mar 2025 — https://arxiv.org/html/2503.06639v1
- ICML 2026 poster

*Verification vote: 3-0 (merged claims 22 and 23)*

### 11. [MEDIUM] R1-Zero's RL uses GRPO (critic-free, group-relative advantage) with purely outcome-based, rule-based/verifiable rewards — final-answer correctness (math answer-matching, code unit tests) plus a format reward — imposing no constraints on the reasoning trace itself. Adopter caveat: this is precise for R1-Zero/the reasoning stage; full R1 adds a trace-level language-consistency reward and uses neural preference reward models for non-reasoning data.

**Evidence.** 2-1 split vote. Core verbatim-supported ('reward signal is only based on the correctness of final predictions...without imposing constraints on the reasoning process'). The absolute phrasing holds strictly only for R1-Zero, hence medium. A stronger sibling claim that R1 avoids neural reward models entirely was REFUTED (1-2).

**Sources:**
- DeepSeek-R1, Nature s41586-025-09422-z, Sep 2025 — https://www.nature.com/articles/s41586-025-09422-z
- arXiv 2501.12948

*Verification vote: 2-1*

### 12. [MEDIUM] During R1-Zero RL, self-correction/reflection strengthens, marked by a sudden rise in reflective tokens (e.g. 'wait' virtually absent early, appearing sporadically at steps 4,000–7,000, surging after ~step 8,000) — the 'aha moment.' The token-rise is confirmed; the 'spontaneous self-evolution' interpretation is contested (Sea AI Lab: reflective keywords pre-exist in base models, and 'wait'-type tokens can be superficial and do NOT reliably track answer correctness).

**Evidence.** 2-1 split; verifier medium. Directly relevant to orchestration design: reflective-token frequency is NOT a valid correctness/confidence proxy for disagreement-escalation heuristics.

**Sources:**
- DeepSeek-R1, Nature s41586-025-09422-z, Sep 2025 — https://www.nature.com/articles/s41586-025-09422-z
- Contra: Understanding R1-Zero-Like Training / OAT-Zero, Sea AI Lab, arXiv 2503.20783

*Verification vote: 2-1*

### 13. [MEDIUM] DeepSeek-V3.2 scales post-training RL under a 'Scalable RL Framework' and adds a 'Large-Scale Agentic Task Synthesis Pipeline' (reported ~1,800+ environments, ~85k prompts) integrating reasoning into tool-use. The lab reports V3.2 as comparable to GPT-5 and a high-compute variant V3.2-Speciale as surpassing GPT-5, matching Gemini-3.0-Pro reasoning, and taking 2025 IMO + IOI gold (reported 35/42 on IMO).

**Evidence.** Method existence 3-0 / Confirmed-in-paper; but the frontier-comparison benchmarks and IMO/IOI results are first-party self-reports (tagged Reported), partly marketing-framed and not independently verified — hence medium. Improvement magnitudes for the synthesis pipeline are vague ('substantial').

**Sources:**
- DeepSeek-V3.2, DeepSeek-AI, Dec 2025 — https://arxiv.org/abs/2512.02556
- HF deepseek-ai/DeepSeek-V3.2 and DeepSeek-V3.2-Speciale

*Verification vote: 3-0 on faithfulness-to-source (merged claims 11 and 12); numbers self-reported*

### 14. [LOW] Implications for a solver-panel + judge-escalation + retrieval/verification orchestration layer (SYNTHESIS, inferred from single-model results): (a) STRONGLY supported — deterministic verifiable checks (unit tests, answer-matching, CAS) are the reliable arbiter, mirroring rule-based RL rewards, and majority-vote self-consistency materially beats single samples (R1-Zero cons@64 86.7% vs 71.0% pass@1); (b) CAUTION — reflective-token counts ('wait') do NOT track correctness, so do not use them as a disagreement/confidence signal; (c) the strongest genuinely decorrelated cross-vendor deliberation candidates are Kimi K2 (non-thinking agentic tool-use), DeepSeek-R1/V3.2/-Speciale (long-CoT reasoners, MIT), and Qwen3 (RL-methodology source) — different architectures and training objectives make a mixed panel more diverse than same-model self-ensembling.

**Evidence.** Inferential, not a directly-sourced claim. Its inputs are primary-sourced and high-confidence (cons@64 self-consistency numbers, verifiable-reward efficacy, aha-token unreliability), but the leap to multi-agent/ensemble design is unvalidated by the surviving evidence set — no verified claim covers mixture-of-agents, LLM-as-judge, self-preference bias, or debate. Flagged low.

**Sources:**
- Derived from Nature s41586-025-09422-z; arXiv 2501.12948; 2507.20534; 2512.02556; 2503.06639

*Verification vote: N/A (synthesis)*

## Caveats (verification harness)

MAJOR GAP: No surviving claim addresses the entire multi-agent section of the brief — ensembling, mixture-of-agents (Self-MoA vs mixed-MoA), model routing, LLM-as-judge, self-preference bias, or debate/deliberation, nor the conditions under which combining models helps vs hurts. The orchestration synthesis (final finding) is therefore inferential and rated low. SCOPE GAPS: DeepSeek-V3's base architecture (MLA internals, fine-grained/shared experts, aux-loss-free load balancing, Multi-Token Prediction, FP8 mixed-precision training) is NOT covered by any surviving standalone claim — only referenced obliquely (Kimi K2 adopts MLA; DSA succeeds MLA in the V3 line). Treat V3 internals as out of verified scope here. KIMI K3: not confirmed by any surviving primary source; the only 'signal' is local tooling naming 'kimi-k3/kimi-k2.6', which is not a citable source — status Unverifiable. Kimi-K2-Thinking (a long-CoT variant) appears only in verifier notes = Reported, not primary-confirmed. SELF-REPORTED / MARKETING-FRAMED: DeepSeek-V3.2 and V3.2-Speciale's GPT-5 / Gemini-3.0-Pro comparisons and IMO/IOI gold are lab-reported and not independently verified; Kimi's 'zero loss spike' and 'SOTA among non-thinking' are first-party self-reports. SPLIT VOTES: the GRPO-reward-only claim and the aha-moment claim each passed 2-1; the 'spontaneous emergence' interpretation of the aha moment is actively contested (Sea AI Lab). TRANSFER RISK: DAPO/GSPO/VAPO/Lite-PPO are training-time methods for BUILDING models (mostly on Qwen/DeepSeek bases, math benchmarks) and are only indirectly relevant to an inference-time orchestration layer; their results may not transfer to heterogeneous panels. TIME-SENSITIVITY: V3.2 is very recent (Dec 2025) and the open-weight frontier moves fast; this is a mid-2026 snapshot.

## Refuted / killed in verification

- R1 uses rule-based (verifiable) rewards only — accuracy rewards from deterministic checks (math answer boxes, code compiler/test cases) plus format rewards — and deliberately avoids neural outcome/process reward models because they induce reward hacking at scale. This is the transferable signal for a verification-tool-driven orchestration layer. — https://arxiv.org/pdf/2501.12948

## Open questions

- Does Kimi K3 exist as a released model? No citable primary source appears among the verified claims — release status, MoE specs/param counts, license, and benchmarks all need confirmation before any adoption decision (the only reference is unverifiable local tooling).
- When does combining models actually help vs hurt for an orchestration panel — specifically Self-MoA (repeated samples of one strong model) vs mixed-MoA (diverse models), how large is self-preference bias when a model judges its own or same-family outputs, and does debate/deliberation beat simple majority voting? This core orchestration question is entirely unaddressed by the verified evidence.
- Do the RL-for-reasoning gains (GRPO/DAPO/GSPO/VAPO/Lite-PPO) and the self-consistency boost transfer beyond Qwen/DeepSeek bases and math benchmarks to the heterogeneous, multi-vendor panels an orchestration layer would actually run?
- What are DeepSeek-V3's concrete MLA / MoE-routing / MTP / FP8 specifications (uncovered here), and are V3.2 / V3.2-Speciale's frontier-competitor benchmarks and IMO/IOI results independently reproducible rather than lab-reported?

## Source list

-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 
-  — 


---

## Implications for QuorumQA (orchestration-layer absorption)

*Written by the orchestrator, mapping the verified findings above onto our
own committed record. Each point cites the finding it rests on and the
QuorumQA result it touches.*

### 1. External support for what we already do
- **Majority-vote self-consistency is real, and the effect size is large.**
  R1-Zero's cons@64 lifts AIME-2024 from 71.0% pass@1 to **86.7%** (primary,
  Nature 2025). This is independent, primary-source validation of QuorumQA's
  voting core and of **W3 (SC@N + equivalence clustering)** — sampling-based
  aggregation materially beats a single sample. Our grade-equivalence
  clustering is arguably a *better* selector than raw majority vote (it merges
  `\frac12` and `0.5` before counting), which the finding implies should
  widen the margin, not shrink it.
- **Deterministic verifiable checks are the reliable arbiter.** The RL-for-
  reasoning literature rewards *only* rule-based/verifiable signals (answer-
  matching, unit tests) and DeepSeek deliberately avoided neural reward models
  to dodge reward-hacking (that specific "avoids RMs entirely" claim was
  softened to 2-1 in verification, but the verifiable-reward core is HIGH-
  confidence). This is direct external support for **W1-B (sympy_check /
  substitute_check)**, the **Verifier's `safe_calculate`/`lookup_constant`
  tools**, and **`math_grade`** — computation-grounded verification is the
  decorrelated channel the whole field leans on.

### 2. A finding that independently confirms one of our cautions
- **Reflective-token counts do NOT track correctness.** The "aha moment" is
  real as a token-frequency rise but its "spontaneous self-correction"
  reading is contested (Sea AI Lab: "wait"-type tokens pre-exist in base
  models and don't reliably predict answer correctness). This is a *direct,
  external corroboration* of our **W5 wrongness-predictor** result: hedge/
  reflection-style trace features landed in the BAND (AUC 0.625) and F3's
  distribution-feature upgrade was NEGATIVE. Two independent roads to the same
  place — do not build a confidence/escalation gate on reflection-word counts.

### 3. The biggest strategic takeaway: our orchestration work is on
### genuinely uncharted ground
- The harness's flagged **MAJOR GAP**: *no* verified frontier-lab publication
  covers multi-agent ensembling, mixture-of-agents (Self-MoA vs mixed-MoA),
  LLM-as-judge, self-preference bias, or debate/deliberation. The labs
  publish on *building single models*, not on *orchestrating panels of them*.
  Consequences for us, both real:
  - **Caution:** we cannot lean on external validation for the panel/tribunal/
    routing thesis — our own 3-seed empirical record IS the evidence base.
    Keep the honest-negative discipline; there is no published prior to fall
    back on.
  - **Opportunity:** the same-provider-scaling questions we've been measuring
    (Self-MoA-like `flagship_panel`, the homogeneity trap, the P4 self-
    preference audit, P(wrong|unanimous)) are largely *unpublished territory*.
    Our results are a genuine contribution, not a re-derivation.

### 4. Track-B (cross-vendor) candidate assessment, if ever revived
Cross-vendor is parked, but the research names the strongest OSS deliberation
candidates and — importantly — their *decorrelation* value:
- **Kimi K2** (Moonshot, 1T-total/32B-active MoE, modified-MIT): explicitly a
  **"non-thinking" agentic tool-use solver**, not a long-CoT reasoner. That
  training-objective difference from a reasoning model is exactly the
  *engineered decorrelation at the top tier* our Track-B logic wants — a K2
  seat would fail differently from a DeepSeek-R1 seat by construction.
- **DeepSeek-R1 / V3.2 / V3.2-Speciale** (MIT): long-CoT reasoners; V3.2 adds
  DeepSeek Sparse Attention and lab-reported (NOT independently verified)
  GPT-5-class results. The reasoning counterpart to K2's non-thinking solver.
- A cross-vendor panel of **{Kimi K2 non-thinking, DeepSeek-R1 thinking, Qwen
  flagship}** would be three genuinely different lineages AND two different
  inference modes — the maximum decorrelation available in open weights.
  Both are MIT-family licensed, both OpenAI-compatible-servable, so the
  provider-agnostic client (parked build) is the only blocker.

### 5. What is NOT actionable / must not be over-absorbed
- **"Kimi K3" is unconfirmed.** No citable primary source; the only "signal"
  is local tooling named `kimi-k3/kimi-k2.6`, which is not a source. Treat K3
  as non-existent until a real model card appears. The user's original
  question named K3 — the honest answer is *it isn't documented; K2 (+ a
  Reported Kimi-K2-Thinking variant) is what exists*.
- **DeepSeek V3.2-Speciale's frontier-beating / IMO-gold numbers are lab
  self-reports**, not independently reproduced — do not cite them as fact.
- **GRPO/DAPO/GSPO/VAPO are model-BUILDING (training-time) methods.** They are
  only *indirectly* relevant to an inference-time orchestration layer; their
  math-benchmark, Qwen/DeepSeek-base results may not transfer to a
  heterogeneous panel. We are not fine-tuning — so these inform *why*
  verifiable rewards work, not a lever we can run.

### 6. Net: does this change the plan?
No re-plan needed — it *reinforces* the current one. W1-B (computational
verification), W3 (SC@N voting), and the W5 caution are all independently
supported. The one net-new item worth queuing: **if Track B is revived, Kimi
K2 is the single best first cross-vendor seat to add** (non-thinking solver =
maximal decorrelation, permissive license, cheap to serve), and the provider-
agnostic client is its only prerequisite. Logged, not scheduled.
