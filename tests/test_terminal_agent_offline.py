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


def test_parse_next_action_timeout_sec_absent_defaults_to_none():
    # No timeout_sec in the model's JSON -- NextAction should carry None so
    # the agent knows to fall back to its own configured default, not some
    # parser-invented number.
    data = {"done": False, "command": "ls", "summary": "listing"}
    action = parse_next_action(data)
    assert action.timeout_sec is None


def test_parse_next_action_with_timeout_sec_in_range():
    data = {"done": False, "command": "make build", "summary": "building", "timeout_sec": 600}
    action = parse_next_action(data)
    assert action.timeout_sec == 600


def test_parse_next_action_timeout_sec_clamped_to_minimum():
    # Model asks for something below the floor -- clamp up to 10, don't
    # let a hung command get an effectively-zero timeout.
    data = {"done": False, "command": "echo hi", "summary": "quick", "timeout_sec": 1}
    action = parse_next_action(data)
    assert action.timeout_sec == 10


def test_parse_next_action_timeout_sec_clamped_to_maximum():
    # Model asks for something above the ceiling -- clamp down to 1200 so
    # one bad request can't eat an entire budgeted run.
    data = {"done": False, "command": "make build", "summary": "building", "timeout_sec": 999999}
    action = parse_next_action(data)
    assert action.timeout_sec == 1200


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
        self.timeouts_used = []

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.commands_run.append(command)
        self.timeouts_used.append(timeout_sec)
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


def test_agent_uses_a_generous_default_command_timeout():
    # Live 2026-07-21: a hardcoded 60s command timeout killed 6 of 14
    # real Terminal-Bench tasks (compiling, downloading, building) with
    # RuntimeError before the agent ever got a chance to finish -- not a
    # capability ceiling, a too-aggressive default. Locks in the fix.
    fake_env = FakeEnvironment([FakeExecResult(stdout="ok\n", stderr=None, return_code=0)])
    fake_client = FakeQwenClientForAgent([
        {"done": False, "command": "make build", "summary": "building"},
        {"done": True, "command": None, "summary": "done"},
    ])
    fake_context = FakeAgentContext()

    agent = QuorumQAAgent(logs_dir=None, model_name="qwen/qwen3.7-max", client=fake_client, max_turns=5)
    asyncio.run(agent.run("Build the project.", fake_env, fake_context))

    assert fake_env.timeouts_used == [300]  # generous default, not the old 60s


def test_agent_command_timeout_is_configurable():
    fake_env = FakeEnvironment([FakeExecResult(stdout="ok\n", stderr=None, return_code=0)])
    fake_client = FakeQwenClientForAgent([
        {"done": False, "command": "quick-check", "summary": "checking"},
        {"done": True, "command": None, "summary": "done"},
    ])
    fake_context = FakeAgentContext()

    agent = QuorumQAAgent(logs_dir=None, model_name="qwen/qwen3.7-max", client=fake_client,
                           max_turns=5, command_timeout_sec=900)
    asyncio.run(agent.run("Do a slow build.", fake_env, fake_context))

    assert fake_env.timeouts_used == [900]


def test_agent_uses_model_requested_timeout_sec_per_command():
    # 2026-07-21 pilot follow-up: compile-compcert and count-dataset-tokens
    # need individual commands >300s while most commands finish in seconds --
    # a flat higher default would waste a budgeted run on every hung command.
    # The model can now request a per-command timeout_sec; when it does, the
    # actual environment.exec call must receive that value, not the agent's
    # configured default.
    fake_env = FakeEnvironment([
        FakeExecResult(stdout="ok\n", stderr=None, return_code=0),
        FakeExecResult(stdout="ok\n", stderr=None, return_code=0),
    ])
    fake_client = FakeQwenClientForAgent([
        {"done": False, "command": "make compcert", "summary": "slow build", "timeout_sec": 900},
        {"done": False, "command": "ls", "summary": "quick check"},
        {"done": True, "command": None, "summary": "done"},
    ])
    fake_context = FakeAgentContext()

    agent = QuorumQAAgent(logs_dir=None, model_name="qwen/qwen3.7-max", client=fake_client, max_turns=5)
    asyncio.run(agent.run("Build compcert.", fake_env, fake_context))

    # First command's requested timeout is honored; second omits it and
    # falls back to the agent's own configured default (300).
    assert fake_env.timeouts_used == [900, 300]


def test_agent_clamps_model_requested_timeout_sec_out_of_range():
    fake_env = FakeEnvironment([FakeExecResult(stdout="ok\n", stderr=None, return_code=0)])
    fake_client = FakeQwenClientForAgent([
        {"done": False, "command": "make compcert", "summary": "slow build", "timeout_sec": 50000},
        {"done": True, "command": None, "summary": "done"},
    ])
    fake_context = FakeAgentContext()

    agent = QuorumQAAgent(logs_dir=None, model_name="qwen/qwen3.7-max", client=fake_client, max_turns=5)
    asyncio.run(agent.run("Build compcert.", fake_env, fake_context))

    assert fake_env.timeouts_used == [1200]  # clamped down to the ceiling
