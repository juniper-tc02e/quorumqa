# TB-1 — the scaffolded flagship does NOT beat the solo flagship. Null, and it dominates the architecture.

**Measured 2026-08-02.** `docs/spec-trackb-flagship-comparison.md`, arm B, fired
as a **falsification test** (its own statistical review put P(confirm) ≈ 0.05
and P(kill) ≈ 0.25–0.38 before it ran). Independently re-derived from the raw
files, not read off the report.

Reproduce: `python -m benchmark.verify_tb1_flagship`

---

## 1. The result

Paired on the question_id intersection, GPQA-Diamond, seeds 1001/2311/3407.
|S| = 88 / 88 / 89, every seed clearing the pre-registered ≥81 gate.

| seed | A `universal_gate` | B flagship 1× | b | c | net |
|---|---:|---:|---:|---:|---:|
| 1001 | 79/88 | 79/88 | 2 | 2 | **0** |
| 2311 | 79/88 | 78/88 | 3 | 2 | **+1** |
| 3407 | 80/89 | 80/89 | 3 | 3 | **0** |
| **pooled** | **238/265 (89.8%)** | **237/265 (89.4%)** | **8** | **7** | **+1** |

**Primary test (pooled 3-seed exact one-sided McNemar): p = 0.50. Does not
clear.** Accuracy difference: **+0.38 pp**. The secondary single-seed branch
(Bonferroni α = 0.0167) does not clear at any seed.

**The whole QuorumQA apparatus — three cheap drafts, a skeptic, a tool-using
verifier, and a `qwen3.7-max` judge — scores the same as calling `qwen3.7-max`
once.**

## 2. What this does and does not establish

**Does:** it rules out any large advantage. The 95% interval on the paired
difference spans **[−6.6, +8.6] items over n=265**, centred on +1.

**Does not:** prove exact equivalence. A true effect of a few items is
compatible with this data — the reviewer's pre-run power analysis said as much
(expected net ≈ +1.2, P(clearing) ≈ 5.4%). This is a **failure to demonstrate
superiority with a tight bound**, not a proof of parity. Stated because the
distinction is exactly the kind this repo has previously blurred.

## 3. The finding that actually matters: the architecture is dominated

Put the three measured configurations side by side on the same benchmark, with
measured token costs:

| configuration | GPQA-Diamond accuracy | tok/item | verdict |
|---|---:|---:|---|
| **`qwen3.7-max`, one call** | **89.4%** | **3,022** | — |
| `universal_gate` (escalate all) | 89.8% | 13,541 | **4.5× the cost, +0.4 pp, p=0.50** |
| shipped engine (escalate splits only) | ~80% | 9,145 | 3.0× the cost, **−9 pp** |

**On GPQA-Diamond, QuorumQA is strictly dominated by a single flagship call.**
The best configuration matches it and costs 4.5×; the shipped configuration is
both worse and 3× more expensive.

This is the honest reading and it must not be softened. It is also the reading
an external reviewer would reach immediately, which is why it is better found
here.

## 4. How this reframes the `universal_gate` result

`universal_gate`'s +25 over the shipped cheap panel
(`universal_gate_3seed_result.md`) is **real, correctly measured, and survives
its own compute-matched control**. Nothing about it is retracted.

But TB-1 supplies the missing denominator. The +25 was measured against a weak
internal baseline. Placed against the obvious external one:

> **The scaffolding's entire measured gain is climbing back to where a single
> flagship call already was.**

It buys back the ~9 points the cheap panel gives up, and stops there. That is
why the +25 and the +1 are both true and not in tension: they are measured
against comparators 9 points apart.

## 5. Arm C was cancelled here — and that decision was REVERSED (see §5.1)

*The section below is the original cancellation, kept verbatim as the record of
what was decided and why. It was overturned on 2026-08-03 and arm C was fired;
§5.1 states the reasons and the cost. Read both.*

The spec funds arm C (flagship self-consistency @ N=5, 4.08M) as the attribution
guard that decides whether a win is orchestration or budget.

**There is no win to attribute.** Spending 4.08M — 13.6% of the week-1 cap — to
explain the mechanism of a p=0.50 null would be waste. Formally amending the
spec: **arm C is CANCELLED**, not deferred, on the grounds that its
pre-registered purpose is void.

