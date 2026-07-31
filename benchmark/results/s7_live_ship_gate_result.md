# S7 ship-gate live run — DO NOT SHIP on both shippable selectors (SuperGPQA-hard, seeds 411/523/631)

**Measured 2026-08-01.** `docs/experiment-spec-book.md` §3's S7 spec — *"the
only spec that can ship a selector"* — fired live for the first time, against
three fresh, pre-registered, unburned seeds. Independently re-verified from the
three raw pool files using `benchmark/score_selectors.py`'s own `load_pool`,
`score_pool`, `selector_report`, `ship_gate_verdict` (imported, not
reimplemented): **zero mismatches found** against the committed log and JSON.

Reproduce:
```
.venv/Scripts/python.exe -m benchmark.score_selectors --ship-gate \
    --selector max_single_confidence --pools \
    benchmark/results/pool_supergpqa_cheap_k8_seed411.jsonl \
    benchmark/results/pool_supergpqa_cheap_k8_seed523.jsonl \
    benchmark/results/pool_supergpqa_cheap_k8_seed631.jsonl
```
(swap `--selector confidence_weighted` for the second verdict below). Both
commands now refuse to re-run — see §5.

---

## 1. What ran, and why

Three fresh K=8 pools, SuperGPQA-hard, `cheap` solver tier, n=90 items each
(270 pooled), at seeds **411 / 523 / 631** — the exact triple pre-registered in
`benchmark/data/seed_registry.json`'s `selection_pools` / `SEL-7` block, which
itself matches `score_selectors.py`'s own S7 CLI example. Each pool logs 8
independently sampled candidate answers per item with letter, confidence, and
reasoning, generated fresh via `run_pool.py` (`benchmark/results/s7_live_run.log`)
with no reuse of any previously-audited seed.

S7 is the only spec in the selector-audit family that can ship a selector: S1's
in-sample selector bake-off scores a candidate against the same pool it was
picked on, which is exactly the fitting risk a ship decision cannot tolerate.
FREE SPRINT #2's S1 audit found what looked like a **"candidate free win"** —
`max_single_confidence` at net +121 overall (p<0.0001) and `confidence_weighted`
at net +49, both clearing the pre-registered bar on GPQA-Diamond and
SuperGPQA-hard — but flagged it explicitly as **"NOT SHIPPABLE YET... S7 is now
promoted to the front of the paid queue"** (`docs/improvement-loop-state.md`,
FREE SPRINT #2 section). That promotion happened once the harness itself had
been through an adversarial pass and passed
(`benchmark/results/s7_harness_adversarial_review.md`, which found and fixed
one gap — pool files not burning themselves after a completed verdict — before
this run was trusted to gate anything). This run is that held-out confirmation.

GPQA-Diamond was not attempted: `score_selectors.py`'s own power analysis
(`minimum_pooled_n_for_audit_effect`) shows GPQA-Diamond needs a pooled n≥600 to
reach the S1 audit's effect size at p<0.05, which the entire 198-question
benchmark cannot supply even across all 3 seeds. SuperGPQA-hard needs only
n≥210 and is reachable at 3×90=270 — the correctly-powered home benchmark, per
the spec-book's own design.

## 2. The verdict: DO NOT SHIP — for both shippable selectors

### 2a. `max_single_confidence` (the stronger S1 candidate, net +76 in-sample on SuperGPQA-hard)

| seed | b | c | net |
|---|---|---|---|
| 411 | 6 | 7 | −1 |
| 523 | 5 | 4 | +1 |
| 631 | 8 | 12 | −4 |

**Pooled: b=19, c=23, net=−4, discordant=42, p=0.7796, n=270.**

| | value |
|---|---|
| Required net | ≥ +5 |
| Observed pooled net | **−4** |
| Pooled McNemar p (one-sided) | 0.7796 (need < 0.05) |
| Observed net rate | −1.4815% (−4 / 270) |
| Original S1 audit rate | +4.1260% (+76 / 1,842) |
| Required replication band (±50%) | [+2.0630%, +6.1889%] |

