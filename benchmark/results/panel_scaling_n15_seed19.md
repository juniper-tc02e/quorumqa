# Merged N=15 odd-N harvest (PS-1 + PS-2), seed 19 — a clean null

**Measured 2026-07-31.** `docs/experiment-spec-book.md` §2's pre-registered
S1/S2 specs, fired as the "merged N=15 harvest" (§6.2 item 3 of the spec-book
firing order): `diversified_panel` (independent random choice-permutation per
seat) and `cycled_panel` (deterministic seat-index → procedure/temperature
cycling), both on SuperGPQA-hard, seed 19 (fresh, unburned, confirmed against
`benchmark/data/seed_registry.json`), `--n-solvers 15 --no-tribunal`. Two paid
runs (5.42M budgeted); every intermediate odd N (3,5,7,9,11,13) is then derived
**offline, free**, from the 15 logged seat answers per item — the entire point
of the harvest design.

Reproduce: `python -m benchmark.analyze_panel_scaling benchmark/results/lever_diversified_panel_supergpqa_seed19.jsonl`
(and the same for `lever_cycled_panel_supergpqa_seed19.jsonl`).

---

## 0. A false alarm caught before it became a finding

The first live result (`diversified_panel`, 47.1% at N=15) looked like a severe
degradation against the N=3 cheap control's historical range on this same
dataset (63.6–74.4% across seeds 123/271/606/7/838). Rather than publish that
comparison, the same 15-seat log was used to derive N=3 on **the identical 87
items** — 47.1%, not 63.6–74.4%. The gap was never an N-scaling effect; seed 19
is simply a harder item sample than the seeds used for the earlier control
runs. Cross-seed accuracy comparisons on GPQA/SuperGPQA are never valid without
pairing on shared items — the same lesson this repo has already learned twice
this session (the D0 bar, the flagship claim) — and this is the third time
checking before publishing caught it before it happened.

---

## 1. S1 — does any panel size beat N=3?

| N | diversified acc | diversified coverage | cycled acc | cycled coverage |
|---|---|---|---|---|
| 3 | 47.1% | 71.3% | 47.1% | 64.4% |
| 5 | 48.3% | 78.2% | 46.0% | 72.4% |
| 7 | 48.3% | 81.6% | 43.7% | 74.7% |
| 9 | 50.6% | 86.2% | 49.4% | 75.9% |
| 11 | 46.0% | 89.7% | 47.1% | 77.0% |
| 13 | 47.1% | 90.8% | 47.1% | 78.2% |
| 15 | 47.1% | 90.8% | 48.3% | 79.3% |

**Plurality accuracy is flat within noise from N=3 to N=15 in both arms.**
Paired against the N=3 baseline (diversified arm), the best net is **+3 items**
(N=9), against the pre-registered bar of **+5**. **S1 does not clear.**

**Coverage climbs steadily and substantially** — 71.3%→90.8% (diversified),
64.4%→79.3% (cycled) — while accuracy does not move. This is the same
"coverage, not selection, is the bottleneck" pattern already recorded elsewhere
in this repo (the stronger-judge null: 9/9 overturns correct, zero net gain),
now visible directly in an odd-N sweep: more solvers make it steadily more
likely that *someone* says the right answer, and the plurality rule captures
almost none of that gain.

## 2. S2 — does the permutation scheme matter?

Paired at each N, diversified vs cycled, same items:

| N | net (diversified − cycled) | p (one-sided) |
|---|---|---|
| 3 | −1 | 0.661 |
| 5 | +2 | 0.416 |
| 7 | +4 | 0.252 |
| 9 | +1 | 0.500 |
| 11 | −1 | 0.696 |
| 13 | 0 | 0.593 |
| 15 | −1 | 0.710 |

**No N shows a significant difference.** Independent random permutation per
seat and deterministic seat-index cycling produce statistically
indistinguishable plurality accuracy at every panel size tested. Per
spec-book §2's own decision rule ("S2 is the spec that settles the record: if
diversified minus cycled is < 3..."), **the record is settled**: the specific
scheme for assigning procedures/temperatures across a large panel does not
matter here. Whatever headroom panel scaling might have, it is not unlocked or
blocked by this choice.

## 3. Reading this alongside today's compute-matched result

This null and `benchmark/verify_compute_matched_control.py`'s result are the
same finding from two directions. The compute-matched control showed
`flagship_panel`'s advantage over 1× is carried by **self-consistency
sampling**, not the tribunal. This harvest shows that on SuperGPQA-hard,
scaling the **sampling** itself — from 3 to 15 same-family cheap solvers, with
either permutation scheme — buys **coverage without buying accuracy**. Put
together: more samples from one model family increase the odds the right
answer is *said*, but neither more samples nor a tribunal reliably improves
whether the *right one is picked*. Selection is the shared bottleneck in both
results.

## 4. Honest limits

- **Single seed.** This is one 87-item sample; the spec-book's own firing order
  budgets a single-seed screen at this stage. Extending to additional seeds is
  unfunded this window.
- **SuperGPQA-hard specific.** The unanimous-gate finding
  (`unanimous_gate_headroom.md`) already showed GPQA and SuperGPQA-hard behave
  very differently for related mechanisms (4.2 vs 24.0 escalations per net
  item); this null should not be assumed to transfer to GPQA without checking.
- **Escalation-policy sweep (S3) run for free alongside this** (same offline
  derivation) shows no threshold/policy combination materially changes the
  picture at this seed — full table in the reproduce output, not reproduced
  here for space.
- **3/90 items dropped in both arms**, same drop pattern (`272df86d` dropped in
  both) — consistent with the chronic-timeout item class already documented
  elsewhere in this repo, not a new failure mode.
