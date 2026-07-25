# QuorumQA experiment spec book

*Assembled 2026-07-24 from 6 spec-writer agents (38 specs) filtered by 3 adversarial
critics (85 issues). Pre-registered and runnable when the token quota resets
**2026-07-28 03:32 UTC**. Companion to `docs/capability-roadmap.md` (which decides
WHICH axes to chase); this book decides HOW each experiment runs.*

## 1. How to read this book

Every spec is bound by these house rules. They are not negotiable per-spec.

**The bar is net-discordant, McNemar-tested.** The old "+3 net discordant per 90"
bar is **RETIRED as statistically unreachable**: exact one-sided McNemar gives
p = 0.125 at +3 (best case, zero losses) and p = 0.0625 at +4. The minimum that
clears p < 0.05 with zero losses is **+5**. Rule: **net >= +5 at one seed
(p < 0.05), OR net >= +3 at 2 of 3 seeds with the pooled McNemar (n = 270)
clearing p < 0.05.** Seven levers had been pre-registered to declare success on
evidence their own analysis plan rejects; all are restated.

**KILL DOMINATES BAR.** A run that passes its bar while tripping its kill is a
kill. Precedence is pre-registered, never decided after seeing data.

**Paired, same-item designs only.** Deltas are quoted on items completed in
*both* arms. A run with drops is re-run, never analysed — AIME run #1 was
invalidated by 32/60 panel + 12/60 baseline drops, whose 26 survivors then
showed a meaningless 100%/100%.

**GPQA is keyed on choice TEXT, never letter.** `load_gpqa._shuffle_choices`
reshuffles options per seed, so cross-seed or cross-config joins on letters are
noise.

**Burned seeds** (never reuse where the config was tuned on them): 42, 7, 123,
555, 777, 888, 271, 314, 217, 471, 606, 838. seed42 appears in 50 result files.
Screens that gate spend run on unburned seeds and are excluded from validation
seeds.

**Cost is TOKENS, not dollars** — `cost_usd` logs 0.0 on this endpoint. Weekly
quota measured at **~43.8M tokens**.

### 1.1 The cost correction that changes prior reasoning

Two measured findings overturn the "cheap tier is ~4x cheaper" assumption that
shaped earlier planning. **Under a token quota, tier labels do not predict cost:**

| Measured, per solver call | Tokens |
|---|---|
| Cheap flash seat, SuperGPQA-hard (1,341 logged calls) | **2,009** |
| Flagship thinking seat, SuperGPQA-hard (729 logged calls) | **3,096** |
| Flagship single call, AIME | **5,327** |
| Cheap flash call, AIME | **24,411** |

The USD price table (0.60/2.75 vs 2.50/7.50 per Mtok) implies a 4x discount the
**meter does not deliver**: on SuperGPQA-hard a cheap seat is only ~35% cheaper,
so **15 cheap seats ≈ 10 flagship seats** in quota terms. On AIME the inversion
is worse — the "cheap" call costs **4.6x the flagship call**, because
`max_tokens=2048` is demonstrably not enforced by this endpoint and flash
rambles. Every cost model in this book uses measured tokens per role, never tier
labels.

---

## 2. Panel scaling — the odd-N sweep (N = 3,5,7,9,11,13,15)

### 2.1 Why the earlier N=5 result did not answer this question

Our only prior scaling datapoint: `N_SOLVERS=5` scored **81.1%** vs the shipped
3-solver engine's **78.9%** — a genuine rise — but *below* the flagship's
**84.4%**, at higher cost. It was **confounded**: `SOLVER_LENSES` defines only 3
lenses and `_lenses_for()` cycles them, while `solve_all()` cycles 3 temperatures
on the same period. Seat 4 was therefore a **byte-identical config** to seat 1,
and seat 5 to seat 2. It tested more *copies*, not more *perspectives* — the
homogeneity trap in miniature. The genuine scaling question is untested.

### 2.2 The design fix: a coprime factorial

Seats are built from **5 procedures x 3 temperatures**, periods that are
**coprime**, so all 15 seats occupy unique (procedure, temperature) cells — plus
a per-seat option-permutation seeded on (seed, question_id, seat_index). No two
seats are duplicate configs by construction. Procedures reuse the three already
written as `METHOD_PROMPTS` (solve-forward, verify-by-candidate, estimate-first)
plus two new ones.

### 2.3 The efficiency trick: one run buys the whole curve

Each spec runs **one** paid arm at max N in **vote-only mode** (`--no-tribunal`),
then derives every intermediate N **offline by nested seat-subsampling** of the
logged per-seat answers. Dropping the tribunal (~9,290 tok per escalated item)
is what makes N=15 affordable at all.

### 2.4 The specs

| ID | What it tests | Cost | Priority |
|---|---|---|---|
| **S1** | PRIMARY: diversified N=15 harvest on SuperGPQA-hard; full N-curve + coverage@N derived offline | 2.71M (6.2%) | P0 |
| **S2** | CONFOUND CONTROL: lens-cycled N=15 on the *identical* items — does removing duplicate seats actually explain the N=5 null? | 2.71M (6.2%) | P0 |
| **S3** | Escalation policy as a function of N (unanimity degenerates at N=15); 4 trigger families replayed FREE first, one paid confirm | 0 then 2.78M | P0 |
| **S4** | Cost frontier: where accuracy-per-token peaks, + equal-token head-to-head vs a bare flagship call | 0 then 3.07M | P1 |
| **S5** | **The arm that could actually win**: diversified N=9 at the FLAGSHIP tier — scaling our best validated lever instead of our cheapest | 2.51M (5.7%) | P1 |
| **S6** | How high is worth going: N=63 probe on *only* the residual items nothing solves (the cons@64 question, priced honestly) | 3.54M (8.1%) | P2 |

**S1 bar:** max over odd N of [plurality@N − plurality@3] >= **+5 discordant/90**
AND coverage@15 − coverage@3 >= +5 items. **Kill (dominates):** if both are < +3,
then 12 genuinely-diversified seats produced fewer than 3 new solvable items —
the same-family blind spot dominates seat count. Declare the cheap-seat scaling
family **dead**, and do not run S3-paid, S4, S5 or S6.

**S2 is the spec that settles the record.** If diversified minus cycled is < 3
discordant at *every* N >= 5, lens-cycling was never the cause — seat count simply
does not buy decorrelation — and the record's "CONFOUNDED / untested" note must be
corrected to **"tested, negative."**

**S5 is the most promising arm in the family.** At the flagship tier the measured
coverage-to-plurality gap is only 1.7pt (83.5% plurality vs 85.2% coverage@3),
so selection is nearly perfect there and **coverage is unambiguously the binding
constraint** — exactly what adding decorrelated seats should attack. Its gate:
does not run until S1 has named a diversity source that works.

**S6 prices the cons@64 anchor honestly.** Rather than 90 items x 63 seats
(11.4M, 26% of a week, 70% of it re-confirming items already solved at N=3), it
runs 63 seats on **only the ~28 residual items nothing solved** (3.54M). Seats
16–63 repeat cells with fresh permutations and fresh samples — honest
resampling, labelled as the self-consistency mechanism rather than as further
procedure diversity.

---

## 3. Selection — how you PICK from N candidates

F1(b) showed GPQA's remaining gap to `qwen3.8-solo` is **selection-side**, and the
external cons@64 result (86.7% vs 71.0%) shows the gain comes from aggregating
many samples *with a good selector*. We have never systematically compared
selectors. The family's structure is deliberately economical: **generate one
frozen K=8 pool, then score many selectors against it for zero additional
tokens.**

| ID | What it tests | Cost | Priority |
|---|---|---|---|
| **S1** | Zero-token selector audit over the 60 already-logged 3-candidate pools | **0** | P0 |
| **S2** | The K=8 pool + the **ORACLE coverage ceiling** — the generation-vs-selection ROI decision | ~4.3M/3 seeds | P0 |
| **S3** | Selector bake-off on the frozen pool (confidence-weighted, cluster-margin, etc.) | **0** | P0 |
| **S4** | Judge-over-**all**-candidates vs pairwise tournament vs today's split-only judge | ~4.6M/3 seeds | P1 |
| **S5** | Verifier-selected: prefer candidates that survive a mechanical check | 0 (open) / ~2.2M (MC) | P1 |
| **S6** | Pool-size scaling: does the best selector's gain grow with K, and where does it flatten? | **0** | P1 |
| **S7** | Held-out confirmation of the winner — **the only ship gate** | ~4.3M+ | P1 |

**S1 is runnable today, during the block, for zero tokens** — it reconstructs
alternative selectors over pools we already logged.

**S2 is the load-bearing measurement of the whole book.** Oracle coverage (is the
gold answer equivalent to *any* candidate?) minus plurality accuracy tells us,
per benchmark, whether to invest in better **generation** or better **selection**.
Its output is a decision rule, not a win/lose bar: *invest-in-selection* iff
(oracle@8 − plurality@8) >= 10 points on >= 2 of 3 seeds with >= 9 recoverable
items. S3, S6 and half of S5 then cost **nothing** on top of it — which is what
makes S2's spend worth paying.

**S7 is the only spec that can ship a selector.** A selector chosen on the same
pool it was scored against is fitted to that pool; S7 re-tests the winner on
freshly generated pools at seeds never used in selection, on its home benchmark
*and* one it was not chosen on.

---

## 4. Math + programmatic verification

*(catalogue continues below, as assembled)*

2024 predates plausible training cutoffs and is a contamination suspect; a headline number that mixes them hides it.
- **Minimum falsifiable effect at n=60.** Under the repo's one-sided McNemar convention (§1.1), **+5 net discordant with zero losses** is the floor (p=0.031). MATH-0 retains the stricter **6-discordant, two-sided** figure (2×(1/2)^6 = 0.031) as the AIME house minimum, since it is the more conservative of the two and this surface has no second population to fall back on. Any bar phrased below 6 discordant items on AIME is unfalsifiable and must be rewritten or dropped.
- **Seeds.** Replicate labels **101 / 202 / 303**. Seed 42 is burned on AIME specifically by the invalidated run #1.
- **Command.** No paid command. The precedent this codifies is measured: `benchmark/results/aime_cheap_pilot_seed42.log` — 12/60 baseline drops + 32/60 panel drops (HTTP 429), leaving 26 common items on which BOTH arms scored 100.0% (`aime_open_baseline_seed42.jsonl` 48/48 correct; `aime_open_panel_cheap_seed42.jsonl` 28/28 correct). That run is **UNUSABLE** and must not be cited as evidence for or against anything.
- **Admissibility bar.** A run is admissible iff: 60/60 rows in every arm, question_id intersection = 60, year split reported, discordant b/c reported. Inadmissible runs are logged as spend and discarded.
- **Kill.** N/A as a spec, but it kills runs: if the log shows any drop, the run's numbers are never analysed — only re-run.
- **Token cost.** **0** (analysis contract only).
- **Build needed.** None to state it; ~40 lines to enforce cheaply — a math-side equivalent of `benchmark/retry_dropped.py` (which only understands GPQA rows) that reads an existing `aime_open_*.jsonl`, re-solves the missing question_ids, and appends. Optional: re-running the whole 60 at concurrency 3 also satisfies the rule.
- **If it fails, we learn.** This is what makes every other spec in the family readable. Without it, a repeat of run #1's 100%/100% survivor artifact would be mistaken for "AIME is saturated" when it is actually "the hard items timed out."
- **Priority.** P0, free.

---

#### MATH-1 — AIME liveness screen: is there a cheap-to-flagship gap at all?

- **Hypothesis (falsifiable).** On the full 60-item AIME population, the cheap tier (qwen3.6-flash, thinking off, single call) trails the flagship (qwen3.7-max, thinking on, single call) by a **net** ≥10 discordant items — i.e. AIME has the large cheap-to-flagship gap the validated law says is the precondition for every deliberation lever in this family.
- **Arms.** Two arms, same 60 items, same run, paired by construction. (A) **flagship single call** = `run_math_open`'s always-on `solve_single_math` baseline (ORCHESTRATOR_MODEL, thinking=True, BASELINE_LENS, temp 0.3). (B) **cheap single call** = `solve_selfconsistency_math` with n=1 and margin_threshold=1, which collapses offline to exactly one flash call and NO judge (`_sc_cluster_margin(['237'])` → margin 1, escalated = 1<1 = False). No new code path, no new lever.
- **Dataset / n / seeds.** AIME 2024+2025, n=60 (full population). Report overall and split 2024 (30) vs 2025 (30). Seed **101** (screen). If admissible and the result lands within 3 discordant of a kill/bar boundary, replicate on 202 and 303 before deciding.
- **Command.**
  ```
  python -m benchmark.run_math_open --dataset aime --n 60 --seed 101 --mode sc \
    --sc-n 1 --sc-margin 1 --solver-tier cheap --concurrency 3
  # writes aime_open_baseline_seed101.jsonl (flagship) + aime_open_sc_cheap_seed101.jsonl
  # then an offline paired diff by question_id + year prefix (~20 lines, 0 tokens)
  ```
