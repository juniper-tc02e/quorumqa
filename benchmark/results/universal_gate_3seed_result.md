# `universal_gate` — 3 seeds, net +25, zero losses, and it survives its compute-matched control

**Measured 2026-08-01.** `docs/spec-sci1-and-knowledge-injection.md` §3.2 and
§3.3, fired as the only live arm the adversarial review funded. This is now the
strongest result in the repo, and — unlike the last headline — its mechanism
control was run **up front, in the same seed**, not appended after the fact.

Reproduce: `python -m benchmark.verify_universal_gate`

---

## 1. What ran

`universal_gate` escalates **every** unanimous panel to the tool-using tribunal,
unconditionally — no doubt-check, no subject filter, no trigger to tune. The
shipped orchestrator instead returns early on unanimity (`if unanimous: return`),
which is why 61.6% of its wrong answers were structurally unreachable.

| seed | status | n | drops |
|---|---|---:|---:|
| 1001 | banked earlier (2026-07-30) | 90 | 0 |
| 2311 | fresh, fired 2026-08-01 | 89 | 1 (1.1%) |
| 3407 | fresh, fired 2026-08-01 | 90 | 0 |

All three well under the 10% survivorship-void threshold. Seeds 2311/3407 were
verified fresh against the burned list, this session's used list, and every
filename in `benchmark/results/` before firing, and committed to the registry
in advance.

## 2. The result

Paired **within each run**: same items, same panels, differing only in whether
a unanimous panel is allowed to escalate. The counterfactual comes from each
run's own logged `plurality_letter`, so no second live run was needed.

| seed | shipped | universal_gate | b | c | net | p (one-sided exact McNemar) |
|---|---:|---:|---:|---:|---:|---:|
| 1001 | 78.9% | 88.9% | 9 | 0 | **+9** | 0.00195 |
| 2311 | 77.5% | 89.9% | 11 | 0 | **+11** | 0.00049 |
| 3407 | 83.3% | 88.9% | 5 | 0 | **+5** | 0.03125 |
| **pooled** | — | — | **25** | **0** | **+25** | **2.98 × 10⁻⁸** |

**Every seed clears the single-seed bar on its own** (net ≥ +5, p < 0.05) — so
both branches of the repo bar are satisfied, not just the 2-of-3 branch that was
the target. **Zero losses across 269 items.** The pre-registered kill (both
fresh seeds ≤ +2 ⇒ retract seed 1001 as seed luck) did not fire; it was
inverted, with both fresh seeds independently clearing.

Recovery and breakage, pooled: **25 of 38 unanimous-wrong items recovered
(65.8%)**, **0 of 118 unanimous-right items broken (0.0%)**.

## 3. The mechanism control — the part that matters

`flagship_panel`'s +10 survived arithmetically and lost its *story* to a
compute-matched control fired afterwards: +9 of it was plain self-consistency
sampling, only +2 the tribunal (p=0.344, n.s.). Repeating that sequence would
have been a choice, not an oversight. So the control ran **at seed 2311, on the
same items, in the same queue**.

**Arm:** `diversified_panel --n-solvers 9 --no-tribunal` — 9 cheap seats, vote
only, no skeptic/verifier/judge. At ~15,700 tok/item against `universal_gate`'s
measured 13,541, the control is *over*-matched on compute, which is the
conservative direction.

| arm at seed 2311 (n=89 shared) | accuracy |
|---|---:|
| shipped 3-seat panel, no escalation | 77.5% |
| **`universal_gate` (tribunal)** | **89.9%** |
| compute-matched N=9 vote-only | **65.2%** |

| paired comparison | b | c | net | p |
|---|---:|---:|---:|---:|
| `universal_gate` vs N=9 vote-only | 24 | 2 | **+22** | 0.00001 |
| N=9 vote-only vs shipped 3-seat | 5 | 16 | **−11** | 0.996 |

**The control does not match `universal_gate`. It does not even match the
shipped panel.** Spending the same tokens on more cheap votes is *worse* than
spending them on three votes plus a tribunal, decisively.

### 3.1 Ruling out the obvious objection

