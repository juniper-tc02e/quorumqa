"""Offline tests for src/quorumqa/engine/profiles.py -- the M0 declarative
OrchestrationProfile registry (docs/mixture-of-orchestrations-plan.md section
7, "M0 -- Profile registry refactor"). No live API calls, no cost.

This suite has two jobs:

1. STRUCTURAL: assert each registry profile's declarative fields (panel
   seats, acceptance policy, tribunal, retrieval, subject overrides) encode
   the real config read from benchmark/lever_experiments.py and
   quorumqa/config.py -- cross-checked by hand against the lever source, not
   guessed.

2. EQUIVALENCE (the acceptance criterion for "zero behavior change"):
   for every registry profile, run BOTH the original lever path
   (benchmark.lever_experiments.run_question_lever, or
   quorumqa.baseline.solve_single_agent / quorumqa.engine.orchestrator.
   run_question for the two profiles with no lever equivalent) AND
   quorumqa.engine.profiles.run_profile against two separate RecordingClient
   instances configured with IDENTICAL canned responses, then assert the two
   clients recorded the EXACT SAME multiset of (role, model, thinking,
   temperature, system, user) calls. Comparing full system+user text (not
   just role/model) means lens content, evidence blocks, and question/choice
   formatting are all covered by the same assertion -- this is what proves
   run_profile dispatches to the identical underlying helpers with identical
   arguments, not just "produces the same final answer by coincidence".

   Call order is intentionally NOT part of the equivalence check: solver
   seats run concurrently via asyncio.gather(asyncio.to_thread(...)), so
   their relative order in a recording client's call log is not guaranteed
   stable even between two runs of the SAME code path. Comparing as a
   Counter (multiset) of call fingerprints sidesteps that non-determinism
   while still requiring the exact same calls, with the exact same
   arguments, the exact same number of times.
"""

import asyncio
from collections import Counter

import pytest

import benchmark.lever_experiments as lever_experiments
import quorumqa.engine.profiles as profiles
from quorumqa.baseline import solve_single_agent
from quorumqa.config import MECHANICAL_MODEL, ORCHESTRATOR_MODEL
from quorumqa.engine.orchestrator import run_question
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem


# ---------------------------------------------------------------------------
# shared fakes
# ---------------------------------------------------------------------------


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class RecordingClient:
    """Records every chat_json call's full (role, model, thinking,
    temperature, system, user) so two independently-driven runs (lever path
    vs profile path) can be compared call-for-call, not just result-for-
    result. `solver_letters` may be a single letter (every seat agrees) or a
    list consumed in call order per role (used for split-panel scenarios)."""

    def __init__(self, solver_letters="B", gate_doubt=False, judge_letter=None, judge_overturns=False, verifier_claims=None):
        self.calls = []
        self._solver_letters = solver_letters
        self._solver_call_count = 0
        self._gate_doubt = gate_doubt
        self._judge_letter = judge_letter
        self._judge_overturns = judge_overturns
        self._verifier_claims = verifier_claims or []
        self._verifier_call_count = 0

    def _next_solver_letter(self):
        if isinstance(self._solver_letters, str):
            return self._solver_letters
        letter = self._solver_letters[self._solver_call_count % len(self._solver_letters)]
        self._solver_call_count += 1
        return letter

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append(
            {"role": role, "model": model, "system": system, "user": user, "thinking": thinking, "temperature": temperature}
        )
        if role in ("solver", "solver_thinking"):
            return JsonCallResult(
                data={"letter": self._next_solver_letter(), "confidence": 0.7, "reasoning": "because"},
                usage=_usage(role),
            )
        if role == "gate":
            return JsonCallResult(data={"doubt": self._gate_doubt, "reason": "looks fine"}, usage=_usage("gate"))
        if role == "skeptic":
            return JsonCallResult(
                data={"target_letter": "B", "disputed_step": "step X", "argument": "argument Y"},
                usage=_usage("skeptic"),
            )
        if role == "verifier":
            self._verifier_call_count += 1
            if self._verifier_call_count == 1:
                return JsonCallResult(data={"claims": self._verifier_claims}, usage=_usage("verifier"))
            findings = [{"claim": c["claim"], "supports_claim": True, "explanation": "checked"} for c in self._verifier_claims]
            return JsonCallResult(data={"findings": findings}, usage=_usage("verifier"))
        if role == "judge":
            final_letter = self._judge_letter or "B"
            return JsonCallResult(
                data={
                    "final_letter": final_letter,
                    "decisive_reasoning": "confirmed",
                    "dissent": None,
                    "overturned_plurality": self._judge_overturns,
                    "confidence": "high",
                },
                usage=_usage("judge"),
            )
        if role == "baseline":
            return JsonCallResult(data={"letter": self._next_solver_letter(), "reasoning": "r"}, usage=_usage("baseline"))
        raise AssertionError(f"unexpected role {role!r}")


