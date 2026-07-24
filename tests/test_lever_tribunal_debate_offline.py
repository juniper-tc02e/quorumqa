"""Offline tests for the tribunal_debate lever (benchmark/lever_experiments.py,
docs/reasoning-supercharge-plan.md W4 -- escalation-only debate round).
CONDITIONAL lever: built now, run only if W1/W2 screen positive -- these
tests prove the machinery works, nothing here runs a live pilot. No live
API calls, no cost.

Base solver panel = thinking_gate's (solve_all_thinking_seat +
second_opinion_gate). Every escalation runs the shipped one-shot tribunal
first (skeptic -> verifier -> judge, unchanged) and its ruling is recorded
as the ONE-SHOT ruling. ONLY escalations with a genuine minority (>=1 seat
differing from the plurality) get a structured rebuttal round: one call per
minority seat, then a SECOND judge call over the full exchange. Covers:

  (a) split escalation with a genuine minority -> minority seat(s) called
      with the correct framing (system names both letters), majority
      reasoning + verifier findings reach the minority call, concession
      JSON parsed, both rulings logged, final = post-debate ruling.
  (b) all-concede path: concession_rate=1.0, ruling unchanged when the
      minority concedes and the post-debate judge agrees.
  (c) counter-argue path: concession_rate=0.0, ruling_changed=True when
      the post-debate judge is swayed by the minority's counter-argument.
  (d) unanimous-but-gate-fired escalation -> debate_applicable=false, NO
      minority_rebuttal/post_debate_judge calls at all (proven by NOT
      scripting those roles -- an unscripted call raises AssertionError).
  (e) non-escalated (gate confident, no doubt) -> no tribunal, no debate
      machinery at all; note carries the default all-empty debate dict.
  (f) _build_output_row folds the W4 note fields into the row.
  (g) tribunal_debate is a real argparse --lever choice.

Mirrors the ScriptedClient/RecordingClient fake-client patterns in
tests/test_lever_verified_gate_offline.py and
tests/test_lever_rag_thinking_gate_offline.py.
"""

import asyncio
import inspect

import pytest

import benchmark.lever_experiments as lever_experiments
from quorumqa.config import MECHANICAL_MODEL
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class ScriptedClient:
    """Fake QwenClient for tribunal_debate. `solver_letters` is consumed in
    order across thinking_gate's three solver calls (roles "solver" for
    seats 1-2, "solver_thinking" for seat 3 -- see solve_all_thinking_seat).
    `gate_doubt` controls second_opinion_gate's verdict on a unanimous
    plurality. Every other role must have a scripted response in
    `responses`: either ONE JsonCallResult (returned every time that role
    is called) or a LIST of JsonCallResult (consumed in order -- needed for
    "verifier" when a claim is scripted, since verify() calls it twice
    [extract, finalize], and for "minority_rebuttal" when there is more
    than one minority seat). An unscripted role raises AssertionError,
    which is exactly how "no debate calls happened" is proven."""

    def __init__(self, solver_letters, gate_doubt=False, responses=None):
        self.calls = []
        self._solver_letters = list(solver_letters)
        self._solver_idx = 0
        self._gate_doubt = gate_doubt
        self._responses = responses or {}
        self._role_counts = {}

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "system": system, "user": user, "thinking": thinking})
        if role in ("solver", "solver_thinking"):
            letter = self._solver_letters[self._solver_idx]
            self._solver_idx += 1
            return JsonCallResult(
                data={"letter": letter, "confidence": 0.7, "reasoning": f"reasoning for {letter}"},
                usage=_usage(role),
            )
        if role == "gate":
            return JsonCallResult(data={"doubt": self._gate_doubt, "reason": "gate reason"}, usage=_usage("gate"))
        if role in self._responses:
            resp = self._responses[role]
            if isinstance(resp, list):
                idx = self._role_counts.get(role, 0)
                self._role_counts[role] = idx + 1
                return resp[idx]
            return resp
        raise AssertionError(f"unexpected role {role!r} with no scripted response (calls so far: {self.calls})")


