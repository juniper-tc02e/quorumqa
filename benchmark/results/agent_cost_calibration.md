# Agent cost calibration -- measured, not estimated

Reproduce: `.venv/Scripts/python.exe benchmark/analyze_agent_costs.py`

**Zero paid tokens.** Log mining only, over Harbor job artifacts already
on disk from prior `harbor run` invocations. No Terminal-Bench task,
Harbor invocation, or model call was made to produce this report.

## 1. What was found

Search roots (Harbor `--jobs-dir` locations, deduplicated):
- `C:\Users\ONGJUN~1\AppData\Local\Temp\harbor_jobs` (exists)
- `C:\Users\ONGJUN~1\AppData\Local\Temp\harbor_jobs_pilot` (exists)
- `C:\Users\ONGJUN~1\AppData\Local\Temp\harbor_jobs_quorumqa` (exists)

In-repo search for stray agent/Harbor artifacts (`benchmark/results/`, anywhere else under the repo): **0 found** -- none. Harbor writes to its own --jobs-dir, never into this repo.

Harbor job directories found: 8

| job_name | root | agent | job max_turns | task dirs | included in cost stats |
|---|---|---|---|---|---|
| 2026-07-21__15-21-01 | `harbor_jobs` | nop | - | 1 | no (not QuorumQAAgent) |
| hardened-baseline-seed3 | `harbor_jobs_pilot` | quorumqa.agents.terminal_agent:QuorumQAAgent | 15 | 14 | yes |
| phase1-pilot-seed42 | `harbor_jobs_pilot` | quorumqa.agents.terminal_agent:QuorumQAAgent | 15 | 14 | yes |
| phase1-pilot-seed42-retry | `harbor_jobs_pilot` | quorumqa.agents.terminal_agent:QuorumQAAgent | 15 | 7 | yes |
| phase1-pilot-seed7 | `harbor_jobs_pilot` | quorumqa.agents.terminal_agent:QuorumQAAgent | 15 | 1 | yes |
| phase1-pilot-seed7c | `harbor_jobs_pilot` | quorumqa.agents.terminal_agent:QuorumQAAgent | 15 | 13 | yes |
| seed7-hardened-rerun | `harbor_jobs_pilot` | quorumqa.agents.terminal_agent:QuorumQAAgent | 15 | 14 | yes |
| 2026-07-21__15-28-24 | `harbor_jobs_quorumqa` | quorumqa.agents.terminal_agent:QuorumQAAgent | 15 | 1 | yes |

QuorumQAAgent task trials recovered: **64**

## 2. Turn-cap discrepancy (found while reading job configs)

Every real historical QuorumQAAgent job passed an explicit `max_turns` override. Caps observed across all 8 jobs: **[15]**.
`src/quorumqa/agents/terminal_agent.py`'s constructor **default** is `max_turns=30`, and `docs/capability-roadmap.md` itself refers to 'the existing 30-turn cap' / 'the unchanged 30-turn cap' (A1a, A2 rows, section 3.5). **Every actual historical run used 15, not 30.** No historical run exists at the 30-turn cap the roadmap's own prose assumes P13/P15 will run at. This matters directly for re-pricing below: tasks that exhaust their turn budget without finishing pay for roughly twice as many turns at cap=30 as at cap=15, and per-turn prompts grow with transcript length, so the cost of a capped-out task is *worse* than linear in the cap. The measured distribution below is a same-cap (15) read; it
does not by itself tell us the cost at cap=30 (see section 5).

## 3. Per-turn granularity: not available

