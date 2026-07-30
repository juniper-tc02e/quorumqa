# Pre-registration — repairing the GPQA family-best bar (D0/R0)

**Written 2026-07-26, BEFORE the repair run exists.** The analysis plan below is
fixed now so it cannot be chosen after seeing the result. Approved by Jun Kai as
item 1 of three. Fires at the quota reset (2026-07-28 03:32 UTC).

## The problem

`benchmark/results/qwen38_baseline_seed123.jsonl` holds **78 rows, 73 correct =
93.6%** — against an intended n=90. **12 items are missing**, lost to 300s
ReadTimeouts and 429s on the Token-Plan endpoint.

This is the *identical* survivorship contamination our own F2 review used to
disqualify `qwen38_panel`'s 87.3% on SuperGPQA-hard. The rule was simply never
applied to this row (`docs/capability-roadmap.md` D0, `docs/negative-results.md`
§4). Timeout drops are **not random**: they correlate with long, hard questions,
so the survivors are an easier subset and 93.6% is an **upper-biased** estimate.

## Why it matters more than it looks

We have repeatedly published that our best society (`chem_thinking_gate`, 90.9%)
sits **"2.7pt below the family bar."** That sentence assumes 93.6% is real.

The honest bound, from the data we actually have:

| Assumption about the 12 missing items | True accuracy |
|---|---|
| All 12 wrong | 73/90 = **81.1%** |
| All 12 right | 85/90 = **94.4%** |
| Missing behave like survivors (93.6%) | ≈ 93.6% |

**The true value lies in [81.1%, 94.4%] — a 13.3pt band — and our own 90.9% sits
inside it.** So the direction of the gap is not established: depending on the 12
items, we are anywhere from **9.8pt ahead** to **3.5pt behind**. The "2.7pt
behind" claim silently picked the top of the interval.

**A second, independent defect in the same comparison:** the bar was measured at
**seed 123** while `chem_thinking_gate` ran at seeds **314/217/471**. GPQA
reshuffles its item sample per seed, so this was never a paired comparison — it
comes with the full cross-seed sampling error on top of the survivorship bias.

## The repair

`benchmark/qwen38_baseline.py` already has a resume path (`--retry-missing`,
`done_ids` at line 115) that skips completed ids and re-runs only the missing
ones. Concurrency default is 2 and the per-call timeout is already 300s.

```bash
python -m benchmark.qwen38_baseline --n 90 --seed 123 --concurrency 1 \
  --retry-missing --out benchmark/results/qwen38_baseline_seed123.jsonl
```

`--concurrency 1` deliberately: the original failure was 429s plus timeouts, and
12 items do not need parallelism. Estimated cost ~0.05M tokens (12 items at the
measured ~4.2k tok/row), well inside the ~0.4M budgeted.

## Pre-registered analysis plan (fixed before the data exists)

1. **Publish BOTH numbers side by side, always.** The repaired n=90 figure AND
   the original 73/78 survivor figure, with the drop count. Never the repaired
   number alone — the difference between them is the measurement of the bias, and
   it is a finding in its own right.
2. **If any items still fail to complete**, report the result as an **interval**
   with all-correct / all-wrong imputation bounds over the residual, exactly as
   tabulated above. Do not quote a point estimate over a partial set.
3. **Recompute every downstream claim built on 93.6%**, and say so explicitly:
   the "2.7pt below the family bar" sentence in `docs/FINDINGS.md` and the
   Track-B framing; the F1(b) GPQA-deficit decomposition (0 blind-spot / 2
   escalated-and-lost) in `family_floor_analysis.md`, whose 2-item basis may
   change; and the D2 council-gate ceiling comparison, which reads +4 against
   this bar but +9 against `chem_thinking_gate`.
4. **The cross-seed defect is NOT repaired by this run.** Even a clean 90/90 at
   seed 123 is not paired with our seeds 314/217/471. Any claim of the form
   "society vs family-best" must either run 3.8-solo at our seeds, or be stated
   as cross-seed with that caveat attached at the point of use. Pre-registering
   this now so the repaired number is not over-read the moment it lands.
5. **No outcome is a failure.** If the repaired bar is ~93-94%, we are genuinely
   behind and the Track-B target stands. If it drops toward 85%, our best society
   may already exceed the family's best single model — a materially different
   strategic position. Both are publishable; neither changes what we do next
   except by pointing it.

## Kill

If the 12 items cannot be completed after 3 paced attempts, record the interval
and **retire the point estimate entirely** — the bar becomes "between X% and Y%"
in every document that cites it, and no "N pt from the bar" sentence may be
written at all.

## Result, 2026-07-30 — the kill clause fired

Three paced attempts were run (`--retry-missing`, `--timeout 900`, concurrency
1): 78 → 79 → 80 survivors, recovering only **2 of the original 12** missing
items. Each attempt hit **504 Gateway Timeout from Aliyun's own infrastructure**
on the same residual items — not a client-side timeout, so raising `--timeout`
past the default could never have fixed it. `rec5rjeLsEq5Fg7Oj`, one of the
still-dropped items, is independently named in `lever_findings.md` as a
chronic-drop offender ("the slowest-reasoning questions hitting the API
read-timeout ceiling") across multiple prior runs — this is a structural
property of these specific items' generation length, not transient load.

**Per the kill clause: the point estimate is retired.** 10 of 90 items remain
unreachable via this API path.

| | value |
|---|---|
| survivors | 80/90 |
| survivor-only accuracy (upper-biased) | 93.8% |
| all-10-missing-wrong | **83.3%** |
| all-10-missing-right | **94.4%** |

**The honest bar is the interval [83.3%, 94.4%], not a point.** Our own society
(`chem_thinking_gate`, 90.9%) sits **inside** this band. The sign of the
society-vs-family-bar gap remains undetermined — from +7.6pt ahead to −3.5pt
behind, depending on the 10 unreachable items — and no further attempt at this
API path is planned; reaching these 10 items would need a different approach
(e.g. a stricter `max_tokens` forcing shorter generation, changing the model's
behavior) rather than more retries at the same settings.

No document may state "the society is Npt under/over the family bar" without
either citing this interval or re-deriving it with a materially different
method.

**Note on the imputation model (`analyze_dropout_bias.py`), not the point
estimate.** That script's secondary "slowest-survivors" imputation flipped
direction with the 2 newly-recovered items: pre-repair it read "society ahead"
(slow-survivor rate 66.7% < flip threshold 73.4%); post-repair it reads
"bar ahead, barely" (70.0% > 68.1%). This is a narrow, genuine shift from more
data, not an error — and it changes nothing about the retired point estimate
above, which stays the full [83.3%, 94.4%] interval regardless of which
imputation model is preferred. Flagged so the reversal isn't mistaken for a
bug if someone diffs the script's output.
