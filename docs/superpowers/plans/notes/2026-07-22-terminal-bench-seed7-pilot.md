# Terminal-Bench 2.1 seed-7 pilot (second seed), 2026-07-22

14 fresh tasks (seed-7 sample over the 74 not yet attempted; zero overlap
with the 15 from the seed-42 pilot verified before launch). One task
(sam-cell-seg) ran alone due to a CLI stumble disclosed in the loop log;
the other 13 ran as one job. All results below are from each task's own
verifier, none self-graded.

## Outcomes

| Outcome | Count | Tasks |
|---|---|---|
| Solved (1.0) | 2 | configure-git-webserver, portfolio-optimization |
| Failed cleanly (0.0) | 3 | filter-js-from-html, sam-cell-seg, cobol-modernization (hit harbor's 900s agent cap, graded 0) |
| Exception before grading | 9 | 3x API ReadTimeout, 4x command timeout (30s/120s/300s/300s), 1x JSON truncation ("Unterminated"), 1x command timeout at 120s (mteb-retrieve) |

**Graded: 5/14. Solved among graded: 2/5 (40%).** Seed-42 pilot for
comparison: graded 11/14, solved 6/11 (54.5%).

## Two-seed combined picture (n=29 attempted tasks)

- Graded outcomes: 16/29 (55%). Solved among graded: 8/16 (50%).
- Blocked by exceptions before grading: 13/29 (45%).

## The real finding: robustness is now the binding constraint

The two-seed evidence is consistent: when the agent gets to finish, it
solves roughly half. But nearly half of all attempts never reach grading,
and the exception mix is dominated by three fixable classes:

1. **Fatal command timeouts (5 this seed).** A command exceeding its
   timeout kills the whole task. Worse, the new model-requestable
   timeout_sec made this *more* dangerous, not less: the model requested
   30s and 120s timeouts that a slower command then exceeded fatally. A
   timeout should be an observation the model reacts to (retry longer,
   background it, change approach), not a run-ending exception.
2. **Model-API ReadTimeouts (3 this seed, 1 last seed).** A single slow
   API response kills the task with no retry.
3. **JSON truncation (1).** The agent inherits the QA engine's
   max_tokens=1024, which truncates verbose turns.

All three fixes dispatched as one TDD'd hardening pass. Only after it
lands and a fresh sample runs is a real "QuorumQAAgent baseline solve
rate" claim meaningful -- the current 50%-of-graded is conditioned on
surviving infrastructure that eats 45% of attempts, which would misstate
the agent's actual per-task performance in either direction.

## Quota context, disclosed

The 3 ReadTimeouts all hit the Token Plan API endpoint during a daytime
window with 4 concurrent agent trajectories. Whether this is pure API-side
latency or quota-throttling interaction isn't distinguishable from our
side; the retry fix will absorb either. The seed-42 pilot (2 concurrent,
overnight discount window) saw 1 in 14 -- concurrency and time-of-day are
both plausible contributors, neither provable from n=4 events.

## Hardened-agent rerun (same 14 tasks, same day)

The three-fix hardening pass rerun against the identical seed-7 sample,
n=2 concurrency to keep API-timeout noise out of the measurement:

| | Pre-fix | Post-fix |
|---|---|---|
| Graded outcomes | 5/14 (36%) | **12/14 (86%)** |
| Blocked by exceptions | 9/14 | 2/14 (both double-ReadTimeout) |
| Solved | 2 | **4** |

The two newly-recovered solves are exactly the fix working as designed:
mteb-retrieve died pre-fix on a fatal command timeout and now solves
(the model reacted to the TIMEOUT observation); break-filter-js-from-html
died pre-fix on a ReadTimeout and now grades 1.0 (reaching the agent-cap
wire but with solved container state). The two remaining ReadTimeout
deaths hit the timeout twice in a row (retry consumed) on heavy reasoning
turns -- a real remaining ceiling, same class as the qwen38 baseline's
12 undroppable questions, not fixable from the client side alone.

Honest accounting note: solve-rate-among-graded went 2/5 (40%) -> 4/12
(33%) -- these are not comparable numbers, since pre-fix grading was
survivorship-biased toward tasks that happened to finish fast. 4/12 with
86% grading coverage is the more trustworthy baseline read. Pooling
hardened seed-7 with unhardened seed-42 would mix harness generations;
a fresh-seed run under the hardened agent is the right next baseline
sample, not a pool.

## Fresh-seed hardened baseline (seed-3 sample, 14 more tasks)

12/14 graded (86% coverage -- replicates the hardened rerun's coverage on
an untouched sample), 5/12 solved: code-from-image, nginx-request-logging,
polyglot-c-py, sqlite-db-truncate, sqlite-with-gcov. Two ungraded: one
JSON-parse failure surviving even the 4096-token budget, one new HTTP 400
from the Token Plan API (first of its class; watch for recurrence before
engineering around it).

**The honest hardened-agent baseline, pooled across both hardened
samples (28 tasks, 24 graded): 9/24 solved = 37.5%, at ~86% grading
coverage.** This is the number Phase 2 (best-of-N filtered by each task's
own verifier) should be sized against and measured from. Not comparable
to the pre-hardening 54.5%-of-graded figure, which was survivorship-
biased toward fast-finishing tasks.
