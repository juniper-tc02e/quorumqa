# Terminal-Bench 2.1 14-task pilot, 2026-07-21

The honest next step flagged at the end of Phase 1: one task (`cancel-async-tasks`,
reward 1.0) is an anecdote, not a pilot. This is a seeded random sample of
14 more tasks (seed 42, `random.Random(42).sample()` over the full 89-task
list minus the already-tested one), run with `QuorumQAAgent` through Harbor,
matching this project's established sampling discipline.

## Round 1: 14 tasks, first pass

7/14 completed cleanly. **7/14 threw an exception** -- 6 `RuntimeError:
Command timed out after 60 seconds`, 1 `ReadTimeout` on the model API
itself (300s). Investigated rather than reported as-is: **the 6
RuntimeErrors were a real bug in `QuorumQAAgent`**, not a capability
ceiling -- every shell command was hardcoded to a 60-second timeout,
regardless of what it was doing. Compiling, downloading a model, building
a Cython extension all routinely exceed 60s. Fixed: default raised to
300s (matching the exact precedent already set today for `qwen_client.py`'s
own request timeout), made configurable via `command_timeout_sec`, locked
in with two new offline tests before touching the fix.

## Round 2: retry the 7 affected tasks with the fix

4/7 completed cleanly (2 pass, 2 fail). **3/7 still threw an exception**,
but the picture changed meaningfully:

| Task | Round 1 | Round 2 |
|---|---|---|
| build-cython-ext | timeout (60s) | 0.0 |
| build-pmars | timeout (60s) | 0.0 |
| compile-compcert | timeout (60s) | **still fails: timeout (300s)** |
| count-dataset-tokens | timeout (60s) | **still fails: timeout (300s)** |
| fix-git | timeout (60s) | 1.0 |
| git-leak-recovery | timeout (60s) | 1.0 |
| winning-avg-corewars | ReadTimeout (API, 300s) | **still fails: ReadTimeout (API, 300s)** |

The fix recovered 4 of the 6 originally-mistimed tasks outright. The
other 2 (`compile-compcert`, `count-dataset-tokens`) now fail with the
*same class* of error at the *new* limit -- meaning some individual
commands genuinely take longer than 300 seconds (compiling a full C
compiler from source is a legitimately multi-minute build in any context,
agent or not). `winning-avg-corewars` hit the identical model-API
`ReadTimeout` on both attempts, not a one-off -- this is the same
reasoning-latency ceiling already found earlier today on hard Organic
Chemistry questions (`qwen_client.py`'s 300s request timeout, itself
already raised once from 120s), not something a shell-command timeout
fix touches at all.

## Combined result across all 14 tasks

| Outcome | Count | Tasks |
|---|---|---|
| Solved (reward 1.0) | 6 | constraints-scheduling, hf-model-inference, sanitize-git-repo, torch-tensor-parallelism, fix-git, git-leak-recovery |
| Failed cleanly (reward 0.0) | 5 | db-wal-recovery, overfull-hbox, raman-fitting, build-cython-ext, build-pmars |
| Still can't complete | 3 | compile-compcert, count-dataset-tokens (both: command needs >300s), winning-avg-corewars (model API needs >300s) |

**11/14 tasks (78.6%) got a real, graded outcome. Of those, 6/11 (54.5%)
were solved.** The remaining 3/14 (21.4%) are disclosed as genuinely
unresolved, not folded into either the numerator or denominator of a
success rate, and not silently dropped from the report either.

## What this actually establishes

A real, if noisy, single-agent baseline: **QuorumQAAgent solves roughly
half of the Terminal-Bench 2.1 tasks it's able to attempt to completion**
(6/11), with a genuine ~21% of tasks currently unreachable due to
timeout ceilings that are themselves real and disclosed, not hidden. This
is a single seed, n=15 total (14 + the earlier anecdote) out of 89 tasks
-- a real pilot, not yet a claim about the full benchmark, matching the
same "small sample, be honest about what it does and doesn't establish"
discipline used for the LEXam and MMLU-Pro pilots.

## Honest next steps, not built here

- The two remaining timeout classes point at two different, legitimate
  fixes, not one: a longer (or task-adaptive) `command_timeout_sec` for
  genuinely slow builds like `compile-compcert`, versus nothing currently
  fixes the model-API `ReadTimeout` class short of the model itself
  responding faster on hard reasoning turns -- these should not be
  conflated into a single "raise all the timeouts more" fix without
  checking each is actually the right lever for its own failure mode.
- A larger, still-unseen sample (a second seed) before treating 54.5%
  as a stable single-agent baseline rate rather than one noisy read.
- Only once a real baseline rate is trusted: Phase 2 per
  `docs/agentic-rebuild-scoping.md` -- best-of-N filtered by each task's
  own real verifier -- sized against these actual measured per-task costs
  and turn counts, not a guess.
