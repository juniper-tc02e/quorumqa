# TB-1B — `universal_gate` on SuperGPQA-hard: the screen kill fired

**Measured 2026-08-03, seed 7, n=87 paired items.** Pre-registered in
`docs/spec-tb1b-supergpqa.md` before any data existed. Verdict computed by
`python -m benchmark.verify_tb1b_supergpqa`.

---

## 1. The result

| comparison | A correct | comparator | b | c | net | p (one-sided) | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| **PRIMARY** — vs one `qwen3.7-max` call | 67/87 | 69/87 | 2 | 4 | **−2** | **0.8906** | **loses** |
| SECONDARY — vs the shipped escalate-on-split rule | 67/87 | 61/87 | 8 | 2 | +6 | 0.0547 | does not clear |

**Cost: 15,255 tok/item vs the flagship's 2,969 — 5.1×.**

Both pre-registered kill clauses fired:

- **Screen kill** (spec §6.1): seed 7 net ≤ 0 → the extension to seeds 42 and
  123 is **not funded**. ~2.7M tokens not spent confirming a thesis that failed
  on its most favourable surface.
- **Cost kill** (spec §6.2): >4× the flagship's tokens while net < +5 → reported
  as **dominated**, in those words, the same framing GPQA's result got.

## 2. Why this was the interesting test, and why the answer matters

SuperGPQA-hard is the one benchmark where orchestration has ever cleared the
bar against a flagship call: `flagship_panel` scores 82.2% vs 79.2%, pooled net
+7, p=0.0327 over seeds 7/42/123. The obvious reading was *"orchestration pays
where the base model has headroom."*

`universal_gate` is the natural test of that reading, because it is the same
escalate-everything architecture built from **cheap seats**. If headroom were
what mattered, it should win here too.

It does not. It loses by 2.

**So the SuperGPQA win is not about headroom, and not about orchestration. It
is about which model is doing the sampling.** `flagship_panel` samples
`qwen3.7-max` three times; `universal_gate` samples `qwen3.6-flash` three times
and then escalates. Same benchmark, same headroom, same escalate-everything
gate — opposite outcomes, and the only difference is the seat tier. That is the
compute-matched control's conclusion arriving a second time by a different
route: **sampling the strong model is what works, deliberation among weak ones
is not.**

## 3. The two claims, kept apart

`universal_gate` **does** beat the shipped rule, by +6 (p=0.055). The spec
exists to stop that being reported as the headline, because it is exactly the
error the GPQA result invited: there, `universal_gate` beat the shipped cheap
panel by **+25** and was read as a flagship win, when against an actual flagship
call it was net +1 at p=0.50.

The pattern now holds on both benchmarks measured:

| benchmark | vs shipped rule | vs one flagship call |
|---|---:|---:|
| GPQA-Diamond | **+25** (p = 3×10⁻⁸) | +1 (p = 0.50) |
| SuperGPQA-hard | **+6** (p = 0.055) | **−2** (p = 0.89) |

**`universal_gate`'s gain is always measured against the cheap panel and never
survives against the flagship.** Two benchmarks, two confirmations. The lever is
real — it recovers 8 of 18 unanimous-wrong items here and breaks 2 — but §4
shows that **7 of those 8 are items the flagship already had**. What it recovers
is, almost entirely, ground the flagship never lost.

## 4. Mechanism detail

Of 87 shared items, 46 were unanimous among the three cheap solvers and **18 of
those were unanimous-wrong** — the pool invisible to the shipped
escalate-on-split rule. Escalating everything recovered **8** and broke **2**,
net +6 against the shipped rule.

That recovery is genuine and is why the SECONDARY column is positive. Decomposing
it against the flagship shows why the PRIMARY column is not:

| of the 8 unanimous-wrong items `universal_gate` recovered | count |
|---|---:|
| the flagship **already had correct** — buys nothing against it | **7** |
| the flagship **missed** — a genuine gain against it | **1** |

**Seven of eight recoveries are redundant with the flagship.** The lever
recovers almost exactly the items the flagship also finds easy, so nearly all of
its measured +6 against the shipped rule converts to zero against a flagship
call — leaving 1 gain to be outweighed by the 2 breakages and the 4 items the
flagship gets that the stack loses.

*(An earlier draft of this paragraph asserted the flagship "had already answered
most of those 18 correctly". Checked rather than left standing: it is **8 of 18,
44%** — not most. The real result is sharper than the guess and sits one level
down, in which of the recovered items overlap.)*

## 5. Admissibility

- **|S| = 87** against the intended 90, clearing the ≥81 gate (spec §5).
- **3 items dropped.** The verifier flags these as 504-correlated and therefore
  **not missing-at-random** — the same Aliyun-side gateway timeouts that retired
  the D0 point estimate, concentrated on long-generation items. With net = −2
  and p = 0.89 the verdict is not close enough to the bar for 3 items to change
  it, but the drops are stated rather than assumed harmless.
- Unparseable answers counted **wrong**, never dropped.

## 6. What was not spent

The extension (seeds 42 and 123, ~2.7M tokens) is **not funded**, per the kill
clause fixed before the screen ran. Total spend on TB-1B: ~1.35M tokens for a
definitive negative.

## 7. Reproduce

```
python -m benchmark.verify_tb1b_supergpqa
```

Source: `benchmark/results/TB1B_universal_gate_supergpqa_seed7.jsonl` (arm A),
`benchmark/results/lever_baseline_supergpqa_seed7.jsonl` (arm B).