The control arm is not simply "more of the shipped seats." `solve_all_diversified_panel`
builds seat *i* from `SOLVER_PROCEDURES[i%5] × SOLVER_TEMPERATURES[i%3]` with an
independently permuted choice order — different seats, and evidently weaker
ones (its N=3 point is 65.6% vs the shipped panel's 77.5%). So a sceptic could
say the control lost because its seats are bad, not because votes don't scale.

That objection is answerable **for free**, from the arm's own logged
`seat_answers`, and it does not survive:

| N (within the diversified arm) | accuracy |
|---:|---:|
| 1 | 57.8% |
| 3 | 65.6% |
| 5 | 61.1% |
| 7 | 64.4% |
| 9 | 65.6% |

**Paired N=9 vs N=3 within the arm: b=5, c=5, net = 0, p = 0.62.** Scaling cheap
votes from 3 to 9 buys **exactly nothing**. The arm's low absolute score is
weak seats; its *failure to improve with more votes* is a separate and
independently-measured fact. Even had the seats matched the shipped panel,
tripling them would not have closed a +22 gap that more voting cannot touch.

This also **independently replicates on GPQA** the flat-N finding
`panel_scaling_n15_seed19.md` measured on SuperGPQA-hard (flat 47–51% from N=3
to N=15). Two benchmarks, two seat configurations, same shape.

**Mechanism verdict: the tribunal is doing the work, and it is not compute.**
Unlike `flagship_panel`, this claim survives the control that killed the last one.

## 3.2 Robustness: the seeds overlap, and the result survives it

GPQA-Diamond holds only ~198 questions, so three 90-item draws **cannot** be
disjoint. Measured overlap:

| pair | shared items |
|---|---:|
| 1001 ∩ 2311 | 34 (38%) |
| 1001 ∩ 3407 | 46 (51%) |
| 2311 ∩ 3407 | 31 (34%) |
| in all three | 12 |

The 269 pooled rows therefore cover **170 unique items**, with **99 repeated
observations**. Summing per-seed 2×2 tables — this repo's pooling convention —
implicitly treats those 269 as independent, and they are not. Stated plainly
because it inflates the pooled figure and a reader would be right to object.

**How much does it matter? Almost none.** Counting each item **once**, however
many seeds recovered it:

| | b | c | net | p |
|---|---:|---:|---:|---:|
| as reported (per-seed pooled) | 25 | 0 | +25 | 2.98 × 10⁻⁸ |
| **conservative, unique items only** | **21** | **0** | **+21** | **4.77 × 10⁻⁷** |

Only **4 items** were recovered at more than one seed. The conservative
statistic is still overwhelming, and — because `c = 0` on both counts — no
weighting scheme can produce a loss where none exists. **The conclusion is
unchanged; the honest number to quote for a cross-seed-independence-sensitive
reader is net +21, p = 4.8 × 10⁻⁷.**

This is a property of GPQA-Diamond's size, not of the design: any 3-seed,
n=90 GPQA study in this repo has the same structure, including every prior
result quoted with a pooled p-value.

## 4. What the claim reads

> On GPQA-Diamond, three cheap `qwen3.6-flash` seats that escalate **every**
> unanimous answer to a tool-using tribunal with a `qwen3.7-max` judge score
> 88.9 / 89.9 / 88.9% against 78.9 / 77.5 / 83.3% for the byte-identical panel
> without escalation — pooled net **+25 discordant items, 0 losses**, exact
> one-sided McNemar **p = 3.0 × 10⁻⁸**, 3 seeds, paired in-run — recovering
> **65.8%** of unanimous-wrong answers while breaking **0%** of unanimous-right
> ones, and beating a **compute-matched 9-seat cheap panel** that spends the
> same tokens on more votes instead of a tribunal by a further **+22 (p=0.00001)**.

Paired, controlled, within-family, 3 seeds, and the control is in the run rather
than appended to it.

## 5. Honest limits

1. **GPQA-Diamond only.** `unanimous_gate_headroom.md`'s cost table is why: GPQA
   converts unanimous-wrong at 55–75% and costs ~4.2 escalations per net item,
   while SuperGPQA-hard converts at **9.5%** and costs **24.0**. The same
   command there projects **+3.2 net at n=180 — below the bar.** This result
   does not transfer and must not be quoted as if it does.
2. **This is a cost trade, not a free win.** Escalating every unanimous panel
   means escalating ~59% of all items that would otherwise have returned
   immediately. Measured cost: **13,541 tok/item** vs the shipped panel's
   **9,145** — roughly 1.5×. The finding is that this is a *good* trade on
   GPQA, not that it is costless.
3. **Same model family throughout.** The judge is `qwen3.7-max` and the seats
   are `qwen3.6-flash` — a tier gap, not an independence gap. Self-preference
   risk is not eliminated, only reduced by the tier difference.
4. **The control is over-matched on compute but differs in seat construction.**
   §3.1 addresses this with the within-arm flat curve, but the cleanest possible
   control — 9 *shipped-lens* seats — was not run, because
   `diversified_panel` is the only lever that accepts `--n-solvers`.
5. **One drop at seed 2311** (1/90). Under the 10% void threshold, reported
   rather than hidden.
6. **Not a cross-lab claim.** This says a Qwen society beats a Qwen panel on
   shared items. It says nothing about any other lab's model, and that sentence
   is not expressible with these instruments.
