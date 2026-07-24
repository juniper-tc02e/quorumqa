"""Offline tests for the verified_gate_flaw / verified_gate_cas levers
(benchmark/lever_experiments.py, docs/reasoning-supercharge-plan.md W1) and
the new sympy_check/substitute_check MCP tools they lean on
(src/quorumqa/tools/mcp_server.py, W1 Build 2) -- no live API calls, no
cost. Covers:

  (a) sympy_check / substitute_check unit tests: pass/fail/unparseable,
      LaTeX + plain relations, substitute_check's numeric tolerance.
  (b) Arm A (flaw-finder): unanimous+flaw escalates and the tribunal's
      outcome is used; unanimous+no-flaw accepts with NO tribunal calls.
  (c) Arm B (computational check): checkable+pass accepts; checkable+fail
      escalates; unparseable accepts (fail-safe, same as not-checkable).
  (d) A non-unanimous (split) plurality escalates exactly like the shipped
      engine, WITHOUT ever calling either gate.
  (e) pre_gate_votes is logged (the byte-identical shipped-panel vote,
      before any gate runs) for every verified_gate_* case.
  (f) _build_output_row folds arm/unanimous/gate_fired/gate_reason/
      pre_gate_votes into the output row for both levers.
  (g) Both levers are registered in the CLI's --lever choices.

Mirrors the fake-client pattern in tests/test_lever_qwen38_panel_offline.py
and tests/test_lever_qwen38_judge_offline.py."""

import asyncio
import inspect

import pytest

import benchmark.lever_experiments as lever_experiments
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem
from quorumqa.tools import mcp_server


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class ScriptedClient:
    """A fake QwenClient. `solver_letters` is consumed in order across the
    three solve_all() solver calls (all role="solver", matching engine/
    solver.py's _solve_one). Every other role must have a scripted response
    in `responses` (a JsonCallResult, or a zero-arg callable returning one)
    -- an unscripted role raises AssertionError, which is exactly how these
    tests prove a call was (or wasn't) made (e.g. "no tribunal calls" is
    proven by NOT scripting skeptic/verifier/judge)."""

    def __init__(self, solver_letters, responses=None):
        self._solver_letters = list(solver_letters)
        self._solver_calls = 0
        self._responses = responses or {}
        self.calls = []  # (role, system, user) for every call made

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append((role, system, user))
        if role == "solver":
            letter = self._solver_letters[self._solver_calls]
            self._solver_calls += 1
            return JsonCallResult(
                data={"letter": letter, "confidence": 0.7, "reasoning": f"reasoning for {letter}"},
                usage=_usage("solver"),
            )
        if role in self._responses:
            resp = self._responses[role]
            return resp() if callable(resp) else resp
        raise AssertionError(f"unexpected role {role!r} with no scripted response (calls so far: {self.calls})")


def _tribunal_responses(final_letter, plurality_letter="A"):
    return {
        "skeptic": JsonCallResult(
            data={"target_letter": plurality_letter, "disputed_step": "step", "argument": "argument"},
            usage=_usage("skeptic"),
        ),
        "verifier": JsonCallResult(data={"claims": []}, usage=_usage("verifier")),
        "judge": JsonCallResult(
            data={
                "final_letter": final_letter, "decisive_reasoning": "tribunal ruling",
                "dissent": None, "overturned_plurality": final_letter != plurality_letter, "confidence": "high",
            },
            usage=_usage("judge"),
        ),
    }


# ---------------------------------------------------------------------------
# (a) sympy_check / substitute_check unit tests
# ---------------------------------------------------------------------------


def test_sympy_check_pass_plain_equation():
    result = mcp_server.sympy_check("2 * 3 + 4 = 10", "10")
    assert result["status"] == "pass"


def test_sympy_check_fail_plain_equation():
    result = mcp_server.sympy_check("2 * 3 + 4 = 11", "11")
    assert result["status"] == "fail"


def test_sympy_check_pass_with_free_symbol_substitution():
    result = mcp_server.sympy_check("x**2 - 9", "3")
    assert result["status"] == "pass"


