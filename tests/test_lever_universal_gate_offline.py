"""Offline tests for the universal_gate lever (benchmark/lever_experiments.py)
-- no live API calls, no cost.

universal_gate is the gate-recall lever from
benchmark/results/unanimous_gate_headroom.md: escalate EVERY unanimous panel
to the tribunal, unconditionally -- no doubt-check, no subject filter. It
tests whether the 47.6%-recovery / 0.8%-breakage asymmetry measured on
EXISTING doubt-gates (which only fire on detectable doubt) holds when nothing
is filtered.

MUST be run live only on fresh, unburned seeds -- see BURNED_SEEDS in
benchmark/score_selectors.py.

Mirrors the fake-client pattern in tests/test_lever_chem_thinking_gate_offline.py.
"""

import asyncio

import benchmark.lever_experiments as lever_experiments
from quorumqa.config import MECHANICAL_MODEL
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class RecordingClient:
    """All solvers agree on `solver_letter` by default (unanimous), or a
    scripted per-seat sequence if `solver_letters` is given (to force a
    split). Fails loudly on an unexpected role or an unexpected "gate" call
    -- universal_gate must never invoke second_opinion_gate."""

    def __init__(self, solver_letter="B", solver_letters=None, judge_letter=None):
        self.calls = []
        self._solver_letter = solver_letter
        self._solver_letters = list(solver_letters) if solver_letters else None
        self._judge_letter = judge_letter or solver_letter

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "thinking": thinking})
        if role in ("solver", "solver_thinking"):
            if self._solver_letters:
                letter = self._solver_letters.pop(0)
            else:
                letter = self._solver_letter
            return JsonCallResult(
                data={"letter": letter, "confidence": 0.7, "reasoning": "because"}, usage=_usage(role),
            )
        if role == "gate":
            raise AssertionError(
                "universal_gate must escalate unconditionally and must NEVER call "
                "second_opinion_gate (role='gate')"
            )
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
                    "final_letter": self._judge_letter, "decisive_reasoning": "confirmed",
                    "dissent": None, "overturned_plurality": False, "confidence": "high",
                },
                usage=_usage("judge"),
            )
        raise AssertionError(f"unexpected role {role!r}")


def _item(subject="Quantum Mechanics", correct_letter="B", question_id="q"):
    return GPQAItem(
        question_id=question_id, question="What is 2+2?", choices=["3", "4", "5", "6"],
        correct_letter=correct_letter, subject=subject,
    )


def test_unanimous_panel_always_escalates_regardless_of_subject():
    for subject in ("Quantum Mechanics", "Organic Chemistry", None):
        client = RecordingClient(solver_letter="B")
        result, note = asyncio.run(
            lever_experiments.run_question_lever(client, None, _item(subject=subject), "universal_gate")
        )
        assert result.escalated is True, f"subject={subject!r} did not escalate"
        assert note == "universal-unconditional"


def test_no_doubt_gate_call_is_ever_made():
    """The RecordingClient raises if role='gate' is called at all -- this
    test passing at all is the proof."""
    client = RecordingClient(solver_letter="A")
    asyncio.run(lever_experiments.run_question_lever(client, None, _item(), "universal_gate"))
    gate_calls = [c for c in client.calls if c["role"] == "gate"]
    assert gate_calls == []


def test_uses_the_standard_cheap_panel_not_a_special_one():
    """universal_gate is not in any special-panel branch, so it must fall
    through to the default shipped cheap panel -- same as plain 'gate'."""
    client = RecordingClient(solver_letter="C")
    asyncio.run(lever_experiments.run_question_lever(client, None, _item(), "universal_gate"))
    solver_calls = [c for c in client.calls if c["role"] in ("solver", "solver_thinking")]
    assert len(solver_calls) == 3
    assert all(c["model"] == MECHANICAL_MODEL for c in solver_calls)
    assert all(c["thinking"] is False for c in solver_calls)


def test_split_panel_still_reaches_the_tribunal_normally():
    """A split (non-unanimous) panel already escalates for every lever --
    universal_gate must not change that path or double-escalate it."""
    client = RecordingClient(solver_letters=["A", "A", "B"], judge_letter="A")
    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, _item(correct_letter="A"), "universal_gate")
    )
    assert result.escalated is True
    assert result.final_letter == "A"


def test_universal_gate_recovers_a_unanimous_wrong_item():
    """The mechanism this lever exists to test: a unanimous-wrong panel that
    a doubt-gate would never see reaches the Judge and can be corrected."""
    client = RecordingClient(solver_letter="A", judge_letter="B")
    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, _item(correct_letter="B"), "universal_gate")
    )
    assert result.escalated is True
    assert result.plurality_letter == "A"  # unanimous wrong
    assert result.final_letter == "B"  # tribunal recovered it
    assert result.correct is True


def test_universal_gate_is_a_valid_cli_choice():
    """Guards against re-adding the branch without registering it -- the
    exact mistake the degeneracy-guard drift (C1, this session) made."""
    import argparse
    import re

    src = open(lever_experiments.__file__, encoding="utf-8").read()
    m = re.search(r'parser\.add_argument\("--lever".*?choices=\[(.*?)\]\)', src, re.S)
    assert m, "could not find the --lever argparse definition"
    assert '"universal_gate"' in m.group(1)
