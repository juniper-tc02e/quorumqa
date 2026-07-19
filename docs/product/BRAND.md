# MagiAchiral — Brand & Feature Spec

*(Companion to PRODUCT.md. Covers identity, type, color, motion, naming,
voice, and the deployable feature list for magiachiral.com.)*

## 1. Brand position

**Evoke Evangelion's MAGI command-center aesthetic; never copy its
assets.** The resonance is structural — MAGI is three units that vote and
surface dissent, which is literally our mechanism — so the brand earns the
reference instead of wearing it as a costume.

Legal guardrails (non-negotiable):
- No Studio Khara/Gainax marks, logos, character art, or the NERV leaf.
- No Matisse EB (the Eva title font — licensed); we use free stand-ins.
- Seat names use the **biblical Magi** (Casper, Balthasar, Melchior) —
  public domain; Evangelion itself borrowed them.
- Anime references live in *subtext* (layout, color, motion), never in
  copy. The product reads as a serious instrument to someone who has never
  seen Eva, and as an obvious homage to someone who has.

One-line brand: **"Three minds. One verdict. Dissent on the record."**

## 2. Typography

| Role | Font | Why |
|---|---|---|
| Display / wordmark / hero titles | **Shippori Mincho B1** (800) | Heavy Japanese mincho — the canonical free stand-in for Eva's title-card look; ships JP glyphs for accent characters; Google Fonts |
| UI / body | **Inter** (400/500/600) | Workhorse legibility at chat sizes; neutral so the display face carries the drama; Google Fonts |
| Data / verdicts / tool calls / seat readouts | **JetBrains Mono** (400/700) | The command-center voice: consensus strips, tool-call lines, costs, transcripts; Google Fonts |

Rules:
- Display face is rationed: wordmark, page heroes, and the words "QUORUM /
  TRIBUNAL / VERDICT / OVERRULED" only. Everything else is Inter.
- All numbers a user might compare (costs, confidences, latencies, votes)
  render in JetBrains Mono — tabular, honest, instrument-like.
- Self-host via `@font-face` (fontsource packages) — no Google Fonts CDN
  call, for privacy posture and CN-region reliability.

## 3. Color system (dark-first)

Dark is the default and the identity (every competitor screenshot the
product brief was built against is dark; the command-center aesthetic
demands it). Light mode is a Phase-2 accessibility deliverable, not a
launch item.

| Token | Hex | Use |
|---|---|---|
| `bg.void` | `#0B0D14` | App background (near-black indigo) |
| `bg.panel` | `#12151F` | Cards, sidebar, timeline |
| `bg.raised` | `#1A1E2C` | Hover, active case |
| `text.primary` | `#E8EAF2` | Body text (off-white, blue cast) |
| `text.dim` | `#8A90A6` | Metadata, timestamps |
| `accent.consensus` | `#00E37D` | Phosphor green — unanimity, verified tool checks, 3/3 chips |
| `accent.alert` | `#FF6B1A` | Hazard amber — splits, ESCALATING banner, primary CTA |
| `accent.tribunal` | `#7C5CFF` | Judge purple — Tribunal tier, Verdict Cards, judge timeline node |
| `accent.overrule` | `#FF3355` | Red — "Panel overruled" ring, dissent markers |

**The state→color mapping is load-bearing and must never be reused
decoratively:** green = consensus, amber = split/escalation, purple =
adjudication, red = overrule/dissent. A user should learn the color
language within three questions.

Texture: 1px technical rules, thin hexagon seat-glyphs, subtle scanline on
the deliberation timeline only (CSS, reduced-motion-safe). No gradients on
content surfaces; the accents do the work.

## 4. Logo & wordmark

- **Mark:** three hexagonal seat-lights arranged in a triangle (negative
  space forms an implicit "M"). Each hex can carry state color — meaning
  the logo IS the consensus strip, the loading state, and the favicon in
  one glyph. Animatable: hexes pulse while a case deliberates.
- **Wordmark:** MAGIACHIRAL in Shippori Mincho B1; "MAGI" in
  `text.primary`, "ACHIRAL" in `text.dim` — teaches the pronunciation
  (Magi·Achiral) and foregrounds the reference.
- Favicon: the tri-hex mark, amber on void.

## 5. Naming surfaces

| Surface | Name |
|---|---|
| Product | MagiAchiral |
| Solver seats | **CASPER-1, BALTHASAR-2, MELCHIOR-3** (displayed in mono, with seat model underneath) |
| Tiers | **Quorum** (default) / **Tribunal** |
| Escalation roles | Skeptic, Verifier, Judge (plain English — clarity over lore; the lore lives in the seats) |
| Answer artifact | **Verdict Card** |
| Audit trail | Transcript |

## 6. Voice & microcopy

Calm, technical, honest. The system reports its own uncertainty and its own
cost. Never cute, never anime-quoting.

Canonical strings:
- "3/3 consensus"
- "Split 2–1 — escalating"
- "Panel overruled — see the decisive argument"
- "1 seat maintains dissent"
- "This answer cost $0.041 and took 62s"
- Empty state: "Ask something that matters."
- Tribunal button: "Convene Tribunal"

## 7. Feature spec — deployable checklist

### Phase 0 — landing (ships first, days of work)
- [ ] magiachiral.com static landing: wordmark, one-line brand, live
      **replayed** deliberation demo (real transcripts from the n=90 GPQA
      run — zero inference cost, includes a genuine Panel-Overruled case)
- [ ] Waitlist (email capture), GitHub repo link, benchmark numbers table
- [ ] OG/share meta with the tri-hex mark

### Phase 1 — chat MVP
- [ ] Auth: email magic link + Google/GitHub OAuth
- [ ] Case sidebar (recents, like standard chatbot shells) + message box
      with Quorum/Tribunal toggle (Quorum default)
- [ ] Live deliberation stream over WebSocket: seat pulse → votes land →
      ESCALATING banner → Skeptic/Verifier/Judge stream → answer
- [ ] Consensus strip (Layer 1) on every answer + dissent footer
- [ ] Expandable deliberation timeline (Layer 2) + Verdict Card render
- [ ] Case follow-ups (Judge-context, no re-panel) + Re-adjudicate button
- [ ] Transcript persistence (Alibaba OSS, already built) + history
- [ ] Per-answer cost chip + monthly usage meter
- [ ] Free tier caps (30 Quorum / 3 Tribunal per month) + waitlist-gated Pro
- [ ] Settings: default tier, data retention, transcript export (JSON)

### Phase 2 — product depth
- [ ] Verdict Card PNG/PDF export + public case share links (opt-in)
- [ ] API keys + per-case billing (Stripe)
- [ ] Free-form stance clustering hardened (beyond short-answer domains)
- [ ] Light mode; full reduced-motion audit
- [ ] Teams/workspaces

## 8. Deployment architecture (pragmatic)

- **Backend:** FastAPI (the engine is already Python) + WebSocket events;
  runs on the existing Alibaba Cloud ECS instance. SQLite → RDS when load
  justifies it. Transcripts stay on OSS (deploy/oss_client.py).
- **Frontend:** Next.js static-exported where possible, served from the
  same ECS behind Nginx (simplest single-box story); CDN later.
- **Models:** Qwen Cloud via the existing engine config — seat/judge tier
  mapping unchanged from the benchmarked configuration.
- **Domain:** magiachiral.com (purchased 2026-07-19). DNS → ECS; TLS via
  Let's Encrypt/certbot.
- **Sequencing:** nothing above starts until the hackathon submission is
  in (deadline 2026-07-21 05:00 SGT).
