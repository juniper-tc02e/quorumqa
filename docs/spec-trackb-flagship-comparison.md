# TB-1 — Does the scaffolded flagship beat the solo flagship? Pre-registration

**First draft written 2026-08-02. Rewritten 2026-08-02 after three independent
adversarial reviews (statistical, fairness/confound, executability), BEFORE any
arm runs at these seeds.** Fixed now so the analysis cannot be chosen after
seeing the result — the same discipline applied to the D0 bar repair, the
chemistry claim, `universal_gate`'s own transfer replication, META-2 and MATH-1.

The first draft failed all three reviews. §0.5 records exactly how. Nothing in
this document is a softened version of what the reviewers said.

---

## 0. Why this experiment, and why now

`universal_gate` is now the repo's strongest result: GPQA-Diamond, 3 seeds
(1001/2311/3407), pooled net **+25**, zero losses, p = 2.98 × 10⁻⁸, and it
survives a compute-matched control against 9 cheap seats
(`benchmark/results/universal_gate_3seed_result.md`).

But every one of those numbers is measured **against the shipped cheap panel**.
That answers "does escalating unanimity help?" It does **not** answer whether
the whole apparatus beats the simplest thing you could do instead: call the
flagship once.

That comparison has never been run at these seeds. The nearest existing
evidence is unusable for it:

- **D0 (`qwen3.8-max-preview` solo)** — point estimate **retired** to the
  interval [83.3%, 94.4%] after 10/90 items proved unreachable behind chronic
  server-side 504s, and it was measured at seed 123 while our societies ran at
  other seeds. Cross-seed *and* survivorship-biased.
- **Flagship (`qwen3.7-max`) solo on GPQA** — exists at seeds 217/314/471 only,
  none of which are `universal_gate`'s seeds.

Cross-seed borrowing is a real hazard here, but the first draft oversold it.
The flagship's measured spread is 83.0% / 86.5% / 94.3% at seeds 217/314/471 —
an 11.3-point range. **Most of that is ordinary binomial noise**: at p ≈ 0.88,
n = 88, the standard deviation is 3.46 pp, so 83.0 → 94.3 is about 1.6 sd. It
is not evidence of exotic seed sensitivity. Pairing is still the right design,
but for the ordinary reason — it removes *item difficulty* from the comparison.
**Pairing does not remove decode noise**, and the first draft implied it did.

## 0.5 What the adversarial review changed

Three reviewers were run independently against the first draft. All three
returned a negative verdict: **RUN-WITH-CHANGES** (statistical),
**REJECT AS WRITTEN** (fairness), **REJECT as fireable** (executability). The
following is what was actually wrong. It is stated bluntly because a
pre-registration whose failure modes were quietly patched is worth less than
one that shows its scars.

**1. The headline claim was false as a description of arm A.** The first draft
quoted `docs/spec-sci1-and-knowledge-injection.md` §1.2 — *"orchestration of
cheap Qwen seats beats a single call of a stronger Qwen"* — and proposed to
test it. But `universal_gate` sets `force_escalate = True` for **every**
unanimous panel (`benchmark/lever_experiments.py:1975`), and splits escalate
anyway. Verified on the committed files: **90/90, 89/89, 90/90 items escalated;
judge calls/item = 1.00 at all three seeds.** Every single item gets a
`qwen3.7-max` call. Arm A is not cheap seats beating a flagship — it is *one
flagship call, scaffolded*. The claim as written was not merely generous; it
was wrong. **Struck from §0, §1 and §8 throughout.** Both the statistical and
fairness reviewers flagged this independently as fatal.

**2. The flagship call inside arm A is bigger and better-prompted than arm B's
entire arm.** Measured, seed 1001: judge = **4,116 tok/item**; solo baseline =
**3,066 tok/item**. The baseline is told *"Keep reasoning to at most 3
sentences."* (`src/quorumqa/baseline.py:29`); the judge gets no length cap, a
five-field verdict schema, and adjudication framing. Arm A also has calculator
and constant-lookup tools (`src/quorumqa/engine/verifier.py`) that arms B and C
do not. So an A > B result confounds orchestration with **prompt richness** and
**tool access**. The fairness reviewer's verdict: without a control for this,
the result is uninterpretable. **New arm B′ added** (§2.4) to bound it.

**3. The experiment was a superiority test with ~5% power.** Arm A pooled =
240/269 = 89.2%. Flagship solo mean = 87.9%. Expected net at n = 90 is
**+1.2 items**. The statistical reviewer simulated the design (latent-difficulty
model, marginals fixed, σ = 1.0–2.2, 8k trials/cell) and found the per-seed
probability of clearing the repo bar is **5.4% — indistinguishable from the
nominal α**. A "win" under that design would carry essentially no evidence.
Worse, if any seed lands near the flagship's own 94.3%, arm A *loses* it with
89% probability. **The first draft's §8 listed three outcomes and omitted the
modal fourth** — nothing clears, no kill fires, the experiment is indecisive
(P ≈ 0.45–0.55). That omission is now fixed in §8, and arm B is **re-framed
from a superiority test to a falsification test** (§1), which is the only thing
it is actually powered to do.