Two supporting reasons, both already measured: same-family sampling has failed
to scale twice in this repo (panel-scaling flat N=3→15 on SuperGPQA-hard;
N=3→9 flat on GPQA inside `universal_gate`'s own control), so a flagship SC@5
arm is unlikely to beat either A or B; and A-vs-B needing no compute-matching
to interpret a *null* — the compute asymmetry only ever threatened a positive.

Arm B′ (the prompt-richness control) is cancelled for the same reason: it
existed to bound a confound in a positive result.

### 5.1 ⚠ The cancellation was REVERSED on 2026-08-03. Arm C was fired.

Recording this as an overturned decision rather than quietly absorbing the
data — a test (`test_arm_c_remains_unrun_by_design`) existed specifically to
force this paragraph to be written, and it is the only reason the reversal was
noticed rather than silently landing.

**What the cancellation got right:** arm C cannot rescue an accuracy claim, and
attribution-of-a-win is indeed void when there is no win.

**What it missed:** arm C answers a *second* question the cancellation never
considered. A-vs-B establishes that the stack **ties one flagship call**.
A-vs-C establishes whether the stack is **dominated at the same token budget** —
whether the 13,175 tok/item it spends would buy more accuracy spent on plain
sampling instead. That is a materially stronger and more useful claim, and it is
the one a reader deciding whether to build this architecture actually needs.

**Its second supporting reason is now falsified.** The cancellation argued that
"same-family sampling has failed to scale twice in this repo… so a flagship SC@5
arm is unlikely to beat either A or B." Measured at seed 1001: flagship SC@5
scores **79/85 against the stack's 78/85**, with mean per-sample accuracy
**92.3%**. It did beat arm A. The prediction was reasonable and wrong, which is
the ordinary reason to run an experiment rather than reason about it.

**Cost, stated plainly:** ~4.0M tokens, the same 13.6% of the week-1 cap the
cancellation called waste. That judgement was defensible on the information
available then; it is being overridden with the reason above, not ignored.

**Its third reason still stands** and is worth keeping: A-vs-B needed no
compute-matching to interpret a *null*, because the compute asymmetry only ever
threatened a positive. Arm C is not a correction to A-vs-B. It is a different
question.

### 5.2 Arm C result — the attribution kill fires

**Measured 2026-08-03. Seeds 1001/2311/3407, |S| = 85 at every seed, n = 255
paired.** All three seeds clear the ≥81 gate. Reproduce with
`python -m benchmark.verify_tb1_flagship`.

| comparison | b | c | net | p (one-sided) | verdict |
|---|---:|---:|---:|---:|---|
| **A vs C** — stack vs the same budget sampled | 3 | 9 | **−6** | 0.981 | **KILL FIRES** |
| A vs B — stack vs one flagship call | 7 | 7 | **+0** | 0.605 | ties |
| C vs B — sampling vs one call *(context, not pre-registered)* | 10 | 4 | +6 | 0.090 | directional |

Per seed, A-vs-C is **−1 / −2 / −3**. Every seed points the same way; none of
them is carrying the result.

**Verdict, in the wording §6.1 fixed before the data existed: a COMPUTE EFFECT,
NOT AN ORCHESTRATION EFFECT.**

#### The frontier, on identical items

| configuration | accuracy | tok/item | accuracy per 1k tokens |
|---|---:|---:|---:|
| `qwen3.7-max` ×1 | 90.6% | **2,627** | **34.5** |
| `universal_gate` | 90.6% | 12,991 | 6.97 |
| **`qwen3.7-max` SC@5** | **92.9%** | 13,833 | 6.72 |

At **essentially the same token budget** — 12,991 against 13,833, a 6%
difference — plain self-consistency scores **2.3 points higher** than the full
scaffolded stack. The tribunal does not merely fail to add value over sampling;
spending its budget on sampling instead is measurably better.

#### Kill clause 4 did not fire, and that matters

The control is **admissible at every seed**:

| seed | mean pairwise agreement | items where the 5 seats split | degenerate? |
|---|---:|---:|---|
| 1001 | 0.963 | 8.1% | no |
| 2311 | 0.927 | 12.8% | no |
| 3407 | 0.931 | 12.9% | no |

Thresholds were **≥0.98 agreement** or **<5% split**, both fixed on 2026-08-03
while seed 1001 was still running and before any accuracy was read — see the
note at `verify_tb1_flagship.py`'s constants. Had the agreement threshold been
set at 0.95 instead, all three seeds would have been voided, and voiding A-vs-C
is precisely the outcome that would have protected arm A's mechanism claim.

Diversity parity was verified from the run rather than from config: all 430
seat records at seed 1001 fire at temperatures 0.3/0.6/0.9/0.3/0.6, matching
arm A's own cycle. Review point 7 of the spec rejected a 0.4-uniform arm C as an
under-diversified straw control; this is not that.

#### Why C-vs-B is reported alongside

A-vs-C alone is ambiguous: "the stack loses to SC@5" is consistent both with
*sampling is good* and with *the stack is bad*. C-vs-B separates them —
**+6, p = 0.090** — so sampling is directionally worth its budget while the
scaffold on top of that budget is not. It is labelled *not a pre-registered
test* because it is not one.

#### What moved, and what did not

Adding arm C shrank S from **265 to 255** items, because the analysis set is the
intersection of every arm present (§5). A-vs-B therefore reads **net +0,
p = 0.605** here where it read net +1, p = 0.50 before. **Nothing was
re-measured and nothing is corrected** — a paired statistic is defined on its
item set, and the spec requires all arms share one set so arm A's accuracy is a
single number in both comparisons. Both figures describe the same null.

#### Drops

Every seed lost 5 items (|S| = 85 of 90), well inside the 9-drop kill. Drops are
504-correlated and therefore **not MCAR**; with net −6 against a bar the result
misses by a wide margin, 5 items could not reverse it, but the bias is stated
rather than assumed harmless.

> **⚠ That sentence is WRONG, corrected 2026-08-03.** The drops CAN reverse it
> and they do. Counting a non-completion as a failure over the intended 270
> items, A-vs-C goes from **net −6 to net +1** — eight items the stack answered
> correctly are excluded from the complete-case set solely because arm C
> returned nothing on them. Excusing an arm the items it failed to finish is
> exactly the bias "not MCAR" warns about, and I asserted the opposite without
> computing it. See `python -m benchmark.analyze_dropout_sensitivity`. The 300 s client timeout that caused them is
filed as separate work — `lever_experiments.py` does not expose the `timeout`
parameter `QwenClient` already has.

#### Cost

~4.0M tokens across three seeds, at 14,740 tok/item measured (the spec budgeted
~15,000). Slightly **over**-matching `universal_gate`'s own spend, which is the
conservative direction.

## 6. What survives, honestly

Nothing here rescues an accuracy claim on GPQA-Diamond. What remains true:

- **`universal_gate` vs the cheap panel is a genuine, well-controlled finding**
  about *when to escalate*, and generalises as a design principle (escalate on
  unanimity, not just on disagreement) independently of whether this particular
  stack is worth running.
- **The kill-list is the session's real output.** Eight mechanisms that re-read
  existing model output are now dead, plus self-authored tool verification, plus
  confidence selection out-of-sample. That is a substantial negative result set.
- **Auditability is not an accuracy claim** and is not measured here. A tribunal
  transcript with tool checks is more inspectable than one opaque call. If that
  is the product argument, it must be made as a product argument — this
  document establishes that it cannot be made as an accuracy-per-token one.

## 7. Honest limits

1. **GPQA-Diamond only, n=265 pooled over 170 unique items.** SuperGPQA-hard is
   untested against a flagship comparator and is where the cheap panel's floor
   is largest — the domination result may not transfer, and saying it does
   would repeat exactly the error TB-1 just corrected.
2. **`qwen3.7-max` only.** Against `qwen3.8-max-preview` the comparison is
   unrun and, per D0, currently unrunnable without survivorship bias.
3. **Drops are not MCAR.** 2/2/1 items short of 90 per seed, 504-correlated.
   All seeds cleared the ≥81 gate, but the missing items skew long/hard.
4. **This is one prompt configuration.** The baseline is told "keep reasoning to
   at most 3 sentences"; the judge is not. If anything that handicaps arm B,
   which makes the null *more* damning for arm A, not less.
5. **Failure to show superiority ≠ equivalence** (§2).