- **Bar (pre-registered, made directional).** **ALIVE** iff `b − c ≥ 10` where b = flagship-correct/cheap-wrong and c = the reverse (**net** flagship advantage, not just b ≥ 10) **AND** flagship accuracy ≤85% (≥9 items of headroom left for any lever to win). Both conditions.
- **Kill (dominates — precedence stated explicitly, which the draft omitted).** **KILL DOMINATES BAR.** Kill the ENTIRE AIME branch (MATH-2, MATH-3 and MATH-4's replacement read die with it; redirect to MATH-5/MATH-6) if EITHER: cheap single-call accuracy ≥90% (AIME is saturated exactly like MATH-500 L5, and run #1's flash 100% was not purely survivorship), OR flagship accuracy ≥95% (no headroom — a lever cannot move 6 discordant items into a 3-item gap). The draft's bar and kill were simultaneously satisfiable (flagship 85% / cheap 90% with b=10, c=13 passes both); the directional bar plus this precedence rule removes the undefined state. **CONTAMINATION FLAG** (a caveat, not a kill, and it must travel with every later AIME number): if 2024 accuracy exceeds 2025 accuracy by ≥8 items at the cheap tier, treat AIME-2024 as memorised and run all subsequent AIME specs on the 2025 half only (n=30, which raises the minimum falsifiable effect and probably kills the branch on power grounds anyway — say so).
- **Token cost.** ~**1.8M** (4.1% of weekly). Measured, not guessed, from run #1's logged usage: flagship baseline 5,327 tok/call (median 4,454 output + ~1.1k input); cheap flash solver 24,411 tok/call (median 22,792 output). **Note the inversion:** on AIME the "cheap" flash call costs ~4.6× the flagship call in tokens, because `max_tokens=2048` is demonstrably not enforced by this endpoint (both tiers blew past it) and flash rambles. Every cost model in this family uses measured tokens, never tier labels.
- **Build needed.** **NONE.** Every flag used already exists in `benchmark/run_math_open.py` (`--dataset aime`, `--mode sc`, `--sc-n`, `--sc-margin`, `--solver-tier cheap`, `--concurrency`). Only the offline paired/year-split diff is new (~20 lines, zero tokens).
- **If it fails, we learn.** We retire AIME with a clean, drop-free, publishable null ("both tiers saturate the only hard-math set we can load"), which is the honest closure of the MATH-500 story rather than a second survivorship artifact — and MATH-5 becomes the family's only live open-answer path. Either way it delivers the measured cheap-vs-flagship **token** ratio on hard math, which reprices every SC@N design below.
- **Priority.** **P0 — one of only two paid week-1 items in this half of the book.**

---

#### MATH-2 — AIME SC@N curve at flagship tier, N=1..17, from ONE run

- **Hypothesis (falsifiable).** Flagship-tier self-consistency accuracy on AIME rises with N and has not flattened by N=17, gaining ≥6 discordant items from N=1 to N=17; and the F4 early-stop rule at margin_threshold=2 recovers ≥35% of the sample budget at zero accuracy cost.
- **Arms.** ONE paid arm — SC@17, flagship solvers, thinking on, `--no-early-stop` so all 17 draws are always taken. **The N=1 anchor is corrected:** it is the **first logged SC draw** (or the mean over single-draw prefixes, free once `sample_answers` is logged), *not* the always-on flagship baseline. The baseline uses a different configuration (BASELINE_LENS, temp 0.3), so anchoring on it would confound sampling scale with a prompt/temperature change — on the one comparison the entire 5.9M exists to make. The separate flagship baseline is reported only as an **external reference**. Every intermediate N is reconstructed OFFLINE from the ordered per-sample answers by re-clustering the first N with `math_grade.grade`, bootstrapped over sample orderings. Early-stop savings are likewise replayed offline at margin_threshold ∈ {2,3,4}. One arm buys a 7-point curve and a 3-point margin sweep; separate paid arms would cost ~4×.
- **Dataset / n / seeds.** AIME n=60 full population (or 2025-only n=30 if MATH-1 raised the contamination flag — in which case declare up front that only a ≥6-discordant effect on 30 items is readable, and consider not running). Seed **202** primary; **303** as the replicate if the N=17 vs N=1 discordant count lands in the ambiguous 5-8 band. Seed 101 is spent on MATH-1 and its items are identical anyway — a "second seed" adds decoder-noise replication, **not** new items; say so in the writeup.
- **Command.**
  ```
  python -m benchmark.run_math_open --dataset aime --n 60 --seed 202 --mode sc \
    --sc-n 17 --sc-margin 2 --solver-tier flagship --no-early-stop --concurrency 3
  # -> aime_open_sc_seed202.jsonl (17 ordered samples/item) + aime_open_baseline_seed202.jsonl
  ```