class FakeToolSession:
    async def call(self, tool_name, arguments):
        if tool_name == "lookup_constant":
            return {"found": True, "name": arguments.get("name"), "value": 3.14159}
        return {"ok": True, "value": 1.0}


class FakeRagIndex:
    def __init__(self, results):
        self._results = results
        self.search_calls = []

    def search(self, query, query_vector, k=5):
        self.search_calls.append({"query": query, "query_vector": query_vector, "k": k})
        return self._results[:k]


def _canned_rag_results():
    return [
        {
            "passage_id": 1, "article_id": "a1", "title": "Photon",
            "text": "A photon is a quantum of electromagnetic radiation carrying energy. " * 5,
            "score": 0.9, "source_url": "https://example.org/Photon", "snapshot_id": "test-snapshot:v1",
        },
        {
            "passage_id": 2, "article_id": "a2", "title": "Electron",
            "text": "An electron is a subatomic particle with negative electric charge. " * 5,
            "score": 0.8, "source_url": "https://example.org/Electron", "snapshot_id": "test-snapshot:v1",
        },
    ]


def _rag_config(results=None, k=5):
    return lever_experiments.RagPresolveConfig(
        index=FakeRagIndex(results if results is not None else _canned_rag_results()),
        embedder=None, k=k, snapshot_id="test-snapshot:v1",
        db_path=lever_experiments.Path("fake_index.sqlite3"),
    )


def _item(subject=None, correct_letter="B", question_id="q"):
    kwargs = dict(
        question_id=question_id, question="What is 2+2?", choices=["3", "4", "5", "6"], correct_letter=correct_letter,
    )
    if subject is not None:
        kwargs["subject"] = subject
    return GPQAItem(**kwargs)


def _fingerprint(call):
    return (call["role"], call["model"], call["thinking"], round(call["temperature"], 6), call["system"], call["user"])


def assert_same_calls(calls_a, calls_b, label=""):
    fa = Counter(_fingerprint(c) for c in calls_a)
    fb = Counter(_fingerprint(c) for c in calls_b)
    only_a = fa - fb
    only_b = fb - fa
    assert not only_a and not only_b, (
        f"{label}: call mismatch.\nOnly in lever/baseline path: {list(only_a.elements())}\n"
        f"Only in profile path: {list(only_b.elements())}"
    )


@pytest.fixture(autouse=True)
def _reset_benchmark_mode():
    profiles.set_benchmark_mode(False)
    yield
    profiles.set_benchmark_mode(False)


# ---------------------------------------------------------------------------
# Registry structure
# ---------------------------------------------------------------------------

REQUIRED_PROFILES = {
    "standard-tribunal", "thinking_gate", "stem-max", "flagship_panel",
    "rag_presolve", "rag_thinking_gate", "single-call",
}


def test_registry_contains_required_validated_profiles():
    assert REQUIRED_PROFILES <= set(profiles.REGISTRY.keys())


def test_every_registry_profile_is_an_orchestration_profile():
    for name, profile in profiles.REGISTRY.items():
        assert isinstance(profile, profiles.OrchestrationProfile)
        assert profile.name == name


@pytest.mark.parametrize("name", sorted(REQUIRED_PROFILES))
def test_required_profiles_default_to_deliberation_mode(name):
    assert profiles.REGISTRY[name].mode == "deliberation"


# ---------------------------------------------------------------------------
# Structural cross-checks against the real lever config
# ---------------------------------------------------------------------------


def test_standard_tribunal_panel_matches_shipped_solver_config():
    p = profiles.REGISTRY["standard-tribunal"]
    assert len(p.panel) == 3
    assert all(seat.model == MECHANICAL_MODEL for seat in p.panel)
    assert all(seat.thinking is False for seat in p.panel)
    assert [seat.temperature for seat in p.panel] == [0.3, 0.6, 0.9]
    assert p.acceptance_policy.kind == "unanimity"
    assert p.retrieval.mode == "none"
    assert p.subject_overrides is None
    assert p.tribunal.judge_model == ORCHESTRATOR_MODEL


