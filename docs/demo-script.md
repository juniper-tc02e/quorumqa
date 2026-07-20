# MagiAchiral — Demo Video: Shot List & Narration Script (REVISED)

**Target length: 2:56.** Target ceiling 2:55–2:58 (same safety margin as the prior draft, which landed at 2:55 against the 3:00 Devpost hard cap). All figures below are from the frozen n=90 run only.

Record https://magiachiral.com (fixed replay, no live API calls). Streamlit dashboard is the fallback only if the site is down.

## The two cases this demo uses

| Case | What it proves | Panel | Judge | Flagship |
|---|---|---|---|---|
| **recIj8lR4tuDgrHou** (Quantum Mechanics) | Majority voting fails and adjudication fixes it. Does **not** beat the flagship — the flagship also got this one right, so it only demonstrates the mechanism. | D, C, D → plurality D | C (correct) | C (also correct) |
| **recBhnXrUyTJ6WHIR** (Quantum Mechanics) | The cheap society beats the expensive model outright. | Leaned D | D (correct) | B (**wrong**) |

## What changed in this revision

1. Added a new beat, **shot 10 — "We overrule ourselves, too"** (17s), a fast 3-entry glimpse of the new Build Log section, drawing the explicit thematic line from the product's self-correction to the team's own.
2. Placed it **right before Reproduce/Close**, not right after the Judge Rules shot. The Build Log sits near the bottom of the live page, right before Reproduce — putting the beat there keeps the whole video a single continuous downward scroll instead of jumping down the page and back up.
3. Folded the new **Verdict Wall** (90-hexagon honeycomb) into the gallery shot (shot 9), as a glanceable hold before the filter/case-open action.
4. Freed the runway by tightening shot 3 and the Scoreboard hold time — trimming pause/hold time and a few words, not the mechanism's substance — plus small trims elsewhere. Net runtime grew by only 1 second against the old script (2:55 → 2:56) despite adding a whole new section.
5. **Judge-review pass folded in:** the Skeptic hold (shot 4) is restored from an initial 11s cut back to 13s, funded by trimming the Scoreboard hold and the case-gallery filter line rather than the mechanism block itself; the cut clarity line *"The saving is routing it, not avoiding it"* is back in the Scoreboard beat; the Build Log's architecture-lever line is reworded to drop any residual echo of "beat the flagship"; and the two-case section above now uses a comparison table for faster briefing. Runtime holds at 2:56.
6. **Disclosed for audit (fact-check pass):** shot 6's direction changed from the source script's "Hold 3s, do not rush" over a 22s shot to this draft's "Hold 4–5s, do not rush" over a 23s shot. That change predates this revision and was not previously logged in this list; it is recorded now so the "untouched by this pass" claim in Tradeoff 1 below is auditable against the source packet.

## Shot list (12 shots, 0:00 to 2:56)

