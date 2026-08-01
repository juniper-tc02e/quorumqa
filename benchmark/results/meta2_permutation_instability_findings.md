# META-2 — permutation instability is NOT a wrongness signal: KILL, pooled 3-seed

**Measured 2026-08-01.** `docs/experiment-spec-book.md`'s META-2 — described in
its own spec as *"the single load-bearing unmeasured number in the record: 61.6%
of all wrong rows are unanimous and no logged feature can see them"* — fired
for the first time. `permuted_panel` had been built and offline-tested for
weeks (`tests/test_lever_permuted_panel_offline.py`) with **zero** result
files ever produced from it. This closes that gap.

Independently re-derived from the three raw seed files directly (not just
re-reading `benchmark/analyze_unanimous_stability.py`'s own printed output):
every number below matches exactly.

Reproduce:
```
.venv/Scripts/python.exe -m benchmark.analyze_unanimous_stability \
    --control benchmark/results/META2_control_supergpqa_seed909.jsonl benchmark/results/META2_control_supergpqa_seed1313.jsonl benchmark/results/META2_control_supergpqa_seed2027.jsonl \
    --permuted benchmark/results/META2_permuted_panel_supergpqa_seed909.jsonl benchmark/results/META2_permuted_panel_supergpqa_seed1313.jsonl benchmark/results/META2_permuted_panel_supergpqa_seed2027.jsonl
```

---

## 1. What ran

Staged per the spec: screen seed **909** (arms A/`control` + B/`permuted_panel`,
90 items each), then — since the screen's coverage gate cleared decisively —
the 2-seed extension at **1313** and **2027**, same two arms, SuperGPQA-hard,
concurrency 3. All three seeds admissible (drops 0–3 of 90 per arm, well under
the 10% re-run threshold). Arm C (resample-only control, the mechanism
decomposition) was **not fired** — see §5.

## 2. The coverage gate — clears easily

| Seed | control-unanimous | flipped | flip rate |
|---|---|---|---|
| 909 (screen) | 41 | 18 | 43.9% |
| 1313 + 2027 (extension) | 98 | 41 | 41.8% |
| **Pooled (3 seeds)** | **139** | **59** | **42.4%** |

Required to authorise the extension: **≥10%**. Observed: **42.4%** — over
4x the floor. Nearly half of every panel this project has been calling
"unanimous" does not survive an independently-shuffled choice order per seat,
with each seat's own letter mapped back to canonical before voting (the task
itself is unchanged by construction). **The panel's own "unanimous" label is
far less robust than its name implies.**

## 3. The load-bearing question — KILLED

Coverage tells you flips happen often; it says nothing about whether a flip
means the panel was WRONG. That is the actual claim META-2 exists to test,
and it needs the full pooled 3-seed sample to have any power (~139 unanimous
items observed, matching the spec's own ~140-pooled power estimate almost
exactly).

| | unanimous & wrong | unanimous & right |
|---|---|---|
| n | 40 | 99 |
| flipped | 19 | 40 |
| flip rate | 47.5% | 40.4% |

**Contrast: +7.1pp. Fisher exact p = 0.4552.**

Pre-registered bar to confirm the signal: contrast ≥ **25pp**, p < **0.05**,
≥ **8** flipped items total. Observed contrast is **3.5x too small**, and the
p-value is **9x** the significance threshold. The bar does not merely fail to
clear — it isn't close.

**Pre-registered kill clause: "Contrast gap < 10pt or p > 0.2 → permutation
instability is NOT a wrongness signal."** Both disjuncts fire independently
(7.1pp < 10pt; p=0.455 > 0.2). **Formal verdict: KILL.**

This screen-stage read at seed 909 alone (+10.0pp, p=0.75, also a kill) already
pointed this direction; the pooled 3-seed figure is not a reversal, it is
confirmation at the power the bar was actually designed to test at.

## 4. What this retires

Per the spec's own pre-registered consequence of this exact kill:

- **Do not build the paraphrase arm** (SCI-1's restatement-based instability
  probe was designed as a parallel/merged test of the same underlying idea —
  restating the question instead of permuting choice order — and shares this
  kill's implication).
- **Do not build an instability-fed router.** Flip status cannot be used as a
  wrongness-detection feature for routing, gating, or escalation.
- **The unanimous-wrong floor is irreducible by cheap perturbation.** Neither
  choice-order permutation (this result) nor answer instability under
  resampling (the earlier "clean kill" in `docs/improvement-loop-state.md`'s
  FREE SPRINT #2 — permutation-holding-replicate-count-fixed showed the
  observed lift lands on the null mean) can see inside the 61.6%-unanimous
  slice of wrong answers.
- **META-1 is also finished by this result**, per the spec's own explicit
  statement: *"if neither logged features (META-1) nor instability (META-2)
  can see inside the unanimous pool, the calibration thesis is dead and
  effort moves to knowledge injection."* Three independent mechanisms —
  logged features (META-1), resampling instability (the earlier clean kill),
  and now permutation instability (META-2) — have all failed to find any
  signal inside the unanimous-wrong pool. Nothing about generation-time
  metadata predicts whether a confident, unanimous panel is actually right.

## 5. Why arm C (mechanism decomposition) was not fired

The spec's own design makes arm C's purpose explicit: separate "unanimity
breaks because of permutation specifically" from "unanimity breaks because of
plain decoder resampling." That question only has practical value if flipping
predicts wrongness — attributing a *mechanism* to a phenomenon already shown
to carry *no signal* is not worth the ~0.95M-token spend. This is the same
"no further spend on a dead branch" discipline already applied elsewhere this
session (MATH-4 dropped once its answer was already implied; S2 settled once
its own decision rule triggered). If the calibration thesis is ever revived
via a genuinely new observation mechanism (not a re-reading of existing
generation metadata — see §6), re-testing whether THAT mechanism's noise is
permutation-specific would be the moment to fund arm C, not before.

## 6. How this connects to the rest of the repo

This is the fourth independent line of evidence this session pointing at the
same wall: confidence-based selection failed out-of-sample (S7, net -4,
sign-reversed); coverage climbs while plurality accuracy stays flat across
panel sizes (Tier D panel-scaling); the compute-matched control showed
whole-panel gains are carried by self-consistency sampling, not judgment
(verify_compute_matched_control.py); and now, permutation instability — despite
being remarkably COMMON (42.4% of "unanimous" panels aren't robust to it) —
carries zero wrongness signal. Every tested mechanism that reads *existing*
model output (confidence, resampling, permutation, reasoning length) has
failed to find the wrong answers hiding inside a confident-looking panel.
Selection is not merely under-exploited by this project's tooling; on the
evidence gathered so far, it may not be reachable by any technique that only
re-reads what the model already said. The `docs/orchestration-contract.md`
design (Program 1) already anticipated this direction — its typed verification
grades (H/E/X/R/S/N) assume genuinely NEW observations (tool checks,
independent re-solves), not re-weighted metadata, are what any future
selection mechanism needs.

## 7. Honest limits

- **SuperGPQA-hard only.** Not tested on GPQA-Diamond or any other benchmark;
  the 61.6%-unanimous figure and its irreducibility should not be assumed to
  transfer without checking.
- **Cheap tier only, 3-seat panel.** Whether the same instability pattern
  holds at the flagship tier, or at other panel sizes, is untested.
- **3 seeds, not more.** 139 pooled unanimous items is close to the spec's
  own power target, but a wider confidence interval than a larger sample
  would give; the p-value (0.455) is so far from significance that additional
  seeds are very unlikely to change the verdict, and are not planned.
- **Accuracy side-comparison also null** (b=23, c=16, net=+7, p=0.168 —
  does not clear the standard net≥+5-and-p<0.05 bar): `permuted_panel` is not
  measurably more or less accurate than `control` either. Permutation neither
  helps nor hurts accuracy; it just reveals that "unanimous" was doing less
  work than its name suggested.