def test_thinking_gate_panel_matches_solve_all_thinking_seat():
    p = profiles.REGISTRY["thinking_gate"]
    assert len(p.panel) == 3
    assert [seat.thinking for seat in p.panel] == [False, False, True]
    assert all(seat.model == MECHANICAL_MODEL for seat in p.panel)
    assert [seat.temperature for seat in p.panel] == [0.3, 0.6, 0.9]
    assert p.acceptance_policy.kind == "unanimity+gate"


def test_stem_max_default_panel_matches_thinking_seat_non_chem_branch():
    p = profiles.REGISTRY["stem-max"]
    assert [seat.thinking for seat in p.panel] == [False, False, True]
    assert all(seat.model == MECHANICAL_MODEL for seat in p.panel)


def test_stem_max_subject_override_matches_chem_flagship_branch():
    p = profiles.REGISTRY["stem-max"]
    assert p.subject_overrides is not None
    override = p.subject_overrides["Organic Chemistry"]
    assert len(override) == 3
    assert all(seat.model == ORCHESTRATOR_MODEL for seat in override)
    assert all(seat.thinking is True for seat in override)
    assert [seat.temperature for seat in override] == [0.3, 0.6, 0.9]
    assert p.acceptance_policy.kind == "unanimity+gate"  # universal gate, both branches


def test_flagship_panel_matches_solve_all_flagship_panel():
    p = profiles.REGISTRY["flagship_panel"]
    assert len(p.panel) == 3
    assert all(seat.model == ORCHESTRATOR_MODEL for seat in p.panel)
    assert all(seat.thinking is True for seat in p.panel)
    assert [seat.temperature for seat in p.panel] == [0.3, 0.6, 0.9]
    assert p.acceptance_policy.kind == "unanimity"  # NOT gated -- flagship_panel isn't in the gate-lever list


def test_rag_presolve_matches_solve_all_rag_presolve():
    p = profiles.REGISTRY["rag_presolve"]
    assert len(p.panel) == 3
    assert all(seat.model == MECHANICAL_MODEL for seat in p.panel)
    assert all(seat.thinking is False for seat in p.panel)
    assert p.retrieval.mode == "pre_solve"
    assert p.retrieval.k == lever_experiments.DEFAULT_RAG_K
    assert p.acceptance_policy.kind == "unanimity"


def test_rag_thinking_gate_matches_solve_all_rag_thinking_gate():
    p = profiles.REGISTRY["rag_thinking_gate"]
    assert [seat.thinking for seat in p.panel] == [False, False, True]
    assert p.retrieval.mode == "pre_solve"
    assert p.acceptance_policy.kind == "unanimity+gate"


def test_single_call_profile_has_no_panel_and_never_escalates():
    p = profiles.REGISTRY["single-call"]
    assert p.panel == []
    assert p.subject_overrides is None
    assert p.acceptance_policy.kind == "never_escalate"
    assert p.retrieval.mode == "none"
    assert p.tribunal.skeptic_enabled is False
    assert p.tribunal.verifier_enabled is False


# ---------------------------------------------------------------------------
# Equivalence: standard-tribunal vs the shipped orchestrator.run_question
# ---------------------------------------------------------------------------


def test_standard_tribunal_unanimous_matches_shipped_orchestrator():
    item = _item()
    client_a = RecordingClient(solver_letters="B")
    client_b = RecordingClient(solver_letters="B")

    result_a = asyncio.run(run_question(client_a, FakeToolSession(), item))
    result_b = asyncio.run(profiles.run_profile(client_b, FakeToolSession(), item, profiles.REGISTRY["standard-tribunal"]))

    assert_same_calls(client_a.calls, client_b.calls, "standard-tribunal/unanimous")
    assert result_a.final_letter == result_b.final_letter
    assert result_a.escalated == result_b.escalated == False
    assert result_a.correct == result_b.correct


