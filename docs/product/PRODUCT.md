# MagiAchiral — Product Plan

*(magiachiral.com — the consumer product built on the QuorumQA adjudication
engine. Decided 2026-07-19; two-tier model locked in by Jun Kai.)*

## Thesis

Every mainstream chatbot (ChatGPT, Claude, Z.ai) returns **one voice's
answer** with no visible basis for trust. MagiAchiral is the chatbot for
answers you need to trust: **ask like a chatbot, adjudicated like a
tribunal.** The chat UI is the familiar shell; the visible deliberation is
the product.

Design rule that governs everything: **the disagreement is the feature.**
Other chatbots hide uncertainty; we sell it.

There is **no single-model mode**. MagiAchiral never returns an unvetted
single voice — that's the brand promise. Every substantive question gets at
least a three-seat panel.

## Interaction model — two tiers, one box

| Tier | What runs | Latency | Framing |
|---|---|---|---|
| **Quorum** *(default)* | 3 solver seats vote independently → Skeptic/Verifier/Judge escalate **only on split** | ~10s unanimous / ~45–90s escalated | The everyday tier |
| **Tribunal** | Full pipeline forced: panel + Skeptic + Verifier + Judge, always, regardless of unanimity | ~60–90s | The "I need to be sure" button |

- Unanimous Quorum answers cost ~$0.004; escalated ~$0.05 (measured, n=90
  GPQA benchmark). Tribunal always pays the full pipeline.
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
   financial *information* (hard disclaimers, never advice). The dissent
   surface is uniquely honest here.
3. **Fact-checked research answers** — claims forced through Verifier
   tools; answers ship with receipts.
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

See BRAND.md (same directory) for fonts, color system, naming surfaces,
and the deployable feature spec.
