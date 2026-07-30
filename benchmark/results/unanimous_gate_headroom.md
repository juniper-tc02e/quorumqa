# The unanimous-wrong ceiling is a gate-recall problem, not a tribunal limit

**Measured 2026-07-26. Offline, from committed logs only — no API calls, no
tokens.** Reproduce with:

```bash
python benchmark/analyze_judge_anchoring.py
```

Corpus: **1,998 escalations carrying a Judge verdict, across 58 result files**,
plus **3,660 unanimous panels** (escalated or not) as the recall denominator.

---

## 1. What prompted this

A read of AggLM (arXiv:2509.06870, FAIR/Meta) suggested a lever: its aggregator
prompt licenses *"any, all, or **none** of these solutions are correct"* and
permits synthesising an answer present in no candidate. QuorumQA's
`JUDGE_SYSTEM` instead asks the Judge to *"rule on the single best answer
letter"* — framing the job as selection among presented positions. For multiple
choice, AggLM's "none are correct" case has an exact analogue: **picking a letter
no solver picked.** The hypothesis was that our phrasing anchors the Judge to the
solver slate.

## 2. That hypothesis is dead — the Judge is not anchored

| | count | share |
|---|---|---|
| Judge chose an **off-slate** letter | 203 / 1,998 | 10.2% |
| …and was **correct** | 169 / 203 | **83.3%** |
| Gold offered by **no solver** | 378 / 1,998 | 18.9% |
| …Judge **recovered gold anyway** | 169 / 378 | **44.7%** |

The Judge already leaves the slate at a material rate and is right five times in
six when it does. **No "none-of-the-above" licence is needed** — the existing
"weigh ARGUMENTS, not headcounts; an unrefuted minority position beats a
conforming majority" phrasing already produces the behaviour. This lever is
**killed before any token was spent**, which is the entire point of checking the
logs first.

*Convergence worth recording:* our Judge independently arrived at AggLM's
inference-time shape — full solver rationales rather than a vote tally, and
adjudication rather than counting. The paper's own untrained control ("Prompted
Aggregation") *loses* to majority voting on strong solutions (AIME24 63.57 vs
67.92) and only sweeps it in the weak/noisy regime, so this convergence is
directional support, not a validated win.

## 3. The finding that replaced it

Chasing the dead hypothesis surfaced a subset nobody had measured: panels that
were **unanimous AND all wrong, yet still escalated**. The shipped orchestrator
returns early on unanimity (`if unanimous: return` in
`src/quorumqa/engine/orchestrator.py`), so these reached the tribunal only via a
lever's doubt/score gate. They are members of the very set the repo calls
unreachable *"by construction."*

| | count | rate |
|---|---|---|
| Unanimous **wrong**, escalated anyway | 84 | — |
| …tribunal **recovered** gold | 40 | **47.6%** |
| Unanimous **right**, escalated anyway | 130 | — |
| …tribunal **broke** a right answer | 1 | **0.8%** |

**Recovery beats breakage roughly 60 : 1.** So the tribunal is not incapable on
unanimous items — it is simply never shown them. The binding constraint is
**gate recall**, which is a different and attackable problem from the one
currently recorded.

### Gate recall, and the headroom it leaves

| | value |
|---|---|
| Unanimous panels observed | 3,660 |
| …of which **wrong** (this is *w*) | 659 = **18.0%** |
| Unanimous-wrong that escalated | 84 = **12.7% recall** |
| Unanimous-wrong never surfaced | 576 |
| Headroom at 47.6% conversion | **≈ 274 items** pooled |

### Break-even

Expected net gain per 100 newly-surfaced unanimous items is
`100 · (w · 0.476 − (1−w) · 0.008)`, so break-even sits at

> **w = 1.6%** — against a measured **w = 18.0%**, i.e. **11× above break-even.**

## 4. Why this does NOT contradict D2 (the wrongness-predictor null)

D2 established that no trace/distribution feature separates unanimous-correct
from unanimous-wrong: *"on unanimous items the agreement/entropy features are
maximal-and-useless by construction."* That null stands exactly as written.

It does not block this lever, because **at a 1.6% break-even you do not need to
know which unanimous items are wrong.** You escalate all of them and let the
60:1 asymmetry do the work. D2 asked "can we target?"; the answer here is
"targeting is unnecessary." A predictor would only reduce cost, never
correctness. This also completes the existing *"coverage, not judge quality, is
the bottleneck"* finding — a stronger judge got 9/9 overturns right for zero net
gain because it never saw the failures. This measures what giving it coverage
would buy.

## 5. The catch: it is a Track-B lever, and GPQA-specific

The pooled 47.6% hides a **5× spread**. Breakage is ~0 everywhere, so a wider
gate is accuracy-positive almost regardless of surface — but *cost* decides
whether it is worth firing, and each firing spends ~4 extra calls.