def test_standard_tribunal_split_matches_shipped_orchestrator():
    item = _item(correct_letter="D")
    client_a = RecordingClient(solver_letters=["B", "B", "D"], judge_letter="D", judge_overturns=True)
    client_b = RecordingClient(solver_letters=["B", "B", "D"], judge_letter="D", judge_overturns=True)

    result_a = asyncio.run(run_question(client_a, FakeToolSession(), item))
    result_b = asyncio.run(profiles.run_profile(client_b, FakeToolSession(), item, profiles.REGISTRY["standard-tribunal"]))

    assert_same_calls(client_a.calls, client_b.calls, "standard-tribunal/split")
    assert result_a.final_letter == result_b.final_letter == "D"
    assert result_a.escalated == result_b.escalated == True
    assert result_a.false_escalation == result_b.false_escalation
    assert result_a.correct == result_b.correct == True


# ---------------------------------------------------------------------------
# Equivalence: thinking_gate vs lever_experiments "thinking_gate"
# ---------------------------------------------------------------------------


def test_thinking_gate_unanimous_no_doubt_matches_lever():
    item = _item()
    client_a = RecordingClient(solver_letters="B", gate_doubt=False)
    client_b = RecordingClient(solver_letters="B", gate_doubt=False)

    result_a, _note = asyncio.run(lever_experiments.run_question_lever(client_a, None, item, "thinking_gate"))
    result_b = asyncio.run(profiles.run_profile(client_b, None, item, profiles.REGISTRY["thinking_gate"]))

    assert_same_calls(client_a.calls, client_b.calls, "thinking_gate/unanimous-no-doubt")
    assert result_a.escalated == result_b.escalated == False
    assert result_a.final_letter == result_b.final_letter


def test_thinking_gate_doubt_forces_escalation_matches_lever():
    item = _item(correct_letter="B")
    client_a = RecordingClient(solver_letters="B", gate_doubt=True, judge_letter="B", judge_overturns=False)
    client_b = RecordingClient(solver_letters="B", gate_doubt=True, judge_letter="B", judge_overturns=False)

    result_a, _note = asyncio.run(
        lever_experiments.run_question_lever(client_a, FakeToolSession(), item, "thinking_gate")
    )
    result_b = asyncio.run(
        profiles.run_profile(client_b, FakeToolSession(), item, profiles.REGISTRY["thinking_gate"])
    )

    assert_same_calls(client_a.calls, client_b.calls, "thinking_gate/gate-doubt-escalates")
    assert result_a.escalated == result_b.escalated == True
    assert result_a.final_letter == result_b.final_letter


def test_thinking_gate_split_matches_lever():
    item = _item(correct_letter="D")
    client_a = RecordingClient(solver_letters=["B", "B", "D"], judge_letter="D", judge_overturns=True)
    client_b = RecordingClient(solver_letters=["B", "B", "D"], judge_letter="D", judge_overturns=True)

    result_a, _note = asyncio.run(
        lever_experiments.run_question_lever(client_a, FakeToolSession(), item, "thinking_gate")
    )
    result_b = asyncio.run(
        profiles.run_profile(client_b, FakeToolSession(), item, profiles.REGISTRY["thinking_gate"])
    )

    assert_same_calls(client_a.calls, client_b.calls, "thinking_gate/split")
    assert result_a.final_letter == result_b.final_letter == "D"


# ---------------------------------------------------------------------------
# Equivalence: stem-max vs lever_experiments "chem_thinking_gate"
# ---------------------------------------------------------------------------


def test_stem_max_organic_chemistry_matches_chem_thinking_gate_lever():
    item = _item(subject="Organic Chemistry")
    client_a = RecordingClient(solver_letters="B", gate_doubt=False)
    client_b = RecordingClient(solver_letters="B", gate_doubt=False)

    result_a, _note = asyncio.run(
        lever_experiments.run_question_lever(client_a, None, item, "chem_thinking_gate")
    )
    result_b = asyncio.run(profiles.run_profile(client_b, None, item, profiles.REGISTRY["stem-max"]))

    assert_same_calls(client_a.calls, client_b.calls, "stem-max/organic-chemistry")
    solver_models_a = {c["model"] for c in client_a.calls if c["role"] in ("solver", "solver_thinking")}
    assert solver_models_a == {ORCHESTRATOR_MODEL}
    assert result_a.escalated == result_b.escalated
    assert result_a.final_letter == result_b.final_letter