| # | Time | On-screen | Action |
|---|------|-----------|--------|
| 1 | 0:00–0:17 | Site hero, chamber dark | Load magiachiral.com, do not scroll yet, hold ~1–2s. |
| 2 | 0:17–0:34 | 'Votes land' chapter | Scroll slowly, stop with all three seat cards visible, cursor-highlight the 10% confidence figure. |
| 3 | 0:34–0:45 | 'Split detected' chapter | Continue scrolling, mark shifts amber. |
| 4 | 0:45–0:58 | 'Skeptic' chapter | Pause on the disputed-step block. Hold the full 13s — this is one of the four dominant mechanism beats, don't rush it. |
| 5 | 0:58–1:20 | 'Verifier' chapter | Pause on the two `safe_calculate` rows, cursor over 'verified'. |
| 6 | 1:20–1:43 | 'Judge rules' chapter | Land on the PANEL OVERRULED card. Hold 4–5s, do not rush. |
| 7 | 1:43–2:06 | Scoreboard section (#results) | Scroll to the three bars, let +20.0 numeral fill frame, pan the three stat tiles (11% cheaper, 62.2% never pay, $0.0065). |
| 8 | 2:06–2:13 | Escalation economics (#economics) | Show the four metric tiles quickly, land on the 58.8% false-escalation figure. |
| 9 | 2:13–2:26 | Case gallery + Verdict Wall (#record) | Hold on the 90-hexagon Verdict Wall as one glanceable image, then scroll to the table, click filter 'Beat the flagship', open recBhnXrUyTJ6WHIR, show flagship = B (wrong) vs society = D (correct). |
| 10 | 2:26–2:43 | **Build Log (#buildlog)** | Scroll past Generalize without stopping. Quick cuts across 3 of the 8 entries: "A credential bug that survived a rotation" (FIXED), "First design pass, called ugly, and it was" (REDESIGNED), "Eight architecture levers, tested at two independent seeds" (REAL FINDING, NOT SHIPPED). Cursor briefly touches the color-coded verdict tags so the legend echoes the case table above. |
| 11 | 2:43–2:51 | Reproduce section (#reproduce) | Show the terminal block with the two commands. |
| 12 | 2:51–2:56 | Close card | Scroll to 'Answers you can audit' + tri-hex mark, hold. |

## Narration script (370 words, ~2:28 of speech inside the 2:56 video)

**[Shot 1 — dark chamber]** *(running: 33 words)*
> Ask three cheap language models a hard question and take the majority answer. That's the standard trick.
> Two models said D. One said C. Majority wins — the answer is D.
> D is wrong.

**[Shot 2 — the three seat cards, highlight the 10%]** *(running: 66 words)*
> Now look at the confidence. The seat that broke ranks was ninety-five percent sure. One of the majority was ten percent sure.
> Majority voting counted those votes the same.
> MagiAchiral doesn't count votes.

**[Shot 3 — split detected, mark goes amber]** *(running: 92 words)*
> Three cheap solvers answer independently, through different reasoning lenses. Agree, and the question costs two thirds of a cent. Split, and that disagreement is the signal.

**[Shot 4 — skeptic, disputed step]** *(running: 107 words)*
> A Skeptic has to name the exact inferential step it disputes. It cannot simply object.

**[Shot 5 — the two MCP tool calls]** *(running: 157 words)*
> Then a Verifier pulls out the checkable claims and runs each through a real MCP tool server. These energy sums aren't recalled from memory — they're computed. Ten E. Fifteen E. Both verified.
> Only now does a flagship judge read the whole record and rule, weighing arguments instead of counting votes.

**[Shot 6 — PANEL OVERRULED, hold]** *(running: 190 words)*
> It rules C, and overturns its own panel. C is correct. The seat that stood alone was right, and the record says so permanently. That is the product. The disagreement is the artifact.

**[Shot 7 — scoreboard]** *(running: 249 words)*
> Ninety GPQA Diamond questions, complete run. The same cheap models as a plain ensemble: fifty-nine percent. Organized this way: seventy-nine.
> A single flagship model: eighty-four. It still wins on accuracy — we put that on the page. But we run eleven percent under its cost, and the judge is that same flagship. The saving is routing it, not avoiding it.

**[Shot 8 — the uncomfortable number]** *(running: 266 words)*
> We publish the number that hurts, too: fifty-eight point eight percent of escalations only re-confirm the panel.

**[Shot 9 — Verdict Wall, filter to 'Beat the flagship', open the case]** *(running: 299 words)*
> Ninety questions, one honeycomb — every hexagon a real result, agreed, split, or overruled. Filter to 'Beat the flagship': five cases. Here's one. The flagship said B. The society said D. D is correct.

**[Shot 10 — Build Log: "We overrule ourselves, too"]** *(running: 339 words)*
> The judge overturns its own panel and keeps the record. We hold the build to the same rule: a credential bug caught only in testing, a design we called ugly publicly, an architecture we tried and chose not to ship.

**[Shot 11 — reproduce block]** *(running: 359 words)*
> That shape fits claims triage, moderation appeals, medical second opinions. Clone the repo, run two commands, check every number yourself.

**[Shot 12 — close]** *(running: 370 words)*
> Three minds. One verdict. Dissent on the record.
> magiachiral dot com.

## Recording notes (updated)

- Only one new top-level section since the last recording pass: Build Log. The Verdict Wall is new too, but it lives inside the existing Gallery/Record section rather than as its own scroll stop. Generalize was already on the page before this session — it is not new; this corrects a stray claim in the previous draft. Total scroll distance is still longer than the last pass thanks to Build Log, so rehearse the scroll speed once before the real take so shot 10's timing lands without a rushed final scroll.
- The Verdict Wall is a static SVG (no animation/render wait needed) — hold on it long enough to read as "one image of the whole run," then move to the table.
- Shot 10 deliberately does not stop to let any single Build Log entry be fully read; it is a fast pass across 3 of the 8 entries by design, timed to the verdict-tag colors, not to the body text.
- Scroll past Generalize (#generalize) without stopping between shots 9 and 10 — it isn't cut for content reasons, purely for time.
- Shot 4 now holds for the full 13 seconds — resist the urge to speed through the disputed-step block just because the spoken line is short; the silence is doing narrative work here.
- Everything else (fixed replay, no live API calls, Streamlit fallback) carries forward unchanged.
- **Pacing risk to watch:** shots 7, 9, and 11 have close to zero slack between their spoken word count and their nominal shot duration at a literal 150 words/minute. Narrate at a steady, unhurried 150 wpm on these three specifically — do not slow down further on the numbers, or they will run past their cut points. If it feels tight in a take, trim a word or two from shot 9's "Filter to 'Beat the flagship': five cases" line rather than rushing the delivery.

## Claims to avoid (hard guardrails, carried forward unchanged)

- Never say the hero case (recIj8lR4tuDgrHou) beat the flagship — it did not, flagship also got C right there.
- Never say 'the same cheap models, only reorganised' — the Judge is qwen3.7-max, the SAME model as the flagship baseline. All three solver seats plus the Skeptic and the Verifier run on qwen3.6-flash, the cheapest tier. Only the Judge is flagship-tier, and only on the 37.8% of questions that escalate.
- Never say the flagship is 'twelve percent' more expensive — MagiAchiral runs 11% UNDER the flagship's cost; do not conflate these framings.
- Never describe the Skeptic as mid-tier — it is qwen3.6-flash, the cheapest tier.
- Do NOT fold any unshipped lever-experiment numbers (e.g. thinking_gate, 86.7%) into the video as if they were the shipped result. Those are a disclosed-as-unshipped research finding on the Build Log page, tagged 'Real finding, not shipped.' The video's numbers must ONLY be the frozen n=90 run above.
