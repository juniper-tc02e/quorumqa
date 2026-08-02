# TB-1B — does the *cheap-seat* architecture beat a flagship call where the flagship is weak?

**Written 2026-08-03, BEFORE any arm runs at these seeds.** Fixed now so the
analysis cannot be chosen after seeing the result.

---

## 0. Why this, and why it is the thesis test

Two results bracket the question and neither answers it:

- **TB-1 (GPQA-Diamond):** `universal_gate` vs one `qwen3.7-max` call is **net
  +1, p = 0.50** — a null. But GPQA's flagship is already at 89.4%; there was
  almost nothing to win.
- **SuperGPQA-hard:** `flagship_panel` **beats** one flagship call, **net +7,
  p = 0.0327**, 3 seeds. But `flagship_panel` is *three flagship seats*. That
  is a self-consistency result (vs its own compute-matched SC@3 control: net
  +1, p = 0.50), not a test of the cheap-seat architecture.

**`universal_gate` has never run on SuperGPQA-hard** (verified: zero matching
result files). It is the actual QuorumQA design — three cheap `qwen3.6-flash`
seats, unconditional escalation of every answer to a tool-using tribunal with a
`qwen3.7-max` judge — and SuperGPQA-hard is the one surface measured to have
real headroom (flagship 79.2%). This is the direct test.

## 1. Hypothesis (falsifiable, directional)

On SuperGPQA-hard, at identical items and identical seeds, `universal_gate`
beats a single `qwen3.7-max` call by pooled net ≥ +5 discordant items with
exact one-sided McNemar p < 0.05.

**Stated honestly: the pre-run expectation is a NULL, for a measured reason.**
`benchmark/results/unanimous_gate_headroom.md` finds SuperGPQA-hard converts
unanimous-wrong items at **9.5%** against GPQA's **55–75%**, at **24.0
escalations per net item** against GPQA's 4.2. If that transfers,
`universal_gate` will lift the cheap panel (69.0%) toward, not past, the
flagship (79.2%). This is fired as a **falsification test** of the thesis, in
the same posture TB-1 used — and it is worth firing precisely because a
positive would be the strongest result the project could produce.

## 2. Arms

Same items, same seeds, per-seed `question_id` intersection.

- **(A) `universal_gate`** — TO RUN. Cheap 3-seat panel, escalate every item.
- **(B) flagship 1× solo** — **ALREADY RUN**, no new spend:
  `lever_baseline_supergpqa_seed{7,42,123}.jsonl`.
- **(C) cheap panel, no universal escalation** — **FREE**, derived in-run from
  arm A's own logged `plurality_letter` on unanimous rows and `final_letter` on
  split rows, exactly as `verify_universal_gate.py` already does on GPQA. This
  gives the *within-architecture* delta at zero additional cost.

Arm C matters: it separates "the architecture beats a flagship call" (A vs B)
from "universal escalation beats the shipped rule" (A vs C), which are
different claims and were conflated once already this session.

## 3. Staged firing — screen first

**Stage 1 (screen): seed 7 only.** ~1.35M tokens.
**Stage 2 (extension): seeds 42 and 123**, ~2.7M, fired **only if** the screen
does not trigger the kill below.

Staging is not caution theatre: at the measured 24.0 escalations per net item,
a full 3-seed run that lands where the headroom analysis predicts would spend
~4M tokens to confirm a number already implied by a committed document.

## 4. Command

```bash
python -m benchmark.lever_experiments --lever universal_gate \
  --dataset supergpqa --n 90 --seed 7 --concurrency 3 \
  --out benchmark/results/TB1B_universal_gate_supergpqa_seed7.jsonl
```

Every flag verified present in `benchmark/lever_experiments.py`'s argparse
block; `universal_gate` and `supergpqa` are both in its `choices`.

**On seed reuse:** seeds 7/42/123 are in `BURNED_SEEDS`, which is scoped
**only** to S7 selector-shipping (`assert_seeds_not_burned` is called solely on
the `--ship-gate` path, and its own docstring says plain scoring on a burned
seed stays legitimate). Reusing them here is *required*, not permitted: arm B
already exists at exactly these seeds, and pairing is the entire design. Same
pattern as `chemistry_matched_baselines` at seeds 217/471.

## 5. Bar and analysis

**PRIMARY (A vs B): pooled exact one-sided McNemar over the fired seeds,
p < 0.05 with net ≥ +5.** Pooling sums per-seed 2×2 tables; items are never
re-joined across seeds. SuperGPQA seeds are near-disjoint (measured: 2 shared
items of 88 between seeds 7 and 123), so pooling is sound here in a way it is
not on GPQA.

**SECONDARY (A vs C), reported always, never alone:** the within-architecture
delta. Labelled as a different claim from the primary.

**Analysis set:** per seed, S = A ∩ B on `question_id`. **Gate |S| ≥ 81** (90%
of the intended 90), measured against the intended 90, not against either arm's
row count. Unparseable answers count **wrong**, never dropped.

## 6. Kill clauses (kill dominates the bar)

1. **Screen kill:** if seed 7 lands **net ≤ 0** against arm B, do **not** fire
   the extension. The thesis fails on its most favourable surface and 2.7M is
   not spent confirming it.
2. **Cost kill:** if `universal_gate` costs > 4× the flagship's measured
   tok/item and its net is not ≥ +5, report it as **dominated** and say so in
   those words — the GPQA framing, applied consistently.
3. **>9 item drops (10%) voids that seed** for every arm.

## 7. Token cost

Measured basis: `universal_gate` on GPQA = **13,541 tok/item** (recomputed from
seed 1001). SuperGPQA items are longer, so budget **~15,000 tok/item**.

| stage | seeds | items | tokens |
|---|---|---:|---:|
| screen | 7 | 90 | **~1.35M** |
| extension | 42, 123 | 180 | ~2.70M |
| | | | **~4.05M if fully fired** |

Arms B and C cost **zero** — B exists, C is derived.

## 8. What we learn either way

- **A > B** — the strongest result this project could produce: the cheap-seat
  architecture beats the family's best single call on shared items, paired.
  It would also localise *when* the architecture pays (headroom), turning
  TB-1's GPQA null from a refutation into a boundary condition.
- **A ≈ B** — the architecture reaches flagship parity on both surfaces and
  beats it on neither. Combined with TB-1 that is a clean, general negative:
  scaffolding recovers what cheap seats give up and stops there, regardless of
  headroom.
- **A < B** — worse than the GPQA null, and the measured 9.5% conversion rate
  would be the explanation.

## 9. Out of scope

- `qwen3.8-max-preview` (unrunnable without survivorship bias, per D0).
- Any cross-lab comparison.
- Re-cutting by subject after a null — named here so it cannot be proposed
  later as a fresh idea.