def _tribunal_responses(one_shot_letter, plurality_letter, overturned=None, verifier_claims=None):
    overturned = (one_shot_letter != plurality_letter) if overturned is None else overturned
    responses = {
        "skeptic": JsonCallResult(
            data={"target_letter": plurality_letter, "disputed_step": "the disputed step", "argument": "the skeptic's argument"},
            usage=_usage("skeptic"),
        ),
        "judge": JsonCallResult(
            data={
                "final_letter": one_shot_letter, "decisive_reasoning": "one-shot ruling",
                "dissent": None, "overturned_plurality": overturned, "confidence": "high",
            },
            usage=_usage("judge"),
        ),
    }
    if verifier_claims:
        findings = [{"claim": c["claim"], "supports_claim": True, "explanation": "checked"} for c in verifier_claims]
        responses["verifier"] = [
            JsonCallResult(data={"claims": verifier_claims}, usage=_usage("verifier")),
            JsonCallResult(data={"findings": findings}, usage=_usage("verifier")),
        ]
    else:
        responses["verifier"] = JsonCallResult(data={"claims": []}, usage=_usage("verifier"))
    return responses


class FakeToolSession:
    async def call(self, tool_name, arguments):
        return {"ok": True, "value": 1.0}


def _item(question_id="td1", correct_letter="A"):
    return GPQAItem(question_id=question_id, question="Q?", choices=["1", "2", "3", "4"], correct_letter=correct_letter)


# ---------------------------------------------------------------------------
# (a)/(b) split escalation, genuine minority, all-concede path
# ---------------------------------------------------------------------------


def test_split_escalation_minority_called_with_correct_framing_and_concedes():
    item = _item(correct_letter="A")
    verifier_claims = [{"claim": "the constant is 3.0", "tool": "lookup_constant", "arguments": {"name": "x"}}]
    responses = _tribunal_responses(one_shot_letter="A", plurality_letter="A", overturned=False, verifier_claims=verifier_claims)
    responses["minority_rebuttal"] = JsonCallResult(
        data={"concede": True, "reason": "the majority's argument holds up", "counter_argument": ""},
        usage=_usage("minority_rebuttal"),
    )
    responses["post_debate_judge"] = JsonCallResult(
        data={
            "final_letter": "A", "decisive_reasoning": "post-debate ruling",
            "dissent": None, "overturned_plurality": False, "confidence": "high",
        },
        usage=_usage("post_debate_judge"),
    )
    client = ScriptedClient(solver_letters=["A", "A", "B"], responses=responses)  # split: plurality A (2), minority B (1)

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "tribunal_debate")
    )

    assert result.escalated is True
    assert result.plurality_letter == "A"
    assert result.final_letter == "A"
    assert result.correct is True

    assert note["debate_applicable"] is True
    assert note["minority_seats"] == ["B"]
    assert note["concessions"] == [{"letter": "B", "concede": True, "reason": "the majority's argument holds up"}]
    assert note["concession_rate"] == 1.0
    assert note["ruling_changed"] is False
    assert note["one_shot_ruling"]["decisive_reasoning"] == "one-shot ruling"
    assert note["one_shot_ruling"]["final_letter"] == "A"
    assert note["post_debate_ruling"]["decisive_reasoning"] == "post-debate ruling"
    assert note["post_debate_ruling"]["final_letter"] == "A"

    minority_calls = [c for c in client.calls if c["role"] == "minority_rebuttal"]
    assert len(minority_calls) == 1
    # System framing names both the minority seat's own letter and the
    # majority's letter, per docs/reasoning-supercharge-plan.md W4's spec.
    assert "answered B" in minority_calls[0]["system"]
    assert "majority answered A" in minority_calls[0]["system"]
    # The minority call sees the majority's reasoning and the verifier's
    # findings (both required inputs per the build spec).
    assert "reasoning for A" in minority_calls[0]["user"]
    assert "the constant is 3.0" in minority_calls[0]["user"]

    post_debate_calls = [c for c in client.calls if c["role"] == "post_debate_judge"]
    assert len(post_debate_calls) == 1
    assert "CONCEDED" in post_debate_calls[0]["user"]
    assert "the majority's argument holds up" in post_debate_calls[0]["user"]
    # The verifier findings reach the post-debate judge too, not just the
    # minority call.
    assert "the constant is 3.0" in post_debate_calls[0]["user"]

    # Exactly one one-shot judge call and one post-debate judge call --
    # never conflated into the same tag.
    assert len([c for c in client.calls if c["role"] == "judge"]) == 1