**4. Multiplicity roughly doubled the real α.** Success could fire on any of
four correlated one-sided tests at α = 0.05 (three single seeds plus the
2-of-3 + pooled branch). Simulated under exact equality: P(single-seed branch
fires) = 0.102, P(2-of-3 branch fires) = 0.047, **P(either) = 0.121**. The
declared 5% test was a 12% test. **Fixed** (§5): the pooled 3-seed McNemar is
now **primary**; the single-seed branch is demoted to secondary and
Bonferroni-corrected to α = 0.0167, whose stated consequence is that
**b=5, c=0 (p = 0.03125) no longer passes** — the secondary branch now needs
net ≥ +6 with zero losses.

**5. The bar was asymmetric in arm A's favour, and the author knew the
numbers.** Arm A won on net ≥ +5 at *one* seed but only died on losses at *two
of three*. Against a comparator with real seed-to-seed variance, one lucky seed
is precisely the failure mode. **Fixed** (§6): the kill is now symmetric —
pooled net ≤ 0 kills — and "loses at a seed" is defined as net ≤ −3, not the
undefined "loses" of the first draft.

**6. N=4 was the wrong estimator and the reasoning was backwards.** The first
draft called N=4 "conservatively under-matched" while admitting it "favours
`universal_gate`". Those are opposites, and repo precedent says so: the
`universal_gate` control was deliberately **over**-matched (15,700 vs 13,541)
on the stated grounds that over-matching is the conservative direction. N=4 is
also the worst N for ties — at N=4 essentially every 2–2 tie has the correct
letter among the tied options, and a lowest-index rule coin-flips it, moving
**7–15 pooled items** against a bar of +5. **Fixed** (§2.2): **N=5**.

**7. Arm C was a straw control on decoding, and its decoding was never
registered at all.** `_ask_once` passes no temperature, so the client default
of **0.4** applies (`src/quorumqa/qwen_client.py:99`) — never stated in the
first draft. Standard self-consistency uses 0.7–1.0, and arm A's own seats use
0.3/0.6/0.9 *for diversity*. A 0.4-uniform SC is under-diversified and
suppresses the control's gain — the exact mechanism that produced
`flagship_panel`'s +9. **Fixed** (§2.2) by routing arm C through the existing
`cycled_panel` path, which cycles temperature 0.3/0.6/0.9 across seats,
matching arm A's own diversity.

**8. Arm C as specified would most likely have voided all three seeds.**
`benchmark/run_compute_matched_control.py:121-126` records that at **N=3**
sequential flagship `thinking=True` calls, seed 123's first attempt **dropped
75/90 items**; `--retry-missing` had to be added, and the committed control
files still land at 84/85/84 of 90. The first draft proposed **N=4** — 33% more
sequential calls per item — with no `--retry-missing` in its build list, against
a kill clause that voids any seed above 9 drops. Fired as written, the modal
outcome was 3.26M tokens spent and zero analysable seeds. **Fixed** (§2.2): the
adopted `cycled_panel` path fires its seats **concurrently** via
`asyncio.gather` (`benchmark/lever_experiments.py:1073-1078`) rather than in a
serial `for` loop, which removes the mechanism that caused the 75/90 collapse.
A 5-item pre-flight is now mandatory before committing the budget (§4.1).

**9. The runner the first draft said must be built does not need building — and
the script that actually must be built was never mentioned.** The executability
reviewer found that `--lever cycled_panel --solver-tier flagship --no-tribunal
--n-solvers 5` already does what arm C needs, with zero new code, and writes
pairable rows. Meanwhile **no analysis script exists** that pairs GPQA
`universal_gate` seeds 1001/2311/3407 against anything — §5 of the first draft
specified statistics but named no script, and the build list covered only the
runner that turned out to be unnecessary. As written, the run would have
finished with no number. **Fixed** (§10): the build list is now the analysis
script first, runner second (none needed), pre-flight third.

**10. Pairing was gated per-arm, never on the intersection.** Arm A has
90/89/90 rows (the first draft misreported this as 89/90/90); historical arm-B
runs dropped 2/1/2. Disjoint drops of 1+5+5 would leave |A∩B∩C| = 79/90 = 12.2%
loss with **every arm individually passing the 10% gate**, and A-vs-B and
A-vs-C would then run on different item sets — making the two tables §5 requires
be shown together non-comparable. **Fixed** (§5, §6): one analysis set
S = A∩B∩C per seed, gated at |S| ≥ 81/90 against the intended 90.

