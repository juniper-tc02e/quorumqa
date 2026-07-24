"""Offline tests for the F6 rigor-wiring params on QwenClient (seed,
thinking_budget) -- no live API calls, no cost. Monkeypatches
quorumqa.qwen_client.requests.post to capture the exact request body sent,
the same fake-transport pattern tests/test_lever_qwen38_panel_offline.py /
tests/test_lever_qwen38_judge_offline.py already use for this repo's
offline suite.

Covers:
  (a) seed=None, thinking_budget=None (the default for every existing
      caller) -> request body is BYTE-IDENTICAL to the pre-F6 body, for
      both thinking=True and thinking=False.
  (b) seed set -> body["seed"] == the given value; body is otherwise
      unchanged.
  (c) thinking_budget set + thinking=True -> body["thinking"] ==
      {"type": "enabled", "budget_tokens": N}.
  (d) thinking=False + thinking_budget set -> the budget is DROPPED (no
      "enabled"/budget_tokens block); body["thinking"] stays exactly
      {"type": "disabled"}, same as when thinking_budget is never passed.
  (e) chat_json forwards seed/thinking_budget through to chat() unchanged.
"""

import pytest

import quorumqa.qwen_client as qwen_client_module
from quorumqa.qwen_client import QwenClient


class FakeResponse:
    """Stands in for requests.Response -- just enough surface for
    QwenClient.chat (json() + raise_for_status())."""

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _fake_post_capturing(captured: dict):
    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse({
            # Valid JSON text -- chat_json's tests exercise the SAME fake
            # transport as chat()'s, and chat_json feeds this string
            # through _extract_json(), which raises (and retries, then
            # eventually errors) on a bare non-JSON string like "ok".
            "content": [{"type": "text", "text": '{"reasoning": "r", "answer": "ok"}'}],
            "usage": {"input_tokens": 5, "output_tokens": 5},
        })
    return fake_post


def _client() -> QwenClient:
    return QwenClient(api_key="fake-key", base_url="https://fake.example/apps/anthropic")


_MESSAGES = [{"role": "user", "content": "What is 2+2?"}]


# ---------------------------------------------------------------------------
# (a) Defaults (seed=None, thinking_budget=None) -> byte-identical body
# ---------------------------------------------------------------------------


def test_chat_default_params_body_identical_to_pre_f6_thinking_true(monkeypatch):
    captured = {}
    monkeypatch.setattr(qwen_client_module.requests, "post", _fake_post_capturing(captured))

    _client().chat("qwen3.7-max", _MESSAGES, role="solver", temperature=0.4, max_tokens=1024, thinking=True)

    # The exact body shape the client sent before seed/thinking_budget
    # existed: no "thinking" key at all when thinking=True, no "seed" key.
    assert captured["json"] == {
        "model": "qwen3.7-max",
        "max_tokens": 1024,
        "temperature": 0.4,
        "messages": _MESSAGES,
    }
    assert "thinking" not in captured["json"]
    assert "seed" not in captured["json"]


def test_chat_default_params_body_identical_to_pre_f6_thinking_false(monkeypatch):
    captured = {}
    monkeypatch.setattr(qwen_client_module.requests, "post", _fake_post_capturing(captured))

    _client().chat("qwen3.6-flash", _MESSAGES, role="solver", temperature=0.4, max_tokens=1024, thinking=False)

    assert captured["json"] == {
        "model": "qwen3.6-flash",
        "max_tokens": 1024,
        "temperature": 0.4,
        "messages": _MESSAGES,
        "thinking": {"type": "disabled"},
    }
    assert "seed" not in captured["json"]


def test_chat_json_default_params_body_identical_to_pre_f6(monkeypatch):
    captured = {}
    monkeypatch.setattr(qwen_client_module.requests, "post", _fake_post_capturing(captured))

    _client().chat_json(
        model="qwen3.7-max", system="You are a solver.", user="What is 2+2?", role="solver",
    )

    body = captured["json"]
    assert "thinking" not in body
    assert "seed" not in body
    assert body["model"] == "qwen3.7-max"


# ---------------------------------------------------------------------------
# (b) seed set
# ---------------------------------------------------------------------------