def test_sympy_check_fail_with_free_symbol_substitution():
    result = mcp_server.sympy_check("x**2 - 9", "4")
    assert result["status"] == "fail"


def test_sympy_check_unparseable_never_raises():
    result = mcp_server.sympy_check("(((", "anything")
    assert result["status"] == "unparseable"
    assert "detail" in result


def test_sympy_check_unparseable_on_garbage_relation():
    # No exception even on input with no mathematical structure at all.
    result = mcp_server.sympy_check("this is not math at all !!!", "1")
    assert result["status"] == "unparseable"


def test_sympy_check_unparseable_with_too_many_free_symbols():
    result = mcp_server.sympy_check("x + y - 5", "3")
    assert result["status"] == "unparseable"


def test_sympy_check_accepts_latex_relation():
    result = mcp_server.sympy_check(r"\frac{1}{2} + \frac{1}{2} = 1", "1")
    assert result["status"] == "pass"


def test_sympy_check_accepts_latex_and_detects_mismatch():
    result = mcp_server.sympy_check(r"\sqrt{16} = 5", "5")
    assert result["status"] == "fail"


def test_substitute_check_pass_within_tolerance():
    result = mcp_server.substitute_check("x + 2 = 5", "x", "3")
    assert result["status"] == "pass"

    # Tiny floating-point noise (1e-10) is within the 1e-9 tolerance.
    close = mcp_server.substitute_check("x + 2 = 5", "x", "3.0000000001")
    assert close["status"] == "pass"


def test_substitute_check_fail_outside_tolerance():
    result = mcp_server.substitute_check("x + 2 = 5", "x", "3.1")
    assert result["status"] == "fail"


def test_substitute_check_unparseable_no_equals_sign():
    result = mcp_server.substitute_check("bad ill-formed no equals", "x", "1")
    assert result["status"] == "unparseable"


def test_substitute_check_unparseable_never_raises_on_bad_value():
    result = mcp_server.substitute_check("x + 2 = 5", "x", "not a number @@@")
    assert result["status"] == "unparseable"


# ---------------------------------------------------------------------------
# (b) Arm A -- flaw-finder
# ---------------------------------------------------------------------------


def test_verified_gate_flaw_unanimous_with_flaw_escalates_to_tribunal():
    item = GPQAItem(question_id="vgf1", question="Q?", choices=["1", "2", "3", "4"], correct_letter="B")
    client = ScriptedClient(
        solver_letters=["A", "A", "A"],  # unanimous WRONG plurality
        responses={
            "verified_gate_flaw": JsonCallResult(
                data={"flaw_found": True, "flaw": "misapplied a conservation law", "confidence": 0.9},
                usage=_usage("verified_gate_flaw"),
            ),
            **_tribunal_responses(final_letter="B", plurality_letter="A"),
        },
    )

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "verified_gate_flaw"))

    assert result.escalated is True
    assert result.plurality_letter == "A"
    assert result.final_letter == "B"
    assert result.correct is True
    assert result.verdict.decisive_reasoning == "tribunal ruling"

    assert note["arm"] == "flaw"
    assert note["unanimous"] is True
    assert note["gate_fired"] is True
    assert "misapplied a conservation law" in note["gate_reason"]
    assert len(note["pre_gate_votes"]) == 3
    assert all(v["letter"] == "A" for v in note["pre_gate_votes"])

    # The gate call went to ORCHESTRATOR_MODEL with thinking=True (framed as
    # verification, not solving), not the cheap gate's model/thinking shape.
    flaw_calls = [c for c in client.calls if c[0] == "verified_gate_flaw"]
    assert len(flaw_calls) == 1


