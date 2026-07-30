# Prior art and positioning

**Review date: 2026-07-30.** This is the repository's source of truth for what
QuorumQA may and may not claim about novelty. If another document in this repo
contradicts this one, this one is correct and the other should be fixed.

**Every research citation below was fetched from its primary source and verified
on 2026-07-30** (20 sources: 18 fully verified, 2 partial — see §8). Titles,
author lists, dates and venues are as stated on the publisher's own page. No
citation here was reconstructed from memory.

---

## 1. Scope and limitations of this review

This is a **targeted review**, not an exhaustive global novelty search. It
covers the components QuorumQA actually implements: multi-agent debate, council
and peer-review aggregation, same-model vs mixed-model aggregation,
agreement-conditioned adaptive computation, weak-to-strong routing,
LLM-as-judge, and tool-assisted verification. It does not attempt full coverage
of any of those literatures.

**What prompted it.** Several documents in this repo had generalized a narrow
finding from `frontier-oss-model-research.md` — that no *surviving claim in that
report's corpus* addressed orchestration — into claims that no published prior
work existed at all. That inference is invalid: the corpus was frontier-lab
technical reports about **building single models**, never a review of the
multi-agent literature.

**The claim was also self-refuting from this repo's own files.** The repository
cites Self-MoA (arXiv 2502.00674) in eleven places — including as the source of
the *prediction* that its homogeneity trap would occur — and cites Sea AI Lab
(arXiv 2503.20783) as an external refutation of its own reflection-token null.
A project citing external orchestration literature to corroborate its findings
cannot simultaneously claim that literature does not exist.
`frontier-oss-model-research.md` even rated its own orchestration synthesis
*"inferential and rated low"*; downstream docs quoted it as settled fact.

---

## 2. What QuorumQA is

QuorumQA is a cost-asymmetric adjudication cascade on the Qwen family. Three
`qwen3.6-flash` solvers answer a multiple-choice question independently and in
parallel — the **same model**, differentiated by an assigned reasoning lens and
a per-seat temperature (0.3 / 0.6 / 0.9). A 2-of-3 majority is accepted
immediately and costs nothing further. Only a **split** escalates: a Skeptic
attacks the plurality answer's weakest inferential step, a Verifier extracts
checkable claims and grounds them through five MCP tools, and a `qwen3.7-max`
Judge rules on the full transcript. The panel split, the ruling, and any
unresolved dissent are retained as audit artifacts, and escalation rate, false
escalation, overturn frequency and overturn correctness are all measured.

Its contribution is **the integration and empirical characterization of this
specific cascade** — not the invention of debate, councils, routing, judging, or
verification.

---

## 3. Component-level prior art