# ---------------------------------------------------------------------------
# (c) counter-argue path: minority holds its position, post-debate judge is
#     swayed -> ruling_changed True, final = post-debate (overturned)
# ---------------------------------------------------------------------------


def test_split_escalation_minority_counter_argues_and_ruling_changes():
    item = _item(correct_letter="D")
    responses = _tribunal_responses(one_shot_letter="A", plurality_letter="A", overturned=False)
    responses["minority_rebuttal"] = JsonCallResult(
        data={"concede": False, "reason": "I still believe D is right", "counter_argument": "The majority ignored a key constraint that only D satisfies."},
        usage=_usage("minority_rebuttal"),
    )
    responses["post_debate_judge"] = JsonCallResult(
        data={
            "final_letter": "D", "decisive_reasoning": "the counter-argument was decisive",
            "dissent": None, "overturned_plurality": True, "confidence": "high",
        },
        usage=_usage("post_debate_judge"),
    )
    client = ScriptedClient(solver_letters=["A", "A", "D"], responses=responses)

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "tribunal_debate")
    )

    assert result.escalated is True
    assert result.plurality_letter == "A"
    assert result.final_letter == "D"  # post-debate ruling wins, not the one-shot ruling
    assert result.correct is True
    assert result.verdict.overturned_plurality is True

    assert note["debate_applicable"] is True
    assert note["minority_seats"] == ["D"]
    assert note["concessions"] == [{"letter": "D", "concede": False, "reason": "I still believe D is right"}]
    assert note["concession_rate"] == 0.0
    assert note["ruling_changed"] is True  # post-debate "D" != one-shot "A"
    assert note["one_shot_ruling"]["final_letter"] == "A"
    assert note["post_debate_ruling"]["final_letter"] == "D"

    post_debate_calls = [c for c in client.calls if c["role"] == "post_debate_judge"]
    assert "MAINTAINED" in post_debate_calls[0]["user"]
    assert "The majority ignored a key constraint that only D satisfies." in post_debate_calls[0]["user"]


# ---------------------------------------------------------------------------
# (d) unanimous-but-gate-fired escalation -> NO minority, NO debate round
# ---------------------------------------------------------------------------


def test_unanimous_gate_fired_escalation_has_no_minority_no_debate_calls():
    item = _item(correct_letter="C")
    responses = _tribunal_responses(one_shot_letter="C", plurality_letter="C", overturned=False)
    # Deliberately NOT scripting "minority_rebuttal"/"post_debate_judge" --
    # any call to either raises AssertionError, proving the debate round
    # never runs for a unanimous-but-gate-fired escalation.
    client = ScriptedClient(solver_letters=["C", "C", "C"], gate_doubt=True, responses=responses)

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "tribunal_debate")
    )

    assert result.escalated is True
    assert result.plurality_letter == "C"
    assert result.final_letter == "C"
    assert result.correct is True

    assert note["debate_applicable"] is False
    assert note["minority_seats"] == []
    assert note["concessions"] == []
    assert note["concession_rate"] is None
    assert note["ruling_changed"] is False
    # Final == one-shot ruling verbatim when no debate ran.
    assert note["one_shot_ruling"]["final_letter"] == "C"
    assert note["post_debate_ruling"] == note["one_shot_ruling"]

    gate_calls = [c for c in client.calls if c["role"] == "gate"]
    assert len(gate_calls) == 1
    assert not any(c["role"] in ("minority_rebuttal", "post_debate_judge") for c in client.calls)