**11. Smaller corrections applied.** "Identical items" → **"question_id-paired"**:
re-loading `DATASET_LOADERS['gpqa'](90, seed, True)` reproduces every
question_id, order and `correct_letter`, but 12/89 items at seed 2311 and 13/90
at seed 3407 differ in trailing whitespace from arm A's committed files.
Pairing is safe; byte-identity is not claimed. Token-matching is not
cost-matching — §7 now carries USD, calls/item and s/item. Kill clause 1
granted mechanism survival on an unsignificant net ≥ +1; it now requires the
same bar. Commands now use `./.venv/Scripts/python.exe`, not bare `python`,
which on this machine resolves to a stale OneDrive shadow copy. And §5 now
states plainly that pre-registration binds **arms B, B′ and C only** — arm A's
per-item results are already known to the author.

## 1. Hypothesis (falsifiable, directional) — and what it is *not*

On GPQA-Diamond, at question_id-paired items and identical seeds,
`universal_gate` — 3 cheap `qwen3.6-flash` drafts, an adversarial rebuttal,
tool-grounded checks, and **unconditional escalation of every item to a
`qwen3.7-max` judge** — scores higher than that same `qwen3.7-max` answering
alone.

**This is a claim about scaffolding a flagship call, not about replacing one.**
The society issues one flagship call per item (measured: judge calls/item =
1.00 at all three seeds), and that call is larger than the solo baseline's
(4,116 vs 3,066 tok/item). No outcome of this experiment may be worded as
"cheap-seat orchestration beats a stronger model." That wording is
pre-registered as prohibited.

**Arm B is fired as a falsification test, not a superiority test.** Per the
statistical review it has P ≈ 0.25–0.38 of killing the claim and only P ≈ 0.05
of confirming it at the modal effect size. A null result from arm B is the
expected outcome and is **not** evidence for arm A.

## 2. Arms

All arms on the **same 90 items per seed**, seeds **1001 / 2311 / 3407**,
analysed on the intersection S defined in §5.

### 2.0 Summary

| arm | what | status |
|---|---|---|
| **A** `universal_gate` | scaffolded flagship, already run | **RUN — no new spend.** 90/89/90 rows |
| **B** flagship 1× solo | `--lever baseline` | **FIRE — falsification test** |
| **B′** flagship 1×, rich prompt | prompt-richness control, 1 seed | **FIRE after build** — diagnostic only, no bar |
| **C** flagship SC @ N=5 | compute-matched, diversity-matched | **PRE-FLIGHT PASSED 2026-08-03, FIRING.** 5/5 returned, mean pairwise agreement 0.920 (<1.0 required), temps cycling 0.3/0.6/0.9 matching arm A, tier confirmed `qwen3.7-max` thinking=True from `src/quorumqa/config.py` rather than from this spec's description of it. 14,740 tok/item — slightly OVER-matching `universal_gate`'s 13,175, the conservative direction. |

### 2.1 Arm B — flagship 1× solo (the falsification comparator)

One `qwen3.7-max` call per item via `solve_single_agent`. Deliberately *not*
compute-matched: it answers "does the society beat the simplest single call you
could make instead?" Under-powered to confirm, well-powered to kill. Fired for
the kill.

### 2.2 Arm C — flagship self-consistency @ N=5, compute- and diversity-matched

**Why the control is required at all.** `flagship_panel`'s +10 survived
arithmetically and then **lost its mechanism** to exactly this control: +9 of it
was self-consistency sampling (p = 0.0245), only +2 the tribunal (p = 0.344,
n.s.). See `benchmark/verify_compute_matched_control.py`. Arm C is
non-negotiable for that reason.

**Why N=5, not the first draft's N=4.**

Measured: `universal_gate` = **13,541 tok/item** (recomputed from seed 1001:
13,541.2). Flagship 1× = **~3,022 tok/item** (3,065.7 / 2,958.9 / 3,042.0 →
mean 3,022.2). So the society spends **~4.5×** a single flagship call.

- 4 × 3,022 = **12,088** — *under* `universal_gate`'s 13,541. Under-matching
  favours arm A. The first draft called this "conservative"; it is the
  opposite. Repo precedent over-matches: the `universal_gate` cheap-seat
  control ran 15,700 vs 13,541 on the stated grounds that over-matching is the
  conservative direction.