`>>> DO NOT SHIP` — four independent reasons, each on its own sufficient to
fail the gate: pooled net (−4) is below the required +5; pooled p (0.7796) is
nowhere near significant; the observed rate sits **outside and on the opposite
sign** from the ±50% replication band around the original audit's rate; and two
of the three individual seeds (411, 631) show a negative net, violating the
per-seed non-negativity clause on their own.

This is not "didn't clear the bar" — the effect **inverted**. In-sample, the
selector was the single strongest result in the whole audit (net +76 on
SuperGPQA-hard, +121 pooled overall). Held out, net went **negative** and
flipped sign on two of the three seeds. A selector that looked like a
zero-token free win collapsed to worse-than-plurality on fresh data.

### 2b. `confidence_weighted` (the other shippable S1 candidate, net +25 in-sample on SuperGPQA-hard)

| seed | b | c | net |
|---|---|---|---|
| 411 | 2 | 2 | 0 |
| 523 | 1 | 1 | 0 |
| 631 | 4 | 1 | +3 |

**Pooled: b=7, c=4, net=+3, discordant=11, p=0.2744, n=270.**

`>>> DO NOT SHIP` — three reasons: pooled net (+3) is below the required +5;
pooled discordant count (11) is below the required 12; pooled p (0.2744) is not
significant. (The gate short-circuits before reaching the replication-band or
per-seed checks, since net already fails — all three per-seed nets are
individually non-negative, unlike `max_single_confidence`.)

`confidence_weighted` failed **less catastrophically** than
`max_single_confidence` — a positive but under-powered net rather than a sign
reversal, and no negative seeds — but it still fails the same gate on the same
held-out triple. Both of S1's shippable candidates die here.

## 3. Why this is not a data-quality artifact

An independent corruption and calibration check was run over all 2,160 samples
(270 rows × 8, across the 3 pool files):

- **Structurally clean.** Zero confidence values outside [0,1], zero duplicate
  `sample_index`, only 4 null/empty `letter` (0.2%) and 19 empty `reasoning`
  (0.9%). No corruption.
- **Confidence is coarse but not degenerate.** Only 15 distinct confidence
  values appear at all; the top 5 (0.95, 0.85, 0.90, 0.60, 1.0) cover 91.8% of
  samples (mean 0.858, stdev 0.165). **37/270 rows (13.7%) have all 8 samples
  reporting the identical confidence value**, making `max_single_confidence` a
  pure arbitrary tiebreak on those rows. Median within-row confidence range is
  only 0.10.
- **Calibration direction is real but tiny, and never reverses.** Argmax
  confidence = plurality winner in 216/270 rows (80.0%); mean confidence when
  it agrees (0.940) vs disagrees (0.935) — delta +0.005, near noise. Argmax =
  gold in 162/270 (60.0%); mean confidence 0.947 vs 0.927 — delta +0.020, and
  this direction holds on every individual seed file (411: +0.015, 523:
  +0.011, 631: +0.035). At the full-sample level the gap is a bit larger:
  samples matching plurality average 0.868 vs 0.825 (+0.043); matching gold
  0.881 vs 0.830 (+0.051).

Because argmax already reproduces the plurality vote 80% of the time, a
confidence-based selector is mostly just re-deriving the plurality answer; the
remaining 20% of disagreements add roughly as much noise as signal. The
57.78–65.56% (mean 61.5%) spread in raw plurality accuracy across the three
seeds was checked separately and is **ordinary binomial sampling noise**: at
n≈90, p≈0.6, the expected SE is ≈5.2pp, so a 7.78pp 3-seed range is almost
exactly the textbook-expected spread (≈8.8pp), all three seeds sit within
~1.1 SE of the mean, and this is *narrower* than other n≈90 SuperGPQA-hard
plurality figures already logged in this repo (the
`lever_control_supergpqa_seed{123,271,606,7,838}.jsonl` control spans
44.94–56.67%, an 11.7pp spread on the same benchmark/n). **Conclusion: the
signal is real but coarse and weak, and the pools show no distributional
anomaly** — this reads as a genuine generalization failure, not a pipeline bug
or an unlucky sample.

## 4. How this connects to the rest of the repo

