# MoO M1 corrected router: the calibrated fix, scored offline

Follow-up to `moo_m1_findings.md` (the honest negative: the R1 heuristic
router lost to flat-best flagship_panel, -2.7pts and costlier, because its
hard-STEM rules wrongly avoided flagship_panel). This doc corrects the
router per that diagnosis and re-scores it **entirely offline** against the
already-recorded `moo_m1_eval.jsonl` data (120 questions x 7 profiles) --
**zero new paid API calls** for everything below except the optional live
confirmation discussed at the end (not run; see "What wasn't done").

## 1. The calibration table (measured, from existing data)

Built by `benchmark/build_moo_calibration.py` from `moo_m1_eval.jsonl`'s
own recorded outcomes, grouped by (profile, router-bucket) -- the router's
own `_domain_bucket()` classification, not the coarser workload-bucket
label, so the table is keyed exactly the way the router looks things up.
Saved as `benchmark/results/moo_calibration_table.csv` (42 rows); loader:
`quorumqa.engine.calibration.load_calibration_table`.

The two buckets this correction touches (full accuracy/tokens/escalation
table, all 7 profiles, sorted by measured accuracy):

**supergpqa_hard_stem** (n=26-30/profile -- robust sample):

| profile | n | accuracy | mean tokens | escalation |
|---|---|---|---|---|
| flagship_panel | 26 | **84.6%** | **9553** | 7.7% |
| single-call | 29 | 79.3% | 4106 | 0.0% |
| stem-max | 28 | 75.0% | 16094 | 78.6% |
| rag_presolve | 30 | 73.3% | 12515 | 43.3% |
| rag_thinking_gate | 30 | 73.3% | 17719 | 63.3% |
| thinking_gate | 30 | 73.3% | 15882 | 73.3% |
| standard-tribunal | 30 | 56.7% | 10727 | 63.3% |

