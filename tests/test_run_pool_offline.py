"""Offline tests for benchmark/run_pool.py -- no live API calls, no cost.
Uses a fake QwenClient matching the real client.chat_json return shape (an
object with .data/.usage), the same fake-client pattern
tests/test_math_sc_offline.py and tests/test_math_open_engine_offline.py
already use for this repo's offline suite.

Covers (per the task spec):
  (a) pool generation writes K ordered samples per item with all required
      fields (question_id, sample_index, letter, confidence, reasoning,
      usage), for both solver tiers.
  (b) retry-on-transient-error: a sample that fails N times then succeeds
      recovers, consuming exactly N+1 calls and no more.
  (c) a permanently failing sample drops the WHOLE item (never a partial
      pool) and logs a warning -- other items in the same run are
      unaffected.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from quorumqa.config import MECHANICAL_MODEL, ORCHESTRATOR_MODEL
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem

from benchmark.math_open_engine import SC_TEMPERATURE_SCHEDULE
from benchmark.run_pool import _MAX_ATTEMPTS, generate_pool


async def _no_sleep(_seconds):
    """Fast stand-in for asyncio.sleep so retry-backoff tests (5/10/20s in
    production) run instantly."""
    return None


def _item(question_id: str, question: str = "What is the answer?", correct_letter: str = "A") -> GPQAItem:
    return GPQAItem(
        question_id=question_id,
        question=question,
        choices=["opt1", "opt2", "opt3", "opt4"],
        correct_letter=correct_letter,
        subject="Physics",
    )


def _find_key(mapping, user, temperature):
    for (qsub, temp) in mapping:
        if temp == temperature and qsub in user:
            return (qsub, temp)
    return None


class FakePoolClient:
    """Keys scripted behavior by (question_substring, temperature) rather
    than call order: run_pool.py cycles SC_TEMPERATURE_SCHEDULE strictly by
    sample_index BEFORE making any call, so temperature alone identifies a
    sample deterministically, independent of how asyncio actually
    schedules/interleaves concurrent tasks. `question_substring` further
    scopes behavior to one item, so a multi-item test can make ONE item's
    samples fail without affecting another item's identically-timed
    samples.

    fail_n_times: {(question_substring, temperature): n} -- that pair
        raises a transient error n times, then succeeds.
    permanent_fail: {(question_substring, temperature)} -- that pair always
        raises (simulates an item that never recovers).
    """

    def __init__(self, fail_n_times=None, permanent_fail=None):
        self._fail_n_times = dict(fail_n_times or {})
        self._permanent_fail = set(permanent_fail or set())
        self.calls: list[dict] = []

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"model": model, "role": role, "temperature": temperature, "thinking": thinking, "user": user})

        if _find_key(self._permanent_fail, user, temperature) is not None:
            raise RuntimeError("simulated permanent transient failure")

        fkey = _find_key(self._fail_n_times, user, temperature)
        if fkey is not None and self._fail_n_times[fkey] > 0:
            self._fail_n_times[fkey] -= 1
            raise TimeoutError("simulated transient failure")

        letter = "A" if temperature < 0.5 else "B"
        return JsonCallResult(
            data={"letter": letter, "confidence": round(min(0.99, temperature + 0.1), 3), "reasoning": f"reasoning@{temperature}"},
            usage=CallUsage(model=model, input_tokens=5, output_tokens=5, cost_usd=0.0, role=role),
        )


# ---------------------------------------------------------------------------
# (a) K ordered samples with all required fields
# ---------------------------------------------------------------------------


def test_generate_pool_writes_k_ordered_samples_with_all_fields_cheap_tier():
    client = FakePoolClient()
    items = [_item("q1", question="What is 2+2?")]

    rows, dropped = asyncio.run(generate_pool(client, items, k=4, solver_tier="cheap", concurrency=2, sleep_fn=_no_sleep))

    assert dropped == []
    assert len(rows) == 1
    row = rows[0]
    assert row["question_id"] == "q1"
    assert row["k"] == 4
    assert row["solver_tier"] == "cheap"
    assert row["solver_model"] == MECHANICAL_MODEL
    assert row["item"]["correct_letter"] == "A"
    assert row["item"]["choices"] == ["opt1", "opt2", "opt3", "opt4"]

    samples = row["samples"]
    assert len(samples) == 4
    assert [s["sample_index"] for s in samples] == [0, 1, 2, 3]
    for i, s in enumerate(samples):
        expected_temp = SC_TEMPERATURE_SCHEDULE[i % len(SC_TEMPERATURE_SCHEDULE)]
        assert s["question_id"] == "q1"
        assert s["letter"] in ("A", "B")
        assert s["confidence"] == round(min(0.99, expected_temp + 0.1), 3)
        assert s["reasoning"] == f"reasoning@{expected_temp}"
        assert set(s["usage"].keys()) >= {"model", "input_tokens", "output_tokens", "cost_usd", "role"}
        assert s["usage"]["role"] == "solver"  # _solve_one's hardcoded role

    # cheap tier: thinking=False and MECHANICAL_MODEL on every call.
    assert all(c["thinking"] is False for c in client.calls)
    assert all(c["model"] == MECHANICAL_MODEL for c in client.calls)


def test_generate_pool_flagship_tier_uses_orchestrator_model_and_thinking_true():
    client = FakePoolClient()
    items = [_item("q1", question="A flagship-tier question")]

    rows, dropped = asyncio.run(generate_pool(client, items, k=3, solver_tier="flagship", concurrency=3, sleep_fn=_no_sleep))

    assert dropped == []
    row = rows[0]
    assert row["solver_tier"] == "flagship"
    assert row["solver_model"] == ORCHESTRATOR_MODEL
    assert len(row["samples"]) == 3
    assert row["samples"][0]["usage"]["role"] == "solver_thinking"  # _solve_one_thinking's hardcoded role
    assert all(c["thinking"] is True for c in client.calls)
    assert all(c["model"] == ORCHESTRATOR_MODEL for c in client.calls)


def test_generate_pool_multiple_items_all_survive():
    client = FakePoolClient()
    items = [_item("q1", question="question one"), _item("q2", question="question two", correct_letter="B")]

    rows, dropped = asyncio.run(generate_pool(client, items, k=2, solver_tier="cheap", concurrency=4, sleep_fn=_no_sleep))

    assert dropped == []
    assert {r["question_id"] for r in rows} == {"q1", "q2"}
    assert all(len(r["samples"]) == 2 for r in rows)


def test_generate_pool_rejects_bad_solver_tier():
    client = FakePoolClient()
    items = [_item("q1")]
    with pytest.raises(ValueError, match="solver-tier"):
        asyncio.run(generate_pool(client, items, k=2, solver_tier="bogus", concurrency=1, sleep_fn=_no_sleep))


# ---------------------------------------------------------------------------
# (b) retry-on-transient-error recovers
# ---------------------------------------------------------------------------


def test_retry_recovers_from_transient_failure_then_succeeds():
    temp0 = SC_TEMPERATURE_SCHEDULE[0]  # sample_index=0's temperature
    client = FakePoolClient(fail_n_times={("q1", temp0): 2})  # fails twice, then succeeds
    items = [_item("q1", question="q1 question text")]

    rows, dropped = asyncio.run(generate_pool(client, items, k=1, solver_tier="cheap", concurrency=1, sleep_fn=_no_sleep))

    assert dropped == []
    assert len(rows) == 1
    assert len(rows[0]["samples"]) == 1
    # 2 failed attempts + 1 successful attempt.
    assert len(client.calls) == 3


def test_retry_succeeds_on_the_very_last_allowed_attempt():
    temp0 = SC_TEMPERATURE_SCHEDULE[0]
    # Fails _MAX_ATTEMPTS - 1 times, succeeding exactly on the last try.
    client = FakePoolClient(fail_n_times={("q1", temp0): _MAX_ATTEMPTS - 1})
    items = [_item("q1", question="q1 question text")]

    rows, dropped = asyncio.run(generate_pool(client, items, k=1, solver_tier="cheap", concurrency=1, sleep_fn=_no_sleep))

    assert dropped == []
    assert len(rows) == 1
    assert len(client.calls) == _MAX_ATTEMPTS


def test_retry_does_not_fire_on_a_clean_success():
    client = FakePoolClient()
    items = [_item("q1")]

    rows, dropped = asyncio.run(generate_pool(client, items, k=3, solver_tier="cheap", concurrency=1, sleep_fn=_no_sleep))

    assert dropped == []
    assert len(client.calls) == 3  # exactly one call per sample, no wasted retries


# ---------------------------------------------------------------------------
# (c) permanently failing sample drops the WHOLE item, with a warning
# ---------------------------------------------------------------------------


def test_permanently_failing_sample_drops_whole_item_with_warning(caplog):
    temp1 = SC_TEMPERATURE_SCHEDULE[1]  # sample_index=1's temperature
    client = FakePoolClient(permanent_fail={("q1", temp1)})
    items = [_item("q1", question="q1 question text")]

    with caplog.at_level(logging.WARNING):
        rows, dropped = asyncio.run(generate_pool(client, items, k=2, solver_tier="cheap", concurrency=1, sleep_fn=_no_sleep))

    assert rows == []
    assert dropped == ["q1"]
    assert any("q1" in r.message and "DROPPED" in r.message for r in caplog.records)

    # sample_index=1 (temperature=temp1) must have been retried the full
    # _MAX_ATTEMPTS times before giving up -- not silently given up on
    # early, and not retried forever either.
    n_calls_failing_sample = sum(1 for c in client.calls if c["temperature"] == temp1)
    assert n_calls_failing_sample == _MAX_ATTEMPTS


def test_one_permanently_failing_item_does_not_block_other_items():
    temp1 = SC_TEMPERATURE_SCHEDULE[1]
    # Only "q_bad"'s sample_index=1 fails permanently -- "q_good" shares the
    # same temperature schedule but a different question text, so it must
    # be unaffected.
    client = FakePoolClient(permanent_fail={("q_bad question", temp1)})
    items = [
        _item("q_bad", question="q_bad question text"),
        _item("q_good", question="q_good question text"),
    ]

    rows, dropped = asyncio.run(generate_pool(client, items, k=2, solver_tier="cheap", concurrency=4, sleep_fn=_no_sleep))

    assert dropped == ["q_bad"]
    assert [r["question_id"] for r in rows] == ["q_good"]
    assert len(rows[0]["samples"]) == 2


def test_dropped_item_never_appears_as_a_partial_row():
    """A permanently-failing sample must never produce a row with fewer
    than k samples -- score_selectors.py's prefix subsampling assumes every
    row is complete."""
    temp2 = SC_TEMPERATURE_SCHEDULE[2]
    client = FakePoolClient(permanent_fail={("q1", temp2)})
    items = [_item("q1", question="q1 question text")]

    rows, dropped = asyncio.run(generate_pool(client, items, k=3, solver_tier="cheap", concurrency=1, sleep_fn=_no_sleep))

    assert rows == []
    assert dropped == ["q1"]
