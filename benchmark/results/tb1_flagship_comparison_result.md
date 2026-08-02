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

## 5. Arm C is NOT being fired, and why

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