- 5 × 3,022 = **15,110** — *over* 13,541, matching precedent, and conservative
  on both axes (see §7: N=5 is also 3.0× arm A's dollars).

**Tie rates, exact enumeration over 4 letters** (`conc` = error mass on the
dominant distractor):

| N | p=0.83 ties/90 | p=0.87 ties/90 | max swing (items/90) between best- and worst-case tie rule |
|---|---:|---:|---:|
| 3 | 3.7–4.4 | 2.3–2.7 | 2.2–4.3 |
| **4** | **3.9–5.0** | **2.5–3.1** | **2.5–4.9** |
| **5** | **2.0–2.1** | **1.0** | **0.9–2.0** |

At N=4 essentially every 2–2 tie has the correct letter as one of the two tied
options, and lowest-index resolves it 50/50 — roughly 1.5–2.5 coin-flipped
items per seed, **7–15 pooled**, against a bar of +5. An arbitrary tie
convention could single-handedly decide the kill clause. N=5 halves it.

**How arm C is run: the existing `cycled_panel` path, zero new runner code.**

`--lever cycled_panel --solver-tier flagship --no-tribunal --n-solvers 5` runs
5 `ORCHESTRATOR_MODEL` calls (`config.py:62`: `BASELINE_MODEL =
ORCHESTRATOR_MODEL = qwen3.7-max`, `SOLVER_TIER_THINKING["flagship"] = True`),
majority-votes via `_plurality`, skips skeptic/verifier/judge entirely
(`lever_experiments.py:2040-2050`), and writes `{"engine": …}` rows with
`correct`. Three things this buys:

1. **It defuses the drop risk.** Seats fire **concurrently** via
   `asyncio.gather` (`lever_experiments.py:1073-1078`), not in the serial `for`
   loop that made `solve_compute_matched_control` timeout-prone enough to drop
   75/90 items on its first attempt.
2. **It satisfies diversity parity.** Seats cycle temperature 0.3/0.6/0.9 —
   the same diversity arm A's own seats use. A 0.4-uniform iid SC would be an
   under-diversified straw control.
3. **It is pairable with zero new code.** `_outcomes()` in
   `verify_compute_matched_control.py:63-72` already tolerates
   `engine`/`baseline`/`result` wrappers and keys on `item.question_id`.

**Honest caveats, pre-registered.** Because seats cycle lens *and* temperature,
arm C is a **diverse-ensemble** self-consistency, not iid, and its prompt is
`SOLVER_SYSTEM`-derived rather than `BASELINE_SYSTEM` — so **arm C is not "5
copies of arm B."** Both deviations make the control *stronger*, i.e. they push
against arm A. That is the conservative direction and is why they are accepted.
This must be stated at the point of use.

**Decoding, pre-registered now:** `thinking=True`, per-seat temperatures
0.3/0.6/0.9/0.3/0.6 (`SOLVER_TEMPERATURES[i % 3]`), no permutation
(`cycled_panel` is the no-permutation arm), unseeded sampling. The run report
must include **mean per-sample accuracy** and **mean pairwise seat agreement**
as a non-degeneracy check — if agreement is ~1.0 the control is degenerate and
the comparison is void.

**Vote recomputation, pre-registered now.** `parse_letter`
(`src/quorumqa/letters.py:58-75`) returns `""` for a missing letter — a
deliberately preserved quirk, not the fallback — so two unparsed samples can
carry `_plurality` to `answer_letter = ""`, scored wrong, biased *in arm A's
favour*. Arm C's `correct` field as written by the runner is therefore
**ignored**. The analysis script recomputes arm C's vote **offline** from the
`seat_answers` field (persisted per row, `lever_experiments.py:2206`) as:
drop seats whose `letter` is empty; majority over the rest; on a tie, the letter
of the **lowest `seat_index`** among those tied; if every seat is unparsed, the
item scores **wrong** (not dropped). This is deterministic, needs no runner
change, and is **not** a confidence tie-break — S7 killed confidence-based
selection out-of-sample (in-sample net +76 → held-out net −4, sign-reversed on
2/3 seeds), so reintroducing confidence anywhere here would be indefensible.

### 2.3 Why arm C cannot be silently skipped

If arm C is unrun, **every A-vs-B number must carry "compute-unmatched" at the
point of use**. §10's build item 1 enforces this in code, not prose: the
analysis script prints `arm C NOT RUN — every A-vs-B number is
compute-unmatched` when C's files are absent.

### 2.4 Arm B′ — flagship 1×, adjudication-style prompt (NEW; prompt-richness control)

**Added because the fairness review found A-vs-B uninterpretable without it.**
Arm A's flagship call is better-prompted and 34% larger than arm B's entire arm
(4,116 vs 3,066 tok/item). Arm B′ is a single `qwen3.7-max` call using a
`JUDGE_SYSTEM`-style adjudication framing, **no 3-sentence cap**, and **no
cheap panel, no skeptic, no tools**. It is the only arm that separates
orchestration from prompt richness.

**Scope, pre-registered:** **one seed (1001), diagnostic only, no bar.** It
cannot clear or fail anything. Its job is to *bound* the prompt-richness
contribution. Pre-registered reporting rule: if B′ beats B at seed 1001 by a
margin comparable to A-vs-B's pooled per-seed net, the A-vs-B gap **must** be
reported as "confounded with prompt richness, magnitude bounded by B′-vs-B at
seed 1001." Requires a build (§10, item 3).

## 3. Dataset / n / seeds

GPQA-Diamond, n = 90/seed, seeds **1001, 2311, 3407** — already claimed by the
`universal_gate` block in `benchmark/data/seed_registry.json`, deliberately
reused because **reuse is the entire point**: arms B, B′ and C must land on the
items arm A already ran. This is not seed-burning in the S7 sense (no selector
is being fitted); it is paired-control construction, the same pattern
`chemistry_matched_baselines` used at seeds 217/471.

**Items are question_id-paired, not byte-identical.** Re-loading
`DATASET_LOADERS['gpqa'](90, seed, True)` reproduces every question_id, the
order, and every `correct_letter` in arm A's committed files — pairing is safe.
But **12/89 items at seed 2311 and 13/90 at seed 3407** differ in trailing
whitespace, because arm A's committed items carry `\n`/spaces the current
loader strips. The analysis script asserts identity **by question_id**, never
by string equality.

## 4. Commands

Every flag below was verified to exist against `benchmark/lever_experiments.py`
at the time of writing. `--lever` `choices` includes both `baseline` and
`cycled_panel` (l.2386); `--seed` is an unrestricted `int` (l.2388, default 42 —
there is no `CLAIM_SEEDS` restriction on this runner); `--dataset gpqa`,
`--n`, `--concurrency`, `--out`, `--n-solvers`, `--solver-tier {cheap,flagship}`
and `--no-tribunal` all exist (l.2387-2422).

Use `./.venv/Scripts/python.exe`. **Bare `python` on this machine resolves to a
stale OneDrive shadow copy** and will silently run the wrong tree.

```bash
# Arm B -- flagship 1x solo, 3 seeds (~0.82M total). FIRE AFTER build item 1.
./.venv/Scripts/python.exe -m benchmark.lever_experiments \
  --lever baseline --dataset gpqa --n 90 --seed 1001 --concurrency 3 \
  --out benchmark/results/TB1_flagship1x_gpqa_seed1001.jsonl
#   ... same for 2311 and 3407

# Arm C -- flagship SC@N=5 via the existing cycled_panel path (~4.08M total).
# HELD until the §4.1 pre-flight passes.
./.venv/Scripts/python.exe -m benchmark.lever_experiments \
  --lever cycled_panel --dataset gpqa --n 90 --seed 1001 \
  --n-solvers 5 --solver-tier flagship --no-tribunal --concurrency 3 \
  --out benchmark/results/TB1_flagship_sc5_gpqa_seed1001.jsonl
#   ... same for 2311 and 3407

# Analysis (offline, no tokens). MUST EXIST BEFORE EITHER ARM FIRES.
./.venv/Scripts/python.exe -m benchmark.verify_tb1_flagship
```

Arm B′'s command is **not listed here** because its lever does not exist yet.
See §10 item 3.

### 4.1 Mandatory pre-flight for arm C

Before committing 4.08M tokens, run arm C at **`--n 5`, seed 1001**, to a
throwaway `--out`. Proceed only if **5/5 items return** and mean pairwise seat
agreement is < 1.0. This exists because the N=3 sequential precedent dropped
75/90 on its first attempt; the concurrent path is *expected* to fix it, and
this pre-flight is what turns that expectation into a fact.

Arm C has no resume path in this runner. If a seed voids, it is a full re-run —
§7 carries headroom for exactly one.

## 5. Bar and analysis (fixed now)

**Pre-registration binds arms B, B′ and C only.** Arm A's per-item results are
already committed and known to the author. This is stated so no reader mistakes
this document for a blind pre-registration.

**Analysis set.** For each seed, S = A ∩ B ∩ C on question_id.
**Gate: |S| ≥ 81 (90% of the intended 90)** — measured against the intended 90,
**not** against arm A's row count. Both A-vs-B and A-vs-C are computed on the
same S, so the two tables §5 requires be shown together are comparable and arm
A's accuracy is identical in both. Unparseable or ungradable answers count
**wrong, not dropped**. Drops are 504-correlated and therefore **not MCAR** —
state this whenever a seed carries drops.

**PRIMARY test (arm A vs arm B): pooled 3-seed exact one-sided McNemar,
p < 0.05.** Pooling sums per-seed 2×2 tables; items are never re-joined across
seeds. This is the single primary test, chosen to fix the multiplicity defect.

**SECONDARY / exploratory (single-seed).** Bonferroni-corrected to
α = 0.05/3 = **0.0167**. The stated consequence, registered now: **b=5, c=0
(p = 0.03125) does NOT pass this branch.** The single-seed branch is therefore
**net ≥ +6 with zero losses** (b=6, c=0, p = 0.015625). Note b=7, c=1 gives
p = 0.03516 and also fails. Any single-seed result must be labelled secondary
and exploratory wherever it appears.

Why this correction was necessary, simulated under exact equality (both arms
88.9%): P(single-seed branch fires) = 0.102; P(2-of-3 branch fires) = 0.047;
**P(either) = 0.121**. The undeclared test was a 12% test.

**Attribution (arm A vs arm C).** Same pairing, same S, same test. Symmetric
bar — see §6 kill clause 1.

**Reporting rule.** Arms B and C are reported **together, always**. Publishing
"society beats flagship 1×" without the compute-matched number next to it is
the exact failure that required retracting `flagship_panel`'s mechanism.

## 6. Kill clauses (kill dominates the bar)

1. **Attribution kill.** If arm C matches or beats `universal_gate` — pooled
   A-vs-C net ≤ 0 — the result is a **compute effect, not an orchestration
   effect**. Report it in those words; arithmetic intact, mechanism retracted,
   exactly as `flagship_panel`'s was. **Symmetric requirement (new):** arm A
   only earns a mechanism claim if A-vs-C clears the *same* primary bar
   (pooled exact one-sided McNemar p < 0.05). A positive but unsignificant
   A-vs-C is reported as **"attribution unresolved"**, not as a win. The first
   draft granted mechanism survival on net ≥ +1 with no significance
   requirement; that asymmetry is removed.
2. **Falsification kill (now symmetric and now defined).** A "loss at a seed"
   means **net ≤ −3** for arm A on that seed; net −1 is noise and does not
   count. If arm A loses at **2 of 3 seeds**, *or* if **pooled A-vs-B net ≤ 0**,
   the society does not beat the flagship on this surface and Track-B's central
   claim is **dead on GPQA**. Say so plainly; do not re-cut by subject to find
   a surviving slice.
3. **Drop kill.** **|S| < 81 on any seed voids that seed** for every arm — the
   gate is on the intersection, not per-arm. The AIME run died of exactly this,
   and per-arm gating would have let a 12.2% intersection loss through with
   every arm individually passing.
4. **Degeneracy kill (arm C).** If arm C's mean pairwise seat agreement is
   ≈ 1.0, the samples are degenerate, the control is defeated by construction,
   and the A-vs-C comparison is void rather than favourable.

   > **Quantified 2026-08-03, before arm C's result existed.** "≈ 1.0" is not a
   > threshold, and `verify_tb1_flagship.py` only *printed* agreement without
   > evaluating it — so this clause was unenforceable and would have been
   > settled after seeing the number. That matters more here than elsewhere
   > because the incentive is one-directional: **voiding A-vs-C is the outcome
   > that protects arm A's mechanism claim.**
   >
   > Fixed while seed 1001 was still running, with only the §4.1 pre-flight
   > (5 items, agreement 0.920) and a running item *count* observed — no
   > accuracy read. Two conditions, either sufficient:
   >
   > | condition | value | why |
   > |---|---|---|
   > | mean pairwise agreement ≥ **0.98** | `DEGENERACY_MAX_AGREEMENT` | ~18 of 900 pairs disagree; SC can move only a handful of items |
   > | items where the 5 seats split at all < **5%** | `DEGENERACY_MIN_SPLIT_ITEM_RATE` | under ~4 of 90; voting over samples that never disagree *is* a single call |
   >
   > A third figure — how often the majority differs from the first seat — is
   > reported and **deliberately not a kill**, because that is the effect under
   > test and gating on it would condition the control's admissibility on its
   > own result. Both thresholds carry bounds-checking tests so loosening them
   > later is a visible edit, not a quiet nudge.

## 7. Cost — tokens *and* dollars

Token-matching is not cost-matching: `qwen3.6-flash` and `qwen3.7-max` differ
by roughly an order of magnitude in price. Both columns are reported. USD uses
`config.PRICING_USD_PER_MTOK` (qwen3.7-max $2.50/$7.50 per Mtok in/out;
qwen3.6-flash $0.60/$2.75), recomputed from the committed files.

| arm | tok/item | \$/item | calls/item | s/item | n | total tokens |
|---|---:|---:|---:|---:|---:|---:|
| A `universal_gate` | 13,541 | **0.03636** | 6.60 | 72.0 | already run | **0** |
| B flagship 1× | 3,022 | **0.02149** | 1.00 | 51.3 | 270 | **0.82M** |
| B′ flagship 1× rich | ~4,116 (judge basis) | ~0.029 | 1.00 | ~55 | 90 | **0.37M** |
| C flagship SC@5 | 15,110 | **0.10745** | 5.00 | concurrent | 270 | **4.08M** |
| | | | | | | **5.27M** |

**Direction of the match, stated honestly.** Arm C at N=5 is **over**-matched on
both axes — 15,110 vs 13,541 tokens (1.12×) and \$0.107 vs \$0.036 (**2.96×**).
Over-matching favours the control and pushes against arm A; that is the
conservative direction and it is why N=5 was chosen. For the record, the
first draft's N=4 was under-matched on tokens (12,088 < 13,541) yet already
**2.4× over-matched in dollars** (\$0.086 vs \$0.036) — the fairness reviewer's
point that the first draft's "conservative" label was direction-wrong on price
as well as on tokens.

**Arm A's token cost is 69.6% cheap-tier**, which is why its 4.5× token
multiple is only a **1.7× dollar multiple** over arm B. Per-role, seed 1001:
solver 5,234.2 tok/item (38.7%, `qwen3.6-flash`), judge 4,115.9 (30.4%,
`qwen3.7-max`), skeptic 2,757.3 (20.4%, flash), verifier 1,433.8 (10.6%,
flash). Both multiples must appear together; quoting 4.5× alone overstates the
cost of the society, and quoting 1.7× alone understates its token footprint.

*Correction to the fairness review:* that review reported arm A as "61%
cheap-tier". Recomputed from the committed file it is **69.6%** — only the
judge role runs `qwen3.7-max`. The reviewer's \$/item figures (\$0.03636 /
\$0.02149) and the 1.7× multiple all reproduce exactly; this one derived
figure did not, and the corrected value is used throughout.

