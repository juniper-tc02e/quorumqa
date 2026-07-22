# QuorumQA Recursive RAG: retrieval driven by deliberation, recursively improving itself

Written 2026-07-22. Design plan. Like the MoO plan, every choice cites a
measured finding; the verified OSS/technique appendix lands from the
running research pass.

## 1. Why retrieval, and why RECURSIVE — from our own data

The project's central measured weakness is the **unanimous-wrong floor**:
all three cheap solvers confidently agree on the same wrong answer, so
nothing escalates and the tribunal never gets a chance. On SuperGPQA-hard
it is 23% of questions; it is the dominant loss term on every benchmark
where the engine underperforms. Two facts about it are established:

- **It is a knowledge gap, not an effort gap.** More thinking time on the
  same model made chemistry WORSE (smart_gate); a stronger model fixed it
  (chem_flagship_gate, validated). The cheap tier doesn't know things.
- **The known fixes trade money for knowledge.** Tier-swap works
  (flagship_panel: −11.6 → +3.8 on SuperGPQA-hard, 2-seed replicated)
  but costs ~3× a single flagship call. `single-call` fallback gives up
  deliberation's upside entirely.

**Retrieval is the third fix: inject the missing knowledge instead of
buying a bigger model.** If a cheap panel + retrieved evidence can close
even half the gap flagship_panel closes, the economics transform — cheap
tokens + free corpus lookups vs. flagship tokens on every seat.

Why *recursive* rather than one-shot RAG: our deliberation produces,
as a byproduct, exactly the signal that makes retrieval smart. The
Skeptic must name the specific disputed step; the Verifier extracts the
checkable claims; the Judge knows precisely what the disagreement hinges
on. One-shot pre-retrieval has to guess what's relevant from the question
alone; QuorumQA can retrieve AGAIN, better, at each stage, targeted by
the argument state. And one level up, the system's own outputs (validated
verdicts, failed-case post-mortems) become retrievable knowledge for
future questions — retrieval that improves recursively with use. That is
the "eventually improves outputs" property.

## 2. Architecture: the Discovery loop

Tribunal framing on purpose: courts call this **discovery** — evidence
gathering ordered as the dispute sharpens. Four layers, each gated by
measurement before the next is built.

### R1 — Pre-solve retrieval (router-gated, standard RAG)
Before solvers answer, retrieve k passages for the question; solvers see
them as context. Critically: **router-gated per the MoO gap-lens.**
Retrieval is spend-and-context-budget wasted where the panel is already
competent (medicine, 4% unanimous-wrong) and *cannot* help where the
benchmark is retrieval-proof by construction (GPQA-Diamond is literally
"Google-proof" — see §4). Target: high-unanimous-wrong knowledge domains
(hard STEM breadth, law statutes, future fresh-knowledge queries).

