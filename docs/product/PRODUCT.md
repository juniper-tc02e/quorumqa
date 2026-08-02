# MagiAchiral — Product Plan

*(magiachiral.com — the consumer product built on the QuorumQA adjudication
engine. Decided 2026-07-19; two-tier model locked in by Jun Kai.)*

## Thesis

Most mainstream chatbots (ChatGPT, Claude, Z.ai) present **one synthesized
answer**, with the reasoning that produced it largely invisible to the reader.
MagiAchiral is the chatbot for answers you need to trust: **ask like a chatbot,
adjudicated like a tribunal.** The chat UI is the familiar shell; the visible
deliberation is the product.

*Scoped 2026-07-30: this previously read "Every mainstream chatbot… with no
visible basis for trust." Several assistants do expose reasoning traces or
citations, and multi-model council products exist (see
`docs/prior-art-and-positioning.md`). The differentiator is not that we
deliberate and nobody else does — it is **what we surface**: the panel's actual
split, which claims were tool-checked, the adjudicator's ruling, and any dissent
that survived it.*

Design rule that governs everything: **the disagreement is the feature.**
Other chatbots hide uncertainty; we sell it.

There is **no single-model mode**. MagiAchiral never returns an unvetted
single voice — that's the brand promise. Every substantive question gets at
least a three-seat panel.

## Interaction model — two tiers, one box

