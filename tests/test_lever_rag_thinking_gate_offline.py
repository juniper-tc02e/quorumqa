"""Offline tests for the rag_thinking_gate lever (benchmark/lever_experiments.py)
-- no live API calls, no cost, no real RAG index on disk. This lever stacks
two independently-validated cheap-tier levers to test COMPOSITION vs
OVERLAP: rag_presolve's R1 pre-solve retrieval (top-k passages retrieved
ONCE per question, injected into every solver seat's user prompt) feeds
thinking_gate's panel shape (seats 1-2 plain MECHANICAL_MODEL, seat 3
MECHANICAL_MODEL with thinking=True) -- the retrieved evidence block reaches
ALL THREE seats, including the thinking seat. The universal
second_opinion_gate doubt-check applies to unanimous answers, same as
thinking_gate. Skeptic/Verifier/Judge and the escalation trigger are
completely untouched -- no R2 (that was rag_recursive's validated no-gain,
not repeated here).

MUST be piloted on a FRESH seed only when run live -- seeds 42/7/123 are
burned (both parents, rag_presolve and thinking_gate, were validated on
them) and 217/314/471/555/777/888 are used by other levers' validation.
This stack pilots on seed 271.

Mirrors the fake-client / FakeRagIndex pattern in
tests/test_lever_rag_presolve_offline.py and the thinking-seat-panel
assertions in tests/test_lever_chem_thinking_gate_offline.py.
"""

import asyncio
import inspect

import pytest

import benchmark.lever_experiments as lever_experiments
from quorumqa.config import MECHANICAL_MODEL
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem, QuestionResult, SolverAnswer


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class FakeRagIndex:
    """Stands in for quorumqa.rag.store.RagIndex -- just enough surface
    (.search) for solve_all_rag_thinking_gate, plus call recording so tests
    can assert retrieval happened exactly once per question (not once per
    solver seat)."""

    def __init__(self, results):
        self._results = results
        self.search_calls = []

    def search(self, query, query_vector, k=5):
        self.search_calls.append({"query": query, "query_vector": query_vector, "k": k})
        return self._results[:k]


class RecordingClient:
    """Records every chat_json call's (role, model, system, user, thinking).
    Handles solver/solver_thinking/gate/skeptic/verifier/judge roles so both
    the unanimous-accept path and the escalation tribunal can be exercised."""

    def __init__(self, solver_letter="B", gate_doubt=False):
        self.calls = []
        self._solver_letter = solver_letter
        self._gate_doubt = gate_doubt

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "system": system, "user": user, "thinking": thinking, "temperature": temperature})
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


def _canned_results():
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


def _rag_config(results=None, k=5, embedder=None):
    return lever_experiments.RagPresolveConfig(
        index=FakeRagIndex(results if results is not None else _canned_results()),
        embedder=embedder, k=k, snapshot_id="test-snapshot:v1",
        db_path=lever_experiments.Path("fake_index.sqlite3"),
    )


def _item(question_id="q1", correct_letter="B", subject=None):
    kwargs = dict(
        question_id=question_id, question="What carries energy as electromagnetic radiation?",
        choices=["Photon", "Neutron", "Quark", "Proton"], correct_letter=correct_letter,
    )
    if subject is not None:
        kwargs["subject"] = subject
    return GPQAItem(**kwargs)


# ---------------------------------------------------------------------------
# (a) evidence block reaches all 3 seats, including the thinking seat;
#     retrieval fires exactly once per question
# ---------------------------------------------------------------------------


def test_evidence_block_reaches_all_three_seats_including_thinking_seat():
    rag = _rag_config()
    client = RecordingClient()
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "rag_thinking_gate", rag=rag)
    )

    solver_calls = [c for c in client.calls if c["role"] in ("solver", "solver_thinking")]
    assert len(solver_calls) == 3
    for c in solver_calls:
        assert "Relevant reference passages (may or may not be useful):" in c["user"]
        assert "[Photon]" in c["user"]
        assert "[Electron]" in c["user"]
        assert lever_experiments.SOLVER_SYSTEM in c["system"]

    # Retrieval happened exactly ONCE for the question, not once per seat.
    assert len(rag.index.search_calls) == 1
    assert rag.index.search_calls[0]["k"] == 5
    assert rag.index.search_calls[0]["query"] == item.question


def test_rag_thinking_gate_no_results_yields_unmodified_prompt_but_still_three_seats():
    rag = _rag_config(results=[])
    client = RecordingClient()
    item = _item()

    asyncio.run(lever_experiments.run_question_lever(client, None, item, "rag_thinking_gate", rag=rag))

    solver_calls = [c for c in client.calls if c["role"] in ("solver", "solver_thinking")]
    assert len(solver_calls) == 3
    for c in solver_calls:
        assert "Relevant reference passages" not in c["user"]
        assert c["user"].startswith("Question:")


# ---------------------------------------------------------------------------
# (b) seat 3 uses thinking=True, seats 1-2 do not -- same panel shape as
#     thinking_gate, just fed with retrieved evidence
# ---------------------------------------------------------------------------


def test_seat_three_thinks_seats_one_two_do_not():
    rag = _rag_config()
    client = RecordingClient()
    item = _item()

    asyncio.run(lever_experiments.run_question_lever(client, None, item, "rag_thinking_gate", rag=rag))

    solver_calls = [c for c in client.calls if c["role"] in ("solver", "solver_thinking")]
    assert all(c["model"] == MECHANICAL_MODEL for c in solver_calls)

    plain = [c for c in solver_calls if c["role"] == "solver"]
    thinking = [c for c in solver_calls if c["role"] == "solver_thinking"]
    assert len(plain) == 2
    assert all(c["thinking"] is False for c in plain)
    assert len(thinking) == 1
    assert thinking[0]["thinking"] is True
    # The thinking seat still gets the SAME evidence block as the plain seats.
    assert "Relevant reference passages" in thinking[0]["user"]