### R2 — Disputed-step retrieval (the first recursion)
On a split, the Skeptic's named disputed step and the solvers' divergent
claims form a second, far sharper query set ("heat of formation of X",
"holding of case Y") than the raw question. Retrieve again; results go to
the Verifier, whose tool rack gains a `search_corpus` tool alongside
`safe_calculate`/`lookup_constant` — directly fixing the LEXam diagnosis
(7/9 escalations had ZERO verifier findings because the tools were
science-only; a statute corpus makes the law profile's verifier real).

### R3 — Judge-ordered discovery (the second recursion)
If the Judge finds the record insufficient on the pivotal claim, it may
order ONE more targeted retrieval round (bounded: one order, k small)
before ruling — the analog of reopening discovery. Bounded because the
qwen38_judge null result showed judge-side capability is not the
binding constraint; this exists for the narrower case where the judge
can articulate exactly what evidence would settle the split.

### R4 — Self-improving corpus (the outer recursion)
Two internal sources join the index, growing with use:
- **Case law** (MoO §5.2): past deliberation verdicts, retrieved by
  similarity — router features first, judge precedent after validation.
- **Knowledge cards:** when a validated outcome reveals the panel lacked
  a fact (a unanimous-wrong case whose correct answer is later known),
  a post-mortem writes a short sourced note ("common misconception: X;
  actually Y because Z") into the card index. Future similar questions
  retrieve it. **Guardrails, non-negotiable:** cards are written only
  from outcomes with verified ground truth; every card carries
  provenance; cards are versioned and auditable; and benchmark-mode runs
  never read cards derived from the same benchmark family (see §4).

## 3. Retrieval stack (v1 posture, pending verified appendix)

- **Index:** hybrid BM25 + dense embeddings + reranker as the baseline —
  the fancy indexes (recursive-summary trees, graph RAG) must beat this
  baseline in OUR eval before earning their build cost (same discipline
  as everywhere: the research pass pins current evidence on when they
  do). Local, open-source, no managed services.
- **Corpora v1:** Wikipedia dump (broad STEM breadth — precisely the
  SuperGPQA gap), plus an open-license scientific corpus per the research
  pass; law adds a statute corpus for the LEXam retry; agent tasks add
  tool/docs corpora later.
- **All patterns must work with hosted APIs** — techniques requiring
  trained special tokens or RL-trained retrieval policies are
  adapt-as-pattern or skip (the research pass sorts these).

## 4. The integrity firewall (extends the memory firewall)

1. **Never index benchmark-derived content.** No answer keys, no
   benchmark question dumps, no pages scraped from the benchmark's own
   repo/paper. Index provenance is documented per corpus snapshot.
2. **Labeled numbers.** Every reported result states retrieval ON/OFF and
   the corpus snapshot ID. A RAG-assisted score is never presented beside
   a non-RAG baseline as if same-mode.
3. **GPQA stays the honesty control.** GPQA-Diamond is constructed to be
   search-proof; the EXPECTED result of RAG there is ≈no change. We run
   it anyway: if RAG "improves" GPQA materially, the first hypothesis is
   contamination, not genius — that's a tripwire, and it also tests the
   router's ability to skip retrieval where it can't pay.
4. **R4 cards from verified outcomes only,** provenance-tracked, and
   benchmark-mode never reads same-family cards (a card learned from
   SuperGPQA seed 42 must not serve SuperGPQA seed 123 — that's
   answer-leakage laundering, firewalled by tagging cards with their
   source family).

## 5. Evaluation design (the bets, stated before building)

Primary probe: **SuperGPQA-hard**, because it has the three calibrated
reference points on identical items: cheap 67.9 / flagship-solo 79.5 /
flagship-panel 83.3. The economic question, pre-registered:

- **Bet 1 (R1):** cheap-panel + pre-solve RAG lands materially above
  67.9 by cutting the 23% unanimous-wrong floor. Success threshold to
  keep building: ≥ +4 on the same-items intersection, 1 seed; then the
  3-seed bar.
- **Bet 2 (R2):** disputed-step retrieval raises overturn-correct rate
  and cuts false escalations vs R1-only, measurable on the escalated
  subset (gate-replay style A/B on saved splits keeps this cheap).
- **Bet 3 (cost):** cheap+RAG reaches ≥half of flagship_panel's lift at
  ≤⅓ of its cost — the router then gets a third option between cheap and
  flagship tiers.
- **Null controls:** GPQA (expect ≈0, tripwire per §4), MedQA (expect ≈0
  — 4% floor leaves nothing to fix; confirms the router should skip).
- All the standing discipline applies: matched baselines, drop-bias
  checks, same-items intersections, 3-seed validation, honest negatives.

Reasoning emphasis note: RAG attacks the knowledge term of the loss, not
the reasoning term — and that's the point. Our reasoning machinery
(tribunal, 78-85% overturn-correct everywhere measured) is already the
strong part; it's been starved by knowledge gaps upstream. Feeding it
better evidence is how the reasoning shows. The parallel reasoning-lever
workstream (deliberation depth, panel diversity, qwen3.8-tier panels)
continues in the loop alongside this plan.

## 6. Phasing

- **G0 — Corpus + index + `search_corpus` MCP tool.** Wikipedia snapshot,
  hybrid+rerank, offline tests; tool wired into the Verifier rack behind
  a flag. No benchmark claims yet.
- **G1 — R1 pilot on SuperGPQA-hard** (Bet 1). Kill/continue on the +4
  threshold.
- **G2 — R2 disputed-step retrieval** (Bet 2), gate-replay A/B first,
  then live.
- **G3 — Law-profile retry:** statute corpus + R2 on LEXam — tests
  whether the tribunal's value returns with domain-appropriate evidence
  (the standing LEXam diagnosis).
- **G4 — R3 judge discovery + R4 case-law/knowledge-cards** (with the §4
  firewall built as assertions, same as the memory firewall).
- **G5 — Router integration:** retrieval becomes a profile dimension in
  the MoO registry (`+rag` variants), calibration memory learns where it
  pays.

## Appendix A — verified technique/OSS landscape (verified 2026-07-22, two passes)

First pass: adversarial 3-vote verification (cut off mid-run by a session
limit after 5 claims survived). Second pass: targeted primary-source
verification of every remaining load-bearing claim. All quotes checked
against live sources.

### Adopt-now
- **Hybrid BM25 + dense + reranker as the v1 index.** Systematic
  evaluation (arXiv 2502.11371) confirms vanilla/hybrid RAG beats
  GraphRAG-family on single-hop detail QA (NQ: 64.78 F1 vs 63.01) — and
  QuorumQA's unanimous-wrong gaps are fact-lookup shaped, not multi-hop.
  GraphRAG wins only multi-hop/global-summary, at prohibitive indexing
  cost (Microsoft's own words; LazyGraphRAG is the watchlist item if
  multi-hop traffic ever grows — vector-RAG-parity indexing cost, MSR
  primary source).
- **Reranker: Qwen3-Reranker-4B** (Apache-2.0, 32k context, 69.76 MTEB-R,
  June 2025, actively adopted). Fallback: BGE-reranker-v2-m3 (Apache-2.0,
  mature, integrated everywhere).
- **Corpora v1: Wikipedia via HF `wikimedia/wikipedia`** (CC-BY-SA/GFDL,
  turnkey parquet) + **peS2o v2** (ODC-BY, ~39M scientific docs — the open
  science corpus §3 called for). **Medicine caveat verified:** raw PubMed
  abstracts are NOT blanket-open (NLM: publishers/authors may hold
  copyright) — use the **PMC Open Access commercial-use subset**
  (CC0/CC-BY family) if a medicine corpus is added.

### Adapt-as-pattern (mechanisms don't transfer to hosted APIs; shapes do)
- **Dynamic-RAG taxonomy** (SIGIR 2025 tutorial, arXiv 2506.06704):
  when/what-to-retrieve is decided by trained special tokens OR external
  state monitoring — hosted APIs force the external-monitor family, which
  is exactly what the Discovery loop is (deliberation state = the monitor).
- **DRAG, Debate-Augmented RAG** (ACL 2025 main, arXiv 2505.18581,
  training-free) — the closest published relative; see novelty verdict.
- **HF Open Deep Research** (smolagents): proof a prompting-only search
  agent works — 55% GAIA vs 67% for the trained product it reimplements.
  Realistic ceiling-setting for orchestration-only agentic search.

### Requires-training — skip
- **Self-RAG** (trained reflection tokens), **FLARE** (decode-time
  logprobs), **DRAGIN** (attention/entropy internals — training-free but
  needs model internals hosted APIs don't expose).
- **Search-R1, R1-Searcher, ReSearch, DeepResearcher** — all verified as
  RL-training methods on the base model (primary sources quoted in the
  verification report). Query-planning shapes copyable; methods not.

### Novelty verdict on the Discovery shape
DRAG retrieves for EVERY question (no competence-gated router skip), its
debate argues about retrieval-QUERY adequacy rather than the object-level
claim in dispute, its rounds are fixed (r=3; the paper names fixed
response-debate rounds as its own limitation), and it has no
self-improving corpus. QuorumQA's Discovery shape — retrieval gated by
domain-competence routing (R1), queries derived from the Skeptic's named
disputed step and the Verifier's checkable claims (R2), a judge-ordered
bounded reopening on the pivotal claim (R3), and a provenance-tracked,
family-firewalled case-law/knowledge-card corpus (R4) — **appears
genuinely novel across both research passes.** Worth writing up properly
once G1-G2 produce measured results.

### Contamination standard: none exists — §4 is ahead of the field
Verified: the decontamination literature targets *pretraining* corpora;
no adopted community standard exists for excluding benchmark-derived
documents from *retrieval indexes* (closest: one recent leakage-free-
benchmark-generation paper, arXiv 2605.08838 — a proposal, not a norm).
The §4 firewall is therefore a contribution, not a copy; state that
plainly if this work is ever published.

### DRAG's numbers, for calibration of expectations
Llama-3.1-8B-Instruct, Wikipedia corpus: multi-hop wins (+6 EM
2WikiMultihopQA, +3 HotpotQA vs best baselines) but LOSES to
retrieval-optimized baselines on single-hop (its own "problem drift"
admission). Lesson for our bets: debate-driven retrieval earns its keep
on contested/multi-step questions — reinforcing the R2-on-splits design
(retrieve harder exactly where the panel disagrees) over
always-on-everything.