**Budget.** 5.27M ≈ **17.6%** of the 30M week-1 cap (B + C alone = 4.90M =
16.3%). Arm B alone is 0.82M and is worth firing even if C is deferred, subject
to §2.3. Arm B has **no resume path** — `main_baseline` writes once at the end
and `retry_dropped.py` hardcodes `["engine"]`, so it KeyErrors on baseline rows;
a voided seed is a full re-run. Headroom for **one** full re-run of any single
seed (≤ 1.4M) is reserved inside the 30M cap and is not counted above.

## 8. What we learn either way — including the outcome the first draft omitted

Ordered by prior probability, not by desirability.

- **MODAL (P ≈ 0.45–0.55): A ≈ B, nothing clears, no kill fires.** The
  experiment is **indecisive**. Given arm A pooled 89.2% vs a flagship solo mean
  of 87.9%, expected net at n=90 is **+1.2 items** and the per-seed probability
  of clearing even the uncorrected bar is **5.4%**. This is the single most
  likely result and it must be reported as "no detectable difference at this
  power", not as a near-miss, not as a trend, and never re-cut to find a
  surviving slice.
- **A loses (P ≈ 0.25–0.38 of ≥2 seed losses): Track-B's central claim is dead
  on GPQA.** This is what arm B is actually powered to detect and is the reason
  it is being fired. `universal_gate` remains a true but narrower claim — it
  beats *the cheap panel*, which it does at p = 3 × 10⁻⁸.