def test_stem_max_non_chemistry_matches_chem_thinking_gate_lever():
    item = _item(subject="Quantum Mechanics")
    client_a = RecordingClient(solver_letters="B", gate_doubt=False)
    client_b = RecordingClient(solver_letters="B", gate_doubt=False)

    result_a, _note = asyncio.run(
        lever_experiments.run_question_lever(client_a, None, item, "chem_thinking_gate")
    )
    result_b = asyncio.run(profiles.run_profile(client_b, None, item, profiles.REGISTRY["stem-max"]))

    assert_same_calls(client_a.calls, client_b.calls, "stem-max/non-chemistry")
    solver_models_a = {c["model"] for c in client_a.calls if c["role"] in ("solver", "solver_thinking")}
    assert solver_models_a == {MECHANICAL_MODEL}


def test_stem_max_gate_doubt_on_chemistry_escalates_matches_lever():
    item = _item(subject="Organic Chemistry", correct_letter="B")
    client_a = RecordingClient(solver_letters="B", gate_doubt=True, judge_letter="B", judge_overturns=False)
    client_b = RecordingClient(solver_letters="B", gate_doubt=True, judge_letter="B", judge_overturns=False)

    result_a, _note = asyncio.run(
        lever_experiments.run_question_lever(client_a, FakeToolSession(), item, "chem_thinking_gate")
    )
    result_b = asyncio.run(
        profiles.run_profile(client_b, FakeToolSession(), item, profiles.REGISTRY["stem-max"])
    )

    assert_same_calls(client_a.calls, client_b.calls, "stem-max/chem-gate-doubt")
    assert result_a.escalated == result_b.escalated == True


# ---------------------------------------------------------------------------
# Equivalence: flagship_panel vs lever_experiments "flagship_panel"
# ---------------------------------------------------------------------------


def test_flagship_panel_unanimous_matches_lever():
    item = _item()
    client_a = RecordingClient(solver_letters="B")
    client_b = RecordingClient(solver_letters="B")

    result_a, _note = asyncio.run(lever_experiments.run_question_lever(client_a, None, item, "flagship_panel"))
    result_b = asyncio.run(profiles.run_profile(client_b, None, item, profiles.REGISTRY["flagship_panel"]))

    assert_same_calls(client_a.calls, client_b.calls, "flagship_panel/unanimous")
    gate_calls_a = [c for c in client_a.calls if c["role"] == "gate"]
    assert gate_calls_a == []  # no gate call -- confirms the "not gated" structural assertion behaviorally too
    assert result_a.escalated == result_b.escalated == False


def test_flagship_panel_split_matches_lever():
    item = _item(correct_letter="D")
    client_a = RecordingClient(solver_letters=["B", "B", "D"], judge_letter="D", judge_overturns=True)
    client_b = RecordingClient(solver_letters=["B", "B", "D"], judge_letter="D", judge_overturns=True)

    result_a, _note = asyncio.run(
        lever_experiments.run_question_lever(client_a, FakeToolSession(), item, "flagship_panel")
    )
    result_b = asyncio.run(
        profiles.run_profile(client_b, FakeToolSession(), item, profiles.REGISTRY["flagship_panel"])
    )

    assert_same_calls(client_a.calls, client_b.calls, "flagship_panel/split")
    assert result_a.final_letter == result_b.final_letter == "D"


# ---------------------------------------------------------------------------
# Equivalence: rag_presolve vs lever_experiments "rag_presolve"
# ---------------------------------------------------------------------------


def test_rag_presolve_unanimous_matches_lever():
    item = _item()
    rag_a, rag_b = _rag_config(), _rag_config()
    client_a = RecordingClient(solver_letters="B")
    client_b = RecordingClient(solver_letters="B")

    result_a, _note = asyncio.run(
        lever_experiments.run_question_lever(client_a, None, item, "rag_presolve", rag=rag_a)
    )
    result_b = asyncio.run(
        profiles.run_profile(client_b, None, item, profiles.REGISTRY["rag_presolve"], rag=rag_b)
    )

    assert_same_calls(client_a.calls, client_b.calls, "rag_presolve/unanimous")
    assert rag_a.index.search_calls == rag_b.index.search_calls
    for c in client_b.calls:
        assert "[Photon]" in c["user"]
    assert result_a.escalated == result_b.escalated == False


