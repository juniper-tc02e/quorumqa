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