# ---------------------------------------------------------------------------
# (c) universal second_opinion_gate fires on unanimous answers
# ---------------------------------------------------------------------------


def test_unanimous_answer_triggers_gate_and_accepts_when_no_doubt():
    rag = _rag_config()
    client = RecordingClient(gate_doubt=False)
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "rag_thinking_gate", rag=rag)
    )

    gate_calls = [c for c in client.calls if c["role"] == "gate"]
    assert len(gate_calls) == 1
    assert result.escalated is False
    assert result.final_letter == "B"


def test_gate_doubt_forces_escalation_through_shipped_tribunal_no_r2():
    rag = _rag_config()
    client = RecordingClient(gate_doubt=True)
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "rag_thinking_gate", rag=rag)
    )

    assert result.escalated is True
    assert note is not None and note.startswith("gate-flagged")
    # No R2: the tribunal's disputed-step retrieval must never fire for this
    # lever -- only one search call total (R1's pre-solve retrieval).
    assert len(rag.index.search_calls) == 1
    assert result.rag_r2_query is None
    skeptic_calls = [c for c in client.calls if c["role"] == "skeptic"]
    verifier_calls = [c for c in client.calls if c["role"] == "verifier"]
    judge_calls = [c for c in client.calls if c["role"] == "judge"]
    assert len(skeptic_calls) == 1
    assert len(verifier_calls) == 1
    assert len(judge_calls) == 1


# ---------------------------------------------------------------------------
# (d) dispatch + argparse
# ---------------------------------------------------------------------------


def test_run_question_lever_rag_thinking_gate_without_config_raises_value_error():
    client = RecordingClient()
    item = _item()
    with pytest.raises(ValueError, match="rag_thinking_gate"):
        asyncio.run(lever_experiments.run_question_lever(client, None, item, "rag_thinking_gate"))


def test_rag_thinking_gate_present_in_argparse_choices():
    source = inspect.getsource(lever_experiments)
    assert '"rag_thinking_gate"' in source


def test_rag_thinking_gate_split_panel_still_escalates_through_shipped_tribunal():
    rag = _rag_config()

    class SplitThenTribunalClient:
        def __init__(self):
            self.calls = []

        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            self.calls.append({"role": role, "user": user})
            if role in ("solver", "solver_thinking"):
                letters = ["B", "B", "D"]
                letter = letters[sum(1 for c in self.calls if c["role"] in ("solver", "solver_thinking")) - 1]
                assert "Relevant reference passages" in user
                return JsonCallResult(data={"letter": letter, "confidence": 0.7, "reasoning": "r"}, usage=_usage(role))
            if role == "skeptic":
                return JsonCallResult(
                    data={"target_letter": "B", "disputed_step": "step X", "argument": "argument Y"},
                    usage=_usage("skeptic"),
                )
            if role == "verifier":
                return JsonCallResult(data={"claims": []}, usage=_usage("verifier"))
            if role == "judge":
                return JsonCallResult(
                    data={"final_letter": "D", "decisive_reasoning": "judge ruled", "dissent": None,
                          "overturned_plurality": True, "confidence": "high"},
                    usage=_usage("judge"),
                )
            raise AssertionError(f"unexpected role {role!r}")

    item = GPQAItem(question_id="q2", question="What carries energy?", choices=["Photon", "Neutron", "Quark", "Proton"], correct_letter="D")
    client = SplitThenTribunalClient()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "rag_thinking_gate", rag=rag)
    )

    assert result.escalated is True
    assert result.plurality_letter == "B"
    assert result.final_letter == "D"
    assert result.correct is True
    # Retrieval still only fired once for the whole question (shared by the
    # 3 solver seats), not once per seat and not again for the tribunal (no R2).
    assert len(rag.index.search_calls) == 1


# ---------------------------------------------------------------------------
# (e) output records carry rag="ON" + rag_snapshot_id, and never rag_r2 keys
#     (this lever never does R2)
# ---------------------------------------------------------------------------


def _fake_result(correct_letter="B"):
    item = _item(correct_letter=correct_letter)
    return QuestionResult(
        item=item,
        solver_answers=[SolverAnswer(letter="B", confidence=0.8, reasoning="r", lens="lens")],
        plurality_letter="B", escalated=False, final_letter="B", correct=True,
    )


def test_output_row_carries_rag_on_and_snapshot_id_for_rag_thinking_gate():
    rag = _rag_config(k=5)
    result = _fake_result()

    row = lever_experiments._build_output_row(result, "rag_thinking_gate", 271, "supergpqa", rag)

    assert row["rag"] == "ON"
    assert row["rag_snapshot_id"] == "test-snapshot:v1"
    assert row["rag_k"] == 5
    assert row["rag_db"] == "fake_index.sqlite3"
    assert row["lever"] == "rag_thinking_gate"
    assert row["seed"] == 271
    assert row["dataset"] == "supergpqa"
    assert "rag_r2" not in row


def test_rag_thinking_gate_added_to_main_live_rag_dispatch():
    # Regression guard: main_live must recognize rag_thinking_gate as
    # needing a built RagPresolveConfig (same fail-loud contract as
    # rag_presolve/rag_recursive), not silently run without retrieval.
    source = inspect.getsource(lever_experiments.main_live)
    assert "rag_thinking_gate" in source