- **A > B but A ≈ C:** the win is **budget, not orchestration**. Publishable,
  and a genuine correction to how this repo has framed the tribunal.
- **A > B and A > C (both at the pooled primary bar):** the strongest honest
  claim available — and it is still a claim about **scaffolding a flagship
  call, not replacing one** (§1, §8.1).

Note the asymmetry that makes this experiment worth running despite its power:
a "win" at the modal effect size carries almost no evidence (P(win) ≈ α), while
a loss is decisive. **The kill is the deliverable.**

### 8.1 Exact claim wording if positive

Adopted verbatim from the fairness review. If the result is positive, this is
the wording — no paraphrase, no compression.

> On GPQA-Diamond, at seeds 1001/2311/3407 on identical items, paired: routing
> every question through three cheap `qwen3.6-flash` drafts, an adversarial
> rebuttal, and tool-grounded checks **before** a `qwen3.7-max` judge scores X%
> against Y% for that same `qwen3.7-max` answering alone (pooled net +N, exact
> one-sided McNemar p = …), and against Z% for four independent `qwen3.7-max`
> samples voting under a compute-matched budget (net +M, p = …). **This is a
> claim about scaffolding a flagship call, not about replacing one — the society
> issues one flagship call per item, larger than the solo baseline's (4,116 vs
> 3,066 tok/item), and additionally has calculator and constant-lookup tools the
> baselines do not.** Cost: 4.5× the tokens, 1.7× the list-price dollars, 6.6
> API calls vs 1, 72s vs 51s per item.