# ---------------------------------------------------------------------------
# (e) non-escalated -> no tribunal, no debate machinery at all
# ---------------------------------------------------------------------------


def test_non_escalated_no_debate_machinery_at_all():
    item = _item(correct_letter="A")
    client = ScriptedClient(solver_letters=["A", "A", "A"], gate_doubt=False)
    # No tribunal/debate roles scripted at all -- any call beyond the 3
    # solver calls + 1 gate call raises AssertionError.

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "tribunal_debate")
    )

    assert result.escalated is False
    assert result.final_letter == "A"
    assert result.correct is True

    assert note["debate_applicable"] is False
    assert note["minority_seats"] == []
    assert note["concessions"] == []
    assert note["concession_rate"] is None
    assert note["ruling_changed"] is False
    assert note["one_shot_ruling"] is None
    assert note["post_debate_ruling"] is None

    # 2 plain solver seats + 1 thinking seat + 1 gate call, nothing else.
    assert len(client.calls) == 4
    solver_calls = [c for c in client.calls if c["role"] in ("solver", "solver_thinking")]
    assert len(solver_calls) == 3
    plain = [c for c in solver_calls if c["role"] == "solver"]
    thinking = [c for c in solver_calls if c["role"] == "solver_thinking"]
    assert len(plain) == 2 and all(c["thinking"] is False for c in plain)
    assert len(thinking) == 1 and thinking[0]["thinking"] is True
    assert all(c["model"] == MECHANICAL_MODEL for c in solver_calls)


# ---------------------------------------------------------------------------
# (f) _build_output_row folds the W4 note fields into the row
# ---------------------------------------------------------------------------


def test_build_output_row_folds_tribunal_debate_fields():
    item = _item(correct_letter="A")
    responses = _tribunal_responses(one_shot_letter="A", plurality_letter="A", overturned=False)
    responses["minority_rebuttal"] = JsonCallResult(
        data={"concede": True, "reason": "convinced", "counter_argument": ""}, usage=_usage("minority_rebuttal"),
    )
    responses["post_debate_judge"] = JsonCallResult(
        data={"final_letter": "A", "decisive_reasoning": "post-debate ruling", "dissent": None,
              "overturned_plurality": False, "confidence": "high"},
        usage=_usage("post_debate_judge"),
    )
    client = ScriptedClient(solver_letters=["A", "A", "B"], responses=responses)

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "tribunal_debate")
    )
    row = lever_experiments._build_output_row(result, "tribunal_debate", 42, "gpqa", None, None, note)

    assert row["lever"] == "tribunal_debate"
    assert row["debate_applicable"] is True
    assert row["minority_seats"] == ["B"]
    assert row["concessions"] == [{"letter": "B", "concede": True, "reason": "convinced"}]
    assert row["concession_rate"] == 1.0
    assert row["ruling_changed"] is False
    assert row["one_shot_ruling"]["final_letter"] == "A"
    assert row["post_debate_ruling"]["final_letter"] == "A"
    assert row["engine"]["escalated"] is True
    assert row["engine"]["final_letter"] == "A"


def test_build_output_row_unaffected_for_other_levers_when_note_absent():
    # Backward-compat guard: a pre-existing lever's row shape is unaffected
    # by tribunal_debate's new note-folding branch.
    item = _item(correct_letter="A")
    client = ScriptedClient(solver_letters=["A", "A", "A"], gate_doubt=False)
    result, _note = asyncio.run(lever_experiments.run_question_lever(client, FakeToolSession(), item, "gate"))

    row = lever_experiments._build_output_row(result, "gate", 42, "gpqa")
    assert "debate_applicable" not in row
    assert "one_shot_ruling" not in row


# ---------------------------------------------------------------------------
# (g) tribunal_debate registered in the CLI's --lever choices
# ---------------------------------------------------------------------------


def test_tribunal_debate_present_in_argparse_choices():
    source = inspect.getsource(lever_experiments)
    assert '"tribunal_debate"' in source