def test_chat_seed_set_adds_seed_key_body_otherwise_unchanged(monkeypatch):
    captured = {}
    monkeypatch.setattr(qwen_client_module.requests, "post", _fake_post_capturing(captured))

    _client().chat("qwen3.7-max", _MESSAGES, role="solver", temperature=0.4, max_tokens=1024, thinking=True, seed=1234)

    assert captured["json"] == {
        "model": "qwen3.7-max",
        "max_tokens": 1024,
        "temperature": 0.4,
        "messages": _MESSAGES,
        "seed": 1234,
    }


def test_chat_json_forwards_seed(monkeypatch):
    captured = {}
    monkeypatch.setattr(qwen_client_module.requests, "post", _fake_post_capturing(captured))

    _client().chat_json(model="qwen3.7-max", system="sys", user="usr", role="judge", seed=777)

    assert captured["json"]["seed"] == 777


# ---------------------------------------------------------------------------
# (c) thinking_budget set + thinking=True
# ---------------------------------------------------------------------------


def test_chat_thinking_budget_set_with_thinking_true_adds_enabled_block(monkeypatch):
    captured = {}
    monkeypatch.setattr(qwen_client_module.requests, "post", _fake_post_capturing(captured))

    _client().chat("qwen3.7-max", _MESSAGES, role="solver", thinking=True, thinking_budget=8000)

    assert captured["json"]["thinking"] == {"type": "enabled", "budget_tokens": 8000}


def test_chat_json_forwards_thinking_budget(monkeypatch):
    captured = {}
    monkeypatch.setattr(qwen_client_module.requests, "post", _fake_post_capturing(captured))

    _client().chat_json(model="qwen3.7-max", system="sys", user="usr", role="judge", thinking=True, thinking_budget=4096)

    assert captured["json"]["thinking"] == {"type": "enabled", "budget_tokens": 4096}


def test_seed_and_thinking_budget_can_be_set_together(monkeypatch):
    captured = {}
    monkeypatch.setattr(qwen_client_module.requests, "post", _fake_post_capturing(captured))

    _client().chat("qwen3.7-max", _MESSAGES, role="solver", thinking=True, seed=99, thinking_budget=2048)

    assert captured["json"]["seed"] == 99
    assert captured["json"]["thinking"] == {"type": "enabled", "budget_tokens": 2048}


# ---------------------------------------------------------------------------
# (d) thinking=False + thinking_budget set -> budget dropped, disabled block unchanged
# ---------------------------------------------------------------------------


def test_chat_thinking_false_with_budget_set_drops_budget_keeps_disabled_block(monkeypatch):
    captured = {}
    monkeypatch.setattr(qwen_client_module.requests, "post", _fake_post_capturing(captured))

    _client().chat("qwen3.6-flash", _MESSAGES, role="solver", thinking=False, thinking_budget=5000)

    # A budget on a disabled thinking block is meaningless -- thinking=False
    # always wins, and the body is identical to the thinking_budget=None
    # case (no "enabled"/budget_tokens leak through).
    assert captured["json"]["thinking"] == {"type": "disabled"}


# ---------------------------------------------------------------------------
# (e) full param sweep sanity check on chat_json
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "thinking,thinking_budget,seed,expected_thinking_key",
    [
        (True, None, None, None),
        (False, None, None, {"type": "disabled"}),
        (True, 1000, None, {"type": "enabled", "budget_tokens": 1000}),
        (False, 1000, None, {"type": "disabled"}),
        (True, None, 42, None),
    ],
)
def test_chat_json_param_sweep(monkeypatch, thinking, thinking_budget, seed, expected_thinking_key):
    captured = {}
    monkeypatch.setattr(qwen_client_module.requests, "post", _fake_post_capturing(captured))

    _client().chat_json(
        model="qwen3.7-max", system="sys", user="usr", role="solver",
        thinking=thinking, thinking_budget=thinking_budget, seed=seed,
    )

    body = captured["json"]
    if expected_thinking_key is None:
        assert "thinking" not in body
    else:
        assert body["thinking"] == expected_thinking_key
    if seed is None:
        assert "seed" not in body
    else:
        assert body["seed"] == seed