`QuorumQAAgent.run()` (src/quorumqa/agents/terminal_agent.py) accumulates `total_input_tokens`/`total_output_tokens` in local variables across its turn loop and only ever writes them into `context.n_input_tokens` / `context.n_output_tokens` -- it never calls `self.logger` or writes a per-turn record to `logs_dir`. Harbor's own `result.json` per task mirrors this: it stores only the cumulative `agent_result.n_input_tokens` / `n_output_tokens` for the whole trial, with no turn-by-turn breakdown (`agent/` and `artifacts/logs/` subdirectories under each task trial exist but are empty in every trial checked). Wall-clock timestamps (`agent_execution.started_at`/`finished_at`) ARE present per task and are reported below, but they cannot be divided by a turn count we don't have to back out a reliable per-turn figure. **This report gives per-TASK distributions (measured) and does not fabricate a per-turn number.**

**4 trials have NO recorded usage at all** (agent_result.n_input_tokens/n_output_tokens both null in Harbor's result.json) -- not zero spend, an unrecorded gap. In every case the exception (a bare RuntimeError from an un-caught exec() timeout, or a ValueError from JSON-truncation inside chat_json itself) fired before `QuorumQAAgent.run()` ever reached its `context.n_input_tokens = total_input_tokens` assignment, so real token spend on at least the in-flight turn was never written back to Harbor. These are excluded from every distribution below (not treated as 0) and are all pre-hardening:
  - `phase1-pilot-seed42` / `compile-compcert`: RuntimeError -- Command timed out after 60 seconds
  - `phase1-pilot-seed42` / `count-dataset-tokens`: RuntimeError -- Command timed out after 60 seconds
  - `phase1-pilot-seed42-retry` / `count-dataset-tokens`: RuntimeError -- Command timed out after 300 seconds
  - `phase1-pilot-seed7c` / `distribution-search`: ValueError -- Model qwen3.7-max failed to return parseable JSON after 2 attempts: Unterminated string starting at: line 1 column 28 (c

## 4. Measured per-task token cost distribution

**All eras pooled** (pre-hardening + hardened + the single anecdote task; n=64 task trials across 8 jobs):
- total tokens/task: n=60  min=1,235  median=21,380  mean=20,690  p90=36,674  max=55,814  [tok]
- input tokens/task: n=60  min=874  median=13,481  mean=13,609  p90=22,042  max=41,990  [tok]
- output tokens/task: n=60  min=256  median=4,318  mean=7,080  p90=17,914  max=24,400  [tok]

**Pre-hardening only** (n=32): total tokens/task: n=32  min=1,235  median=18,327  mean=18,400  p90=36,381  max=44,792  [tok]
**Hardened only** (n=28, the fairer analog for a fresh P13/P15 sample since P13/P15 will run the hardened agent): total tokens/task: n=28  min=5,033  median=22,986  mean=23,307  p90=33,124  max=55,814  [tok]
**Hardened-only agent wall-clock/task (seconds)**: n=28  min=42  median=242  mean=451  p90=1,165  max=1,689  [sec]

Status breakdown across all recovered trials: failed_graded=23, solved=18, ungraded_exception=23

(`ungraded_exception` includes trials where an exception co-occurred with a real verifier grade, e.g. `break-filter-js-from-html` hit its own 1200s AgentTimeoutError but the container state still graded 1.0 -- Harbor logs the exception and the grade independently; this script classifies by grade-presence first, so that specific trial shows as `solved`, not `ungraded_exception`. Full per-task detail, including which trials had a co-occurring exception, is in the CSV.)

## 5. Re-pricing P13 and P15

Roadmap's own flagged-unverifiable assumption: **150,000 tok/task-attempt** (docs/capability-roadmap.md lines 683/685, 'the unverifiable ~150k tok/task estimate').

Basis for re-pricing: hardened-only measured mean/p90, n=28 task trials -- mean=23,307 tok/task, p90=33,124 tok/task.
Ratio vs the roadmap's 150k/task assumption: **mean = 0.16x, p90 = 0.22x** the assumed figure.

### P13 -- A1a self-check gate + A0' calibration, fresh disjoint sample
- Roadmap budget: 1,100,000 tokens (2.51% of 43,828,731/wk quota), implying 7.3 task-attempts at the assumed 150k/task rate.
- Re-priced at measured cost, **same task-attempt count** (7.3): point estimate (mean) = **170,917 tokens** (0.39% of weekly quota); p90 upper bound = **242,911 tokens** (0.55% of weekly quota).
- vs roadmap budget: point-estimate ratio = 0.16x, p90 ratio = 0.22x.

### P15 -- A0 Batch-1 oracle gap, 12 fresh tasks x k=3 = 36 rollouts
- Roadmap budget: 5,500,000 tokens (12.55% of 43,828,731/wk quota), implying 36.7 task-attempts at the assumed 150k/task rate.
- Re-priced at measured cost, **same task-attempt count** (36.7): point estimate (mean) = **854,586 tokens** (1.95% of weekly quota); p90 upper bound = **1,214,554 tokens** (2.77% of weekly quota).
- vs roadmap budget: point-estimate ratio = 0.16x, p90 ratio = 0.22x.

## 6. What this licenses, and what it does not

- **Turn cap mismatch (section 2).** All measured data is at max_turns=15. The roadmap's own prose assumes a 30-turn cap for P13/P15's agentic work ('the existing/unchanged 30-turn cap', A1a/A2). No historical run at cap=30 exists. If P13/P15 actually run at 30, tasks that would have exhausted a 15-turn cap can run for materially more tokens than this report's p90 captures -- per-turn prompt size grows with transcript length, so cost is worse than linear in the cap for capped-out tasks. Decide the actual cap for P13/P15 before trusting the p90 figure as a hard ceiling; if it's 30, treat the p90 above as a floor, not a ceiling.
- **The 24-task hardened-against set is not this report's basis, but the underlying agent is the same hardened agent.** P13/P15 explicitly target a *fresh, disjoint* sample specifically because the 24-task set (seed-7 pre/post + seed-3) was used to develop and tune the hardening fixes -- this report's 'hardened' subset overlaps that same 24-task set (it *is* the seed-7-hardened-rerun + seed-3 runs). The token-COST distribution is a reasonable analog for a fresh sample (nothing about token cost per turn is tuned by the hardening fixes -- the fixes changed retry/timeout/error-handling behavior, not prompt size), but the SOLVE-RATE numbers from this same data must not be reused as a fresh-sample accuracy baseline, exactly as capability-roadmap.md section 3.5 already states.
- **Hardening changed token spend, not just error handling, and the direction is toward more tokens per task.** The 3-fix hardening pass (retry-on-ReadTimeout, TIMEOUT-as-observation instead of fatal exception, 1024->4096 max_tokens) means a task that used to die in 1-2 turns pre-hardening now survives to consume more turns post-hardening. Compare pre-hardening vs hardened means printed in section 4 -- if hardened mean > pre-hardening mean (check the numbers above), that is this effect showing up directly, not noise.
- **This is a small, non-uniform sample (mixed task difficulty, mixed concurrency, mixed time-of-day).** Distribution shape (mean vs p90 spread) is informative; the exact p90 value should not be treated as more precise than n=28 tasks supports.

## 7. Decision consequences

At the mean, the roadmap's 150k/task assumption is **0.16x** the measured hardened-era mean (23,307 tok/task) -> the agentic branch is **OVER-PRICED** on point estimate.
At p90, the ratio is **0.22x** (33,124 measured tok/task at p90) -- this is the number that matters for the 20% quota-reserve risk the task brief calls out, since agentic cost is long-tailed by construction (a task that survives to the turn cap costs far more than one that finishes in 2 turns).

p90 ratio <= 1: the roadmap's 150k figure was conservative even at the tail measured so far -- P13/P15 can run with headroom to spare against their own budget line at the SAME turn cap (15) this data was measured at. This is NOT a reason to move them earlier in the firing order (their position was set by information-per-token, a different question), and it is NOT license to skip the turn-cap-30 caveat above -- an under-priced risk at cap=15 can still turn into an over-spend at cap=30 if that is the cap actually used.

