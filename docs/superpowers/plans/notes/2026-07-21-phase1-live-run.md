# Phase 1 live run, 2026-07-21

## Command run

```bash
export QUORUMQA_TOKEN_PLAN_API_KEY="<from .env>"
export QUORUMQA_TOKEN_PLAN_BASE_URL="https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic"
export PYTHONPATH="<repo>/src"

harbor run -d terminal-bench/terminal-bench-2-1 --task terminal-bench/cancel-async-tasks \
  -a quorumqa.agents.terminal_agent:QuorumQAAgent \
  -m qwen3.7-max \
  --ak max_turns=15 \
  -k 1 -n 1 --jobs-dir /tmp/harbor_jobs_quorumqa
```

Explicitly exported the Token Plan credentials as real shell environment variables before invoking `harbor`, rather than trusting `python-dotenv`'s file-discovery to find `.env` from whatever working directory Harbor's spawned agent process runs in -- `os.environ` lookups are robust to that in a way file-search isn't, and this was a real, disclosed risk flagged in the original plan's Task 4 Step 1 rather than assumed away.

## Outcome: genuine task success, not just a harness pass

**Reward: 1.0. Zero exceptions.** This is not merely "the integration point didn't crash" (the bar the plan set as sufficient) -- `QuorumQAAgent` actually solved the real Terminal-Bench 2.1 task `cancel-async-tasks` on its first live attempt, verified by the task's own real grading script, not a self-report.

From `result.json`:
- `agent_info`: `name=quorumqa-single`, `version=0.1.0`, `model=qwen3.7-max` -- confirms the agent registered and ran as itself, not silently falling back to a built-in Harbor agent.
- `agent_result`: `n_input_tokens=6873`, `n_output_tokens=15751`, `cost_usd=0.0` (expected -- Token Plan Credits, no honest $/token figure, per `qwen_client.py`'s own documented behavior).
- `verifier_result.rewards.reward = 1.0`.
- `exception_info: null`.
- Timing: environment setup 3.2s, agent execution 5m 4s (07:28:31 to 07:33:35 UTC), verifier grading 23.5s, total trial 5m 34s.
- Turn budget was 15 (`--ak max_turns=15`); the actual number of turns used before the model reported `done=true` was not separately logged (Phase 1's agent doesn't write a per-turn transcript to `logs_dir` -- `ATIF`/trajectory support is deliberately `False`, out of scope for this phase) -- the output-token count (15,751, from a thinking-enabled flagship model) is consistent with several turns of real reasoning plus command output, not a single-shot lucky guess.

## What this proves, and what it doesn't

Proves: the full integration chain is real and works, end to end, on a
genuinely hard-graded task, not a toy -- `QwenClient` (Token Plan
transport) driving a real multi-turn tool-use loop, `environment.exec()`
executing real commands in a real Docker container, the task's own
verifier grading the real resulting container state. This was the entire
point of Phase 1.

Does not prove: that QuorumQA's multi-agent deliberation adds value here.
This was one agent, one trajectory, no voting, no escalation, no Judge --
by design (see the Phase 1 plan's "What Phase 1 does and does not prove"
section). One task's success also doesn't establish a real accuracy rate
across Terminal-Bench 2.1's 89 tasks -- that requires a proper multi-task
pilot, not a single anecdote, matching this whole project's established
discipline against overgeneralizing from n=1.

## Honest next steps, not built here

- A real pilot across a meaningful sample of the 89 tasks (not just this
  one) to get an actual single-agent baseline accuracy rate on Terminal-
  Bench 2.1 for this model, before any multi-agent comparison is
  meaningful.
- Only then, Phase 2 per `docs/agentic-rebuild-scoping.md`: best-of-N
  filtered by the task's own real verifier (Option A), now sized against
  real measured per-task cost (~6.9K in, ~15.8K out tokens, ~5 minutes)
  rather than a guess.
