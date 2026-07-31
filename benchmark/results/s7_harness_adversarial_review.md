# Adversarial review of the S7 ship-gate harness, before its first live use

**Reviewed 2026-07-31.** `benchmark/score_selectors.py` implements S3/S6/S7
(`docs/experiment-spec-book.md` section 3). No `pool_*.jsonl` file has been
generated yet, so this is a code-only review before the harness is ever
trusted to gate a real SHIP verdict -- not a review of a result. The file had
already been through one adversarial pass (commit `9b82406`, five defects
fixed: a units bug comparing counts across mismatched denominators, an
underpowered-benchmark trap, a duplicate-pool-file exploit, a duplicate-seed
exploit, and one more not re-derived here). This pass looked for what that one
might have missed.

## What was checked and cleared

- **Hardcoded reference constants** (`ORIGINAL_AUDIT_NET`, `ORIGINAL_AUDIT_N`,
  `ORIGINAL_AUDIT_BC`) cross-checked line-by-line against
  `selector_audit.md` section 2's own tables -- all four selector/benchmark
  cells and both denominators match exactly.
- **Rate vs. count units** in the within-50%-replication clause -- correctly
  compares `pooled_net / pooled_n` against `original_net / original_n`, not
  raw counts (this was the commit-`9b82406` fix; re-verified still in place).
- **Power**: `minimum_pooled_n_for_audit_effect` confirms GPQA-Diamond needs
  n>=600 (unreachable: the benchmark only has 198 questions) while
  SuperGPQA-hard needs n>=210 (reachable at 3x90=270) -- matches the docstring
  and is exercised by its own test.
- **Selector tie-breaks** (`sel_max_single_confidence`,
  `sel_longest_reasoning` favor the first sample on an exact tie;
  `sel_plurality`/`sel_confidence_weighted` favor the first-seen letter) --
  same first-index bias already known and accepted for the shipped engine's
  own `_plurality()`, not a new defect.
- **Row-scoped gold matching** -- `score_row_at_k` never joins across rows on
  letter identity, matching `audit_selectors.py`'s own documented discipline
  (shuffled-choices loaders can map the same letter to different choice
  strings across rows).
- **Duplicate-path and duplicate-seed guards** (`_resolve_dataset_and_seeds`)
  -- present and correct; the duplicate-seed case (same seed embedded in two
  differently-named files) has no dedicated test, a minor coverage gap, not a
  logic defect.
- **Dataset-mismatch and pool-count guards** -- correct, tested.

## What was found: pool files never burn themselves after use

`assert_seeds_not_burned` unions a static list with `original_audit_seeds()`,
a dynamic scan of `benchmark/results/*.jsonl` filenames -- deliberately
excluding anything prefixed `pool_`, so a freshly-written pool doesn't burn
itself the instant `run_pool.py` creates it. That exclusion is correct for
*writing* a pool, but nothing re-admitted a pool to the burn scan after it had
actually been *spent* on a completed `--ship-gate` verdict. Concretely: run
`--ship-gate` once on 3 fresh pools for `max_single_confidence`, get a
verdict (either one), and the same 3 pool files could be fed into a second
`--ship-gate` call -- for `confidence_weighted`, or for `max_single_confidence`
again -- with no error. That is the exact fitting failure S7 exists to catch,
just moved one step later: from "seed used to select the selector" to "seed
used in a prior confirmation attempt."

This matters specifically because the file's own threat model, stated
repeatedly in its comments, is "don't let a SHIP verdict be scored against
data that isn't naive" -- and a second look at the same held-out triple after
seeing the first verdict (win or lose) is precisely that.

## The fix

`main()` now writes a small marker file per held-out seed
(`s7_shipgate_consumed_seed<N>.jsonl`, recording selector/benchmark/verdict/
source pool) immediately after a `--ship-gate` call reaches a real verdict --
SHIP or DO NOT SHIP, since a loss is still a genuine look. The marker
filename deliberately does **not** start with `pool_`, so
`original_audit_seeds()`'s existing glob-and-regex scan picks it up with zero
changes to the burn-check logic itself -- the same mechanism that already
burns any other result file. A run that fails a precondition before reaching
`ship_gate_verdict()` (wrong pool count, mismatched dataset, already-burned
seed) writes nothing, matching the existing "only a genuine SHIP verdict
attempt burns the seed" posture.

`main()` gained a `results_dir` parameter (default `benchmark/results/`,
threaded through to both the burn-scan and the marker write, overridable via
`--results-dir` on the CLI) so tests can point the whole guard at a `tmp_path`
instead of writing test artifacts into the real results directory. The two
pre-existing end-to-end tests (`test_main_ship_gate_end_to_end_ships`,
`test_main_ship_gate_end_to_end_do_not_ship`) were updated to pass
`results_dir=tmp_path` for this reason -- they were previously relying on the
default (the real `benchmark/results/`) only working by coincidence, because
their synthetic seeds (900011-900023) never appeared in a real committed
filename.

Four new tests cover: the marker file is picked up by the existing burn scan;
a completed SHIP verdict burns its seeds against a same-pool re-run under a
different selector AND the same selector; a completed DO-NOT-SHIP verdict
burns its seeds too; a run that fails before reaching a verdict burns
nothing. Full suite: 892/892 passing (888 before this change).

## What was not changed

Nothing about the pre-registered S7 bar itself (net>=+5, discordant>=12,
p<0.05, within-50%-of-original-effect, non-negative per seed) was touched --
this review found a seed-reuse gap in the harness's own self-protection, not
a defect in the statistical bar it enforces. The harness has not yet been run
live; no SHIP or DO NOT SHIP verdict exists for any real selector.