| dataset | unan-wrong | recovered | rate | unan-right | broken | escalations per net item |
|---|---|---|---|---|---|---|
| gpqa (default) | 49 | 27 | **55.1%** | 64 | 0 | **4.2** |
| gpqa | 12 | 9 | **75.0%** | 33 | 1 | 5.6 |
| supergpqa | 21 | 2 | **9.5%** | 27 | 0 | **24.0** |
| lexam | 1 | 1 | 100% | 2 | 0 | 3.0 |
| mmlu_pro | 1 | 1 | 100% | 4 | 0 | 5.0 |

**SuperGPQA-hard converts at 9.5% and costs 24 escalations per item gained —
~6× worse than GPQA.** This inverts the usual ordering: SuperGPQA-hard is where
our levers pay best overall (+4.1), yet its unanimous-wrong items are the least
recoverable. The natural mechanistic reading — that SuperGPQA-hard's
unanimous-wrong set is genuine missing *knowledge* while GPQA's is recoverable
reasoning slips — is consistent with the LEXam corpus-gap result, but it is
**inference, not measurement**, and n=21 on the SuperGPQA cell is thin.

## 6. Honest limits — read before acting

1. **Pooled-marginal provenance.** Aggregated across datasets, seeds and lever
   configs. Not a paired delta, not a per-benchmark claim. It *sizes* a
   hypothesis; it validates nothing.
2. **Selection bias, same shape as the D0 bar.** The existing gates fire on
   *detectable* doubt, so both the 47.6% conversion and the 0.8% breakage are
   measured on a boundary-adjacent subset. Conversion on **confidently**-wrong
   unanimous items — precisely the ones a wider gate would newly surface — is
   plausibly lower. **Treat 47.6% as an upper estimate.**
3. **Thin cells.** The decisive SuperGPQA cell is n=21; breakage rests on a
   single event in 130.
4. **Cost is unmodelled here.** The break-even above is accuracy-only. A
   cost-adjusted break-even is far higher, and on SuperGPQA plausibly
   prohibitive.
5. **`w` is not the 61.6% figure.** 61.6% is the unanimous share *of wrong rows*;
   `w` = 18.0% is the wrong share *of unanimous rows*. Different denominators —
   do not substitute one for the other.

## 7. What follows

- **Killed, free:** the AggLM none-of-the-above licence (§2). No run needed.
- **Pre-registered and fired:** a universal-escalation arm on unanimous panels,
  GPQA first. See §8 for the result.
- **Cost, not accuracy, is the gate.** Any spend must be argued on Track-B terms.

## 8. Live result, 2026-07-30 — `universal_gate`, GPQA-Diamond, seed 1001

The pre-registered arm from §7 was built (`--lever universal_gate`, no doubt
check, unconditional escalation on unanimity) and fired on a fresh, unburned
seed. **It clears the repo's single-seed bar cleanly:**

| | shipped (no universal escalation) | `universal_gate` |
|---|---|---|
| accuracy | 71/90 = 78.9% | **80/90 = 88.9%** |

Paired within the same run — both configurations share identical solver panels;
they differ only in whether a unanimous panel is allowed to escalate:
**net +9, one-sided exact McNemar p = 0.00195.** This is the single strongest
p-value of any result in the repo.

Mechanism, measured directly on this run's 48 unanimous panels:

| | count | outcome |
|---|---|---|
| unanimous-wrong | 12 | **9 recovered = 75.0%** |
| unanimous-right | 36 | **0 broken = 0.0%** |

**The pre-registered falsifiable prediction did NOT hold.** §7 predicted
conversion *below* 47.6% (the pooled, selection-biased estimate), reasoning that
a wider gate would newly surface *confidently*-wrong items existing doubt-gates
miss, which should convert worse. Instead this seed converted at 75.0% —
*above* the pooled estimate, and at the high end of this session's earlier
GPQA-only range (55.1–75.0%). Recorded honestly per limit 2's own instruction:
if it lands near or above 47.6%, the selection-bias worry was overblown. It was.

**Read carefully — this does not retroactively validate limit 2's mechanism as
false in general**, only on this one seed: n=12 unanimous-wrong items is small,
and a single seed cannot distinguish "the selection-bias worry was wrong" from
"this seed happened to land well." The repo's own bar treats a single seed at
p<0.05 as sufficient to claim the win — it is not sufficient to retire the
caveat itself. The other branch of the bar (net≥+3 at 2 of 3 seeds, pooled
McNemar p<0.05) would need two more fresh seeds to invoke and was not run.

**GPQA only, as designed** — §5's cost table (4.2 escalations/net item on GPQA
vs 24.0 on SuperGPQA-hard) is why GPQA fired first. This result says nothing
about SuperGPQA-hard.

Reproduce: `python -m benchmark.verify_universal_gate`
