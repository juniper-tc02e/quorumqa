# MATH-1 — AIME liveness screen, seed 101 — retired INADMISSIBLE

**Closed 2026-08-01.** `docs/experiment-spec-book.md`'s MATH-1 spec, fired for
the first time. Pre-registered analysis: `benchmark/verify_aime_liveness_screen.py`
(committed before any live data existed). **Formal verdict: neither ALIVE nor
KILL — the run never reaches admissibility, and per the spec's own rule
("if the log shows any drop, the run's numbers are never analysed") no
accuracy or gap figure from this run may be quoted anywhere.**

Reproduce the failure: `python -m benchmark.verify_aime_liveness_screen` against
the committed `aime_open_baseline_seed101.jsonl` (53/60 rows) raises
`AssertionError: INADMISSIBLE`, by design.

---

## 1. What happened

The cheap arm (`aime_open_sc_cheap_seed101.jsonl`, self-consistency n=1,
margin=1, collapsing to one flash call) completed cleanly: **60/60**. The
flagship baseline arm dropped **8/60** items to Aliyun ReadTimeouts at
concurrency 3.

Two retry passes followed, both against `benchmark/retry_aime_baseline.py`
(built for this run — `run_math_open.py` had no retry-missing path for the
baseline arm):

| Pass | Timeout | Max attempts/item | Recovered | Still failing |
|---|---|---|---|---|
| Original run | 300s (default) | 4 | 52/60 (8 dropped) | 8 |
| Retry 1 | 300s | 4 | +1 (53/60) | 7 |
| Retry 2 | **900s** | 2 | +0 (53/60) | 7 |

**53/60 is where this stops.** Every one of the 7 remaining items has now
failed 10 total attempts (4 + 4 + 2) across three passes, two different
timeout budgets, with zero successes.

## 2. The mechanism — and why raising the timeout was a real, not naive, thing to try

Passes 1 and the original run failed with a client-side `ReadTimeout`: no
response arrived within the 300s window at all. That is a genuinely
different failure signature from the D0 GPQA bar repair's drops (a
fast-returning server-side `504 Gateway Timeout`) — a longer client timeout
is a real fix for a slow-but-eventually-successful generation, and a
no-op for a server that has already given up. Distinguishing the two
required actually raising the timeout and watching what came back, not
assuming.

**Retry 2 (900s) answered the question.** Every one of the 7 items failed
in ~5 minutes — the *same* ~300s mark as before — but now with an explicit
`HTTPError: 504 Server Error: Gateway Timeout ... token-plan.ap-southeast-1.maas.aliyuncs.com`.
The client was willing to wait up to 900s; Aliyun's own infrastructure
gave up first, every time, at what looks like its own internal ~300s
ceiling. **Raising the client-side timeout cannot fix a server-side
timeout that fires before the client's window closes.** This is
mechanistically the same class of failure D0 already documented
(`benchmark/results/qwen38_bar_repair_preregistration.md`'s "Result"
section) — now confirmed, not merely suspected, for these 7 specific AIME
items, and confirmed as a *general* finding: for this failure signature
specifically, retrying with a longer client timeout is not worth
attempting again anywhere else in this repo. It won't help.

## 3. Why this cannot be worked around by re-seeding

MATH-1's admissibility rule says "any drop... re-run." For most specs in
this repo, a fresh seed changes which items are sampled, so a re-run can
plausibly dodge a bad-luck drop. **MATH-1 is different: n=60 is the FULL
AIME 2024+2025 population** (`load_aime.py`'s `load_aime_set` shuffles
*order* but includes all 60 items whenever `n=60`), so **every seed —
101, 202, 303 — draws the identical 60 items.** The 7 chronically-failing
items (`aime2025-13`, `aime2024-2024-II-15`, `aime2024-2024-I-11`,
`aime2024-2024-I-12`, `aime2025-27`, `aime2025-14`, `aime2025-12`) will be
present in every future attempt at this design, regardless of seed. The
spec's own "re-run" escape hatch is, in practice, unreachable for a
chronic per-item drop on a full-population design — worth recording so a
future re-run isn't attempted under the mistaken belief that a different
seed would help.

## 4. What is NOT concluded here

The 53-item survivor split (baseline 100%, cheap ~62%, from the original
run's log) is **not reported as a finding** anywhere in this document,
deliberately. Those 7 items are very plausibly among the longest/hardest
in the set (competition problems whose flagship-tier reasoning traces run
long enough to hit a ~300s server-side generation ceiling) — exactly the
survivorship-bias trap this repo has already learned to distrust twice
this session (the D0 GPQA bar, the flagship claim). Reporting any accuracy
number from the 53 survivors would silently bias toward the easier
majority of the population on precisely the axis (problem difficulty /
required reasoning length) that determines whether a cheap-to-flagship gap
exists at all — the entire question MATH-1 exists to answer.

## 5. Paths forward (not taken here — each needs its own pre-registration)

- **A stricter `max_tokens` forcing shorter flagship generation.** D0's own
  writeup suggested this as the only lever left for this failure class.
  Changes what the "flagship baseline" arm means (a capped generation is a
  methodologically different arm from an uncapped one) — a new spec, not a
  patch to this one.
- **Accept n=53 with an imputation-interval treatment**, matching D0's
  all-wrong/all-right bounds. MATH-1's own bar explicitly forbids this
  ("the run's numbers are never analysed" on any drop) — stricter than
  D0's GPQA bar, which does have an interval fallback. Loosening MATH-1 to
  allow an interval would itself need to be pre-registered, not decided
  after seeing that this is where the data landed.
- **Retry a third time at the same or a longer timeout.** Not recommended
  by this document: 10 consecutive attempts across two timeout budgets
  (300s and 900s) with a confirmed server-side cause and zero successes is
  strong evidence this is deterministic, not stochastic, for these 7
  items. A third identical attempt is very unlikely to add information.

## 6. Reproducibility

```
python -m benchmark.run_math_open --dataset aime --n 60 --seed 101 --mode sc \
    --sc-n 1 --sc-margin 1 --solver-tier cheap --concurrency 3
python -m benchmark.retry_aime_baseline benchmark/results/aime_open_baseline_seed101.jsonl --n 60 --seed 101
python -m benchmark.retry_aime_baseline benchmark/results/aime_open_baseline_seed101.jsonl --n 60 --seed 101 --timeout 900 --max-attempts 2
python -m benchmark.verify_aime_liveness_screen   # raises AssertionError: INADMISSIBLE, by design
```

Full logs: `aime_liveness_screen_seed101.log`, `aime_baseline_retry_seed101.log`,
`aime_baseline_retry900_seed101.log`.