def test_rag_presolve_split_still_escalates_through_shipped_tribunal_matches_lever():
    item = _item(correct_letter="D")
    rag_a, rag_b = _rag_config(), _rag_config()
    client_a = RecordingClient(solver_letters=["B", "B", "D"], judge_letter="D", judge_overturns=True)
    client_b = RecordingClient(solver_letters=["B", "B", "D"], judge_letter="D", judge_overturns=True)

    result_a, _note = asyncio.run(
        lever_experiments.run_question_lever(client_a, FakeToolSession(), item, "rag_presolve", rag=rag_a)
    )
    result_b = asyncio.run(
        profiles.run_profile(client_b, FakeToolSession(), item, profiles.REGISTRY["rag_presolve"], rag=rag_b)
    )

    assert_same_calls(client_a.calls, client_b.calls, "rag_presolve/split")
    assert len(rag_a.index.search_calls) == len(rag_b.index.search_calls) == 1  # R1 only, no R2
    assert result_a.final_letter == result_b.final_letter == "D"


def test_rag_presolve_requires_rag_config():
    item = _item()
    with pytest.raises(ValueError):
        asyncio.run(profiles.run_profile(RecordingClient(), None, item, profiles.REGISTRY["rag_presolve"]))


# ---------------------------------------------------------------------------
# Equivalence: rag_thinking_gate vs lever_experiments "rag_thinking_gate"
# ---------------------------------------------------------------------------


def test_rag_thinking_gate_unanimous_matches_lever():
    item = _item()
    rag_a, rag_b = _rag_config(), _rag_config()
    client_a = RecordingClient(solver_letters="B", gate_doubt=False)
    client_b = RecordingClient(solver_letters="B", gate_doubt=False)

    result_a, _note = asyncio.run(
        lever_experiments.run_question_lever(client_a, None, item, "rag_thinking_gate", rag=rag_a)
    )
    result_b = asyncio.run(
        profiles.run_profile(client_b, None, item, profiles.REGISTRY["rag_thinking_gate"], rag=rag_b)
    )

    assert_same_calls(client_a.calls, client_b.calls, "rag_thinking_gate/unanimous")
    thinking_calls = [c for c in client_b.calls if c["role"] == "solver_thinking"]
    assert len(thinking_calls) == 1
    assert "[Photon]" in thinking_calls[0]["user"]  # evidence reaches the thinking seat too


def test_rag_thinking_gate_doubt_escalates_no_r2_matches_lever():
    item = _item(correct_letter="B")
    rag_a, rag_b = _rag_config(), _rag_config()
    client_a = RecordingClient(solver_letters="B", gate_doubt=True, judge_letter="B", judge_overturns=False)
    client_b = RecordingClient(solver_letters="B", gate_doubt=True, judge_letter="B", judge_overturns=False)

    result_a, _note = asyncio.run(
        lever_experiments.run_question_lever(client_a, FakeToolSession(), item, "rag_thinking_gate", rag=rag_a)
    )
    result_b = asyncio.run(
        profiles.run_profile(client_b, FakeToolSession(), item, profiles.REGISTRY["rag_thinking_gate"], rag=rag_b)
    )

    assert_same_calls(client_a.calls, client_b.calls, "rag_thinking_gate/gate-doubt")
    assert len(rag_a.index.search_calls) == len(rag_b.index.search_calls) == 1  # no R2 for this lever
    assert result_a.escalated == result_b.escalated == True


def test_rag_thinking_gate_requires_rag_config():
    item = _item()
    with pytest.raises(ValueError):
        asyncio.run(profiles.run_profile(RecordingClient(), None, item, profiles.REGISTRY["rag_thinking_gate"]))


# ---------------------------------------------------------------------------
# Equivalence: single-call vs quorumqa.baseline.solve_single_agent
# ---------------------------------------------------------------------------


def test_single_call_matches_baseline_solve_single_agent():
    item = _item(correct_letter="B")
    client_a = RecordingClient(solver_letters="B")
    client_b = RecordingClient(solver_letters="B")

    baseline_result = asyncio.run(asyncio.to_thread(solve_single_agent, client_a, item))
    profile_result = asyncio.run(profiles.run_profile(client_b, None, item, profiles.REGISTRY["single-call"]))

    assert_same_calls(client_a.calls, client_b.calls, "single-call")
    assert baseline_result.answer_letter == profile_result.final_letter
    assert baseline_result.correct == profile_result.correct
    assert profile_result.escalated is False
    assert profile_result.total_cost_usd == baseline_result.total_cost_usd


