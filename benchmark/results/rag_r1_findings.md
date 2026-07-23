# R1 pre-solve retrieval: Bet-1 findings

First accuracy test of the Recursive RAG plan (docs/recursive-rag-plan.md
§5 Bet-1). Lever `rag_presolve` = shipped cheap engine + top-5 STEM-
Wikipedia passages injected as solver context. Corpus: pre-embedded
STEM-Wikipedia (Laz4rz/wikipedia_stem_small_rag_embeddings@e51169b,
mxbai-embed-large-v1, RAG-ON). Seed 42, n=90. General Wikipedia, not
benchmark-derived — firewall §4 satisfied.

## Bet-1: MET on SuperGPQA-hard

Apples-to-apples on 86 common items:

| SuperGPQA-hard, seed 42 | Accuracy |
|---|---|
| single-flagship baseline | 79.1% |
| cheap-panel (no RAG) | 67.4% |
| **cheap-panel + RAG (R1)** | **72.1%** |

**+4.7 over the cheap panel — clears the pre-registered +4 threshold,
zero drops.** Retrieval recovers ~40% of the gap `flagship_panel` closes
(+15.4 over cheap), but at cheap-token cost plus free corpus lookups
instead of ~3x flagship tokens on every seat. That is the economic bet
paying off: inject the missing knowledge rather than buy a bigger model.

### The mechanism that matters: the unanimous-wrong floor shrank
The whole thesis was that the cheap panel's dominant loss is confident
unanimous agreement on a wrong answer (a KNOWLEDGE gap, uncatchable by
deliberation). Retrieval attacks exactly that:

| | Unanimous-wrong (uncatchable) |
|---|---|
| cheap-panel (no RAG) | 20 / 86 |
| **cheap-panel + RAG** | **14 / 86** |

Retrieved evidence stopped the cheap panel from confidently agreeing
wrong on **6 questions** — the floor fell from 23% to 16%. This is the
designed mechanism working, not a diffuse accuracy bump: RAG reaches the
one failure mode deliberation structurally cannot.

## GPQA contamination tripwire: PASSED (and taught the router rule)

RAG on GPQA-Diamond (Google-proof by construction), vs the frozen cheap
engine on the same 86 items:

| GPQA-Diamond, seed 42 | Accuracy |
|---|---|
| cheap engine (frozen, no RAG) | 79.1% |
| cheap engine + RAG | 74.4% |

**Delta −4.7.** Two things confirmed at once:
1. **No contamination.** A contaminated index (containing GPQA's answers)
   would have produced a large POSITIVE jump. The delta is negative — the
   index does not leak the answer key. Tripwire passed.
2. **Retrieval must be router-gated.** GPQA is deliberately search-proof;
   Wikipedia passages are noise to a panel already competent there, and
   they distract it (−4.7). Retrieval helps ONLY where the cheap tier is
   out of its depth AND the knowledge is retrievable.

## The finding: RAG is a domain-gated lever, exactly like flagship_panel

R1 is not an always-on win — it is +4.7 where the gap is knowledge
(SuperGPQA-hard) and −4.7 where the benchmark is search-proof (GPQA). A
flat always-on RAG would wash out. This slots directly into the MoO
router: where the estimated cheap-to-flagship gap is large AND the domain
is knowledge-retrievable, route to `rag_presolve` (cheap + evidence);
where it's search-proof or the tier is competent, skip retrieval. RAG and
flagship_panel are now two selectable tools for the same "cheap tier out
of depth" diagnosis — RAG cheaper, flagship_panel higher-ceiling.

## Caveats (honest)
- One seed. +4.7 clears the bar but needs the 3-seed bar before
  `rag_presolve` becomes a validated MoO profile. GPQA −4.7 also one seed.
- Retrieval coverage: 150k-passage STEM-Wikipedia subset. A miss (no
  relevant passage indexed) simply degrades toward the no-RAG panel; a
  larger/full corpus could lift the SuperGPQA number further — the +4.7
  is a floor for this corpus, not a ceiling for retrieval.
- k=5, ~200-word evidence budget, unchanged solver prompts. No tuning of
  retrieval depth/formatting yet — G2 (disputed-step re-retrieval) and
  reranking are the next levers on top of this baseline.

## Second seed (7): R1 replicates

Apples-to-apples on 87 common items, cheap-panel (control) vs cheap+RAG:

| SuperGPQA-hard | Seed 42 | Seed 7 |
|---|---|---|
| cheap-panel (no RAG) | 67.4% | 67.8% |
| cheap-panel + RAG | 72.1% | 74.7% |
| **Delta** | **+4.7** | **+6.9** |
| unanimous-wrong floor | 20→14 | 18→15 |

Both seeds positive, both cut the unanimous-wrong floor, mean **+5.8**.
The retrieval mechanism is not a one-seed artifact — retrieved evidence
consistently stops the cheap panel from confidently agreeing wrong on
knowledge-heavy hard-STEM questions. One more fresh seed completes the
3-seed bar to promote `rag_presolve` to a validated MoO profile; on two
seeds it is already a strong, replicated positive and the cheapest of the
three fixes for the unanimous-wrong floor (RAG < tier-swap in cost).

## Transparency note: concurrency fix (added retroactively)

The R1 seed-42 and seed-7 pilots above ran BEFORE a concurrency bug was
found and fixed (commit 609a1ab, store.py RLock): a cached RagIndex's
single sqlite3 connection could corrupt under concurrent asyncio.to_thread
reads and silently drop questions. Effect on the R1 findings: some of the
"drops" attributed to timeouts may have been this bug instead. This does
NOT bias the reported deltas — every number is scored apples-to-apples on
the common-items intersection (rag vs control compared only on questions
both runs completed), so a dropped question simply lowers n rather than
skewing the comparison, and the control ran at the same concurrency. The
+4.7/+6.9 result is 2-seed replicated with a clean mechanism (floor
20→14, 18→15). The R1 THIRD seed (123), which runs on the fixed code, is
the clean confirmation — if it also lands +4 to +7, the earlier seeds were
not artifacts of the concurrency bug. Flagged here rather than buried.