Two mechanical amendments at publication time, since the reviewer wrote this
against the N=4 draft: **"four independent … samples" becomes "five"**, and
"identical items" becomes **"question_id-paired items"** per §3. Nothing else
in this paragraph may be altered.

> **⚠ This template was never used, and must not be copy-pasted. Added
> 2026-08-03.**
>
> The result was a **NULL** — net +1, p = 0.50 — so the "if the result is
> positive" branch above never fired. The paragraph is retained as the frozen
> pre-registration it is, deliberately unedited: rewriting a pre-registration
> to match its outcome destroys the only property that makes one worth having.
>
> But two of its numbers are pre-run estimates and would be **wrong if lifted
> into a current claim**. The **4.5×** here is 13,541 / 3,022, computed from
> seed 1001 alone for the N=5 budget decision in §"Why N=5". The published
> figure is **4.7×** (13,175 / 2,792), measured on the 3-seed paired n=265 item
> set. Likewise 4,116 / 3,066 tok/item are seed-1001 estimates. Both are
> correct *for the budget calculation they were written for* and neither is the
> figure to quote about the result.
>
> This doc is excluded from `tests/test_headline_consistency_offline.py` on
> exactly that ground — frozen, not current. The exclusion is what makes this
> note necessary.

**Prohibited wordings, pre-registered:** "cheap seats beat a stronger model",
"orchestration of cheap Qwen seats beats a single call of a stronger Qwen",
"multi-agent beats single-agent", or any phrasing implying arm A replaces the
flagship. Arm A contains the flagship on 100% of items.

