# QuorumQA Terminal-Bench Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get a single, non-deliberating QuorumQA-flavored agent to attempt one real Terminal-Bench 2.1 task end-to-end through the Harbor framework, with a real pass/fail signal, proving the integration point works before any multi-agent deliberation logic is layered on top.

**Architecture:** A new `BaseAgent` subclass (Harbor's pluggable agent interface) whose `run()` method is a plain single-turn-loop: ask the model for the next shell command via `QwenClient.chat_json` (the exact same call shape already used by every role in `quorumqa/engine/`), execute it via `environment.exec()`, feed stdout/stderr back into the conversation, repeat until the model reports done or a turn budget is hit.

**Tech Stack:** Python 3.12, `harbor` (installed via `uv tool install harbor`), the existing `QwenClient` (Token Plan transport), `pytest` for offline tests, Docker (Harbor's default local sandbox provider).

## Global Constraints

- No live API calls inside `pytest` tests -- offline tests use a fake client/fake environment, exactly like `tests/test_engine_offline.py` already does. Verified with real Harbor + real Qwen Cloud calls only in Task 4's manual step, not in the automated test suite.
- New agent code lives under `src/quorumqa/agents/`, mirroring the existing `src/quorumqa/engine/` package structure -- one file per responsibility, not one large file.
- Reuse `QwenClient` unchanged. Do not write a second HTTP client for this.
- This is Phase 1 only: **no multi-agent deliberation in this plan.** A single agent, single trajectory, per task. Layering best-of-N or Judge-based tie-breaking (see `docs/agentic-rebuild-scoping.md`, "Option A/B/C") is explicitly out of scope here and is a separate future plan once this phase proves the integration works at all.

---

### Task 1: Install Harbor and verify the harness itself works, no QuorumQA code yet

**Files:**
- Create: `docs/superpowers/plans/notes/2026-07-21-harbor-sanity-check.md` (a plain text log of the commands run and their output, not code)

**Interfaces:**
- Consumes: nothing (this task touches no QuorumQA code)
- Produces: confirmation that `harbor run` works locally against Docker and that Terminal-Bench 2.1's task set is reachable, which every later task depends on

- [ ] **Step 1: Install Harbor**

```bash
uv tool install "harbor[daytona]"
```

Expected: installs cleanly, `harbor --version` prints a version string.

- [ ] **Step 2: Confirm Docker is available (Harbor's default local sandbox)**

```bash
docker info
```

Expected: prints daemon info without error. If Docker Desktop is not running, start it first -- Harbor's local runs depend on it.

- [ ] **Step 3: Run one Terminal-Bench 2.1 task with Harbor's built-in no-op reference agent**

```bash
harbor run -d terminal-bench/terminal-bench-2-1 -a nop -m qwen/qwen3.7-max -k 1 -n 1
```

Expected: the run completes (the `nop` agent does nothing, so the task should fail its verifier -- that is the correct, expected outcome here). The point of this step is confirming the harness itself runs end-to-end -- dataset downloads, a container spins up, the verifier executes, a result is written -- not confirming a real answer. Record the exact output (including the job directory path Harbor prints) in the notes file from Step 0.

- [ ] **Step 4: Record findings**

Write `docs/superpowers/plans/notes/2026-07-21-harbor-sanity-check.md` containing:
- The exact `harbor` version installed.
- Whether `-m qwen/qwen3.7-max` was accepted as a valid `--model` value by Harbor's CLI, or whether it rejected the provider string (Harbor's model abstraction is not used by our custom agent in Task 2 onward, but the CLI may still validate the flag's format) -- if rejected, note what value Harbor did accept as a placeholder (e.g. `anthropic/claude-3-5-haiku` used only to satisfy CLI validation, never actually called).
- The job directory path and a one-line summary of the `nop` run's result.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/notes/2026-07-21-harbor-sanity-check.md
git commit -m "Confirm Harbor + Docker + Terminal-Bench 2.1 run locally before writing any custom agent code"
```

---

### Task 2: `QuorumQAAgent` skeleton -- `name()`, `version()`, `setup()`, and the action-parsing logic, offline-tested

**Files:**
- Create: `src/quorumqa/agents/__init__.py`
- Create: `src/quorumqa/agents/terminal_agent.py`
- Test: `tests/test_terminal_agent_offline.py`

**Interfaces:**
- Consumes: `quorumqa.qwen_client.QwenClient.chat_json` (existing, unchanged signature: `chat_json(model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True) -> JsonCallResult` where `JsonCallResult.data` is a `dict`).
- Produces: `parse_next_action(data: dict) -> NextAction` -- a pure function later tasks and tests both call directly. `NextAction` is a dataclass with fields `done: bool`, `command: str | None`, `summary: str | None`.

- [ ] **Step 1: Write the failing test for action parsing**

```python
# tests/test_terminal_agent_offline.py
"""Offline tests for the QuorumQA Terminal-Bench agent's pure logic --
no live API calls, no Harbor, no Docker. Mirrors the fake-client pattern
in tests/test_engine_offline.py."""

import pytest

from quorumqa.agents.terminal_agent import NextAction, parse_next_action


def test_parse_next_action_command():
    data = {"done": False, "command": "ls -la /workdir", "summary": "listing files"}
    action = parse_next_action(data)
    assert action == NextAction(done=False, command="ls -la /workdir", summary="listing files")


def test_parse_next_action_done():
    data = {"done": True, "command": None, "summary": "task complete"}
    action = parse_next_action(data)
    assert action.done is True
    assert action.command is None


def test_parse_next_action_missing_command_defaults_to_done():
    # If the model claims not-done but omits a command, treat it as done
    # rather than crashing on a None command sent to environment.exec --
    # this is a real possible malformed-response case, not a hypothetical.
    data = {"done": False, "summary": "confused"}
    action = parse_next_action(data)
    assert action.done is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_terminal_agent_offline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quorumqa.agents'`

- [ ] **Step 3: Write the minimal implementation**

```python
# src/quorumqa/agents/__init__.py
```//empty, marks the package

```python
# src/quorumqa/agents/terminal_agent.py
"""A single, non-deliberating agent for Terminal-Bench-style tasks: ask the
model for the next shell command, run it, feed the result back, repeat.
Phase 1 of docs/agentic-rebuild-scoping.md -- deliberately no multi-agent
logic here, see that doc's Option A/B/C for what comes after this phase
proves the integration point works."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NextAction:
    done: bool
    command: str | None
    summary: str | None


def parse_next_action(data: dict) -> NextAction:
    done = bool(data.get("done", False))
    command = data.get("command")
    summary = data.get("summary")
    if not done and not command:
        # Malformed response: claims more work is needed but gave no
        # command to run. Treat as done rather than looping forever or
        # crashing when this None reaches environment.exec().
        done = True
    return NextAction(done=done, command=command, summary=summary)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_terminal_agent_offline.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/quorumqa/agents/__init__.py src/quorumqa/agents/terminal_agent.py tests/test_terminal_agent_offline.py
git commit -m "Add QuorumQAAgent's action-parsing logic, offline-tested"
```

---

### Task 3: The real agent loop -- `QuorumQAAgent(BaseAgent)`, offline-tested against a fake environment

**Files:**
- Modify: `src/quorumqa/agents/terminal_agent.py`
- Test: `tests/test_terminal_agent_offline.py` (add to the file from Task 2)

**Interfaces:**
- Consumes: `harbor.agents.base.BaseAgent` (abstract methods `name()`, `version()`, `setup(environment)`, `run(instruction, environment, context)`), `harbor.environments.base.BaseEnvironment.exec(command, cwd=None, env=None, timeout_sec=None, user=None) -> ExecResult` where `ExecResult` has `.stdout: str | None`, `.stderr: str | None`, `.return_code: int`, `harbor.models.agent.context.AgentContext` (fields `n_input_tokens`, `n_output_tokens`, `cost_usd`, all `int | float | None`, settable directly).
- Produces: `QuorumQAAgent`, importable as `quorumqa.agents.terminal_agent:QuorumQAAgent` (Harbor's `BaseAgent.import_path()` format, needed for Task 4's `-a` flag).

- [ ] **Step 1: Write the failing test using a fake environment and fake client**

```python
# Append to tests/test_terminal_agent_offline.py

import asyncio
from dataclasses import dataclass

from quorumqa.agents.terminal_agent import QuorumQAAgent


@dataclass
class FakeExecResult:
    stdout: str | None
    stderr: str | None
    return_code: int


class FakeEnvironment:
    """Fake harbor.environments.base.BaseEnvironment -- records every
    command run and returns a scripted result per call, no Docker."""

    def __init__(self, scripted_results):
        self._scripted = list(scripted_results)
        self.commands_run = []

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.commands_run.append(command)
        return self._scripted.pop(0)


class FakeAgentContext:
    def __init__(self):
        self.n_input_tokens = None
        self.n_output_tokens = None
        self.cost_usd = None


class FakeQwenClientForAgent:
    """Scripts a sequence of chat_json responses -- one per turn -- so the
    loop's turn-by-turn behavior is tested without any live call."""

    def __init__(self, scripted_actions):
        self._scripted = list(scripted_actions)
        self.calls = []

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"system": system, "user": user})
        from quorumqa.qwen_client import JsonCallResult
        from quorumqa.schemas import CallUsage

        action_data = self._scripted.pop(0)
        return JsonCallResult(
            data=action_data,
            usage=CallUsage(model=model, input_tokens=100, output_tokens=50, cost_usd=0.0, role=role),
        )


def test_agent_runs_two_commands_then_stops():
    fake_env = FakeEnvironment([
        FakeExecResult(stdout="file1.txt\nfile2.txt\n", stderr=None, return_code=0),
        FakeExecResult(stdout="hello world\n", stderr=None, return_code=0),
    ])
    fake_client = FakeQwenClientForAgent([
        {"done": False, "command": "ls /workdir", "summary": "list files"},
        {"done": False, "command": "cat file1.txt", "summary": "read file1"},
        {"done": True, "command": None, "summary": "task complete"},
    ])
    fake_context = FakeAgentContext()

    agent = QuorumQAAgent(logs_dir=None, model_name="qwen/qwen3.7-max", client=fake_client, max_turns=10)
    asyncio.run(agent.run("List files and print the first one.", fake_env, fake_context))

    assert fake_env.commands_run == ["ls /workdir", "cat file1.txt"]
    assert fake_context.n_input_tokens == 300  # 3 calls * 100
    assert fake_context.n_output_tokens == 150  # 3 calls * 50


def test_agent_stops_at_max_turns_even_if_model_never_says_done():
    fake_env = FakeEnvironment([FakeExecResult(stdout="ok\n", stderr=None, return_code=0) for _ in range(3)])
    fake_client = FakeQwenClientForAgent([
        {"done": False, "command": "echo 1", "summary": "s1"},
        {"done": False, "command": "echo 2", "summary": "s2"},
        {"done": False, "command": "echo 3", "summary": "s3"},
    ])
    fake_context = FakeAgentContext()

    agent = QuorumQAAgent(logs_dir=None, model_name="qwen/qwen3.7-max", client=fake_client, max_turns=3)
    asyncio.run(agent.run("Do something that never finishes.", fake_env, fake_context))

    assert len(fake_env.commands_run) == 3  # stopped by the turn budget, not by "done"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_terminal_agent_offline.py -v`
Expected: FAIL with `ImportError: cannot import name 'QuorumQAAgent'`

- [ ] **Step 3: Write the minimal implementation**

```python
# Append to src/quorumqa/agents/terminal_agent.py

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from quorumqa.qwen_client import QwenClient

AGENT_SYSTEM = (
    "You are an agent operating a real Linux terminal to complete a task. "
    "You can run exactly one shell command per turn and you will be shown "
    "its stdout, stderr, and return code before choosing your next command. "
    "When the task is fully complete, respond with done=true and no command.\n\n"
    'JSON shape: {"done": true|false, "command": "shell command or null", "summary": "one short sentence"}'
)


class QuorumQAAgent(BaseAgent):
    SUPPORTS_ATIF = False
    SUPPORTS_RESUME = False
    SUPPORTS_WINDOWS = False

    def __init__(self, logs_dir, model_name=None, logger=None, mcp_servers=None,
                 skills_dir=None, *args, extra_env=None, client=None, max_turns=30, **kwargs):
        super().__init__(logs_dir, model_name=model_name, logger=logger, mcp_servers=mcp_servers,
                          skills_dir=skills_dir, *args, extra_env=extra_env, **kwargs)
        self._client = client or QwenClient()
        self._max_turns = max_turns

    @staticmethod
    def name() -> str:
        return "quorumqa-single"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        # No extra tooling to install -- the agent only issues plain shell
        # commands via environment.exec(), nothing needs to be copied into
        # the container ahead of time for Phase 1.
        pass

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        transcript = []
        total_input_tokens = 0
        total_output_tokens = 0
        model = self.model_name or "qwen3.7-max"

        for turn in range(self._max_turns):
            user_prompt = self._build_prompt(instruction, transcript)
            result = self._client.chat_json(
                model=model, system=AGENT_SYSTEM, user=user_prompt,
                role="terminal_agent", thinking=True,
            )
            total_input_tokens += result.usage.input_tokens
            total_output_tokens += result.usage.output_tokens

            action = parse_next_action(result.data)
            if action.done or action.command is None:
                break

            exec_result = await environment.exec(action.command, timeout_sec=60)
            transcript.append({
                "command": action.command,
                "stdout": exec_result.stdout or "",
                "stderr": exec_result.stderr or "",
                "return_code": exec_result.return_code,
            })

            # Populate as we go, not just at the end, so a timeout or crash
            # mid-loop still leaves a real token count behind -- matching
            # BaseAgent.run()'s own docstring guidance.
            context.n_input_tokens = total_input_tokens
            context.n_output_tokens = total_output_tokens

        context.n_input_tokens = total_input_tokens
        context.n_output_tokens = total_output_tokens
        # Token Plan billing, not per-token USD -- see qwen_client.py's own
        # cost_usd=0.0 note. No honest dollar figure to report here either.
        context.cost_usd = 0.0

    @staticmethod
    def _build_prompt(instruction: str, transcript: list[dict]) -> str:
        lines = [f"Task: {instruction}", ""]
        if not transcript:
            lines.append("No commands run yet. Propose the first one.")
        else:
            lines.append("Commands run so far, most recent last:")
            for entry in transcript:
                lines.append(f"$ {entry['command']}")
                if entry["stdout"]:
                    lines.append(f"stdout: {entry['stdout'][:2000]}")
                if entry["stderr"]:
                    lines.append(f"stderr: {entry['stderr'][:2000]}")
                lines.append(f"return code: {entry['return_code']}")
                lines.append("")
        return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_terminal_agent_offline.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Run the full offline suite to confirm nothing else broke**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests pass, including the pre-existing 18.

- [ ] **Step 6: Commit**

```bash
git add src/quorumqa/agents/terminal_agent.py tests/test_terminal_agent_offline.py
git commit -m "Implement QuorumQAAgent's real run loop: ask, exec, feed back, repeat until done or turn budget"
```

---

### Task 4: Wire it into Harbor and run against one real Terminal-Bench 2.1 task, live

**Files:**
- Create: `docs/superpowers/plans/notes/2026-07-21-phase1-live-run.md`

**Interfaces:**
- Consumes: `QuorumQAAgent` from Task 3, Harbor's `-a` CLI flag (accepts either a name registered in Harbor's agent factory, or -- per `BaseAgent.import_path()` -- a raw `module:ClassName` import path; Task 1's notes should already have flagged whether Harbor's factory requires pre-registration or accepts a raw import path directly. If Harbor requires registration and rejects a raw import path, the fallback is Harbor's documented custom-agent plugin mechanism -- check `harbor run --help` output saved in Task 1's notes for an `--agent-module` or equivalent flag before assuming registration is mandatory.)
- Produces: one real, live trial result (pass or fail) from a real Terminal-Bench 2.1 task, run through `QuorumQAAgent` end to end -- the actual proof-of-integration this whole plan exists to produce.

- [ ] **Step 1: Confirm the API key environment variable Harbor's process needs**

`QuorumQAAgent` calls `QwenClient()` internally with no arguments, which reads `QUORUMQA_TOKEN_PLAN_API_KEY`/`QUORUMQA_TOKEN_PLAN_BASE_URL` from the environment via `quorumqa.config` (see `src/quorumqa/config.py`). Harbor spawns the agent's `run()` inside its own orchestration process, not necessarily inheriting the shell's exported environment automatically for every provider -- confirm this explicitly rather than assuming:

```bash
echo $QUORUMQA_TOKEN_PLAN_API_KEY | tail -c 8
```

If Harbor's job process does not inherit this (check by adding a one-line `print(os.environ.get("QUORUMQA_TOKEN_PLAN_API_KEY", "MISSING"))` temporarily inside `QuorumQAAgent.setup()` and checking Harbor's captured agent logs after a run), pass it explicitly via Harbor's `--env` mechanism for the agent process, documented in `harbor run --help`.

- [ ] **Step 2: Pick one task and run it**

```bash
harbor run -d terminal-bench/terminal-bench-2-1 \
  -a quorumqa.agents.terminal_agent:QuorumQAAgent \
  -m qwen/qwen3.7-max \
  -k 1 -n 1 \
  --task-id <one-task-id-from-the-dataset>
```

(Pick a task ID from the dataset listing Harbor prints when run without `--task-id`, or from `harbor datasets list` -- do not guess a task ID; list them first if Task 1's notes didn't already record one.)

Expected: the run completes without a harness-level crash (import errors, `setup()`/`run()` exceptions surfacing as agent errors rather than task failures are the thing to watch for -- a genuine task *failure* from the verifier is a fine, expected Phase 1 outcome; a harness *crash* is not).

- [ ] **Step 3: Record the real outcome honestly**

Write `docs/superpowers/plans/notes/2026-07-21-phase1-live-run.md`:
- The exact command run and the task ID chosen.
- Pass or fail, and if fail, whether it was a genuine task failure (verifier ran, task wasn't solved) or a harness/integration failure (agent crashed, environment.exec never got called, etc.) -- these mean very different things and must not be conflated.
- Token counts from the resulting `AgentContext` (`n_input_tokens`, `n_output_tokens`).
- Number of turns the agent actually took before stopping (done vs. hit `max_turns`).
- Anything about the real Harbor/Docker environment that differed from what Tasks 1-3 assumed (e.g. `environment.exec`'s actual stdout/stderr behavior on a real container vs. the fake used in tests).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/notes/2026-07-21-phase1-live-run.md
git commit -m "Phase 1 complete: QuorumQAAgent runs end-to-end against a real Terminal-Bench 2.1 task through Harbor"
```

---

## What Phase 1 does and does not prove

Passing (or even honestly failing, if the harness integration itself works)
one task with `QuorumQAAgent` proves the integration point is real: a
custom agent built on `QwenClient` can run inside Harbor's sandboxed
environment, issue commands, and get graded by Terminal-Bench's own
verifier. It does **not** yet prove QuorumQA's multi-agent deliberation
adds value here -- Phase 1 is deliberately one agent, one trajectory, no
voting, no escalation, no Judge. That comparison -- single agent vs.
best-of-N filtered by the real verifier (Option A from
`docs/agentic-rebuild-scoping.md`) -- is Phase 2, and depends on Phase 1's
real, measured per-task cost and turn count to be sized sensibly, which is
exactly why this plan stops here rather than guessing ahead at Phase 2's
implementation detail.