def test_verified_gate_flaw_unanimous_no_flaw_accepts_without_tribunal():
    item = GPQAItem(question_id="vgf2", question="Q?", choices=["1", "2", "3", "4"], correct_letter="C")
    client = ScriptedClient(
        solver_letters=["C", "C", "C"],  # unanimous CORRECT
        responses={
            "verified_gate_flaw": JsonCallResult(
                data={"flaw_found": False, "flaw": "", "confidence": 0.85},
                usage=_usage("verified_gate_flaw"),
            ),
            # Deliberately NOT scripting skeptic/verifier/judge -- any call
            # to them raises AssertionError, proving no tribunal call fires.
        },
    )

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "verified_gate_flaw"))

    assert result.escalated is False
    assert result.final_letter == "C"
    assert result.correct is True
    assert note["gate_fired"] is False
    assert "no flaw found" in note["gate_reason"]
    # Only 3 solver calls + 1 gate call -- no tribunal calls at all.
    assert len(client.calls) == 4


# ---------------------------------------------------------------------------
# (c) Arm B -- computational (CAS) check
# ---------------------------------------------------------------------------


def test_verified_gate_cas_checkable_and_pass_accepts_without_tribunal():
    item = GPQAItem(question_id="vgc1", question="What is 6*7?", choices=["40", "41", "42", "43"], correct_letter="C")
    client = ScriptedClient(
        solver_letters=["C", "C", "C"],
        responses={
            "verified_gate_cas": JsonCallResult(
                data={"checkable": True, "relation": "6 * 7 = 42", "candidate": "42"},
                usage=_usage("verified_gate_cas"),
            ),
        },
    )

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "verified_gate_cas"))

    assert result.escalated is False
    assert result.final_letter == "C"
    assert note["arm"] == "cas"
    assert note["gate_fired"] is False
    assert "CAS check passed" in note["gate_reason"]
    assert len(client.calls) == 4  # 3 solver + 1 extraction, no tribunal


def test_verified_gate_cas_checkable_and_fail_escalates_to_tribunal():
    item = GPQAItem(question_id="vgc2", question="What is 6*7?", choices=["40", "41", "42", "43"], correct_letter="C")
    client = ScriptedClient(
        solver_letters=["B", "B", "B"],  # unanimous WRONG (41)
        responses={
            "verified_gate_cas": JsonCallResult(
                data={"checkable": True, "relation": "6 * 7 = 41", "candidate": "41"},
                usage=_usage("verified_gate_cas"),
            ),
            **_tribunal_responses(final_letter="C", plurality_letter="B"),
        },
    )

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "verified_gate_cas"))

    assert result.escalated is True
    assert result.final_letter == "C"
    assert result.correct is True
    assert note["gate_fired"] is True
    assert "CAS check failed" in note["gate_reason"]


def test_verified_gate_cas_not_checkable_accepts():
    item = GPQAItem(question_id="vgc3", question="Conceptual Q?", choices=["1", "2", "3", "4"], correct_letter="A")
    client = ScriptedClient(
        solver_letters=["A", "A", "A"],
        responses={
            "verified_gate_cas": JsonCallResult(
                data={"checkable": False, "relation": "", "candidate": ""},
                usage=_usage("verified_gate_cas"),
            ),
        },
    )

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "verified_gate_cas"))

    assert result.escalated is False
    assert note["gate_fired"] is False
    assert note["gate_reason"] == "not checkable"


def test_verified_gate_cas_unparseable_accepts_fail_safe():
    item = GPQAItem(question_id="vgc4", question="Q?", choices=["1", "2", "3", "4"], correct_letter="A")
    client = ScriptedClient(
        solver_letters=["A", "A", "A"],
        responses={
            "verified_gate_cas": JsonCallResult(
                data={"checkable": True, "relation": "(((", "candidate": "1"},
                usage=_usage("verified_gate_cas"),
            ),
        },
    )

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "verified_gate_cas"))

    # Unparseable is treated exactly like not-checkable: accept, never block
    # on a tool limitation.
    assert result.escalated is False
    assert note["gate_fired"] is False
    assert "unparseable" in note["gate_reason"].lower()