# ---------------------------------------------------------------------------
# Guard rails: declared-but-unsupported dimensions fail loudly, not silently
# ---------------------------------------------------------------------------


def test_run_profile_rejects_agent_mode():
    agent_profile = profiles.OrchestrationProfile(
        name="not-yet-supported",
        panel=[profiles.SeatSpec(model=MECHANICAL_MODEL, thinking=False, temperature=0.4, lens_index=0)],
        acceptance_policy=profiles.AcceptancePolicy(kind="unanimity"),
        tribunal=profiles.TribunalSpec(),
        retrieval=profiles.RetrievalSpec(),
        mode="agent",
    )
    with pytest.raises(NotImplementedError):
        asyncio.run(profiles.run_profile(RecordingClient(), None, _item(), agent_profile))


def test_orchestration_profile_rejects_nonempty_panel_with_never_escalate():
    with pytest.raises(ValueError):
        profiles.OrchestrationProfile(
            name="bad",
            panel=[profiles.SeatSpec(model=MECHANICAL_MODEL, thinking=False, temperature=0.4, lens_index=0)],
            acceptance_policy=profiles.AcceptancePolicy(kind="never_escalate"),
            tribunal=profiles.TribunalSpec(),
            retrieval=profiles.RetrievalSpec(),
        )


def test_orchestration_profile_rejects_empty_panel_without_never_escalate():
    with pytest.raises(ValueError):
        profiles.OrchestrationProfile(
            name="bad",
            panel=[],
            acceptance_policy=profiles.AcceptancePolicy(kind="unanimity"),
            tribunal=profiles.TribunalSpec(),
            retrieval=profiles.RetrievalSpec(),
        )


# ---------------------------------------------------------------------------
# The benchmark-mode memory firewall (plan section 5 / 5.1)
# ---------------------------------------------------------------------------


def test_benchmark_mode_defaults_off():
    assert profiles.is_benchmark_mode() is False


def test_set_benchmark_mode_toggles_flag():
    profiles.set_benchmark_mode(True)
    assert profiles.is_benchmark_mode() is True
    profiles.set_benchmark_mode(False)
    assert profiles.is_benchmark_mode() is False


def test_assert_benchmark_mode_no_memory_raises_when_on():
    profiles.set_benchmark_mode(True)
    with pytest.raises(profiles.MemoryFirewallError):
        profiles.assert_benchmark_mode_no_memory()


def test_assert_benchmark_mode_no_memory_silent_when_off():
    profiles.set_benchmark_mode(False)
    profiles.assert_benchmark_mode_no_memory()  # must not raise


def test_calibration_memory_stub_raises_firewall_error_in_benchmark_mode():
    profiles.set_benchmark_mode(True)
    with pytest.raises(profiles.MemoryFirewallError):
        profiles.read_calibration_memory("gpqa", "standard-tribunal")


def test_episodic_memory_stub_raises_firewall_error_in_benchmark_mode():
    profiles.set_benchmark_mode(True)
    with pytest.raises(profiles.MemoryFirewallError):
        profiles.read_episodic_memory("some query")


def test_calibration_memory_stub_raises_not_implemented_in_product_mode():
    # Product mode: the firewall does NOT fire (memory would be allowed) --
    # but the memory store itself doesn't exist yet (M2), so the call still
    # fails, just with a DIFFERENT error, proving the firewall check runs
    # first and is not merely coincidental with "not built yet".
    profiles.set_benchmark_mode(False)
    with pytest.raises(NotImplementedError):
        profiles.read_calibration_memory("gpqa", "standard-tribunal")


def test_run_profile_benchmark_mode_true_sets_global_flag():
    item = _item()
    client = RecordingClient(solver_letters="B")
    asyncio.run(
        profiles.run_profile(client, None, item, profiles.REGISTRY["standard-tribunal"], benchmark_mode=True)
    )
    assert profiles.is_benchmark_mode() is True


def test_run_profile_benchmark_mode_none_leaves_flag_untouched():
    profiles.set_benchmark_mode(True)
    item = _item()
    client = RecordingClient(solver_letters="B")
    asyncio.run(profiles.run_profile(client, None, item, profiles.REGISTRY["standard-tribunal"]))
    assert profiles.is_benchmark_mode() is True  # untouched, still whatever the caller set before
