# Scoping: what it would take for QuorumQA to attempt Terminal-Bench 2.1 or SWE-Bench Pro

Written 2026-07-21, after a verified research pass confirmed neither
benchmark is reachable by QuorumQA as it exists today. This is a scoping
document, not an implementation plan -- it exists to answer "how big is
this, actually" before committing engineering time.

## The core structural change

QuorumQA today does exactly one thing: given a question and a fixed set of
choices, produce one final answer letter, in at most two rounds (solve,
then optionally skeptic+verifier+judge). Every role is a single API call.
The entire "interaction" with a task is one to five model calls and it's
over.

Terminal-Bench 2.1 and SWE-Bench Pro are a different shape of problem
entirely. A task is: here is a live environment (a container with a real
filesystem, a real shell, in Terminal-Bench's case; a real git repo with a
failing test suite, in SWE-Bench Pro's case) and a goal. The agent must run
commands, read output, edit files, run tests, read *those* results, and
decide what to do next -- for anywhere from a handful to dozens of turns --
until it believes the task is done or it runs out of budget. Success is
graded by re-running the environment's own verifier (a test suite, a
container-state check) after the agent stops, not by matching a letter.

This is not "add a new question loader," which is what LEXam and MMLU-Pro
were. It's a different control-flow at the core: **propose one action → see
its real result → decide the next action, in a loop, against live state**
-- versus QuorumQA's current **produce one final answer, once**.

## What's actually reusable

- `QwenClient` (the Token Plan / Anthropic-Messages-API transport) -- the
  model-calling layer is domain-agnostic. Reusable as-is for issuing calls;
  would need real tool-use support added (see below), not just JSON-mode
  prompting.
- `VerifierToolSession` (`quorumqa/tools/mcp_client.py`) -- genuinely
  reusable. `call(tool_name, arguments)` against a live MCP session is
  already the right shape for "execute a named action against a live
  backend and get a result." The wrapper itself doesn't care whether the
  tool is `safe_calculate` or `run_shell_command`.
- The general idea of running multiple independent agents and comparing
  outcomes -- reusable as a *concept*, but see "what would deliberation even
  mean here" below, because the mechanics don't port directly.

## What does not exist yet and would need building

1. **A sandboxed execution environment per task.** Neither benchmark can be
   attempted without one. Both have existing open frameworks that do this
   already -- Terminal-Bench 2.1 ships Harbor (Apache-2.0, `harbor run`,
   isolated Docker sandboxes per task), and SWE-Bench Pro is run via the
   SWE-Agent scaffold against Docker evaluation environments with
   fail-to-pass/pass-to-pass tests. The realistic path is to build against
   one of these existing harnesses, not write a container orchestrator from
   scratch.
2. **A real agent loop**, not the current one-shot-propose-then-Python-
   executes-once pattern the Verifier uses. The model needs to see each
   action's actual output and decide its own next action, repeatedly, with
   a turn/token budget and a stopping condition ("I believe the task is
   done").
3. **State that persists across many turns** -- current transcript,
   command history, file contents -- none of which QuorumQA tracks today
   because every existing role is stateless between the handful of calls
   in one deliberation.
4. **A materially different Verifier tool roster.** The existing two tools
   (`lookup_constant`, `safe_calculate`) are irrelevant here; the tools
   would be `run_command`, `read_file`, `write_file`, `list_directory`, or
   whatever the chosen harness exposes.

## What would "multi-agent deliberation" even mean in this setting?

This is a genuine open design question, not a settled port of the existing
pattern, and it's worth being honest about rather than assuming the QA
architecture just carries over with bigger tools.

QuorumQA's whole premise on GPQA-Diamond is that there's no cheap way to
check if a multiple-choice answer is correct without already knowing the
answer -- so adjudicating between disagreeing solvers by argument has real
value. **Execution-graded agentic benchmarks don't have that problem.**
SWE-Bench Pro and Terminal-Bench both already come with an objective,
cheap-to-run checker built into the task (the test suite, the container-
state verifier). That changes the calculus:

- **Option A -- best-of-N with the real verifier as arbiter.** Run N
  independent agent attempts at the full task, then just run each one's
  result through the benchmark's own test suite and keep whichever passes
  (or the one that passes the most tests, if none fully pass). This needs
  no Judge, no Skeptic, no argument-weighing at all -- the environment
  already tells you who's right. This is a well-established pattern in the
  SWE-bench literature (sample-and-filter), not a novel QuorumQA
  contribution, and it sidesteps the "adjudicate by argument" premise
  entirely.
- **Option B -- step-level review.** A second agent reviews each proposed
  action before it executes (catch a destructive command, catch a patch
  that doesn't address the root cause). This preserves something like the
  Skeptic's role, but at massively higher cost -- deliberation at every
  step of a 50+ turn trajectory, not once per question.
- **Option C -- Judge only on disagreement between attempts that all
  "look done" but disagree.** Closest analog to today's escalate-on-split
  logic: run N attempts, if they converge on the same fix, ship it; if they
  produce materially different final patches and the test suite doesn't
  cleanly discriminate (e.g. different approaches both pass locally but one
  is clearly more fragile), have a Judge compare the diffs. This keeps the
  "argument matters" premise but only for the harder tie-breaking cases,
  mirroring the actual escalate-on-disagreement shape QuorumQA already has.

Recommendation if this gets built: start with Option A as the honest
baseline (it's simpler, and it's what the field already does), and only
build toward C if A's "different attempts, pick whichever passes" turns out
to leave real cases where verification is ambiguous and argument-weighing
would add something A can't already get from the test suite for free. Don't
build B unless there's a concrete reason step-level review beats the
simpler options -- it's the most expensive by a wide margin.

## Which of the two to attempt first, if this gets built

**Terminal-Bench 2.1**, not SWE-Bench Pro, for the first attempt:

- Fully open, self-hostable framework (Harbor, Apache-2.0) with a public
  leaderboard requiring published trajectories -- no lab gatekeeping,
  unlike FrontierCode which Cognition won't release publicly at all.
- 89 tasks is a tractable size to validate an agent loop against before
  scaling up.
- General computer/terminal tasks are a broader proving ground for "does
  the agent loop work at all" than code-repository-specific SWE tasks.

SWE-Bench Pro is also public and self-hostable (Scale AI's leaderboard),
and its ~23% SOTA means there's substantial headroom -- genuinely worth
attempting second, once the agent-loop infrastructure exists and has been
shaken out on the simpler Terminal-Bench tasks. Building both loops
simultaneously from scratch is not recommended.

## Rough scale, stated honestly

This is a multi-day-to-multi-week infrastructure project -- sandboxed
execution environment integration, a real multi-turn tool-use loop with
budget/stopping logic, new evaluation-harness wiring -- not a same-day
addition like LEXam or MMLU-Pro were (those needed only a new question
loader because the underlying single-turn-answer machinery was already
correct for them). Recommend treating this as its own planned piece of
work, not something to bolt on opportunistically between other benchmark
pilots.