flagship_panel is BOTH the accuracy winner (+7.9pt over the next-best
deliberation stack) AND the cost winner among the accurate tier (nearly
half rag_thinking_gate's tokens) -- because it barely escalates (7.7%)
while the "cheap" stacks escalate 63-79% of the time into a full tribunal.
This is the exact mechanism `moo_m1_findings.md` diagnosed, now measured
directly rather than inferred.

**gpqa_hard_stem** (n=4-5/profile -- **thin, not independently trusted**):

| profile | n | accuracy | mean tokens | escalation |
|---|---|---|---|---|
| rag_presolve | 5 | 100.0% | 9608 | 0.0% |
| rag_thinking_gate | 5 | 100.0% | 15773 | 40.0% |
| single-call | 5 | 100.0% | 3804 | 0.0% |
| standard-tribunal | 5 | 100.0% | 6342 | 0.0% |
| stem-max | 4 | 100.0% | 8238 | 0.0% |
| flagship_panel | 5 | 80.0% | 12153 | 40.0% |
| thinking_gate | 5 | 80.0% | 18053 | 20.0% |

n=4-5 per cell means every number here is +/-20pts of sampling noise (one
flipped answer). This table is reported for completeness but NOT used to
drive the gpqa_hard_stem rule below -- see that rule's rationale.

Full 42-row table (all 6 router buckets x up to 7 profiles) is in
`moo_calibration_table.csv`; `medicine` and `saturated_easy` and
`gpqa_organic_chem` and `unknown` are unchanged by this correction (see
section 3).

## 2. The corrected router

`src/quorumqa/engine/router.py`, `_profile_for_bucket()`:

- **`gpqa_hard_stem`** (GPQA physics/chem-hard, excluding Organic
  Chemistry): `cheap` -> `single-call`; `balanced`/`quality` -> cost-aware
  tie-break over `{flagship_panel, thinking_gate, single-call}`
  (RAG excluded by the standing GPQA contamination tripwire, stem-max
  excluded as redundant with thinking_gate here), falling back to
  `flagship_panel` since this bucket's own calibration sample is too thin
  (n=4-5, below the tie-break's `min_n=10` guard) to trust standalone. The
  fallback is grounded in the coarser `gpqa_hard` workload-bucket evidence
  `moo_m1_findings.md` already reported (flagship_panel 93%@12248 vs the
  OLD stem-max pick's 85%@14426) plus consistency with the robust
  supergpqa_hard_stem fix below -- flagged explicitly as a thin-evidence
  call, not an independently robust one.
- **`supergpqa_hard_stem`**: `cheap` -> `single-call`; `balanced`/`quality`
  -> cost-aware tie-break over `{flagship_panel, rag_thinking_gate,
  thinking_gate, single-call}`. This bucket's n=26-30 sample clears the
  tie-break's min_n guard, so the pick is a **live calibration-driven
  decision**, not a fallback: it resolves to `flagship_panel` because
  nothing else is within 1pt of its measured 84.6% accuracy.
- **`medicine`, `saturated_easy`, `gpqa_organic_chem`, `unknown`**:
  **unchanged**. The same calibration table confirms these were already
  correct -- `medicine` ties 96.7% across every profile from 1072 to
  4923 tokens (standard-tribunal at 1683 tok is the deliberate
  balanced/quality pick, single-call at cheap); `saturated_easy` ties
  96.6-96.7% from 919 to 5704 tokens (single-call always wins). No
  code change needed there; item (b) of the task ("easy/competent ->
  single-call/standard-tribunal, ties accuracy at 1/4-1/2 cost") was
  already implemented correctly by the original M1 router.

**The cost-aware tie-break** (`quorumqa.engine.calibration.
cheapest_within_margin`, wired via `router._cost_aware_hard_stem_pick`):
among candidate profiles with a calibration entry for the bucket carrying
at least `min_n=10` measured questions, keep whichever are within
`margin=0.01` (1 accuracy point) of the best measured accuracy, then
return the cheapest of that tied set by measured mean tokens. Returns
`None` (triggering the hardcoded fallback) when no candidate clears
`min_n` -- this is what happens for `gpqa_hard_stem` today. 13 offline
tests (`tests/test_calibration.py`) plus 8 router-level tests
(`tests/test_router.py`) prove the wiring is real (monkeypatched fake
tables flip the routing decision) and not a decorative comment.

All rule changes are cited inline in `ROUTING_RULES`' `finding` fields
and the module docstring, per the plan's "every design choice cites the
measured finding that motivates it" discipline.

## 3. The offline re-score (target metric)

`benchmark/rescore_moo_router.py`: recomputes `route()` for all 120
questions from the ORIGINAL eval's recorded `(question_id, subject)`
metadata (a pure, zero-cost function call), looks up each routed profile's
ALREADY-RECORDED correct/tokens from `moo_m1_eval.jsonl`, and reuses
`run_moo_eval.analyze()` unchanged -- same apples-to-apples n=111-of-120
discipline as the original M1 report, so these numbers are directly
comparable to `moo_m1_findings.md`'s.

| | Accuracy | Cost (tok/q) |
|---|---|---|
| flat-best (flagship_panel / thinking_gate tie) | **92.8%** | 6625 / 9040 |
| OLD ROUTED (R1 heuristic, moo_m1_findings.md) | 90.1% | 7826 |
| **CORRECTED ROUTED** | **91.0%** | **6208** |
| oracle (per-question best) | 96.4% | -- |

- **Corrected router vs OLD router: +0.9pt accuracy, 20.7% cheaper.** A
  clean, unambiguous improvement on both axes -- the fix works.
- **Corrected router vs flat-best (flagship_panel, 6625 tok): -1.8pt
  accuracy, 6.3% cheaper.** Not a clean tie. The corrected router comes
  within 1.8pt of flat-best while costing meaningfully less, but does
  **not** fully close the gap on this exact 120-question sample.

Per-bucket (n_common, apples-to-apples):

| bucket | flat-best (this bucket) | routed (corrected) | verdict |
|---|---|---|---|
| supergpqa_hard | flagship_panel 84.0% | **flagship_panel 84.0%** (25/25 picks) | **fix confirmed: ties the bucket's own best, at flagship_panel's cost -- exactly the diagnosed mechanism working** |
| medqa | all profiles tie 96.7% | standard-tribunal 96.7% | unchanged, still correct (½ cost of flagship) |
| saturated_easy_mmlu | thinking_gate/stem-max/flagship_panel/rag_* tie 96.6% | single-call 96.6% | unchanged, still correct (¼-⅙ cost) |
| gpqa_hard | thinking_gate 100.0% | 85.2% (stem-max:14, thinking_gate:9, flagship_panel:4) | **shortfall -- see below** |

### Where the residual 1.8pt gap comes from

Entirely `gpqa_hard`, entirely in the two sub-buckets this task did NOT
touch:

1. **`gpqa_organic_chem` (14/27 of the bucket, stem-max, unchanged rule):**
   on this specific 14-question draw, stem-max scores only 71.4% (n=14,
   raw) vs thinking_gate's 100% and flagship_panel's 85.7% on the SAME
   subject -- the opposite of stem-max's separately validated **3-seed**
   90.9% mean. This is deliberately **not** touched: a single 14-question
   slice from a blend this eval wasn't designed to isolate cannot
   outweigh a 3-seed, 0.2pt-spread validated result. Flagged honestly,
   not acted on.
2. **`unknown` bucket subjects inside `gpqa_hard`** (Molecular Biology,
   Quantum Mechanics, etc. -- 9/27, routed to thinking_gate per the
   unchanged "unknown" rule): calibration shows thinking_gate at 90.9%
   (n=11) here, vs flagship_panel 100% (n=9) and rag_thinking_gate 100%
   (n=10) -- but n=9-11 on a heterogeneous grab-bag bucket (no shared
   domain identity, that's why it fell through every named rule) is too
   thin and too noisy to act on responsibly, and touching the `unknown`
   rule was outside this task's explicit scope (items 2a/2b/2c above).
   Flagged as a genuine next-candidate, not fixed here.

The hard-STEM fix this task was scoped to make (`gpqa_hard_stem` +
`supergpqa_hard_stem`) performed exactly as diagnosed everywhere it had
data to act on. The residual gap sits entirely in adjacent, unrelated,
thin-sample territory.

## 4. The honest verdict

**Does the corrected router deliver a cost-at-equal-accuracy win?**
Partially, precisely stated:

- **The core M1 diagnosis is validated, not just projected.** flagship_panel
  IS the measured accuracy-and-cost winner on hard STEM where the sample
  is robust (supergpqa_hard_stem, n=26-30): 84.6% @ 9553 tok vs the OLD
  router's rag_thinking_gate pick at 73.3% @ 17719 tok. Routed there, the
  corrected router ties the bucket's own flat-best at flagship_panel's
  (lower) cost -- the exact mechanism the diagnosis predicted, now
  confirmed with real numbers instead of a projection.
- **The corrected router is a clear, unambiguous improvement over the
  shipped R1 router**: +0.9pt accuracy AND 20.7% cheaper. The M1 fix
  works.
- **It does NOT fully tie flat-best accuracy on this 120-question
  sample** (91.0% vs 92.8%, -1.8pt) -- it is a **cost win with a small
  accuracy shortfall**, not a clean cost-at-equal-accuracy win. The
  shortfall is fully attributable to two buckets outside this task's
  scope (organic-chem's noisy 14-question draw, protected by a stronger
  validated finding; the heterogeneous "unknown" bucket's 9-11 question
  draw), not to the hard-STEM rule this task corrected.
- Reported per the plan's honesty discipline: **do not claim the clean
  tie the projection in `moo_m1_findings.md` hoped for; claim exactly
  what was measured** -- a real, validated cost improvement over the
  shipped router, close to but short of flat-best accuracy, with the
  shortfall's source identified and left open rather than papered over.

## 5. Next candidates (not done here, out of scope)

- Revisit the `unknown` bucket's default at "balanced" (currently
  thinking_gate): this data hints flagship_panel or rag_thinking_gate
  may be a better default, but n=9-11 on a heterogeneous bucket is too
  thin to act on without a dedicated, larger, better-isolated eval.
- `gpqa_organic_chem`'s 14-question underperformance this run is very
  likely sampling noise against the 3-seed 90.9% mean validation --
  worth a variance check (another seed) before ever touching that rule,
  not evidence to act on now.
- `_domain_bucket()`'s substring match misses subjects like "Quantum
  Mechanics" and "Molecular Biology" (no "chem"/"physic" substring),
  which is why they fall into `unknown` rather than `gpqa_hard_stem` --
  a real classification gap, unrelated to this task, not fixed here.

## What wasn't done

**No live confirmation run.** The task made this explicitly conditional
("only IF the offline re-score looks promising AND you think a live
confirmation is warranted"). Given the offline result is a genuine but
partial win (cost-favorable, not a clean accuracy tie) and running live
API calls is a real-money spend, this was deferred rather than run
unilaterally -- recommended as an explicit next step (e.g., ~40 questions
across the two hard-STEM buckets at a fresh seed) pending an explicit
go-ahead to spend the budget, rather than assumed.

## Test counts

- `tests/test_calibration.py`: 13 tests (build/write/load round-trip,
  `cheapest_within_margin` tie-break behavior) -- all offline, no live
  calls.
- `tests/test_router.py`: 98 tests (was 89 before this correction; added
  cheap/balanced/quality coverage for both corrected buckets plus 6 new
  tests proving the calibration wiring is real, not decorative).
- Full suite: `328 passed` (`.venv/Scripts/python.exe -m pytest -q`), zero
  live API calls anywhere in the suite.
