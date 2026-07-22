"""Offline tests for the chem_thinking_gate lever (benchmark/lever_experiments.py)
-- no live API calls, no cost. chem_thinking_gate stacks chem_flagship_gate's
Organic-Chemistry solver routing on top of thinking_gate's non-chemistry
solver panel, with the universal second_opinion_gate doubt-check applying to
unanimous answers everywhere, exactly as both parent levers do.

MUST be tested on FRESH seeds only when run live -- its parents
(chem_flagship_gate, thinking_gate) were tuned/validated on seeds
42/7/123/555/777/888; all of those are burned for this lever.

Mirrors the fake-client pattern in tests/test_engine_offline.py and
tests/test_lever_qwen38_judge_offline.py."""

import asyncio
import inspect

import benchmark.lever_experiments as lever_experiments
from quorumqa.config import MECHANICAL_MODEL, ORCHESTRATOR_MODEL
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class RecordingClient:
    """Records every chat_json call's (role, model, thinking) so tests can
    assert on solver-panel routing without caring about the exact JSON
    payload returned for uninteresting roles. All solvers agree on the same
    letter unless overridden, so unanimity (and therefore the gate) is
    exercised by default."""

    def __init__(self, solver_letter="B", gate_doubt=False):
        self.calls = []
        self._solver_letter = solver_letter
        self._gate_doubt = gate_doubt

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "thinking": thinking})
        if role in ("solver", "solver_thinking"):
            return JsonCallResult(
                data={"letter": self._solver_letter, "confidence": 0.7, "reasoning": "because"},
                usage=_usage(role),
            )
        if role == "gate":
            return JsonCallResult(data={"doubt": self._gate_doubt, "reason": "looks fine"}, usage=_usage("gate"))
        if role == "skeptic":
            return JsonCallResult(
                data={"target_letter": self._solver_letter, "disputed_step": "step X", "argument": "argument Y"},
                usage=_usage("skeptic"),
            )
        if role == "verifier":
            return JsonCallResult(data={"claims": []}, usage=_usage("verifier"))
        if role == "judge":
            return JsonCallResult(
                data={
                    "final_letter": self._solver_letter,
                    "decisive_reasoning": "confirmed",
                    "dissent": None,
                    "overturned_plurality": False,
                    "confidence": "high",
                },
                usage=_usage("judge"),
            )
        raise AssertionError(f"unexpected role {role!r}")


def _item(subject, correct_letter="B", question_id="q"):
    return GPQAItem(
        question_id=question_id, question="What is 2+2?", choices=["3", "4", "5", "6"],
        correct_letter=correct_letter, subject=subject,
    )


# ---------------------------------------------------------------------------
# (a) Organic Chemistry -> three-flagship-thinking panel, exactly as
#     chem_flagship_gate's chemistry branch
# ---------------------------------------------------------------------------


def test_chem_question_routes_to_flagship_thinking_panel():
    client = RecordingClient()
    item = _item(subject="Organic Chemistry")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "chem_thinking_gate")
    )

    solver_calls = [c for c in client.calls if c["role"] in ("solver", "solver_thinking")]
    assert len(solver_calls) == 3
    assert all(c["role"] == "solver_thinking" for c in solver_calls)
    assert all(c["model"] == ORCHESTRATOR_MODEL for c in solver_calls)
    assert all(c["thinking"] is True for c in solver_calls)


# ---------------------------------------------------------------------------
# (b) non-chemistry -> thinking-seat panel (seats 1-2 plain flash, seat 3
#     thinking flash), exactly as thinking_gate's panel
# ---------------------------------------------------------------------------


def test_non_chem_question_routes_to_thinking_seat_panel():
    client = RecordingClient()
    item = _item(subject="Quantum Mechanics")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "chem_thinking_gate")
    )

    solver_calls = [c for c in client.calls if c["role"] in ("solver", "solver_thinking")]
    assert len(solver_calls) == 3
    assert all(c["model"] == MECHANICAL_MODEL for c in solver_calls)

    plain = [c for c in solver_calls if c["role"] == "solver"]
    thinking = [c for c in solver_calls if c["role"] == "solver_thinking"]
    assert len(plain) == 2
    assert all(c["thinking"] is False for c in plain)
    assert len(thinking) == 1
    assert thinking[0]["thinking"] is True


# ---------------------------------------------------------------------------
# (c) unanimous answers still trigger the universal doubt-gate, both on and
#     off the chemistry branch
# ---------------------------------------------------------------------------


def test_unanimous_non_chem_answer_triggers_gate():
    client = RecordingClient(gate_doubt=False)
    item = _item(subject="Quantum Mechanics")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "chem_thinking_gate")
    )

    gate_calls = [c for c in client.calls if c["role"] == "gate"]
    assert len(gate_calls) == 1
    assert result.escalated is False
    assert result.final_letter == "B"


def test_unanimous_chem_answer_also_triggers_gate():
    # The gate is universal -- it must not be skipped just because the
    # chemistry branch already spent flagship-tier reasoning on this
    # question.
    client = RecordingClient(gate_doubt=False)
    item = _item(subject="Organic Chemistry")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "chem_thinking_gate")
    )

    gate_calls = [c for c in client.calls if c["role"] == "gate"]
    assert len(gate_calls) == 1
    assert result.escalated is False


def test_gate_doubt_forces_escalation_on_unanimous_chem_answer():
    client = RecordingClient(gate_doubt=True)
    item = _item(subject="Organic Chemistry", correct_letter="B")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "chem_thinking_gate")
    )

    assert result.escalated is True
    assert note is not None and note.startswith("gate-flagged")


# ---------------------------------------------------------------------------
# (d) argparse accepts the new lever name
# ---------------------------------------------------------------------------


def test_chem_thinking_gate_present_in_argparse_choices():
    # Regression guard: the CLI must actually expose the lever, not just the
    # underlying functions.
    source = inspect.getsource(lever_experiments)
    assert '"chem_thinking_gate"' in source