- **Bar (pre-registered).** **SCALES** iff accuracy@17 beats accuracy@1 by ≥6 discordant items **AND** the N=9→N=17 segment slope has a bootstrap CI over sample orderings excluding 0 (replacing the draft's ">= 1 item" conjunct, which was pure noise on 60 fixed items yet gated the whole SCALES/FLATTENS verdict). **FLATTENS** — a real, reportable result — if the 9→17 slope CI contains 0 while accuracy@17 still beats N=1 by ≥6: that is "SC@N pays but saturates at 9," and it sets the shipped N.
- **Kill (dominates).** Kill SC@N on open-answer math if accuracy@17 − accuracy@1 < 6 discordant items — the cons@64 result does not transfer to this model family on this surface. **Also kill on degenerate diversity:** if ≥50 of 60 items produce a SINGLE grade-equivalence cluster across all 17 draws, flagship sampling on AIME is effectively deterministic and there is nothing for voting to select over — report that as the mechanism and stop (the MATH-500 "0% escalation" failure recurring one difficulty tier up). Zero-drop rule from MATH-0 applies absolutely.
- **Token cost.** ~**5.9M** (13.5%): 60 × 17 × ~5,500 measured flagship tok/call = 5.61M, plus 0.32M baseline. Deliberately flagship-only: at the measured 24,411 tok/cheap-call the same curve on the cheap tier would cost ~24.9M (57% of the week). **The cheap tier is not the cheap option here.**
- **Build needed.** ONE small build, and it is the highest-leverage line in the family: `solve_selfconsistency_math` currently returns only `clusters` (sizes + one representative each), which **destroys sample order and membership** — the prefix curve cannot be reconstructed from it. Add `"sample_answers": answers` and `"sample_correct": [grade(item.gold_answer, a) for a in answers]` to the returned dict in `benchmark/math_open_engine.py` (~2 lines), plus one offline test in `tests/test_math_open_engine_offline.py` asserting order preservation and `len == samples_used`. Without it this spec costs 4 paid arms instead of 1 — and MATH-4's replacement read and SEL-2's open pool both become impossible. The early-stop replay analyzer is a further ~50 offline lines (zero tokens).
- **If it fails, we learn.** A strong, quotable result: a direct in-house falsification of the transfer of DeepSeek's cons@64 (86.7% vs 71.0% pass@1) to a different model family on a different-year AIME, on a fixed population with paired items and zero drops.
- **Priority.** P1, conditional on MATH-1 returning ALIVE.

---

#### MATH-3 — Structured-answer programmatic verification on AIME, with the checkable-fraction cap committed BEFORE any spend

- **Hypothesis (falsifiable).** AIME answers are integers 0-999 with no verifiable relation, so a CAS cannot check them directly — but a large minority of AIME problems declare their answer FORM ("find m+n where m/n is in lowest terms", "find a+b+c"). If solvers emit those declared intermediates alongside the final answer, a deterministic checker (range/integrality + gcd coprimality + the declared arithmetic, via the existing `sympy_check`/`substitute_check`) can reject internally-inconsistent candidates, and verified-and-most-clustered selection beats plain majority by ≥6 discordant items.
- **Arms.** **Gate first, arm second.** *GATE (0 tokens, run and committed BEFORE any paid call):* `benchmark/classify_aime_answer_forms.py`, mirroring the existing `benchmark/classify_pool_checkability.py` precedent — classify all 60 statements into {declared-form checkable, integer-range-only, unstructured} and publish the count. *ARM (only if the gate passes):* SC@9 flagship where the solver JSON contract is extended to `{reasoning, answer, form_fields:{...}}`, then selection = largest cluster among candidates PASSING the deterministic check, falling back to largest cluster overall when nothing verifies. **CONTROL:** plain SC@9 on the same 60 items — and MATH-2's N=17 run already provides a **free plain-SC@9 prefix** on the identical population, so the control is nearly free if MATH-2 ran.
- **Dataset / n / seeds.** AIME n=60; the effective denominator is the checkable subset only — report the effect on that subset AND on all 60. Seed **303**. The gate is deterministic, no seed.
- **Command.**
  ```
  python -m benchmark.classify_aime_answer_forms   # NEW, offline, 0 tokens; commit output before spending

  # conditional, and NOT YET RUNNABLE — --verified-select does not exist on run_math_open today
  # (its full arg list is --n --seed --level --concurrency --solver-tier --dataset --mode
  #  --sc-n --sc-margin --no-early-stop); the flag is part of build_needed below:
  python -m benchmark.run_math_open --dataset aime --n 60 --seed 303 --mode sc \
    --sc-n 9 --sc-margin 2 --solver-tier flagship --verified-select --concurrency 3
  ```
- **Bar (pre-registered).** **PRE-RUN CAP dominates everything:** if fewer than **24/60** items (40%) are declared-form checkable, the arm cannot move 6 discordant items even at a 25% flip rate — do not spend, mark it killed-by-cap, move on. If the cap passes, the bar is ≥6 discordant items over plain SC@9 on the same items, with **every flip traced to a specific rejected candidate** (a flip with no logged rejection is an accounting bug, not a win).
- **Kill (dominates).** Killed by cap at <24/60 checkable — **state the expectation now: this is the likely outcome**, so a low number cannot be retro-spun. *Post-run kills, restated as rates:* the draft's "killed if the verifier rejects the CORRECT answer on ANY item" is essentially guaranteed to fire across 60 items × 9 samples through a newly-written `form_fields` parser, which would make the bar unreachable and the 3.1M a foregone conclusion. Replaced by: **false-rejection rate on gold-matching candidates ≤2% (i.e. at most ~1 of 60 items), with every false rejection traced and reported.** Zero tolerance is retained **only** for the deterministic sub-checks whose correctness is proven by unit test (range, integrality), never for the LLM-emitted `form_fields` path. Kill also if net discordant <6.
- **Token cost.** Gate: **0.** Arm: ~**3.1M** (7%) = 60 × 9 × ~5,700, or ~2.8M net if MATH-2's log supplies the plain-SC@9 control for free.
- **Build needed.** (a) `benchmark/classify_aime_answer_forms.py`, ~120 offline lines + tests. (b) An extended solver contract + deterministic checker in `math_open_engine` (`form_fields` parsing, gcd/coprimality, declared-arithmetic re-check, wired to the existing MCP tools) + a `--verified-select` flag on `run_math_open`, ~150 lines + ~8 offline tests. **This is the largest build in the family, and the 0-token gate exists precisely so we do not write it before knowing the ceiling.** Do not start the 150-line build until the gate reports ≥24/60.
- **If it fails, we learn.** The gate alone is a publishable honest fact in the W1-B pool-checkability tradition — what fraction of AIME is programmatically self-checkable at all — and it is the concrete answer to the field's "verifiable rewards are the reliable arbiter" claim on a surface where the answer is a bare integer. A null tells us verifiable-reward machinery does not transfer to answer-only competition math without a proof checker, which is itself the reason to stop looking for one here.
- **Priority.** P2. Gate runs in week 1 (free); arm conditional and expected killed-by-cap.

---

#### MATH-4 — Iso-token cheap vs flagship SC — **DROPPED**, replaced by a free read

- **Why it is dropped.** The draft committed ~6.1M (14% of a week) to cheap SC@4 vs flagship SC@17 at matched tokens, while conceding the answer "is probably already implied by MATH-1." MATH-1 (1.8M) already delivers the measured cheap-vs-flagship token ratio on AIME **and** single-call accuracy at both tiers; MATH-2's log supplies the flagship side of any N-matched comparison for free. Paying 14% of a week for a P2 question whose two inputs are already bought is dominated.
- **Replacement (0 tokens).** If the tier question survives MATH-1, answer it with a **4-draw prefix read** off MATH-2's already-paid flagship log against MATH-1's cheap single-call arm, on the identical 60-item population, and label it explicitly as an **underpowered secondary read** — a 4-draw prefix is not an iso-token cheap arm and must not be described as one. The genuinely decision-relevant number (iso-token) is not obtainable without the cheap arm, and this book declines to buy it.
- **What survives as a finding.** The token-price inversion itself: 4 cheap draws (4 × 24,411 = 97,644 tok/item) cost more than 17 flagship draws (17 × 5,500 = 93,500 tok/item). That arithmetic is the headline the spec existed to make legible, and it is already available from MATH-1's measured rates at zero additional cost.
- **Reinstatement condition.** Only if MATH-1 shows the cheap tier within noise of flagship on AIME accuracy — the one outcome that would make cheap ensembling token-competitive on hard math and genuinely reopen the tier question.
- **Priority.** Dropped.

---

#### MATH-5 — Harder-math sourcing beyond AIME: offline loader + grader gate first, liveness screen second

- **Hypothesis (falsifiable).** At least one additional answer-only competition-math source is loadable AND fully gradable by `benchmark/math_grade.grade`, and it shows a cheap-to-flagship gap that AIME (per MATH-1) may not — giving this family a live surface that is not a 60-item fixed population.
- **Arms.** **PHASE 1 (0 tokens).** Build loaders and run a grader gate. `math_grade` **fails closed**, so a source whose answer shapes it cannot parse would silently score 0%. Candidate ranking, stated honestly:
  - (i) **HMMT Feb 2025** — ~30 answer-only problems, harder than AIME. The HF id must be VERIFIED at build time (`MathArena/hmmt_feb_2025` is the likely id); if it does not resolve, **drop it — no scraping**. ~40 lines mirroring `load_aime.py`.
  - (ii) **OlympiadBench**, English text-only open-answer config (`Hothan/OlympiadBench`, `OE_TO_maths_en_COMP`) — several hundred items, the only candidate big enough to escape the n=60 power trap, but answer shapes are heterogeneous (intervals, sets, multi-valued) so the grader gate is the real risk. **The unverified-identifier risk applies to this config too, not just to HMMT** — verify it resolves before writing anything downstream. ~60 lines.
  - (iii) **Putnam and IMO-shortlist — REJECTED.** Answers are PROOFS; `math_grade` cannot grade them and no proof checker exists in this repo. Stated plainly rather than listed as options.
  **PHASE 2 (paid, only for a source that clears the gate):** the MATH-1 liveness screen, verbatim, on that source.
- **The gate is strengthened (the draft's version was weaker than the risk it retires).** `grade(gold, gold) is True` tests the gold string against itself; it does not test whether the grader can parse **model-shaped** answers. Phase 1 therefore also runs, per source, `grade(gold, f(gold))` over a pre-registered set of realistic formatting transforms — `\boxed{}`, `\text{}` wrappers, unit suffixes, equivalent fraction/decimal forms, set/interval reorderings — and requires ≥95% True on those too. The gate is **all-or-nothing per source**, and the **per-shape breakdown of failures is reported, not just the aggregate**: if failures concentrate on one answer shape, either filter that shape out (and report the filtered n) or drop the source.
- **Dataset / n / seeds.** Phase 1: all golds of each candidate. Phase 2: n=30 (HMMT) or n=90 (OlympiadBench — and n=90 restores the ±2.5pt noise floor and the 3-seed machinery this family loses on AIME). Phase 1 no seed; Phase 2 seed **101** for the screen, 202/303 held for validation.
- **Command.**
  ```
  pytest tests/test_load_hmmt_offline.py tests/test_load_olympiad_offline.py -q
  # NEW, 0 tokens: resolves the HF ids, runs the grader gate + the formatting-transform gate

  # conditional:
  python -m benchmark.run_math_open --dataset hmmt --n 30 --seed 101 --mode sc \
    --sc-n 1 --sc-margin 1 --solver-tier cheap --concurrency 3
  ```
- **Bar (pre-registered).** Phase 1 passes iff ≥95% of a source's golds round-trip through `grade()` **and** ≥95% survive the formatting-transform set (≥5% unparseable means every accuracy number from that source is silently deflated). Phase 2 uses MATH-1's bar: net cheap-vs-flagship discordant ≥10, or ≥6 at n=30, **and** flagship ≤85%.
- **Kill (dominates).** Drop a source immediately if its HF id does not resolve (no scraping, no manual transcription — the provenance would not survive review), or if it fails either gate, or if Phase 2 shows the same both-tiers-saturated pattern. If ALL candidates die, the honest conclusion is that this family has no live surface at the open-answer end and its remaining value is MATH-6.
- **Token cost.** Phase 1: **0.** Phase 2: ~0.9M for HMMT n=30 (2%) or ~2.6M for OlympiadBench n=90 (6%).
- **Build needed.** `benchmark/load_hmmt.py` and/or `benchmark/load_olympiad.py` (~40-60 lines each, mirroring `load_aime.py`'s `MathItem` construction), their offline gate tests, and one line each in `run_math_open`'s `--dataset` choices + dispatch. No engine changes. **All of Phase 1 is pure offline work runnable now, during the freeze.**
- **If it fails, we learn.** With a runnable gate, that no loadable answer-only source outside AIME survives our grader — a negative worth having written down before anyone proposes "just use Putnam" again.
- **Priority.** P1 for Phase 1 (free, week 1); Phase 2 conditional.

---

#### MATH-6 — Sampling vs perspective on multiple choice — **DERIVED, 0 tokens**

- **Hypothesis (falsifiable).** At matched N, a panel whose seats share one lens and differ only by resampling performs no worse than the shipped 3-distinct-lens panel — and the unanimous-wrong rate at high N, compared like-for-like against its own N=3 prefix, bounds what any agreement-based mechanism can reach.
- **Why it is no longer a paid spec.** The draft bought an `sc_mc` lever (~2.75M) plus a paired `control` run (~0.95M) on SuperGPQA-hard — the third purchase of the sampling-vs-perspective question (PS-1/PS-2 and SCI-6 were the other two). Under the merge (§1.6c) both objects are prefixes of the **PS-2 cycled harvest at seed 19**:
  - **Fixed-config SC arm:** seats {0, 3, 6, 9, 12} share lens 0 **and** temperature 0.3 → a genuine 5-sample self-consistency arm. The three lens tracks give three independent 5-sample arms that can be reported separately and pooled.
  - **Matched-N=3 comparison:** seats {0,3,6} (one lens, three samples) vs seats {0,1,2} (three lenses) — the same items, the same run, fully paired. **This is the confound-free version of the invalidated five-solver test:** there, lens cycling meant seat 4 = seat 1's lens, so nobody could tell whether scaling failed or whether copies were mislabelled as perspectives (§2.1, verified from the log). Here the lens is held fixed **by design** and sampling is the only axis.
  - **High-N unanimous-wrong readout:** computed at N=15 and, crucially, at the **N=3 prefix of the same run**, because unanimity of 15 samples is mechanically rarer than unanimity of 3 and the historical 61.6% figure was measured at N=3. The draft's kill compared the N=9 rate against a N=3 number — not apples to apples, and biased the run away from being killed.
- **Honest caveat that must travel with every number here.** The derived SC arm is at **fixed temperature 0.3**, not the shipped cycled schedule, so it is a **conservative, lower-diversity** estimate of SC@N. A temperature-cycled one-lens arm is not derivable from either harvest and is **not funded** — if it is ever wanted, it is a new paid arm and must be re-costed and re-registered.
- **Dataset / n / seeds.** SuperGPQA-hard n=90, seed 19 (inherited). Replication at 91/137 only if PS-1/PS-2 replicate. Seeds 909/1009/2026 are **released** back to the registry (909 is claimed by META-2/SCI-1 on this dataset).
- **Command.**
  ```
  python -m benchmark.analyze_panel_scaling \
    --harvest benchmark/results/PS2_cycled_panel_n15_supergpqa_seed19.jsonl \
    --track-mode fixed-config --n-grid 1,3,5 --compare-seats 0,1,2 \
    --unanimous-wrong-at 3,5,9,15 --paired-mcnemar \
    --out benchmark/results/MATH6_sampling_vs_perspective_seed19.csv
  ```
- **Bar (pre-registered).** The matched-N=3 sub-result is reported **regardless** as the answer to "is diversity coming from sampling or from perspective?" — it is a descriptive contrast, not a lever claim. For any promotion claim: net ≥ +5 discordant at one seed, or ≥ +3 at 2 of 3 seeds with pooled McNemar over n=270 clearing p<0.05 (the draft's "+3 on one seed at n=90" sat exactly on the unfalsifiability floor and gated an 8.3M three-seed spend). Strict monotonicity is **not** required — four noisy points on 90 items will break monotonicity for a real effect while adding no evidence; report `accuracy@9 ≥ accuracy@5 ≥ accuracy@3 within CIs`.
- **Kill (dominates).** Kill the SC-on-MC direction if the fixed-config arm fails the bar. **Ceiling kill, corrected:** compute the **N=3-prefix** unanimous-wrong rate from this same run and compare it against the historical 61.6%; report both the N=3-prefix and N=15 rates. If the N=3-prefix figure confirms ≥55% of wrong items are unanimous, the agreement-signal family is capped there and this is the run that proves it — with the like-for-like comparison the draft could not make.
- **Token cost.** **0.** (Was ~2.75M screen + ~8.3M three-seed validation.)
- **Build needed.** The `--track-mode fixed-config` / `--unanimous-wrong-at` modes in `analyze_panel_scaling.py` (~60 offline lines on top of what PS-1 already requires), plus an offline test asserting that the seat-track extraction really does return same-lens, same-temperature seats. **No `sc_mc` lever is built** — the ~80 lines of new lever code, its 10 tests, and its CLI surface are all avoided.
- **If it fails, we learn.** Either way it settles the single largest confound in the record, for zero tokens. The five-solver null has been uninterpretable since it was run; this read answers it. And the high-N unanimous-wrong measurement is a number the W5 predictor work explicitly flagged as UNMEASURED — it either raises or hard-caps every downstream routing idea.
- **Priority.** P1, free, runs the moment the PS-2 harvest lands.

---

**Bar.** Measured on DISCORDANT items only (`pre_probe_ruling != final_ruling`).
- **(a) COVERAGE GATE (the screen's only job, seed 909):** flip rate on unanimous items ≥ 10%. This is the gate that authorises the 2.6M extension.
- **(b) NET (extension, 3 seeds pooled):** (corrections − breakages) on the flip set **minus** the same quantity on the placebo set, ≥ +5 net discordant at one seed with exact McNemar p < 0.05, OR ≥ +3 at 2 of 3 seeds with pooled McNemar over n=270 clearing p < 0.05.
- **(c) REPORTED REGARDLESS — this is the deliverable even if (a)/(b) fail:** P(wrong | unanimous & flipped) − P(wrong | unanimous & stable), with Wilson 95% CIs. This is the instability feature W5 has never had, and the only feature that can see inside the 61.6% of wrong rows that are unanimous.

**Kill (evaluated before the bar).**
1. **FIDELITY:** blinded majority-of-3 audit against `benchmark/restatement_fidelity_rubric.md` (frozen and committed BEFORE any live call; the harness reads the prompt verbatim, same pattern as the frozen r3 relevance rubric) on a 40-restatement sample. If >20% are judged non-equivalent (gold answer changed, a given dropped, a choice made ambiguous), the lever is dead and NO accuracy number from it is reportable, positive or negative.
2. **COVERAGE FLOOR:** flip rate < 5% on unanimous items → dead, nothing to route.
3. **DECLARED BAND (new):** flip rate in **5–10%** is a formal **BAND / no-verdict** — report the (c) separation statistic, do not promote to a lever, do not fund the extension, and do not cite it as support for any other spec. This band previously had no declared consequence, which is the situation most likely to generate post-hoc reasoning.
4. Net negative on 2 of 3 seeds → dead.
5. **SURVIVORSHIP:** >10% item drops on any seed → re-run that seed before scoring.

**Token cost.** Screen (seed 909): 13.7k/item × 90 = 1.23M + placebo tribunal on ~6 placebo-only items × 9.29k ≈ 0.06M → **~1.3M**. Extension (1313 + 2027): **~2.6M**. Total if fully fired **~3.9M (8.9% of weekly)**. The 13.7k/item is built from measured parts: control 10.5k + ~0.9k rewrite + ~1.2k probe seat on ~73% of items + ~9.29k tribunal on the ~12% newly escalated. **Controls are not charged here** — they are META-2 arm A.

**build_needed.** In `benchmark/lever_experiments.py`: `restate_question()` (flash, frozen prompt, returns `{restated_question, restated_choices[4], canonical_index_map[4]}`, **fails closed to "no probe" on malformed JSON** — a failed rewrite must never silently become a flip); `_solve_one_restated()` (identical to `_solve_one` except the user turn carries restated text, letter mapped back exactly as `_solve_one_permuted` does); `--placebo-escalation-rate` flag with the seeded random trigger; `restate_probe` wired into `--lever` choices, `run_question_lever` (probe fires only on unanimity) and `_build_output_row` (new keys `restate_ok, probe_letter, flip, placebo_triggered, pre_probe_ruling, final_ruling, restated_question, canonical_index_map`). NEW: `benchmark/restatement_fidelity_rubric.md` (frozen, committed first) and `benchmark/score_restatement_fidelity.py` (blinded majority-of-3, mirrors `score_r3_relevance.py`). Offline tests: mapping round-trip, malformed-rewrite fail-closed, byte-identical non-unanimous path vs `control`.

**If it fails.** If the net is null but the flip feature separates, we have solved the stated W5 blocker — no run has ever logged instability features — and the failure is localised to selection/tribunal quality, matching F1(b)'s selection-side finding. If flips are frequent but random, cheap-panel unanimity is unstable-but-uninformative, which kills the whole adversarial-restatement direction (including the already-dropped SCI-6) and redirects everything toward retrieval. If flips are rare, the cheap panel is genuinely input-invariant and the ceiling is knowledge, not framing.

---

### SCI-2 — `backward_check`: blinded per-choice consistency scoring (CONDITIONAL, week 2+)

**Hypothesis.** Scoring each of the four choices INDEPENDENTLY and BLIND — one call per choice, seeing only the question and that single choice — will disagree with the cheap panel's unanimous letter often enough, and correctly enough, to be a net-positive escalation trigger; and the gain is attributable to **blinding** specifically, not to candidate-checking in general.

Stated honestly: this is **partly** the ceiling in a new costume — same model, same content, so shared factual blind spots survive. The narrow new claim is about **anchoring**, not knowledge: every existing seat sees the full choice set and can be pulled by the most-plausible-looking distractor; per-choice blinded scoring removes cross-choice comparison entirely.

**Arms.** **TREATMENT (blinded):** shipped panel unchanged; on UNANIMOUS items, 4 flash calls (each seeing question + exactly ONE choice, blind to the panel's vote and to the other choices) return `{consistency: 0.0-1.0, violated_given: str|null}`. Escalate into the shipped tribunal if argmax-consistency ≠ the panel's letter AND the margin over the panel's letter ≥ 0.2. **MATCHED UNBLINDED COMPARATOR (new — this is the actual falsifier):** the identical 4-call scorer with the FULL choice list visible in each call. One variable changed, same trigger, same items. `method_panel` is **not** used as the falsifier — it replaces the three solver seats while `backward_check` layers a probe on unanimous items only, so their head-to-head isolates nothing about blinding. **PLACEBO ARM:** same seeded random-escalation control as SCI-1, at the observed trigger rate. **CONTROL:** within-run `pre_check_ruling`.

**Dataset / n / seeds.** SuperGPQA-hard, n=90. **Seed 1213 = screen; 1427, 1619 = extension.** All fresh, and deliberately different items from SCI-1's 909/1313/2027 so that at 3 seeds the two probes do not compete for the same ~45 unanimous-wrong items. If the W2 shelf run of `method_panel` (currently **zero logged rows** among the 74 result files) ever happens, it must use these same seeds so the comparison is free; this spec does **not** pay for a second `method_panel` run.

**Command.**

```bash
python -m benchmark.lever_experiments --lever backward_check --n 90 --seed 1213 --dataset supergpqa \
  --unblinded-comparator --placebo-escalation-rate 0.10 --concurrency 4 \
  --out benchmark/results/SCI2_backward_check_supergpqa_seed1213.jsonl
```

**Bar.** On discordant items: **(a)** trigger rate on unanimous items ≥ 10%; **(b)** (corrections − breakages) on the trigger set minus the placebo set ≥ +5 net at the screen seed with exact McNemar p < 0.05, or ≥ +3 at 2 of 3 seeds with pooled n=270 McNemar p < 0.05; **(c)** blinded-minus-unblinded net, reported as the blinding effect; **(d)** reported regardless: P(wrong | unanimous & backward-disagrees) − P(wrong | unanimous & agrees) with Wilson CIs, **and the overlap with SCI-1's flip set** (redundant or additive?).

**Kill (first).** **Gate:** runs only if SCI-1 clears its coverage gate but fails its net bar — the branch where a second, differently-shaped probe is informative. **Degeneracy:** if the panel's letter takes the top consistency score on >80% of unanimous items AND the mean top-vs-second margin is <0.1, the scorer is the same blind spot with a numeric skin — kill and report it as such. Trigger rate <5% → kill. Net ≤ 0 on 2 of 3 seeds → kill. **If the unblinded comparator matches or beats the blinded scorer, the blinding hypothesis is falsified** — report that any gain is from candidate-checking (already built as `method_panel`) and drop this lever. >10% drops → re-run.

**Token cost.** Blinded 4 calls ≈ 4.4k on ~73% of items + tribunal on ~10% newly escalated, over the 10.5k control baseline ⇒ ~15.5k/item; the unblinded comparator adds ~4.4k/item plus its own tribunal share ⇒ ~20k/item. **Screen (1 seed): ~1.8M. Full 3 seeds: ~5.4M.** Committed number is the 1.8M screen; `method_panel` is **not** charged (previously ~2.8M of duplicate spend).

**build_needed.** In `lever_experiments.py`: `_score_choice_blinded(client, question, choice_text)` (frozen prompt; user turn contains the question and **exactly one** choice — no letters, no other options, no panel votes; asserted by an offline test); `solve_all_backward_check()` orchestrating 4 concurrent calls, argmax + margin; the `--unblinded-comparator` path; row keys `per_choice_consistency[4], backward_pick, backward_margin, panel_pick, backward_disagrees, unblinded_pick, unblinded_disagrees, pre_check_ruling, final_ruling`. Offline tests: margin/tie handling, malformed-score fail-closed (no trigger), the exactly-one-choice assertion, byte-identical non-unanimous path.

**If it fails.** A null with a degenerate score distribution is the cleanest available evidence that the cheap model's unanimous errors are **knowledge-shaped** rather than framing-shaped. Together with an SCI-3 null that means the ceiling cannot be moved by any self-inspection variant, and the only remaining routes are external arbiters (verifier tools, CAS) or a stronger model — a decisive narrowing of the search space.

---

### SCI-3 — `step_audit_replay`: does process-level checking see what answer-voting cannot? (offline, frozen logs)

**Hypothesis.** A critic that audits reasoning STEPS rather than final answers will flag unanimous-WRONG panels at a materially higher rate than unanimous-RIGHT ones. Stated adversarially: my prior is that this **is** the ceiling in a new costume — the auditor is the same `qwen3.6-flash` family that produced the reasoning, so a shared blind spot appears in both the answer and the steps. The spec is designed to settle that with the cheapest possible evidence and to be published as a null if it is one. It runs entirely on already-logged rows, so a family whose live version would cost ~4M is screened for ~1.5M.

**Arms.** **ARM A (auditor):** flash step-auditor, frozen prompt, sees question + choices + the three logged seat reasonings, returns `{n_steps_identified, flagged, flaw_step_index, flaw_description}`, **blind** to the panel's letter, the correct letter, and whether the item was ever escalated. **ARM B (null model):** the identical prompt with the reasoning transcripts replaced by those from a different, randomly paired unanimous item on the same dataset (shuffled-transcript control). Arm B measures the auditor's base flag rate on non-diagnostic content; any Arm A separation must exceed it. There is no live engine arm — that is the point.

**Dataset / n / seeds.** Frozen `benchmark/results/lever_*.jsonl`. **Inventory reconciled to the measured figure: 4,624 rows carrying `engine.solver_answers` across exactly 60 files** (the earlier 4,106 figure is superseded; if a filter reproduces 4,106 it must be stated explicitly). Dedupe to distinct `(dataset, question_id)` — rows repeat across levers and seeds and are NOT independent. **Dedupe rule changed from "first occurrence" to a preference order: `control` → `thinking_gate` → others**, because the audited transcript must come from the shipped configuration; "first occurrence" could hand the auditor a `rag_presolve` transcript whose solver prompt carries an injected evidence block, while the conclusion is stated about the shipped cheap panel. **The lever mix of the final sample is reported.** Sample: all ~261 distinct unanimous-wrong + a subject-matched random 261 unanimous-right. LEXam rows excluded (corpus-mismatch confound, engine −14 there). No sampling seed; matched-control pairing uses `analysis:5501`.

**Command.**

```bash
python -m benchmark.replay_step_audit --results-glob "benchmark/results/lever_*.jsonl" \
  --exclude-dataset lexam --dedupe-prefer control,thinking_gate --match-seed 5501 \
  --out benchmark/results/SCI3_step_audit_replay.jsonl
python -m benchmark.analyze_step_audit --in benchmark/results/SCI3_step_audit_replay.jsonl \
  --prevalence-by-dataset --out benchmark/results/SCI3_step_audit_findings.md
```

**Bar.** On the balanced discordant population: flag-rate separation (flag% on unanimous-wrong − flag% on unanimous-right) **≥ 20pp with Wilson 95% CI lower bound > 0**, AND Arm A separation ≥ Arm B separation + 15pp, AND **precision ≥ 40% at the DEPLOYED prevalence, not on the balanced sample.** The balanced sample estimates sensitivity/specificity; precision is then obtained by Bayes at the measured per-dataset unanimous-wrong rate (SuperGPQA-hard 20.6%). At that prevalence, 40% precision implies roughly specificity ≥ 0.77 at sensitivity 0.6 — the implied operating point is printed next to the number so the bar is transparent. Balanced-sample precision is reported as a diagnostic only. At n≈261/261 a 20pp gap is far outside binomial noise.

**Kill (first).** (1) Separation < 10pp, or CI lower bound ≤ 0 → the auditor is the same blind spot in a new costume; publish the null, build no live process-checking lever. (2) Flag rate > 60% of ALL unanimous rows → untargetable; escalating that fraction costs more than calling the flagship on everything, which F2 already showed Pareto-dominates on 6 of 9 benchmarks. (3) **UNDERPOWERED CLAUSE, pre-registered so a null cannot be over-claimed:** if separation is null AND >50% of rows yield `n_steps_identified < 2`, the verdict is **"underpowered, not null"** — the shipped solver prompt caps reasoning at 3 sentences, so logged traces may be too thin to audit. The only licensed follow-up in that branch is a small live arm (n=90, 1 fresh seed, ~1.2M) with the cap lifted, and no claim about process-checking may be published until it runs.

**Token cost.** 261 + 261 = 522 Arm A rows and 261 Arm B rows × ~1.9k tok (question + choices + 3 reasonings in, ~300 out) ≈ **~1.5M (3.4% of weekly)**, no new solver calls.

**build_needed.** Two new files, no change to `lever_experiments.py`: `benchmark/replay_step_audit.py` (iterate results, dedupe by preference order, select unanimous rows, build the shuffled-transcript pairing, call the frozen `step_audit()` flash critic blinded to letters/correctness) and `benchmark/analyze_step_audit.py` (flag rates + Wilson CIs by arm/correctness/dataset, prevalence-corrected precision, ROC-AUC, and the `n_steps_identified` histogram that decides the underpowered clause). Frozen auditor prompt committed in the same commit as the analyser, before the replay runs.

**If it fails.** The most valuable null available: it closes the process-checking branch permanently for ~1.5M and shows the flash family's errors are correlated at the step level as well as the answer level — independently corroborating the qwen38_panel homogeneity trap and the external "reflection tokens do not track correctness" finding, and strengthening the case that decorrelation must come from the INPUT or from an external arbiter. The underpowered branch is itself a finding: our own 3-sentence reasoning cap would have been hiding the signal every wrongness-predictor attempt needed.

---

### SCI-5 — `gap_gate`: does the chemistry win's mechanism transfer, or is it a chemistry artifact? (FREE gate first; GPQA primary)

**Hypothesis.** The chemistry win is an instance of the VALIDATED LAW (route where the cheap-to-flagship gap is large), not a fact about Organic Chemistry: a subject-generic gate routing high-gap subjects to the flagship+thinking panel reproduces `chem_thinking_gate`'s gain on **non-chemistry** high-gap slices. This is not a new mechanism — it is the falsification test for the one predictor we claim is validated. If it fails, "predictor = cheap-to-flagship gap" becomes "we found one good subject", which downgrades the central claim of the record.

**Two fatal corrections applied.**
1. **Dataset flipped to GPQA as PRIMARY.** `chem_thinking_gate` gates on an exact string match `subject == "Organic Chemistry"` (`lever_experiments.py:430, :462`), while `load_supergpqa.py:117` sets `subject = row.get("discipline")` — 13 coarse values (Science / Engineering / Medicine / …). On `--dataset supergpqa` the chemistry branch **never fires** and `chem_thinking_gate` degenerates byte-identically to `thinking_gate`. The SuperGPQA "chemistry control" was dead code, and ~3.3M of the original 9.5M bought a mislabelled duplicate arm. Compounding it: every logged `chem_thinking_gate` run is on **GPQA** (seeds 217/314/471, 264 rows) — the win being "transferred" was never measured on SuperGPQA at all. GPQA is also the only dataset with fine-grained subject labels in the frozen logs. **The SuperGPQA arm is dropped entirely.**
2. **The paid `chem_thinking_gate` control arm is dropped.** Non-inferiority is assessed **descriptively** against the 264 existing GPQA rows and explicitly labelled as unpaired/descriptive, not as a matched control.

**Arms.** **GATE (0 tokens, run and committed BEFORE any paid call):** `benchmark/build_subject_gap_table.py` — per subject, the rate of items where the cheap panel was unanimous-wrong AND the flagship baseline was right (the operational gap, and exactly the F1 family-floor quantity), computed **only on PAIRED items** present in both a control and a baseline run at the same seed, with per-subject paired n and Wilson CI, written to a committed `benchmark/data/subject_gap_table.json`. The table also reports the unpaired rate difference **separately**, so the two can never be conflated. **TREATMENT (conditional):** `gap_gate` — per item, look up the subject in the frozen table; if gap ≥ threshold solve with the 3-flagship-thinking panel (the identical code path as `solve_all_chem_flagship`'s chemistry branch), else `solve_all_thinking_seat`'s panel. **CONTROL:** `control` on the same items and seed. **CEILING REFERENCE:** existing `flagship_panel` numbers.

**Dataset / n / seeds.** GPQA, n=90, **one screen seed: 7103** (fresh). Extension seeds 8117/9127 reserved and fired only on a positive screen. The gap TABLE is computed only from runs on burned seeds and committed **before** 7103 is drawn, so the routing rule cannot have been tuned on the evaluation items.

**Command.**

```bash
# FREE GATE — run and commit FIRST; it may retire the spec at zero cost
python -m benchmark.build_subject_gap_table --results-glob "benchmark/results/lever_*.jsonl" \
  --dataset gpqa --require-paired --min-paired-n 25 \
  --out benchmark/data/subject_gap_table.json
git add benchmark/data/subject_gap_table.json && git commit -m "Freeze SCI-5 subject gap table before any paid run"

# CONDITIONAL screen (only if >=3 non-chemistry subjects reach paired n>=25
# AND the projected non-chem high-gap subset is >=60 of 90 items)
python -m benchmark.lever_experiments --lever gap_gate --n 90 --seed 7103 --dataset gpqa \
  --gap-threshold 0.10 --out benchmark/results/SCI5_gap_gate_gpqa_seed7103.jsonl
python -m benchmark.lever_experiments --lever control --n 90 --seed 7103 --dataset gpqa \
  --out benchmark/results/SCI5_control_gpqa_seed7103.jsonl
```

**Bar.** **(a) TRANSFER — the actual hypothesis:** on items whose subject is NOT chemistry and whose gap ≥ threshold, `gap_gate` beats `control` by ≥ +5 net discordant at the screen seed with exact McNemar p < 0.05 (or ≥ +3 at 2 of 3 seeds pooled at p < 0.05 if extended). **(b) NON-INFERIORITY:** descriptive comparison against the 264 logged GPQA `chem_thinking_gate` rows, labelled unpaired. **(c) SPEND DISCIPLINE:** `gap_gate` routes ≤ 60% of items to the flagship panel; above that it is `flagship_panel` with extra steps and must be compared against `flagship_panel`'s measured +4.1 rather than against `control`.

**Kill (first).** (1) **Killed-by-power at the free gate** — fewer than 3 non-chemistry subjects with **paired** n ≥ 25, or a projected non-chem high-gap evaluation subset below ~60 of 90 items. This is the **expected** outcome (the frozen GPQA logs show Organic Chemistry 25 unanimous-wrong rows, Molecular Biology 5, Electromagnetism and Photonics 6), it is stated now so a low number cannot be retro-spun, and it costs zero tokens to establish. (2) Non-chemistry high-gap net ≤ 0 → the mechanism does NOT transfer; the record must be amended to say the chemistry win is subject-specific and the gap-predictor claim downgraded to a single-subject observation. Expected on mechanistic grounds: `smart_gate` (more thinking, same model) made chemistry **worse** while `chem_flagship_gate` (different model) helped — that pattern says "knowledge blind spot in one subject", which is exactly what fails to transfer. (3) Routing rate > 80% → degenerate. (4) >10% drops → re-run.

**Token cost.** Gate: **0**. Screen: `gap_gate` ~12.3k/item + `control` ~10.5k/item (the SuperGPQA-measured control rate used as a stated proxy for GPQA) × 90 = **~2.1M (4.8% of weekly)**, conditional. Down from 9.5M committed + 9.5M conditional.

**build_needed.** `benchmark/build_subject_gap_table.py`, **including the step the original spec omitted: a uuid re-join** — the frozen logs cannot supply a routing key on their own, so the loader's fine-grained subject must be re-joined onto logged rows by uuid (extending the loader only fixes future runs). In `lever_experiments.py`: `solve_all_gap_gate()` (reuses `solve_all_chem_flagship`'s chemistry branch and `solve_all_thinking_seat` verbatim — no new solving code), a `--gap-threshold` arg, `gap_gate` in `--lever` choices, row keys `gap_lookup_key/gap_value/gap_routed/routing_fallback_level`. Offline tests: lookup with missing/thin subjects falling back one level, threshold boundary behaviour, byte-identical low-gap path vs `thinking_gate`. The `load_supergpqa.py` `field` extension is still worth doing for future runs but is **no longer load-bearing** for this spec.

**If it fails.** The record's "predictor = cheap-to-flagship gap, NOT difficulty" claim would be supported by one subject on one benchmark, and we would be over-claiming until proven otherwise. Catching that ourselves is worth more than another marginal lever — and the frozen gap table is a permanent zero-token asset that other specs can route on.

---

### META-1 — Selective answering: risk-coverage curve from the logged runs (0 tokens)

**Hypothesis.** On held-out benchmarks, some rule computable at inference time abstains on part of the pool and raises accuracy-on-answered by ≥ 5pt MORE than the trivial "abstain iff the panel split" rule at matched coverage.

**Arms.** Scored on identical logged items, no new inference: **(R0)** 100% coverage (the shipped number); **(R1) TRIVIAL CONTROL** — abstain iff `engine.escalated` is True (free, already shipped, and every other rule must beat it); **(R2)** `FEATURES_FULL` logistic score (`build_wrongness_predictor._make_pipeline`) thresholded to matched coverage; **(R3)** verbalised-confidence only; **(R4) ORACLE** abstention as the ceiling reference, not a candidate.

**Dataset / n / seeds — fatal correction applied.** The original bar named four held-out slices, two of which do not exist or cannot carry the test. Measured inventory of rows carrying `engine.solver_answers`: **GPQA 2,731** (601 dataset-tagged + 2,130 pre-dataset-key), **SuperGPQA 1,553**, LEXam 230, MMLU-Pro-STEM 60, MMLU-Pro 50, **MedQA 0**. Leave-one-benchmark-out therefore yields exactly **two usable folds**.
- **PRIMARY:** SuperGPQA-hard and GPQA, group-aware LOBO (fit on one, report only the other).
- **REPORTED, UNDER-POWERED:** LEXam (230 rows, and corpus-mismatched — flagged).
- **DESCRIPTIVE ONLY, with base error rate printed beside every number:** MMLU-Pro-STEM (flagship 96.7%, unanimous-wrong 1.7%) and MMLU-Pro. A risk-coverage curve on a 1.7–4% base error rate has almost nothing to abstain on; a null there would be attributable to slice choice, not to the feature. **MedQA is deleted from the design.**
- **Non-independence fix:** the same `(dataset, question_id)` recurs across 20 levers and overlapping seeds, so the 2,000-sample bootstrap must be **clustered on `(dataset, question_id)`** and the LOBO split must be group-aware, or the rows deduped per benchmark before fitting. The deduped n is reported alongside the raw row count. Rows lacking a dataset key are assigned to GPQA **only** where per-file loader-default provenance is confirmed (e.g. `lever_five_seed42.jsonl` has `dataset: None` = the loader default = GPQA); otherwise excluded.
- **Seeds:** no API seeds. CV/bootstrap seed **`analysis:5309`**, recorded in an analysis-seed namespace that can never be mistaken for a sampling seed (the original 909 collided with three run-seed claims).

**Command.**

```bash
python -m benchmark.analyze_selective --inventory-first \
  --primary supergpqa,gpqa --descriptive mmlu_pro_stem,mmlu_pro --underpowered lexam \
  --coverage-grid 0.4,0.5,0.6,0.7,0.8,0.9 --heldout leave-one-benchmark-out \
  --cluster-on dataset,question_id --n-boot 2000 --analysis-seed 5309 \
  --report benchmark/results/META1_selective_answering_findings.md
```

**Bar.** On **≥ 1 of the 2 primary folds**: (R2 or R3) accuracy-on-answered exceeds R1's at MATCHED coverage by ≥ 5pt, clustered bootstrap 95% CI excluding 0, AND the abstained set carries ≥ 2× the base error rate. Discordant-item counts reported per slice; any comparison resting on < 3 discordant items is declared unfalsifiable and excluded from the bar. The `conf_*` non-nullity audit (the `has_confidence` flag already exists in the feature set) is a **gate that runs before the sweep**, not a caveat afterwards, so R3 is never silently evaluated on a subset.

**Kill (first).** No learned rule beats R1 by ≥ 5pt on either primary fold → feature-engineered abstention is closed; ship or drop the trivial split-flag rule and route all remaining calibration effort into META-2's instability feature. **Second kill:** if R1 itself fails to lift accuracy-on-answered by ≥ 5pt over R0 on both primary folds, the abstention proposition is dead at the agreement layer and META-6's panel arms should not be run.

**Token cost.** **0 API tokens** (~1 CPU-minute). Runnable NOW during the block.

**build_needed.** SMALL. `benchmark/analyze_selective.py` (~180 lines): mandatory inventory print (rows per dataset × lever) as the **first** output so a missing slice is caught before the sweep; coverage-threshold sweep; matched-coverage comparison; clustered bootstrap; oracle ceiling. Reuses `build_inventory` / `FEATURES_FULL` / `FEATURES_VERBALIZED` / `_make_pipeline` from `benchmark/build_wrongness_predictor.py` verbatim.

**If it fails.** A null converts W5's AUC 0.625 into a product statement — "our confidence signal is not good enough to sell abstention" — which is publishable and retires a whole line for free. A positive is the first metric where the engine has a **structural** edge over a bare flagship call: a single call produces no agreement signal at all, so it cannot draw a risk-coverage curve at any price. That attacks the F2 finding by changing the axis rather than the margin.

---

### META-2 — P(wrong | unanimous): permutation-instability probe on the unanimous pool (WEEK-1 FIRST PAID MOVE)

**Hypothesis.** Among items where the shipped cheap panel is unanimous, items whose unanimity BREAKS under independent per-seat choice-order permutation are wrong at ≥ 25pt higher rate than items whose unanimity survives — **and the effect is attributable to permutation rather than to plain decoder resampling.**

**Arms — the missing control is now included.** Same items, same seed:
- **(A) CONTROL / reference:** shipped 3-seat cheap panel, canonical choice order, unanimous-accept / split-escalate. Also serves as SCI-1's paired control (the merge).
- **(B) `permuted_panel`:** identical seats, lenses, temperatures and escalation logic, EXCEPT each seat sees an independently shuffled choice order (RNG seeded `f"{seed}:{question_id}:{seat_index}"`) with its letter mapped back to canonical before voting. The task is unchanged by construction, so per-seat accuracy cannot degrade for task-difficulty reasons.
- **(C) RESAMPLE-ONLY CONTROL (new, mandatory for the permutation claim):** canonical choice order, fresh independent sample — i.e. a second `control` replicate at the same seed. Arms A and B differed in **two** ways at once (order permuted AND seats freshly sampled), so a "flip" could be plain decoder noise at temps 0.3/0.6/0.9. **Flip rate (B) − flip rate (C) is the permutation-specific component; (C) alone is the resampling component.** If arm C is not funded, the hypothesis and every downstream claim must be relabelled **"resample-or-permute instability"** in the record — that relabel is the only permitted alternative.

Secondary readouts, free with the same runs: `permuted_panel` vs `control` accuracy (the original W2 Arm-0 decorrelation question) and per-seat position bias. Position bias also directly settles an assertion PS-1 currently makes without evidence ("permutation cannot lower per-seat accuracy, so 12 of 15 seats carry zero weak-seat risk") — which is why this spec should run **before** PS-1's 15-seat harvest if the schedule allows.

**Dataset / n / seeds.** SuperGPQA-hard, n=90. **Staged:** seed **909** = screen (arms A + B pre-checkpoint, arm C immediately post-checkpoint); seeds **1313** and **2027** = extension, all three arms, fired only if the screen clears the coverage gate. All fresh; burned seeds 42/7/123/555/777/888/271/314/217/471/606/838 excluded. The permutation RNG derives from the run seed, so every shuffle is reproducible from the logged seed alone. Expected pool from measured rates on this dataset (48.1% escalation, ~20.6% unanimous-wrong): ~47 unanimous items per seed, ~140 pooled, ~32 of them wrong. **Power is the binding constraint and is stated with the result:** ~32 positives gives roughly ±15pt CI on the contrast, which is why the bar is set at a large effect and why the screen seed alone cannot carry the predictive claim.

**Command.**

```bash
# stage 1 (pre-checkpoint): arms A and B at the screen seed
python -m benchmark.lever_experiments --lever control --n 90 --seed 909 --dataset supergpqa \
  --out benchmark/results/META2_control_supergpqa_seed909.jsonl
python -m benchmark.lever_experiments --lever permuted_panel --n 90 --seed 909 --dataset supergpqa \
  --out benchmark/results/META2_permuted_panel_supergpqa_seed909.jsonl

# stage 1b (immediately post-checkpoint): arm C, the resample-only control
python -m benchmark.lever_experiments --lever control --n 90 --seed 909 --dataset supergpqa \
  --replicate 2 --out benchmark/results/META2_control_resample_supergpqa_seed909.jsonl

# stage 2 (conditional): repeat all three arms at --seed 1313 and --seed 2027
python -m benchmark.analyze_unanimous_stability \
  --control  benchmark/results/META2_control_supergpqa_seed*.jsonl \
  --permuted benchmark/results/META2_permuted_panel_supergpqa_seed*.jsonl \
  --resample benchmark/results/META2_control_resample_supergpqa_seed*.jsonl \
  --restate  benchmark/results/SCI1_restate_probe_supergpqa_seed*.jsonl \
  --report benchmark/results/META2_unanimous_stability_findings.md
```

**Bar.** **(a) COVERAGE GATE (screen seed):** flip rate on unanimous items ≥ 10%, which authorises the extension. **(b) PREDICTIVE CONTRAST (3 seeds pooled):** flip-rate(unanimous & wrong) − flip-rate(unanimous & right) ≥ **25pt**, Fisher exact p < 0.05, with ≥ 8 flipped items total. **(c) MECHANISM:** flip rate (B) − flip rate (C) reported with CIs; the claim is written as "permutation instability" only if this difference is positive with a CI excluding 0, otherwise as "resample-or-permute instability". Anything resting on < 3 flipped items is declared unfalsifiable and reported as such. **(d)** Accuracy side-comparison (B vs A) under the standard bar: ≥ +5 net discordant at one seed, or ≥ +3 at 2 of 3 with pooled n=270 McNemar p < 0.05.

**Kill (first).** Contrast gap < 10pt or p > 0.2 → permutation instability is NOT a wrongness signal: do not build the paraphrase arm, do not build an instability-fed router, and record the unanimous-wrong floor as irreducible by cheap perturbation. This kill also finishes META-1: if neither logged features nor instability can see inside the unanimous pool, the calibration thesis is dead and effort moves to knowledge injection. Flip rate in the 5–10% band → declared BAND, no verdict, no extension (same declared-band discipline as SCI-1). >10% drops on any seed → re-run.

**Token cost.** Measured 10,505 tok/item on this dataset (`lever_control_supergpqa_seed7.jsonl`) ⇒ 0.95M per arm per seed. **Stage 1 (A + B, seed 909): 1.9M. Arm C: 0.95M. Stage 2 (3 arms × 2 seeds): 5.7M. Full spec 8.55M (19.5% of weekly), of which only 2.85M is committed before the mid-week re-check.** A cheap variant exists — pair `permuted_panel` against the EXISTING control logs on burned seeds 7/123/606 (~2.8M) — and is defensible because `permuted_panel` was pre-registered and never tuned on any item, but those unanimous pools have already been eyeballed and the variant breaks the SCI-1 merge. It is the fallback, not the primary.

**build_needed.** **NONE for the runs.** `permuted_panel` is already implemented, documented, offline-tested (`tests/test_lever_permuted_panel_offline.py`), wired into `--lever` choices, and logs `seat_permutations` per row — and it has **never been run** (zero `permuted_panel` files among the 74 result JSONL). New code: `benchmark/analyze_unanimous_stability.py` (~110 lines) joining the arms on `question_id`, computing the flip-rate contrast, the B−C decomposition, and the **free intersection with SCI-1's restatement-flip set**; plus a `--replicate` flag whose only effect is the output filename (so arm C is provably the same configuration as arm A).

**If it fails.** This is the single load-bearing unmeasured number in the record: 61.6% of all wrong rows are unanimous and no logged feature can see them. A positive gives the first feature that reaches inside that pool and unlocks META-1 abstention, SCI-1's premise, the MoO router's missing input, and every escalation-trigger spec in panel-scaling. A null closes the largest open question honestly, and it costs nothing to build because the lever already exists — which also clears the W2 shelf-build backlog before anyone proposes new levers.

---

### META-3 — Long-context: map-reduce vs a NON-crippled single call (WEEK 2+, probe-gated)

**Hypothesis.** When a document exceeds the flagship's context window, an N-reader map-reduce panel answers planted-fact questions more accurately than the best available single-call alternative — **where "best available" is retrieval-then-answer, not head-truncation.**

**Fatal correction applied.** The original primary comparator was head-truncation while needle position was randomised across start/middle/end, so at the overflow stratum truncation deterministically deletes the planted passage on ~two-thirds of items. A ≥20pt map-reduce advantage would have been guaranteed arithmetic, not evidence.

**Arms.** **(A) truncate-to-fit** with a **pre-registered chunk-selection rule** (not head-truncation), reported as a floor. **(A2) PRIMARY COMPARATOR — retrieval-then-answer:** top-k chunks selected by the already-built BM25 + mxbai dense + RRF fusion, then one `qwen3.7-max` call. **(B) MAP-REDUCE:** `ceil(len/chunk)` `qwen3.6-flash` readers, each given one chunk + the question, each returning `{answer | NOT_PRESENT, quoted evidence}`, then ONE `qwen3.7-max` synthesiser over the non-`NOT_PRESENT` returns. **(C) ORACLE reference:** one flagship call on the planted passage alone (isolates "can the model answer at all" from "can it find the passage"). **Needle-position breakdown is reported for every arm** so any residual truncation advantage is visible rather than pooled.

**Dataset / n / seeds.** Synthetic long-doc MCQ assembled from `benchmark/data/rag_index.sqlite3`: one planted passage plus distractor passages padded to target length; 4 choices so it drops into the existing MCQ scoring path; distractor choices generated from OTHER planted facts with a non-duplication assertion so the answer cannot leak. Strata: **8k (n=30)** and **32k (n=30)** — the fits strata, which are the only honest comparison — and, gated separately, an **overflow stratum at n=30** (raised from 20: at n=20 the old 20pt bar was 4 discordant items, below what clears p<0.05). Doc-assembly seeds **3109, 3221, 3331** (renumbered off the 101/202/303 block to avoid the selection/math collision). Fits strata run at ONE seed as a screen.

**Command.**

```bash
# STEP 1 — its own gated step, cost published BEFORE anything else runs
python -m benchmark.probe_context_limit --model qwen3.7-max --start 32000 --max 1000000 \
  --report benchmark/results/META3_context_limit.json

# STEP 2 — fits strata only, one seed
python -m benchmark.build_longdoc_set --index benchmark/data/rag_index.sqlite3 \
  --lengths 8000,32000 --n 30,30 --seed 3109 --out benchmark/data/longdoc_seed3109.jsonl
python -m benchmark.run_longdoc --arm truncate  --set benchmark/data/longdoc_seed3109.jsonl --concurrency 4
python -m benchmark.run_longdoc --arm retrieval --set benchmark/data/longdoc_seed3109.jsonl --rag-k 5 --concurrency 4
python -m benchmark.run_longdoc --arm mapreduce --set benchmark/data/longdoc_seed3109.jsonl --chunk-tokens 8000 --concurrency 4
python -m benchmark.run_longdoc --arm oracle    --set benchmark/data/longdoc_seed3109.jsonl
```

**Bar.** **8k fits stratum (loss check, runs first):** mapreduce ≥ retrieval − 5pt and ≥ truncate − 5pt — chunking must not itself be lossy. **Overflow stratum (gated):** mapreduce beats **retrieval-then-answer** by ≥ +5 net discordant at n=30 with exact McNemar p < 0.05. The truncate arm is reported as a floor and is never the headline comparator.

**Kill (first).** (a) mapreduce loses > 5pt at the 8k fits stratum → the map-reduce shape destroys accuracy on its own; META-4 dies with it (already dropped) and the overflow stratum is never run. (b) `probe_context_limit` shows the flagship window exceeds the longest context in any loadable real benchmark → no overflow regime exists, the "architecturally impossible for one call" claim is false, retire the pitch. (c) > 10% of calls time out or drop in the fits strata → the regime is unrunnable on this stack (the record already shows 30% timeout drops on heavy calls); report that as the finding and do not fund the overflow stratum. (d) **Probe-cost abort:** if the probe's measured cost exceeds 3.0M, or if the overflow-stratum formula `30 × 1.5 × measured_limit × 2 arms` exceeds 15% of weekly quota, the overflow stratum is not funded this week.

**Token cost — re-costed, the original estimate was understated by roughly an order of magnitude.** The probe **sends** the prompts it binary-searches: ~5–8 probes averaging 200–400k input tokens ⇒ **1.5–3.0M, not 0.2M**. Fits strata, 4 arms, one seed: 8k ≈ 30 × 23k = 0.7M; 32k ≈ 30 × 77k = 2.3M ⇒ **~3.0M**. Overflow stratum is **not a fixed number**: it is `30 items × 1.5 × measured_limit × 2 arms`, pre-registered as a formula with the 15%-of-quota abort above (at a 256k window it is ~15M = 34% of a week, which the abort would refuse). **Committed: probe (1.5–3.0M) + fits strata (3.0M) = 4.5–6.0M, week 2+.**

**build_needed.** ~500 lines. `probe_context_limit.py` (~60): binary-search the largest prompt that does not 400. `build_longdoc_set.py` (~150). `run_longdoc.py` (~280): the map-reduce orchestrator, the retrieval arm wired to the existing `quorumqa.rag` store, and a context-carrying item type — `GPQAItem` has **no** context field (`src/quorumqa/schemas.py:6-11`), so either extend it or add `LongDocItem`. Chunking reuses `quorumqa.rag.chunking.chunk_text`. **Mandatory:** `run_longdoc` must raise `max_tokens` explicitly — `QwenClient.chat` defaults to 1024 (`qwen_client.py:95`) and every reader return would otherwise truncate (note the endpoint does not reliably enforce the cap either way, measured on AIME, so both directions must be checked).

**If it fails.** A null kills the family's cleanest structural claim for ~6% of a week, before any real-benchmark spend. A positive against the retrieval baseline (not against a crippled truncation arm) is the first capability where the multi-agent shape wins by construction rather than by margin.

---

### META-5 — IFEval: deterministic constraint verifier, and whether the verifier or merely the retry is doing the work (DEFERRED past week 1; Phase 0 free)

**Hypothesis.** A deterministic constraint verifier plus up to 2 targeted regenerations raises IFEval prompt-level STRICT accuracy by ≥ 8pt over a single flagship generation — **and the gain survives subtracting a self-critique retry that has no programmatic checker.**

**Arms.** (A) single `qwen3.7-max` generation. (B) A + verify-and-regenerate: violated `instruction_id`s fed back verbatim, max 2 retries, stop on first pass. (C) 3-candidate cheap panel + verifier-select, then the same retry loop — C vs B is the real question (does sampling **breadth** beat retry **depth** at lower cost, as Self-MoA predicts?). **(D) NEW — self-critique retry with NO deterministic verifier**, same retry budget, model asked to check its own compliance. **B − D is the verifier's contribution**; without D, arm B's advantage over A confounds "deterministic verifier" with "a second attempt", and the product claim rests on the checker specifically.

**Dataset / n / seeds.** `google/IFEval`, 541 prompts with 25 programmatically verifiable instruction types; disjoint 150-prompt samples per seed. Metrics: prompt-level strict (primary), instruction-level strict, loose variants secondary. Seeds **1234, 3037, 5150** (fresh, no collisions). Generation temperature pinned at 0.3 with the `QwenClient` seed set to the same value so a re-run is byte-comparable.

**Command.**

```bash
# PHASE 0 — 0 tokens, and the result is unfalsifiable without it
pytest tests/test_ifeval_constraints_official_fixtures.py -q   # must reproduce the official expected outputs exactly
# PHASE 1 — paid, per seed
python -m benchmark.run_ifeval --arm single       --n 150 --seed 1234 --model qwen3.7-max
python -m benchmark.run_ifeval --arm verify_retry --n 150 --seed 1234 --model qwen3.7-max --max-retries 2
python -m benchmark.run_ifeval --arm selfcrit_retry --n 150 --seed 1234 --model qwen3.7-max --max-retries 2
python -m benchmark.run_ifeval --arm panel_verify --n 150 --seed 1234 --candidates 3 --max-retries 2
```

**Bar.** Prompt-level strict: (B or C) − A ≥ +8pt on ALL 3 seeds (at n=150 that is ≥ 12 discordant prompts, comfortably clear of the noise floor — one of the few specs here that is not power-starved). **Additionally reported as the mechanism result: B − D**, the verifier's own contribution.

**Kill (first).** (a) < +4pt over A on 2 of 3 seeds. (b) Retries INTRODUCE new violations on > 20% of retried prompts (whack-a-mole: fixing constraint X breaks constraint Y makes the loop unshippable regardless of the headline). (c) A blinded 3-way judge on 30 retried pairs rates the retried answer's CONTENT worse on > 30% (constraint satisfaction bought with quality degradation). (d) **Phase 0 kill:** if the vendored checkers do not reproduce the official expected outputs exactly, no number is reportable at all. Any one of these kills the lever.

**Token cost.** **Phase 0: 0.** Phase 1: ~2.7M for arms A/B/C + ~0.9M for arm D = **~3.6M (8% of weekly)**. Deferred past week 1 on **engineering-hours** grounds, not token grounds.

**build_needed.** REAL, and the verifier is the bulk — **re-labelled from "cheapest live spec" to build-heavy.** `benchmark/load_ifeval.py` (~60). `quorumqa/verify/ifeval_constraints.py` (~400–600): **vendor** `google-research/instruction_following_eval`'s 25 checkers plus strict/loose normalisation rather than reimplementing — and note this pulls new third-party dependencies (`nltk`, `langdetect`, `immutabledict`, `absl-py`), **none of which are in `requirements.txt` today**. `benchmark/run_ifeval.py` (~250, modelled on `run_math_open.py`). The existing MCQ lever harness is unusable here (free-form generation), so none of the 24 built levers is reusable.

**If it fails.** A null says retry loops are not the fix for format failures — a strong negative worth publishing. Honest caveat: a positive is semi-predictable, so the scientific value sits in the SHAPE — retries-to-saturation, whack-a-mole rate, B vs C (depth vs breadth), and B vs D (verifier vs mere retry).

---

### META-6 — SimpleQA: does a disagreeing panel abstain better than a prompt that just permits "I don't know"?

**Hypothesis.** On SimpleQA, a panel that abstains when its seats disagree achieves ≥ 8pt higher accuracy-given-attempted than a single flagship call **explicitly instructed to say "I don't know" when unsure**, at equal or higher coverage.

**Arms.** (A) single `qwen3.7-max`, plain prompt (hallucination baseline). **(B) single `qwen3.7-max`, IDK-permitted prompt — THE CONTROL THAT MUST EXIST**, otherwise we credit the architecture for what one sentence of prompting does. B, not A, is the comparator for the headline claim. (C) 3-seat `qwen3.6-flash` panel, abstain unless ≥ 2 seats agree after answer normalisation. (D) 3-seat `qwen3.7-max` panel, same rule.

**Dataset / n / seeds.** OpenAI SimpleQA test set (4,326 short-fact questions with gold short answers), n=150 disjoint items per seed. Primary metric: accuracy-given-attempted at matched-or-better coverage. Secondary: SimpleQA F-score (the rare public metric that does not punish abstention). Seeds **7331, 8081, 9091** (fresh).

**Command.**

```bash
# RETRIEVAL GATE — run FIRST and separately; the LEXam lesson pre-registered rather than rediscovered
python -m benchmark.score_r3_relevance --input <top-5 retrievals for 30 sampled SimpleQA questions>

# GRADER VALIDATION — must pass before any headline number is quoted (see §8, Q3)
python -m benchmark.validate_simpleqa_grader --mode alias_proxy --n 50 \
  --out benchmark/results/META6_grader_validation.md

python -m benchmark.load_simpleqa --n 150 --seed 7331 --out benchmark/data/simpleqa_seed7331.jsonl
python -m benchmark.run_simpleqa --arm plain          --set benchmark/data/simpleqa_seed7331.jsonl --grader qwen3.7-max
python -m benchmark.run_simpleqa --arm idk            --set benchmark/data/simpleqa_seed7331.jsonl --grader qwen3.7-max
python -m benchmark.run_simpleqa --arm panel_cheap    --set benchmark/data/simpleqa_seed7331.jsonl --grader qwen3.7-max
python -m benchmark.run_simpleqa --arm panel_flagship --set benchmark/data/simpleqa_seed7331.jsonl --grader qwen3.7-max
```

**Bar.** (C or D) − B ≥ +8pt accuracy-given-attempted (≥ 12 items at n=150) with coverage(C or D) ≥ coverage(B), on all 3 seeds; and SimpleQA F-score higher on ≥ 2 of 3 seeds. A retrieval arm is built **only** if the frozen-rubric gate shows ≤ 50% off-topic retrievals on the 30-question probe.

**Kill (first).** < +3pt over arm B on 2 of 3 seeds → the abstention value lives in the PROMPT, not the panel; publish the null and close the calibration line. **Grader kill:** if the grader disagrees with the validation labels on > 10% of the 50-row sample, no headline number is reported at all — arms A/B are `qwen3.7-max` and so is the grader, so self-preference is a live risk and arm labels are blinded during grading. **Retrieval kill:** > 50% off-topic on the rubric probe kills the retrieval arm before any tokens are spent on it.

**Token cost.** **~1.8M + ~0.1M rubric gate = ~1.9M (4.3% of weekly)** — short questions and answers, 150 × 4 arms × ~0.5–2k × 3 seeds plus ~0.4k/item grading. Cheapest live spec in the family with a real bar on an unsaturated surface.

**build_needed.** ~400 lines. `benchmark/load_simpleqa.py` (~60: CSV fetch from the published test-set URL, cached under `benchmark/data/cache`). `benchmark/run_simpleqa.py` (~250, modelled on `run_math_open.py`). Grader module (~80) using the published CORRECT / INCORRECT / NOT_ATTEMPTED prompt, gold-anchored, arm labels blinded. The subtle piece is short-answer normalisation for panel agreement (case, punctuation, aliases, dates) — `math_grade` is LaTeX-specific and reuses nothing here.

**If it fails.** SimpleQA is the only public benchmark whose scoring matches what a deliberating panel structurally offers (abstention is not punished), and frontier models score poorly on it, so the headroom is real rather than saturated. A null (prompt ≥ architecture) is the strongest available evidence that the entire calibration thesis is a prompting artifact, and it costs 4% of a week to learn.

---

## 5. Dropped specs

Portfolio-wide. **Status** distinguishes permanent drops from parked/deferred items; **Revival condition** is what must be true before anyone re-proposes it. Nothing in this table may be scheduled without meeting its revival condition in writing.

| ID | Title | Status | Severity | Reason | Revival condition |
|---|---|---|---|---|---|
| SCI-6 | `sc_restate` vs `sc_sample` at matched 9-call budget | **DROPPED** | fatal (duplication) + major | Third independent purchase of "is diversity from sampling or from perspective?" on SuperGPQA-hard (~10.3M = 24% of a week, the single most expensive spec proposed) after PS-1/PS-2 (5.42M merged, which also yields the whole N-curve free) and MATH-6's matched-N=3 sub-result. Strictly dominated: ~2× the cost for one N=9 point instead of a curve. Separately uninterpretable — up to ~13% of arm B's seats could be answering a corrupted question under SCI-1's 20% fidelity tolerance, so a loss cannot distinguish "input diversity fails" from "the rewriter damaged the items". | Only as an extra seat-spec **dimension inside the merged N=15 harvest** (seats differing by restatement index), never as a standalone 9-call arm. |
| SCI-4 | `decompose_verify` (choice-blind sub-claim verification) | **DEFERRED (out of weeks 1–2)** | major | 4.6M for a P3 that is third in a chain (SCI-1 flip → SCI-2 blinding → SCI-4 decomposition) with **both** parents unmeasured; the spec itself calls it "the highest-variance and most laundering-prone design in the family" and concedes it almost certainly fails if SCI-2 fails. Two frozen rubrics + a blinded majority-of-3 audit are required before any number is reportable. | SCI-1 coverage gate clears **and** SCI-2 shows a positive blinding effect. A chained P3 with unresolved parents holds no budget. |
| SEL-2 (open arm) | K=8 candidate pool on MATH-500 level 5 | **DROPPED** | fatal | ~3.1M spent on a surface already measured saturated: 96.6% at BOTH tiers, 0% escalation, 55/59 unanimous. The spec's own pool-degeneracy kill (mean distinct ≤ 1.3, or ≥ 70% single-answer) is **already satisfied** by those logged numbers, so the run is pre-killed — and SEL-3/SEL-5/SEL-6 all inherit the pool, compounding the waste across four specs. | Rebuild on AIME instead, conditional on MATH-1 returning ALIVE. Run the degeneracy check offline against existing MATH-500 SC logs first — cluster counts are already logged. |
| MATH-4 | Iso-token cheap SC@4 vs flagship SC@17 on AIME | **DROPPED** | major | 6.1M for a comparison the spec itself concedes is "probably already implied by MATH-1" — MATH-1 (1.8M) already delivers the measured cheap-vs-flagship token ratio on AIME, and MATH-2's N=17 log supplies the flagship side free. Also inherits AIME's fixed 60-item population, so its 6-discordant bar sits at the edge of falsifiability for a P2 question. | Answer it as a **free 4-draw cheap prefix** scored against MATH-2's already-paid flagship log, labelled an underpowered secondary read. Never as a new paid arm. |
| PS-6 | N=63 residual-coverage probe (the cons@64 question) | **DROPPED** | fatal + major | Regression to the mean is uncontrolled and would manufacture the result: the residual set is *defined* as items no seat of 15 got right — selection on a noisy criterion — so resampling them 48 more times covers some purely because the N=15 miss was partly luck, and both the +25% bar and the <10% kill are scored against a null of zero. Also 3.54M on a ~28-item denominator with no seed replication, and 63 concurrent cheap calls against a timeout-fragile endpoint would mechanically depress the very coverage number it measures. | Requires (i) the correct null — expected coverage `1-(1-p_i)^48` from per-item per-seat accuracy, with the bar stated as observed **minus** model prediction, or a matched control on singly-covered items — **and** (ii) both cheaper siblings (SEL-6's free pool-size curve, MATH-2's AIME SC@N curve) still rising at their top N. |
| META-4 | LongBench-v2 medium-stratum map-reduce | **DROPPED from the queue** | major | 6.4M **per seed** (~15% of a week) for a number the spec openly admits cannot meet the house 3-seed bar within one week's quota and must be labelled pilot-grade. Blocked behind META-3's ~500 lines of unbuilt harness plus its own ~120. Worst information-per-token ratio in the portfolio. | Week-1 allowance is the **zero-token load-only dry run** (dataset resolves, fields map, token-length distribution matches published strata). Re-propose only after META-3's fits strata show map-reduce is not lossy AND a token re-cost from measured drop rates. |
| CODE-6 | SWE-Bench Pro best-of-N with a visible test suite | **PARKED** | major | "NONE RUNNABLE TODAY" by its own admission: dataset acquisition, a Harbor adapter, per-instance multi-GB Linux Docker images, `patch_mode` agent changes — multi-day to multi-week, gated on CODE-2's unmeasured headroom. Platform risk was under-stated: this is Windows 11 with Docker Desktop (down at spec-writing time), and the official harness fallback assumes a Linux/POSIX host. | Week-1 allowance is **one zero-token registry check** (`harbor run -d <candidate> --print-config`) to learn whether a SWE-Bench dataset already exists in Harbor. Do not scaffold an adapter until CODE-2 reports oracle@5 − pass@1 ≥ 10pp. Add an explicit **platform kill** alongside the disk kill. |
| SEL-4 (arm C) | Pairwise Copeland tournament over candidates | **DROPPED (arm only)** | major | ~2.4M at ~3× arm B's cost, shippable only if it beats arm B by ≥ 5 net items, with a poor prior: qwen38_judge already showed 9/9 overturns correct and **zero** net gain, i.e. coverage rather than adjudication quality is binding, and a tournament improves only adjudication. Halves SEL-4 to ~2.8M. | Arm B clears its bar **and** the overturn-correctness diagnostic shows judge quality, not coverage, is limiting. |
| SCI-5 (SuperGPQA arm + paid chem control) | `gap_gate` on SuperGPQA with a `chem_thinking_gate` control | **DROPPED (arms only)** | fatal | `chem_thinking_gate` gates on `subject == "Organic Chemistry"` while `load_supergpqa.py:117` sets `subject = discipline` (13 coarse values), so the chemistry branch **never fires** on SuperGPQA and the "control" degenerates byte-identically to `thinking_gate` — ~3.3M of mislabelled duplicate arm. Every logged `chem_thinking_gate` run is on GPQA; the win being "transferred" was never measured on SuperGPQA at all. | Never revive as written. GPQA is the primary surface (§4, SCI-5); non-inferiority is descriptive against the 264 existing GPQA rows. |
| SCI-2 (`method_panel` reference arm) | Re-running `method_panel` at 3 fresh seeds inside SCI-2 | **DROPPED (arm only)** | major | ~2.8M duplicating the already-queued W2 shelf run of a lever that is built, offline-tested and wired in with **zero logged rows**, while also burning three more seeds — and it cannot test the stated hypothesis anyway (it replaces the solver seats; `backward_check` layers a probe on unanimous items only, so their head-to-head isolates nothing about blinding). | Score against the W2 `method_panel` run at matched seeds. The real falsifier is the matched **unblinded** 4-call comparator, which is now inside SCI-2. |
| PS-2 (historical-reproduction kill) | "cycled@5 must reproduce the historical N=5 direction, else halt" | **DROPPED (kill clause)** | major | Not decidable from the data the run produces: the historical five-solver run is `lever_five_seed42.jsonl` with `dataset: None` = loader default = **GPQA**, n=90, seed 42. The 81.1 / 78.9 / 84.4 numbers are GPQA numbers; a SuperGPQA run cannot reproduce them, so the kill either never fires or fires spuriously and halts a P0 family. | Replaced by internal checks decidable from the run itself (byte-identical prompts/temps for seats i and i+3; cycled@3 within the pooled CI of the 447 logged control rows). The "correcting the record" claim must be scoped to "untested on GPQA", not "tested, negative". |

---

## 6. Firing order for week 1

**Quota:** ~43.8M tokens/week, resets **2026-07-28 03:32 UTC**. **Week-1 hard cap: 30M** (pre-registered, published so nothing gets quietly promoted). **Mid-week headroom re-check at ≤ 25% (≤ 10.95M) cumulative paid spend** — nothing past the checkpoint fires until the re-check is done and the cap is re-affirmed.

### 6.0 Pre-flight, blocking, 0 tokens (do these first or the rest is unauditable)

| # | Item | Why blocking |
|---|---|---|
| P1 | Re-key all spec ids to `PS-/SEL-/MATH-/CODE-/SCI-/META-` and commit `benchmark/data/seed_registry.json` | 26 of 31 specs shared an id; result files and kill records would silently merge |
| P2 | `timeout 10 docker info` gate wrapper committed into the CODE-* launcher | Docker Desktop was DOWN at spec-writing time; a half-started daemon already cost 5 unattended hours |
| P3 | Freeze `benchmark/data/tb21_attempted_tasks.json` (43 tasks) | The only record of the attempted tasks lives in the OS temp dir and can be cleaned at any time |

**Seed registry — authoritative for my three families; collisions flagged for the others.**

| Block | Spec | Dataset | Seeds |
|---|---|---|---|
| instability (merged) | META-2 + SCI-1 | SuperGPQA-hard | **909** (screen), 1313, 2027 |
| blinding | SCI-2 | SuperGPQA-hard | 1213 (screen), 1427, 1619 |
| replay | SCI-3 | frozen logs | none; pairing RNG `analysis:5501` |
| transfer | SCI-5 | GPQA | 7103 (screen), 8117, 9127 |
| analysis-only | META-1 | — | `analysis:5309` (namespaced; never a sampling seed) |
| long-doc | META-3 | synthetic | 3109, 3221, 3331 |
| IFEval | META-5 | IFEval | 1234, 3037, 5150 |
| SimpleQA | META-6 | SimpleQA | 7331, 8081, 9091 |
| coding | CODE-1…5 | Terminal-Bench 2.1 | no task-sample seed (explicit task lists); per-trial model seeds derived into 10000–99999; seed 11 reserved if subsampling is ever needed |

Burned, never reusable: **3, 7, 42, 123, 217, 271, 314, 471, 555, 606, 777, 838, 888**. **Collisions requiring resolution before dispatch:** 909 was independently claimed by META-2, SEL-7, MATH-6 and MATH-4 — META-2/SCI-1 keep it (first mover, and the merge is the point); **SEL-7 renumbers to 411/523/631** and MATH-6 renumbers (MATH-4 is dropped). 101/202/303 were claimed by both the SEL pools and the MATH AIME replicates — SEL keeps them, MATH's AIME replicate labels move. See §8 Q2 for the confirm-or-override.

### 6.1 FREE — build and offline work, runnable NOW during the block (0 tokens)

Three of these can **kill their own spec for free**, which is why they precede everything paid.

| # | Item | Owner spec | Can kill? |
|---|---|---|---|
| F1 | `nop` `-k 3` expansion probe + `-i` form probe | CODE-1(a,b) | yes (invalidates CODE-2's design) |
| F2 | `analyze_selective.py` + mandatory inventory print, then run it | META-1 | yes (both kills are free) |
| F3 | `audit_selectors.py` selector audit over the deduped logged pools | SEL-1 | yes |
| F4 | `classify_aime_answer_forms` answer-form gate | MATH-3 | **yes — expected killed-by-cap at <24/60**; do not write the 270-line checker until it passes |
| F5 | HMMT / OlympiadBench loaders + grader-parse **and formatting-transform** gate | MATH-5 Phase 1 | yes |
| F6 | `build_subject_gap_table.py` incl. the **uuid re-join**, paired-n table committed | SCI-5 | **yes — expected killed-by-power** |
| F7 | `--n-solvers` / `--no-tribunal` / per-seat logging + `analyze_panel_scaling.py` (incl. coprimality assertion test) | PS-1/PS-2 | no — gates the merged harvest |
| F8 | `escalation_policies.py` (four triggers as pure vote-vector functions + replay/sweep) | PS-3 Stage A | no |
| F9 | CODE-1 agent instrumentation (`trajectory`/`selfcheck`/`fingerprint`, `--ak` kwargs, derived seed) + `score_bestofn.py` + `freeze_tb_attempted.py` + `tb21_text_only_feasible.json` | CODE-1/2/3 | no |
| F10 | `tb_fingerprint_rules.md` frozen and committed **before CODE-2 runs** | CODE-3 | no |
| F11 | `restate_question()` + `restatement_fidelity_rubric.md` (frozen) + `score_restatement_fidelity.py` + `--placebo-escalation-rate` | SCI-1 | no |
| F12 | `replay_step_audit.py` + `analyze_step_audit.py` + frozen auditor prompt | SCI-3 | no |
| F13 | `analyze_unanimous_stability.py` + `--replicate` flag | META-2 | no |
| F14 | `tb_failure_rubric.md` frozen and committed | CODE-5 | no |
| F15 | META-5 Phase 0: vendor the 25 official IFEval checkers, add `nltk`/`langdetect`/`immutabledict`/`absl-py`, reproduce the official fixtures | META-5 | **yes** (unvalidated verifier ⇒ unfalsifiable spec) |
| F16 | META-6 loaders + grader + alias-proxy validator; SimpleQA retrieval rubric probe scaffolding | META-6 | no |
| F17 | Zero-token registry check for a SWE-Bench dataset in Harbor; LongBench-v2 load-only dry run | CODE-6, META-4 (parked) | yes (closes both) |
| F18 | Raise `max_tokens` explicitly in `run_longdoc` (default is 1024, `qwen_client.py:95`) | META-3 | no |

### 6.2 PAID — ordered, with cumulative spend

| # | Item | Arms / seeds | Tokens | Cumulative | % of week |
|---|---|---|---|---|---|
| 1 | **MATH-1 AIME liveness screen** *(already queued first)* | flagship single + cheap single, n=60, seed 101, concurrency 3, zero-drop rule | 1.80M | 1.80M | 4.1% |
| 2 | **CODE-1(c) live instrumentation probes** | 2 tasks × 1 turn | 0.006M | 1.81M | 4.1% |
| 3 | **Merged N=15 harvest** = PS-1 diversified + PS-2 cycled, same seed, same 90 items, vote-only, concurrency ≤ 3, rerun-on-dropped-seat | SuperGPQA-hard, seed 19 | 5.42M | 7.23M | 16.5% |
| 4 | **Instability block stage 1** = META-2 arm A (`control`) + arm B (`permuted_panel`) + SCI-1 `restate_probe` incl. placebo escalation | SuperGPQA-hard, seed 909 (shared control) | 3.20M | 10.43M | **23.8%** |
| — | **MID-WEEK HEADROOM RE-CHECK** — measure actual vs projected burn, re-affirm the 30M cap, apply every gate below | | | | |
| 5 | META-2 arm C (resample-only control) | seed 909 | 0.95M | 11.38M | 26.0% |
| 6 | **CODE-2 best-of-N** (46 fresh tasks × k=5) — **wall-clock bound, ~10–12h, one overnight window** | Terminal-Bench 2.1 | 6.30M | 17.68M | 40.4% |
| 7 | *Conditional:* instability block stage 2 — all 3 META-2 arms + SCI-1, seeds 1313 + 2027. **Gate:** flip rate ≥ 10% at seed 909 (5–10% = declared BAND, does not fire) | SuperGPQA-hard | 8.30M | 25.98M | 59.3% |
| 8 | *Conditional:* SCI-5 GPQA screen (`gap_gate` + `control`). **Gate:** F6 shows ≥ 3 non-chem subjects at paired n ≥ 25 **and** projected non-chem high-gap subset ≥ 60 items | GPQA, seed 7103 | 2.10M | 28.08M | 64.1% |
| — | **Reserve: 15.7M** for re-runs (survivorship voids a seed), CODE-5 Stage 1 pull-forward (2.0M), or SCI-3's replay (1.5M) | | | | |

**Free follow-ups that cost nothing once item 3 lands:** PS-3 Stage A (escalation-policy replay, tuning/locked half split), PS-4 Stage A (cost frontier on measured per-role tokens, restated as **surface-specific**: cheap seats are ~35% cheaper in tokens on 4-choice MC but ~4.6× *more* expensive on open-answer competition math), SEL-3 / SEL-6 prefix reads, and META-2 × SCI-1's flip-set intersection.

**Explicitly NOT in week 1:** CODE-4 (7.5M, gated on H ≥ 10pp), CODE-5 Stage 2 (4.7M, gated on stall ≥ 25%), SCI-2 (1.8M screen, gated on SCI-1 clearing coverage but failing net), META-3 (4.5–6.0M, probe-gated), META-5 Phase 1 (3.6M, gated on F15), META-6 run (1.9M, gated on grader validation — see §8 Q3).

---

## 7. Dependency graph

```
FREE PRE-FLIGHT (P1-P3, F1-F18)  ──►  everything paid
```

**Hard gates (a paid run may not start until its gate passes).**

| Gate | Gates what | Rule |
|---|---|---|
| P2 Docker readiness | CODE-1 → CODE-2 → CODE-3/4/5 | `timeout 10 docker info` returns, and the job dir is verified non-empty after launch rather than trusting the exit code |
| CODE-1 `/tests` leak probe | CODE-2, CODE-3, CODE-5 | A readable `/tests` contaminates every self-check selector by construction; HALT and re-probe |
| CODE-1 `-k` independence | CODE-2's entire post-hoc design | If containers are shared, CODE-2 becomes N separate `k=1` jobs and must be re-costed |
| F7 (`--n-solvers`/`--no-tribunal`/per-seat logging) | the merged N=15 harvest | The subsampling estimator needs `seat_index`/`temperature`/`permutation`, which `solver_answers` does not carry today |
| F6 (frozen gap table, paired n) | SCI-5's paid screen | < 3 non-chem subjects at paired n ≥ 25 ⇒ killed-by-power at zero cost |
| F4 (AIME answer-form gate) | MATH-3's 270-line build **and** its paid arm | < 24/60 checkable ⇒ killed-by-cap; the checker is never written |
| F5 (grader parse + transform gate) | MATH-5 Phase 2 | A source that fails the transform gate silently deflates every accuracy number |
| F15 (official IFEval fixtures reproduce) | META-5 Phase 1 | An unvalidated verifier makes the whole result unfalsifiable |
| SCI-1 fidelity rubric (frozen, > 20% non-equivalent = dead) | SCI-1's own numbers; formerly SCI-6 | No accuracy number is reportable from a broken rewriter, positive or negative |
| META-3 `probe_context_limit` | META-3 fits strata → overflow stratum → (parked) META-4 | If the window exceeds any loadable benchmark's longest context, the structural claim is false and the pitch is retired |
| META-6 grader validation (≤ 10% disagreement) | every META-6 headline number | Grader and arms A/B are the same model family; self-preference risk |
| META-6 retrieval rubric probe (≤ 50% off-topic) | the META-6 retrieval arm | The LEXam −14 corpus-mismatch lesson, pre-registered rather than rediscovered |

**Screen → extension gates (the mid-week discipline).**

- **META-2 / SCI-1 seed 909 flip rate** → the 8.3M three-seed extension. ≥ 10% fires; **5–10% is a declared BAND** (report the separation statistic, promote nothing, fund nothing); < 5% kills.
- **CODE-2 headroom H** → CODE-4 (needs H ≥ 10pp) and CODE-6 (parked; needs H ≥ 10pp before any adapter work). Note the asymmetry: CODE-6 is gated on **headroom**, not on CODE-2's selector succeeding — a weak-selector null does not condemn a benchmark with a genuinely visible test suite, but a *no-headroom* result kills it before it starts.
- **CODE-2 M (mixed feasible tasks)** → CODE-3 and CODE-5 (M < 5 ⇒ INCONCLUSIVE, neither runs; M < 12 ⇒ CODE-3 is directional-only and may not close the final-state-voting branch).
- **CODE-5 Stage 1 taxonomy** → Stage 2 fires only if stall ≥ 25% of failures; the per-action-voting branch **opens** only if irreversible-destruction ≥ 20%, and is formally **closed** if it is < 10%.
- **SCI-1 outcome** → SCI-2 fires only in the specific branch where SCI-1 clears coverage but fails net; SCI-2's own blinding result then gates the deferred SCI-4.
- **PS-1 weak-seat guard** → PS-5 (flagship diversified panel) is gated **only** on the weak-seat guard, **not** on PS-1's cheap-tier plurality/coverage bar. Applying a cheap-tier coverage failure to the flagship tier is a category error: the measured binding constraints differ (cheap coverage@3 68.5% vs plurality 49.7%, an 18.8pt selection gap; flagship coverage@3 85.2% vs plurality 83.5%, a 1.7pt gap ⇒ coverage-bound).
- **META-1 + META-2 jointly** → the calibration thesis. If neither logged features (META-1) nor instability (META-2) can see inside the unanimous pool, the thesis is dead and effort moves to knowledge injection; META-1's second kill also blocks META-6's panel arms.
- **The oracle/coverage question first, generation-vs-selection second.** SEL-2's coverage read (and, on the cheap-panel side, the merged harvest's coverage@N curve) must land before any further spend on *better generation* vs *better selection*. Every downstream selection lever is sized by that headroom number, and CODE-2's H is its coding analogue. Neither branch gets funded on a hunch about which side is binding.
- **W1/W2 screens gate W4/W6** (unchanged from the existing plan). Additionally: the W2 `method_panel` shelf run — currently **zero logged rows** — should be fired at SCI-2's seeds so SCI-2 never pays for it, and `permuted_panel`'s W2 debt is discharged by META-2 itself, which is part of why META-2 leads the paid queue.

**One-way information flows worth naming:** the merged N=15 harvest feeds PS-3 Stage A, PS-4 Stage A, SEL-3 and SEL-6 for **zero** additional tokens; META-2's arm A control is SCI-1's control; META-2's position-bias readout retires the untested "permutation carries zero weak-seat risk" assumption that PS-1's 12 diversified seats currently rest on.

---

## 8. Open questions for the user

Five genuine choices. Each has a recommended default that will be taken if there is no answer before the 07-28 reset.

**Q1 — META-2 arm C: pay for the resample-only control, or relabel the claim?**
Arm C (canonical order, fresh sample) is what separates *permutation* instability from plain decoder resampling. Without it, arms A and B differ in two ways at once and the headline claim is not identified.
- **(a) Pay it** — +0.95M at the screen seed, +2.85M across three seeds; the claim can be written as "permutation instability".
- **(b) Skip it** — save the tokens; the hypothesis and every downstream claim must be relabelled **"resample-or-permute instability"** in the record, permanently.
- **Recommended default: (a), staged** — arm C at seed 909 only in week 1 (position 5, immediately after the headroom re-check), extended to 1313/2027 only if the screen clears the 10% flip gate. This is the single load-bearing unmeasured number in the record (61.6% of wrong rows are unanimous); buying a version of it that cannot support the claim would be the expensive mistake.

**Q2 — Seed 909 collision: who keeps it?**
Seed 909 was independently claimed by META-2 (SuperGPQA control + permuted), SEL-7 (held-out confirmation pools), MATH-6 (SuperGPQA `sc_mc` screen) and MATH-4 (AIME, now dropped). The META-2 and MATH-6 uses draw the **same 90 items**, so their control runs would duplicate ~0.95M and would not be the independent replications the plan implies.
- **(a)** META-2 + SCI-1 keep 909/1313/2027 (the merge is deliberate and shares one control triple); **SEL-7 renumbers to 411/523/631**; MATH-6 renumbers; 101/202/303 stay with the SEL pools and the MATH AIME replicate labels move.
- **(b)** Some other allocation of your choosing.
- **Recommended default: (a)**, committed to `benchmark/data/seed_registry.json` in pre-flight P1. If MATH-6 genuinely wants the same items as META-2, run **one** shared control arm and label it as shared in both write-ups rather than double-counting it.

**Q3 — META-6's grader validation needs 50 human-labelled rows, in a window that is unsupervised until 2026-07-22 07:15 SGT and now past it.**
The spec's own precondition blocks any reportable SimpleQA number until 50 rows are human-checked, and the grader is the same model family as arms A/B (self-preference risk).
- **(a) You label 50 rows** — strongest validation, but it is a real ask and it blocks the run until done.
- **(b) Mechanical alias-match proxy** — exact/alias match against gold short answers on the decidable subset, with the LLM-grader's agreement rate against that proxy reported instead of against human labels; the limitation is stated in the write-up.
- **Recommended default: (b)** for week 2, with (a) offered as an upgrade before any number is published externally. META-6 is otherwise the cheapest live spec with a real bar on an unsaturated surface (~1.9M), and it should not be blocked indefinitely on 50 labels.

**Q4 — Coding wall clock: one night or two?**
CODE-2 is ~10–12h, CODE-4 ~12–14h, CODE-5 Stage 2 ~8–10h — roughly 30 overnight hours in a 7-day window that must also carry the QA runs. Concurrency cannot be raised (4-concurrent produced API ReadTimeouts).
- **(a) CODE-2 only in week 1**; CODE-4 and CODE-5 Stage 2 in week 2, gated as specified.
- **(b) Two coding nights in week 1** — pull CODE-4 forward, which means cutting roughly one QA arm (most likely the instability extension's third seed).
- **Recommended default: (a).** CODE-4 is gated on CODE-2's headroom anyway, so running it before H is known risks spending 7.5M on an unvalidated premise; and the instability extension is the higher-information use of the same window.

**Q5 — Is the long-context structural claim (META-3) a deliverable, or a research curiosity?**
META-3 is the only place where the multi-agent shape can win *by construction* rather than by margin — a single call cannot answer a document that does not fit at any price. But the honest re-cost is 4.5–6.0M for probe + fits strata, and the overflow stratum is priced by formula with a 15%-of-quota abort.
- **(a) It is a narrative deliverable** — fund probe + 8k/32k fits strata at one seed in week 2, and let the overflow stratum go/no-go be decided by the measured probe cost and the fits-strata drop rate.
- **(b) It is a curiosity** — drop the family; the retrieval-then-answer baseline (already built) probably captures most of the practical value anyway, which is precisely why it is now the primary comparator.
- **Recommended default: (a), with the abort armed** — run it only if the probe lands ≤ 2.0M and the fits strata show ≤ 10% drops. If either fails, take (b) and publish the probe number as the finding.