# ---------------------------------------------------------------------------
# (d) split plurality behaves exactly like the shipped engine, no gate call
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lever", ["verified_gate_flaw", "verified_gate_cas"])
def test_verified_gate_split_escalates_without_calling_either_gate(lever):
    item = GPQAItem(question_id="vgs1", question="Q?", choices=["1", "2", "3", "4"], correct_letter="D")
    client = ScriptedClient(
        solver_letters=["A", "A", "D"],  # split: plurality A (2 votes) vs D (1 vote)
        responses=_tribunal_responses(final_letter="D", plurality_letter="A"),
        # Deliberately no "verified_gate_flaw"/"verified_gate_cas" response
        # scripted -- if the gate were mistakenly called on a split, the
        # ScriptedClient would raise AssertionError and this test would fail.
    )

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, lever))

    assert result.escalated is True
    assert result.plurality_letter == "A"
    assert result.final_letter == "D"
    assert note["unanimous"] is False
    assert note["gate_fired"] is False
    assert note["gate_reason"] is None
    assert len(note["pre_gate_votes"]) == 3


# ---------------------------------------------------------------------------
# (e)/(f) pre_gate_votes + _build_output_row
# ---------------------------------------------------------------------------


def test_pre_gate_votes_records_shipped_panel_letters_and_reasoning():
    item = GPQAItem(question_id="vgv1", question="Q?", choices=["1", "2", "3", "4"], correct_letter="A")
    client = ScriptedClient(
        solver_letters=["A", "A", "A"],
        responses={
            "verified_gate_flaw": JsonCallResult(
                data={"flaw_found": False, "flaw": "", "confidence": 0.7}, usage=_usage("verified_gate_flaw"),
            ),
        },
    )

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "verified_gate_flaw"))

    votes = note["pre_gate_votes"]
    assert len(votes) == 3
    for v in votes:
        assert v["letter"] == "A"
        assert v["reasoning"] == "reasoning for A"
        assert "lens" in v and "confidence" in v


def test_build_output_row_folds_verified_gate_fields_into_row():
    item = GPQAItem(question_id="vgr1", question="Q?", choices=["1", "2", "3", "4"], correct_letter="A")
    client = ScriptedClient(
        solver_letters=["A", "A", "A"],
        responses={
            "verified_gate_cas": JsonCallResult(
                data={"checkable": False, "relation": "", "candidate": ""}, usage=_usage("verified_gate_cas"),
            ),
        },
    )
    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "verified_gate_cas"))

    row = lever_experiments._build_output_row(result, "verified_gate_cas", 42, "gpqa", None, None, note)

    assert row["lever"] == "verified_gate_cas"
    assert row["arm"] == "cas"
    assert row["unanimous"] is True
    assert row["gate_fired"] is False
    assert row["gate_reason"] == "not checkable"
    assert len(row["pre_gate_votes"]) == 3
    assert row["engine"]["escalated"] is False
    assert row["engine"]["final_letter"] == "A"
    assert row["engine"]["correct"] is True
    assert row["engine"]["calls"]  # usage objects present


def test_build_output_row_unaffected_for_other_levers_when_note_is_none():
    # Backward-compat guard: a pre-existing lever's row is byte-identical
    # whether or not the new `note` parameter is passed at all.
    item = GPQAItem(question_id="vgr2", question="Q?", choices=["1", "2", "3", "4"], correct_letter="A")
    client = ScriptedClient(
        solver_letters=["A", "A", "A"],
        responses={"gate": JsonCallResult(data={"doubt": False, "reason": ""}, usage=_usage("gate"))},
    )
    result, _note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "gate"))

    row_without_note = lever_experiments._build_output_row(result, "gate", 42, "gpqa")
    row_with_none_note = lever_experiments._build_output_row(result, "gate", 42, "gpqa", None, None, None)

    assert row_without_note == row_with_none_note
    assert "arm" not in row_without_note
    assert "pre_gate_votes" not in row_without_note


# ---------------------------------------------------------------------------
# (g) both levers registered in the CLI's --lever choices
# ---------------------------------------------------------------------------


def test_verified_gate_levers_present_in_argparse_choices():
    source = inspect.getsource(lever_experiments)
    assert '"verified_gate_flaw"' in source
    assert '"verified_gate_cas"' in source
