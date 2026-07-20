# Demo video: shot list and narration script

Target length **2:55**. Every figure below is from the frozen n=90 run and is
checkable in `benchmark/results/full_run2.jsonl`.

Record **https://magiachiral.com** (fixed replay, no live API calls that can
fail mid take). Streamlit dashboard is the fallback only if the site is down.

## The two cases this demo uses, and why they are different

Do not mix these up. They prove different things.

| Case | What it proves | Panel | Judge | Flagship |
|---|---|---|---|---|
| `recIj8lR4tuDgrHou` (Quantum Mechanics) | **Majority voting fails, adjudication fixes it** | D, C, D to plurality D | ruled **C** (correct) | also got C right |
| `recBhnXrUyTJ6WHIR` (Quantum Mechanics) | **The cheap society beat the expensive model** | to D | ruled **D** (correct) | said B, **wrong** |

The hero case does **not** beat the flagship. Never imply it does. Its value is
the mechanism, and it holds the single best detail in the dataset:

- Seat 1, First principles: **D at 95% confidence**
- Seat 2, Elimination: **C at 95% confidence** (the lone dissenter, and right)
- Seat 3, Recall: **D at 10% confidence** (propped up the wrong majority)

A plurality vote counted that 10% seat exactly equal to the 95% seat. That is
the entire argument for adjudication, demonstrated rather than asserted.

## Shot list

| # | Time | On screen | Action |
|---|---|---|---|
| 1 | 0:00-0:18 | Site hero, chamber dark | Load magiachiral.com. Do not scroll yet. Let the dormant chamber hold for 2s |
| 2 | 0:18-0:35 | "Votes land" chapter | Scroll slowly. Stop with all three seat cards visible. **Cursor-highlight the 10% confidence figure** |
| 3 | 0:35-0:50 | "Split detected" chapter | Continue scrolling. Mark shifts amber |
| 4 | 0:50-1:05 | "Skeptic" chapter | Pause on the disputed-step block |
| 5 | 1:05-1:30 | "Verifier" chapter | Pause on the two `safe_calculate` rows. Cursor over `verified` |
| 6 | 1:30-1:52 | "Judge rules" chapter | Land on the **PANEL OVERRULED** card. Hold 3s. Do not rush this |
| 7 | 1:52-2:15 | Scoreboard section | Scroll to the three bars. Let the +20.0 numeral fill frame briefly |
| 8 | 2:15-2:25 | Escalation economics | Show the four metric tiles, especially the 58.8% false-escalation figure |
| 9 | 2:25-2:40 | Case gallery | Click filter **"Beat the flagship"**. Open `recBhnXrUyTJ6WHIR`. Show flagship = wrong |
| 10 | 2:40-2:50 | Reproduce section | Show the terminal block with the two commands |
| 11 | 2:50-2:55 | Close card | Scroll to "Answers you can audit" + tri-hex mark |

## Narration script

Roughly 365 words. At a normal pace that is about 2:25 of speech inside a
2:55 video, which leaves the visual moments room to breathe. Do not rush shot 6.

---

**[Shot 1 — dark chamber]**

> Ask three cheap language models a hard question and take the majority answer.
> That is the standard trick.
>
> Here is the problem with it. On this question, two models said D. One said C.
> Majority wins, so the answer is D.
>
> D is wrong.

**[Shot 2 — the three seat cards. Highlight the 10%.]**

> Now look at the confidence. The seat that broke ranks was ninety-five percent
> sure. One of the two that formed the majority was **ten** percent sure.
>
> Majority voting counted those two votes exactly the same.
>
> MagiAchiral does not count votes.

**[Shot 3 — split detected, mark goes amber]**

> Three cheap Qwen solvers answer independently, each through a different
> reasoning lens. If they agree, we are done, and the question costs about two
> thirds of a cent.
>
> If they split, that disagreement is the signal.

**[Shot 4 — skeptic, disputed step]**

> A Skeptic has to name the exact inferential step it disputes. It cannot
> simply object.

**[Shot 5 — the two MCP tool calls]**

> Then a Verifier pulls out the checkable claims and runs each one through a
> real MCP tool server. These energy sums are not recalled from memory. They
> are computed. Ten E. Fifteen E. Both verified.
>
> Only now does a flagship judge read the whole record and rule, weighing the
> arguments instead of counting the votes.

**[Shot 6 — PANEL OVERRULED. Hold.]**

> It rules C, and overturns its own panel. C is correct.
>
> The seat that stood alone was right, and the record says so permanently.
> That is the product. The disagreement is the artifact.

**[Shot 7 — scoreboard]**

> Ninety GPQA Diamond questions, complete run. The same cheap models as a plain
> ensemble get fifty-nine percent. Organised this way they get seventy-nine.
>
> A single flagship model answering everything gets eighty-four. It still wins
> on accuracy and we put that on the page. But we run eleven percent under its
> cost, and the judge *is* that same flagship. The saving is routing it, not
> avoiding it.

**[Shot 8 — the uncomfortable number]**

> We publish the number that hurts, too. Fifty-nine percent of escalations only
> re-confirm the panel. That is the price of the eleven it got right.

**[Shot 9 — filter to "Beat the flagship", open the case]**

> Every case is on the record. Here are the five where the cheap society beat
> the expensive model outright. This one: the flagship said B. The society said
> D. D is correct.

**[Shot 10 — reproduce block]**

> Vote cheap, escalate on disagreement, keep the receipts. That shape fits
> claims triage, moderation appeals, medical second opinions.
>
> We proved it on GPQA because the answer key is public. Clone the repo, run
> two commands, and check every number yourself.

**[Shot 11 — close]**

> Three minds. One verdict. Dissent on the record.
>
> magiachiral dot com.

---

## Recording notes

- **Win + Alt + R** (Xbox Game Bar) or OBS. 1080p, 30fps is fine.
- Browser at 100% zoom, **hide the bookmarks bar** (Ctrl+Shift+B) and use a
  clean window. Your bookmark bar currently shows other project names.
- Scroll with a trackpad or smooth-scroll wheel. The hero is scrub-linked to
  scroll, so jerky scrolling looks broken rather than cinematic.
- Do a silent scroll-through once before recording so every frame of the hero
  film is cached. First-load frame streaming can stutter.
- No copyrighted music. Narrate live or add captions.
- If you fluff a line, keep rolling and repeat it. Cut in post.

## Claims to avoid

These would be false, and the whole pitch is auditability:

- Do not say the hero case beat the flagship. It did not; the flagship also
  answered C correctly there.
- Do not say "the same cheap models, only reorganised". The judge is
  `qwen3.7-max`, the same model as the baseline.
- Do not say the flagship is "twelve percent" more expensive. We are eleven
  percent under it; those are different numbers.
- Do not describe the Skeptic as a mid tier model. It runs on `qwen3.6-flash`,
  the cheapest tier.
