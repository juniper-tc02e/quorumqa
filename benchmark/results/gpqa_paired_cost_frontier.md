# The paired cost frontier on GPQA-Diamond — and a retracted number found in a published figure

**Measured 2026-08-02.** The definitive answer to "does any QuorumQA
configuration earn its tokens?", computed on **identical items** rather than
pooled across seeds — the error the pre-existing frontier analysis makes and
that TB-1 was built to avoid.

---

## 1. The paired frontier

Seeds 1001/2311/3407, GPQA-Diamond, n=265 shared items, every configuration
scored on the same questions. Token costs are measured per configuration from
its own logged calls, not estimated.

| configuration | accuracy | tok/item | **accuracy per 1k tokens** |
|---|---:|---:|---:|
| **`qwen3.7-max`, one call** | 89.4% | **2,792** | **0.320** |
| `universal_gate` | 89.8% | 13,175 | 0.068 |
| shipped engine (escalate splits only) | 80.8% | 8,690 | 0.093 |

**A single flagship call is 4.7× more token-efficient than the best QuorumQA
configuration**, for an accuracy difference of +0.4 pp that TB-1 measured at
**p = 0.50** — statistically zero.

**Strict Pareto check:** `universal_gate` technically sits on the frontier,
because +0.4 pp is nominally higher accuracy. That is an artifact of treating a
p=0.50 difference as real. Treat it as the noise it is and **`universal_gate`
is dominated too**. The shipped engine is dominated outright, on both axes, by
a margin no interpretation rescues.

## 2. Why this differs from the existing frontier analysis

`benchmark/results/f2_compute_frontier.csv` pools each configuration across
**whatever seeds it happened to run on** — `baseline_3.7max` over seeds
7/123/314, `chem_thinking_gate` over 217/314/471, and so on. Those are
different item samples. Given the flagship's measured seed-to-seed spread on
GPQA (83.0% / 86.5% / 94.3%), cross-seed frontier comparisons can invert
purely from sampling.

This table fixes that by construction: one item set, every arm.

## 3. A retracted number was doing load-bearing work in a published figure

Found while building the above, and it matters more than the table.

`docs/figures/f04_accuracy_vs_tokens_frontier.svg` plots **`qwen3.8_solo` at
93.6%** as the **highest GPQA point**, with `on_pareto_frontier=True` in the
backing CSV.

**That number was retired on 2026-07-30** by D0's own pre-registered kill
clause (`benchmark/results/qwen38_bar_repair_preregistration.md`). It is the
*survivor-only* rate over 73/78 items; three paced retries recovered just 2 of
12 missing items, and the residual failures are **server-side 504s**, not
client timeouts, so they are structural rather than transient. The honest
figure is the imputation interval **[83.3%, 94.4%]**.

A frontier is a claim about what is *achievable*. A retired point estimate
cannot support one — and this one was not merely present but was setting the
frontier's ceiling.

**Fixed at the data layer**, so it cannot silently recur:

- `RETIRED_POINT_ESTIMATES` added to `benchmark/figure_data.py`, declaring the
  retirement as a category strictly stronger than "contaminated". Retired
  configs must be excluded from any frontier computation or drawn as an
  interval, never as a point.
- The `qwen3.8_solo` contamination footnote is rewritten. It previously said
  *"upper-biased point estimate, not a settled bar"* — accurate before the kill
  clause fired, an understatement after. It now states the retirement, the
  interval, and warns against frontier use specifically.
- Three tests enforce it, including one asserting the footnote names Pareto use.

**The SVG itself is not regenerated here** — that requires re-running the
figure pipeline and is tracked separately. Until it is, `f04` should not be
shown.

## 4. What this means for the project

Combined with TB-1, the position on GPQA-Diamond is unambiguous and should be
stated plainly rather than discovered by a reader:

> **No QuorumQA configuration earns its tokens on GPQA-Diamond.** The best one
> matches a single flagship call at 4.7× the cost; the shipped one is worse and
> 3× the cost.

This does not retract the `universal_gate` result, which is correctly measured
against the cheap panel and survives its own compute-matched control. It
establishes what that result is *worth*: it recovers the ground the cheap panel
gives up, and stops at parity with the obvious alternative.

## 5. Honest limits

1. **GPQA-Diamond only.** SuperGPQA-hard is the surface where the flagship is
   weakest (measured 79.5 / 79.3 / 76.5%) and where `flagship_panel` already
   beats it by pooled net +10, p=0.0032 — though that advantage was itself
   attributed to self-consistency sampling, not deliberation. A paired cost
   frontier there is **not yet built** and is the one place this conclusion
   might not hold.
2. **`qwen3.7-max` as the reference.** Against `qwen3.8-max-preview` the
   comparison is unrunnable without survivorship bias (§3).
3. **Tokens are not dollars.** Cheap-tier and flagship tokens differ in price;
   this table is a token frontier. A dollar frontier would flatter the cheap
   configurations somewhat — but not by the ~9 accuracy points they give up.
4. **Accuracy is not the only axis.** Auditability, tool-grounded checking, and
   an inspectable transcript are real properties of the tribunal that a single
   opaque call does not have. They are simply not accuracy-per-token, and this
   document is about accuracy-per-token.