This closes, rather than opens, a question the compute-matched control and
panel-scaling results left dangling. The compute-matched control showed
`flagship_panel`'s gain is carried by self-consistency sampling, not the
tribunal's judgment — majority vote over resampled candidates does the work,
not deliberate selection. Panel-scaling made this concrete: coverage climbs
from 71% to 91% (N=3 to 15) while plurality accuracy stays flat, meaning the
panel keeps surfacing the right answer without ever reliably picking it. Both
findings point at the same gap: a real, sizeable oracle headroom (12–24pp) that
no tested selection mechanism, plurality or tribunal, captures.

`max_single_confidence` looked like the exception — a cheap, zero-token
selector that appeared to crack part of that gap in-sample (net +76, ~28% of
SuperGPQA-hard's oracle headroom). S7's out-of-sample result (net −4, sign
reversal, n=270) removes the exception. This is not a separate finding; it
sharpens "selection is genuinely hard" into something more specific: not just
"cheap selectors haven't found the trick yet," but "the one selector that
seemed to have found it was fitting noise." It also reconciles backward with
W5's own AUC-0.625 skepticism about verbalized confidence, which the in-sample
audit had appeared to override — held out, it didn't.

Confidence-based selection over already-computed outputs is a dead end here on
SuperGPQA-hard. What panel-scaling and the earlier instability "clean kill"
both point to as the live alternative: selection needs genuinely new
information — an independent re-observation or verification pass — not a
re-reading of existing generation metadata, which is what confidence,
reasoning length, and instability all turned out to be.

## 5. What this retires

- **The "candidate free win" framing from FREE SPRINT #2 is dead.** Both S1
  shippable selectors — `max_single_confidence` and `confidence_weighted` —
  fail the S7 ship gate on held-out SuperGPQA-hard data. Confidence-based
  selection, in either variant tested, does not generalize past the pools it
  was fitted on.
- **No further `--ship-gate` attempt is possible on these three seeds.** The
  harness's own consumption guard burned them the moment this run reached a
  verdict: `benchmark/results/s7_shipgate_consumed_seed{411,523,631}.jsonl` now
  exist, each a single-line JSON record naming
  `seed`/`selector`/`benchmark`/`verdict`. Re-verification confirmed
  `assert_seeds_not_burned([411, 523, 631])` raises `ValueError` with a message
  containing `"burned"` against the default `results_dir`. Re-running either
  selector against these pools, or trying a third selector on them, is refused
  by design — the exact peeking S7 exists to prevent.
- **Reopening selection here needs a different mechanism, not a re-tuned
  heuristic.** Re-weighting confidence, reasoning length, or instability — all
  read *existing* generation metadata — has now been tried and killed in three
  independent ways (this result, the instability clean kill, W5's AUC
  finding). Any future attempt at this oracle headroom needs a genuinely new
  observation (e.g. an independent verification/re-solve pass), on freshly
  drawn seeds, not another selector fit on already-logged pools.

## 6. Honest limits

1. **Single held-out triple, not repeated.** This is one 3-seed confirmation
   run, matching the spec-book's own single-screen firing order at this stage.
   A second independent triple would strengthen "genuine generalization
   failure" into something with replication, but none is available — these
   three seeds are now burned, and a fresh triple would need new pre-registered
   seeds and paid tokens.
2. **SuperGPQA-hard only.** GPQA-Diamond was not attempted here, and the
   harness's own power analysis rules it out as underpowered at this pool size
   (needs pooled n≥600 against a 198-question benchmark ceiling); this result
   says nothing about whether confidence-based selection would generalize
   differently on GPQA-Diamond.
3. **Cheap solver tier only.** All 8 candidates per item come from the cheap
   tier; no claim is made about whether a stronger or more diverse solver mix
   would change the confidence-selection picture.
4. **`longest_reasoning` not re-examined here.** It was never a ship candidate
   in the S1 audit (net −314 overall, a junk control) and was not re-tested
   against these held-out pools — there was no reference net to hold it to and
   no reason to spend on it.
5. **Pooled provenance.** The pooled b/c/net/p figures above aggregate across
   three seeds; the per-seed table is the paired evidence, and it is what
   drives the per-seed non-negativity failure for `max_single_confidence`.