| QuorumQA component | Established precedent | Overlap | Remaining QuorumQA-specific contribution | Source |
|---|---|---|---|---|
| Multiple instances answer, then argue | **Du et al., "Improving Factuality and Reasoning in Language Models through Multiagent Debate"** (Yilun Du, Shuang Li, Antonio Torralba, Joshua B. Tenenbaum, Igor Mordatch) | Total on the core idea: independent proposals then multi-round debate | We do **not** run multi-round debate; one bounded critique pass, then adjudication | arXiv [2305.14325](https://arxiv.org/abs/2305.14325) |
| Debating agents + a judge | **Liang et al., "Encouraging Divergent Thinking in Large Language Models through Multi-Agent Debate"**, EMNLP 2024 main | Debate-plus-judge topology, adaptive stopping, judge-fairness concerns | Ours is disagreement-*gated* rather than always-on | [2024.emnlp-main.992](https://aclanthology.org/2024.emnlp-main.992/) |
| Confidence-weighted consensus among diverse models | **Chen et al., "ReConcile: Round-Table Conference Improves Reasoning via Consensus among Diverse LLMs"** (Justin Chen, Swarnadeep Saha, Mohit Bansal), ACL 2024 pp. 7066–7085 | Round-table discussion, confidence-weighted consensus | ReConcile uses *diverse* models; our seats are same-family, which is why we measure the homogeneity trap | [2024.acl-long.381](https://aclanthology.org/2024.acl-long.381/) |
| Adversarial argument then adjudication | **OpenAI, "AI safety via debate"** (page byline Dario Amodei, Geoffrey Irving; paper arXiv 1805.00899 lists Irving, Christiano, Amodei) | Conceptual precedent | **Their intended judge is human.** Ours is a model. Do not present these as equivalent | [openai.com/index/debate](https://openai.com/index/debate/) |
| Multi-model judging / council | **Zhao et al., "Language Model Council: Democratically Benchmarking Foundation Models on Highly Subjective Tasks"** (Justin Zhao, Flor Miriam Plaza-del-Arco, Benjamin Genchel, Amanda Cercas Curry), NAACL 2025 | Democratic multi-model judging | Theirs is an *evaluation* council; ours produces answers | [2025.naacl-long.617](https://aclanthology.org/2025.naacl-long.617/) |
| Independent answers → peer review → synthesis | **Karpathy, `llm-council`** | Very close at the application level: independent answers, anonymous cross-ranking, chairman synthesis | Theirs runs all three stages **always**; ours is split-triggered, and only the judge is flagship-priced | [github.com/karpathy/llm-council](https://github.com/karpathy/llm-council) |
| Aggregating multiple model outputs | **Wang et al., "Mixture-of-Agents Enhances Large Language Model Capabilities"** (Junlin Wang, Jue Wang, Ben Athiwaratkun, Ce Zhang, James Zou), 2024-06-07 | Layered aggregation of multiple outputs | MoA describes **no voting rule, no disagreement gate, no escalation** — do not cite it for adjudication or gating | arXiv [2406.04692](https://arxiv.org/abs/2406.04692) |
| Same-model seats; quality-vs-diversity trade-off | **Li et al., "Rethinking Mixture-of-Agents: Is Mixing Different LLMs Beneficial?" (Self-MoA)** (Wenzhe Li, Yong Lin, Mengzhou Xia, Chi Jin), 2025-02-02 | **Direct.** Studies exactly the trade-off our homogeneity trap instantiates, and *predicts* it | Our contribution is the Qwen-specific measurement, not the question | arXiv [2502.00674](https://arxiv.org/abs/2502.00674) |
| Agreement governs inference-time compute | **Aggarwal et al., "Let's Sample Step by Step: Adaptive-Consistency for Efficient Reasoning and Coding with LLMs"** (Pranjal Aggarwal, Aman Madaan, Yiming Yang, Mausam), EMNLP 2023, v1 2023-05-19 | The principle that agreement should govern sampling budget | Not a debate tribunal — single-model self-consistency with early stopping. Our escalation adds critique/verification/adjudication | arXiv [2305.11860](https://arxiv.org/abs/2305.11860) |
| Cheap-model-first, escalate to expensive | **Ong et al., "RouteLLM: Learning to Route LLMs with Preference Data"** (Isaac Ong, Amjad Almahairi, Vincent Wu, Wei-Lin Chiang, Tianhao Wu, Joseph E. Gonzalez, M Waleed Kadous, Ion Stoica), 2024-06-26 | Weak/cheap → strong/costly routing for quality-cost | RouteLLM routes on a *learned preference predictor*; we route on **observed disagreement among already-produced answers** | arXiv [2406.18665](https://arxiv.org/abs/2406.18665) |
| **Debate only when needed** | **SELENE: Selective and Evidence-Weighted LLM Debating for Efficient and Reliable Reasoning** (Akshay Verma, Swapnil Gupta, Deepak Gupta, Prateek Sircar, Siddharth Pillai), EACL 2026 industry track | **Closest research analogue.** Selective debate initiation from confidence-likelihood misalignment and semantic disagreement, skipping debate when unnecessary | **"Argue only when it's worth arguing" is NOT a QuorumQA invention.** Ours triggers on a hard non-majority condition rather than a learned misalignment signal | [2026.eacl-industry.7](https://aclanthology.org/2026.eacl-industry.7/) |
| Cost-aware adversarial adjudication with budgets | **Debate, Deliberate, Decide (D3): A Cost-Aware Adversarial Framework for Reliable and Interpretable LLM Evaluation** (Abir Harrasse, Chaithanya Bandi, Hari Bandi), EACL 2026 long, March 2026 | Role-specialized agents, judging, explicit token budgets, convergence checks, anonymization, cost-accuracy frontier | D3's application is **LLM evaluation** (MT-Bench, AlignBench, AUTO-J), not answer production on GPQA | [2026.eacl-long.392](https://aclanthology.org/2026.eacl-long.392/) |
| Tools validate and revise model output | **Gou et al., "CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing"** (Zhibin Gou, Zhihong Shao, Yeyun Gong, Yelong Shen, Yujiu Yang, Nan Duan, Weizhu Chen), ICLR 2024 | Tool-interactive critique and revision | Ours sits inside an escalation path, not a self-correction loop | arXiv [2305.11738](https://arxiv.org/abs/2305.11738) |
| Draft → verification questions → check → synthesize | **Dhuliawala et al., "Chain-of-Verification Reduces Hallucination in Large Language Models"** (Shehzaad Dhuliawala, Mojtaba Komeili, Jing Xu, Roberta Raileanu, Xian Li, Asli Celikyilmaz, Jason Weston) | Staged verification separated from drafting | Ours distributes the stages across *different agents*, not one model's phases | arXiv [2309.11495](https://arxiv.org/abs/2309.11495) |
| Tool-augmented judging | **Findeis et al., "Can External Validation Tools Improve Annotation Quality for LLM-as-a-Judge?"** (Arduin Findeis, Floris Weers, Guoli Yin, Ke Ye, Ruoming Pang, Tom Gunter), ACL 2025 pp. long-779 | Directly studies tools + LLM judging on factual/math/code | Ours feeds tool findings to the judge as declared ground truth | [2025.acl-long.779](https://aclanthology.org/2025.acl-long.779/) |
| Debate + retrieval + roles + judge | **Courtroom-Style Multi-Agent Debate with Progressive RAG and Role-Switching for Controversial Claim Verification** (Masnun Nuha Chowdhury, Nusrat Jahan Beg, Umme Hunny Khan, Syed Rifat Raiyan, Md Kamrul Hasan, Hasan Mahmud) | Adversarial roles, judge, progressive retrieval, evidence negotiation, multi-judge aggregation | **Directly relevant to `recursive-rag-plan.md`** — that plan's novelty verdict must be read against this | arXiv [2603.28488](https://arxiv.org/abs/2603.28488) |

**MCP is a protocol, not a concept.** QuorumQA may accurately claim genuine MCP
integration. It must not imply that tool-backed checking originated here — see
CRITIC (2023) and Findeis et al. (2025).

---

## 4. Closest systems

- **SELENE (EACL 2026)** — closest *research* analogue. Selective debate
  initiation is published prior art.
- **Karpathy's `llm-council`** — closest *user-facing/open-source* analogue.
  Independent answers, anonymous peer ranking, chairman synthesis. Differs in
  that its three stages always run; ours are split-triggered.
- **D3 (EACL 2026)** — closest *cost-aware debate* analogue, but applied to
  evaluation rather than answer production.
- **Courtroom-style Progressive RAG** — closest *retrieval + debate* analogue;
  the benchmark for `recursive-rag-plan.md`'s claims.
- **RouteLLM** and **Adaptive-Consistency** — adjacent precedents for cost
  routing and agreement-conditioned compute respectively.

### Market analogues (positioning only, NOT scientific validation)

- **Omnicall** — commercial; its own headline is *"One question. Multiple AI
  arguments. One clear verdict."* A direct market analogue.
- **Decision Council** — commercial (partial verification; see §8).
- **Google Co-Scientist** — a domain-specific multi-agent system, first-party
  blog (partial verification).
- **AutoGen** — implementation framework. **Now in maintenance mode**, superseded
  by Microsoft Agent Framework; has an associated paper (arXiv 2308.08155), so
  do not describe it as unpublished.
- **LangGraph** — implementation framework, vendor documentation.

Never cite a product page as evidence that councils improve factual accuracy.

---

## 5. Chronology

QuorumQA's submission shipped **~2026-07-19**. Against that date:

**All sixteen research sources above are PRIOR work** — every one was publicly
available before 2026-07-19. The most recent are the two EACL 2026 papers
(SELENE, D3; proceedings dated March 2026, Rabat) and the Courtroom-style RAG
preprint (arXiv 2603.28488, March 2026) — roughly four months before ship.

**Consequences, both ways:**
- Because everything is prior work, **no "later work" defence is available**.
  Present-tense claims that no published work exists on these components are
  false as of the ship date, not merely as of today.
- Equally, prior availability is **not** evidence QuorumQA copied anything. The
  repo's own build log shows the design arrived by internal iteration. The
  correct framing is "related work we did not cite at the time," not
  "derivative."
- No contemporaneous or later work is relied on anywhere in this document.

---

## 6. Claim boundaries

### Safe to claim
- Three independent solver calls precede any adjudication.
- Seats use assigned reasoning lenses and per-seat temperatures (0.3/0.6/0.9).
- The flagship judge is invoked **conditionally**, on a split, in the shipped
  cascade.
- The architecture separates proposal, critique, tool-assisted checking, and
  adjudication into distinct agents.
- The panel split, judge ruling, and unresolved dissent are recorded.
- Escalation rate, false escalation, overturn frequency and overturn
  correctness are measured.
- Benchmark claims are source-traced and reproducible from committed files.
- Cases where deliberation loses, ties, or wastes compute are reported.
- The null ledger consolidates results under one implementation, one model
  family, one harness, and one token-based cost model.
- **Strongest honest research claim:** an empirical characterization of when
  disagreement-triggered escalation works, fails, or cannot observe unanimous
  errors — including that **61.6% of wrong panel rows are unanimous** and thus
  structurally invisible to a disagreement trigger.

### Requires qualification
- "Diverse solvers" → same model, differing lens and temperature. **Not
  independent error sources**; 61.6% unanimous-wrong is the counter-evidence.
- "The judge rules by arguments, not votes" → a **prompt-level** instruction
  (`JUDGE_SYSTEM`). The transcript shows each seat's letter, so the judge is
  told not to count votes, not prevented from doing so.
- "Fact-checked" → five MCP tools only: `lookup_constant`, `safe_calculate`,
  `sympy_check`, `substitute_check`, `search_corpus`. Constants, calculator,
  symbolic equivalence, substitution, local-corpus retrieval. **Not open-domain
  fact verification.**
- "+4.1 on SuperGPQA-hard" → true, at **~3.0× the tokens** of a single flagship
  call, with **no compute-matched control yet run**.
- Chemistry "+12 pooled, p=0.0059" → true, but heterogeneous: seed 217 +9,
  seed 314 +4, **seed 471 −1**.

### Must not be claimed
- That QuorumQA invented multi-agent debate, councils, or LLM-as-judge.
- That agreement-triggered compute allocation is novel (Adaptive-Consistency
  2023; SELENE 2026).
- That weak-to-strong routing is novel (RouteLLM 2024).
- That tool-backed verification is novel (CRITIC 2023; Findeis 2025).
- That MCP makes the verification *concept* novel.
- That no published multi-agent null results exist.
- That the field is "uncharted."
- That QuorumQA is uniquely transparent or uniquely honest.
- That every mainstream chatbot returns an unreviewed single-model answer.
- That different prompts on one model produce genuinely independent agents.
- That the shipped calculator/constant tools amount to general fact checking.
- That failure to find prior art in one narrow corpus establishes novelty.

Any surviving "first / only / unique / novel / unpublished / no prior" claim
**must state its exact unit, source scope, and date**, or be removed.

---

## 7. Reusable public positioning

> QuorumQA builds on established work in self-consistency, multi-agent debate,
> Mixture-of-Agents, model routing, LLM-as-judge, and tool-assisted
> verification. Its contribution is the particular integration — cheap Qwen
> proposals first, stronger adjudication only after visible disagreement,
> tool-backed checks inside the escalation path, and an audit trail recording
> both corrections and unresolved dissent — together with the measured analysis
> of when that policy helps and when it fails.

**One-sentence research positioning.** QuorumQA is a Qwen-specific, cost-aware
adjudication cascade that tests when disagreement among inexpensive solvers is a
useful signal for escalating to stronger critique, verification, and judgment.

**Short product description.** Three Qwen solvers answer independently. If they
split, a skeptic challenges the disputed reasoning, a verifier checks eligible
claims with tools, and a stronger judge rules — with dissent preserved in the
record.

**Negative-results positioning.** The null ledger is not valuable because
nobody has studied multi-agent failure. It is valuable because QuorumQA records
a large set of failures, controls, costs and methodological corrections under
one reproducible stack, each traced to a committed artifact.

**Tagline.** *An agent society that escalates when its solvers disagree.*
(Preferred over "argues only when it's worth arguing" — we report a substantial
false-escalation rate, and SELENE has prior art on selective initiation.)

---

## 8. Verification record

Fetched and checked 2026-07-30, one independent verification per source.

- **18 of 20 fully verified** against the publisher's own page.
- **2 partial:** Google Co-Scientist and Decision Council — pages resolve and
  content is as described, but neither names authors or a legal entity, and
  Decision Council is a client-rendered single-page app whose `<title>` could
  not be separately confirmed. Both are cited **only** as market/product
  analogues, where this is sufficient.
- **0 could-not-verify, 0 mismatches.** The three sources flagged in advance as
  highest-risk (two EACL 2026 papers and arXiv 2603.28488, all past the
  reviewing model's training cutoff) all resolved to real papers with matching
  authors. D3 was additionally spot-checked directly because an automated
  review step was unavailable for it.

Corrections made to the handoff's own citation strings: Adaptive-Consistency's
title is "**Let's** Sample Step by Step… **for Efficient Reasoning and Coding
with LLMs**" (apostrophe and subtitle were dropped); Mixture-of-Agents has no
confirmed peer-reviewed venue on its arXiv page and should be cited as a June
2024 preprint; AutoGen's status changed to maintenance mode.

**Scope disclaimer.** This is a targeted review of the components QuorumQA
implements. It is **not** proof of an exhaustive global novelty search, and no
claim in this repository should rest on it as though it were.