| Tier | What runs | Latency | Framing |
|---|---|---|---|
| **Quorum** *(default)* | 3 solver seats vote independently → Skeptic/Verifier/Judge escalate **only on split** | ~10s unanimous / ~45–90s escalated | The everyday tier |
| **Tribunal** | Full pipeline forced: panel + Skeptic + Verifier + Judge, always, regardless of unanimity | ~60–90s | The "show me the work" button — forces the complete audit trail (panel split, Skeptic's attack, every tool call, ruling, surviving dissent). **Not measured to be more accurate** than a single flagship call on our benchmark (net +1, p=0.50, 3 seeds); it buys visibility, not a better answer |

- Unanimous Quorum answers cost ~$0.004; escalated ~$0.05 (measured, n=90
  GPQA benchmark). Tribunal always pays the full pipeline.

  **⚠ Those are dollars under pre-Token-Plan pricing, and the billing unit
  changed.** Re-derived in tokens from the same frozen n=90 seed-42 run
  (`benchmark/results/full_run.jsonl` + `full_run2.jsonl`, mean input+output
  per item):

  | path | share of questions | tok/item | vs one flagship call |
  |---|---:|---:|---:|
  | Quorum, unanimous | 62.2% | **4,638** | 1.36× |
  | Quorum, escalated | 37.8% | **16,218** | 4.75× |
  | Quorum, blended | 100% | **9,013** | 2.64× |
  | *one `qwen3.7-max` call* | — | *3,415* | 1.00× |

  So the cheap path is **not** cheap relative to the obvious alternative — a
  unanimous three-seat panel still burns 1.36× what a single flagship call
  burns, and the blended figure is 2.64×. The dollar saving came entirely from
  the flash/max price ratio, which the Token Plan removes.

  *Reconciling with the 8,690 / 2,792 pair quoted in `README.md`,
  `docs/architecture.md` and `docs/FINDINGS-2026-08.md`: that pair is measured
  on the **3-seed paired TB-1 item set** (seeds 1001/2311/3407, n=265 shared
  items) and gives 3.1×. The table above is the **frozen n=90 seed-42
  submission run**, the same run the dollar figures on this page come from, and
  gives 2.64×. Both are correct; they are different item sets, and the one to
  quote is whichever run the surrounding claim is about. They are not two
  estimates of one quantity.*
- Follow-up messages within a case (see Conversation model) do NOT re-run
  the panel, so multi-turn chat stays fast and cheap despite there being no
  casual tier.

## The deliberation surface (core differentiator)

Four layers of progressive disclosure:

- **Layer 0 — the answer.** Normal streamed prose. Nobody is forced to read
  a debate to get an answer.
- **Layer 1 — the consensus strip.** One line under every answer: three
  seat-glyphs + verdict chip + metadata (cost, latency).
  - ● ● ● green — "3/3 consensus"
  - ● ● ◐ amber — "Split 2–1 · escalated"
  - ⊗ red ring — **"Panel overruled"** (Judge overturned the majority — the
    signature moment, worn like a badge)
  - Dissent footer when applicable: "⚠ 1 seat maintains a different answer."
- **Layer 2 — the deliberation timeline** (one click). Vertical timeline:
  three solver cards (stance, confidence, 2-line reasoning, seat name) →
  Skeptic's attack quoting the specific disputed step → Verifier tool-call
  rows rendered as terminal lines (`lookup_constant(planck) → 6.626e-34 ✓`)
  → **Verdict Card** (ruling, decisive argument quoted, dissent verbatim).
  Verdict Card is exportable (PNG/PDF) — the shareable growth artifact.
- **Layer 3 — raw transcript + JSON.** Full audit trail; also the API
  surface.

**The waiting state is a feature.** Escalated answers take 45–90s — deadly
as a spinner, compelling as theater. Stream the deliberation live: seats
pulse while thinking, votes land one by one, a split triggers an
ESCALATING banner, the Skeptic's text streams in. The wait is the demo.
Highest-leverage UI investment in the product.

## Conversation model — chat is turns, adjudication is cases

- Each substantive user message = a **case** (conversation context packed
  into the case file).
- Follow-ups ("why not B?", "explain simpler") are answered by the
  Judge-tier model with the existing transcript as context — fast, cheap,
  no re-panel.
- **Re-adjudicate** button on any answer forces a fresh tribunal when the
  user pushes back with new facts.

## Use cases, ranked

1. **STEM verification / homework & exam prep** — literally what we
   benchmarked (GPQA). Launch wedge.
2. **Second opinion on high-stakes personal questions** — medical/legal/
   financial *information* (hard disclaimers, never advice). Dissent is a
   first-class part of the interface here, not a footnote.
3. **Verifier-checked answers on eligible claims — ROADMAP for general
   fact-checking.** What ships today is narrower than "fact-checked research"
   implies: the Verifier's MCP surface is exactly five tools —
   `lookup_constant`, `safe_calculate`, `sympy_check`, `substitute_check`, and
   `search_corpus` (`src/quorumqa/tools/mcp_server.py`). That is constants, a
   calculator, symbolic-equivalence and substitution checks, and retrieval over
   a local corpus. It is **not** open-domain fact verification, and it only
   fires on claims the extractor judges checkable. General fact-checked
   research is a roadmap capability, not a shipped one.
4. **Decision support** — Plan A vs Plan B adversarially argued.
   Anti-sycophancy as a consumer feature.
5. **API / Verdict-Cards-as-a-service** — open-core path; the chat product
   is the live demo for it.

## Engine deltas required (honest list)

- **Free-form answers**: engine votes A–D today. Product needs open-ended
  questions → solvers emit candidate answers; cheap semantic-equivalence
  pass clusters them into stances; agreement = same cluster. *Main new
  engineering.*
- **Streaming events**: orchestrator emits per-role progress events
  (WebSocket) for the live deliberation view.
- **Case/session store**: conversations + transcripts (OSS already stores
  transcripts).
- **Auth + metering**: per-user cost tracking (cost_tracker.py already
  produces the numbers).
- Unchanged: escalation logic, Skeptic/Verifier/Judge roles, MCP tooling,
  Verdict Cards.

## Monetization

- **Free**: ~30 Quorum cases/mo, 3 Tribunals.
- **Pro ($15–20/mo)**: unlimited Quorum, generous Tribunal cap, share
  cards, full history.
- **API**: per-case pricing.
- Unit economics: tribunal answer costs us ~$0.02–0.06 (measured); heavy
  Pro use stays well under subscription price. The per-answer cost chip
  doubles as a trust signal no competitor shows.

  **⚠ Re-derived 2026-08-03 — the margin claim is not currently verifiable, and
  the honest version is stated in tokens.** "Well under subscription price"
  was computed from `PRICING_USD_PER_MTOK`, which prices `qwen3.6-flash` input
  at 0.60 and `qwen3.7-max` input at 2.50 USD/Mtok. The whole saving lives in
  that ~4× spread. The Token Plan bills a **token quota**, not a
  model-differentiated dollar rate, and its rate is not in this repo — so no
  margin figure can be defended here, and none is asserted.

  What *is* measured, from the frozen n=90 run:

  | Pro usage | blended tok/mo | vs the same user on 1× flagship |
  |---|---:|---:|
  | 30 cases/mo (Free ceiling) | 270k | 102k |
  | 200 cases/mo (typical Pro) | 1.80M | 683k |
  | 1,000 cases/mo (heavy Pro) | 9.01M | 3.42M |

  A heavy Pro user costs **2.64× the token budget** of the same user served by
  one flagship call per question — and TB-1 measured that the extra tokens buy
  net +1 accuracy at p=0.50. **The product case for the tribunal is therefore
  visibility, not accuracy and not cost**, which is what the tier table on this
  page now says. Before any pricing decision, this needs the actual Token Plan
  rate and a real margin re-derivation; it is listed as an open question below
  rather than left as a settled claim.

## Phasing

- **Phase 0 (days):** magiachiral.com landing — live *replayed* demos from
  the 90-question benchmark (real transcripts, real overturns, zero
  inference cost), waitlist, repo link.
- **Phase 1 (2–3 wks):** Chat MVP — Quorum default, consensus strip,
  expandable timeline, live streaming states, auth + free tier.
  Short-answer domains first (stance clustering is easy there).
- **Phase 2 (4–6 wks):** Full free-form clustering, Tribunal tier, share
  cards, API keys, billing.

## Open decisions (flagged, not blocking)

- Default-tier confirmation: Quorum as default (recommended — it's the
  identity).
- Disclaimer depth for medical/legal use cases.
- Phase 0 ships after the hackathon submission (sequencing: submission
  first).
- **Pricing is unresolved and currently blocks nothing but should block
  launch.** The $15–20/mo Pro figure was set against a dollar cost that the
  Token Plan superseded. Needs: (a) the actual Token Plan rate or quota, (b) a
  margin re-derivation in tokens against the table in "Unit economics" above,
  and (c) a decision on what the tribunal is priced *for*, given TB-1 measured
  its accuracy contribution at net +1, p=0.50 — the defensible pitch is the
  audit trail, not a better answer. Until (a) exists no margin claim should
  appear on the site or in this doc.

See BRAND.md (same directory) for fonts, color system, naming surfaces,
and the deployable feature spec.