## 9. Explicitly out of scope

- **`qwen3.8-max-preview`.** D0 established its drops are chronic server-side
  504s, unfixable by client timeout (confirmed independently by the MATH-1
  retry at 900s). Attempting it here would risk a survivorship-biased
  comparator on the project's headline claim. If it is ever attempted, it is a
  separate spec with its own drop-rate gate, and its result is an interval
  unless it completes 90/90.
- **SuperGPQA-hard.** `universal_gate` projects +3.2 net at n=180 there —
  below bar — for the measured reason that it converts unanimous-wrong at 9.5%
  vs GPQA's 55–75%. Out of scope, not forgotten.
- **Any cross-lab comparison.** Not expressible with these instruments: no
  client, no shared item sample, no shared grading protocol.
- **Re-cutting by subject after a null.** Named here so it cannot be proposed
  later as a fresh idea.

## 10. Build list — nothing fires until items 1 and 4 are done

1. **`benchmark/verify_tb1_flagship.py` — BLOCKING, build first.** No script in
   `benchmark/` pairs GPQA `universal_gate` seeds 1001/2311/3407 against
   anything. Without it the run finishes with no number. ~60 lines of reuse:
   `_outcomes()` from `verify_compute_matched_control.py:63-72` (already
   tolerates `engine`/`baseline`/`result` wrappers, keys on
   `item.question_id`) plus `mcnemar_exact_one_sided` from
   `benchmark.analyze_panel_scaling`. It must:
   - build S = A∩B∩C per seed and **hard-fail** on zero shared ids or |S| < 81;
   - report **pooled primary** for A-vs-B and A-vs-C, and single-seed as
     clearly-labelled secondary at α = 0.0167;
   - recompute arm C's vote offline from `seat_answers` per §2.2;
   - print `arm C NOT RUN — every A-vs-B number is compute-unmatched` when C's
     files are absent (enforcing §2.3 in code, not prose);
   - print arm C's mean per-sample accuracy and mean pairwise agreement
     (kill clause 4).
2. **Arm C runner — NOT NEEDED.** Resolved to the existing
   `cycled_panel --solver-tier flagship --no-tribunal --n-solvers 5` path
   (§2.2). The first draft's "~90 lines mirroring `run_compute_matched_control`"
   was an underestimate of an unnecessary build: it would have required a new
   function or an `n_samples` param on `solve_compute_matched_control`
   (`baseline.py:66` hardcodes `range(N_SOLVERS)`, behind a published result),
   lifting `--seed choices=list(CLAIM_SEEDS)` which **hard-rejects `--seed
   1001`**, changing the dataset default, porting `--retry-missing`, changing
   the concurrency default, and new offline tests — ~130 runner lines plus a
   `baseline.py` edit across 3 files. None of it is now required.
3. **Arm B′ lever — small build.** A `BASELINE_SYSTEM` variant with
   `JUDGE_SYSTEM`-style adjudication framing and **no 3-sentence cap**, plus a
   lever name wired into `--lever` choices and dispatch. Offline test that the
   prompt contains no length constraint and issues exactly one call. Only arm
   B′ depends on this; B and C fire without it.
4. **Arm C pre-flight — BLOCKING for arm C only.** §4.1, 5 items, before
   committing 4.08M.
5. **Offline tests** for the tie/empty-letter recomputation in item 1:
   all-unparsed → wrong; 2-2-1 tie → lowest `seat_index`; empty seats dropped
   before the majority.

**Fire order.** Build item 1 → fire arm B (0.82M, 3 seeds) → build item 3 →
fire arm B′ (0.37M, seed 1001) → pre-flight item 4 → fire arm C (4.08M, 3
seeds) → run `verify_tb1_flagship`. Arm C stays **held** until its pre-flight
passes. Arm B is safe to run the moment item 1 exists.
