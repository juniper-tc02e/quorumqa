"""Offline tests for the rag_gated_presolve lever (benchmark/lever_experiments.py)
-- no live API calls, no cost, no real RAG index on disk.

Genesis: benchmark/results/rag_r1_findings.md's fourth-seed section (seed
271: rag_presolve went -5.6, 10/13 regressions were unanimous-wrong UNDER
RAG -- the retrieved passages actively misled the panel into confident
false consensus). benchmark/results/rag_gating_calibration.csv (offline
recompute of the top fused RRF score for every common item across seeds
42/7/123/271) showed regressions cluster at a measurably lower top score
than wins/neutrals -- see benchmark/results/rag_gating_analysis.md for the
full calibration and the chosen threshold.

rag_gated_presolve is IDENTICAL to rag_presolve (same solver seats/lenses/
temperatures, same skeptic/verifier/judge/escalation trigger, same
fail-loud missing-index contract) EXCEPT: retrieval still fires once per
question (so the gate has a score to act on), but the evidence block is
only injected into the solver prompts when the top fused RRF score clears
--rag-score-threshold. Below threshold, every solver seat runs on the
PLAIN question -- same as the shipped no-RAG cheap panel for that one
question -- rather than risk injecting a plausible-but-wrong passage.

Mirrors the fake-client / FakeRagIndex pattern in
tests/test_lever_rag_presolve_offline.py exactly, plus threshold-specific
gate assertions.
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


class FakeRagIndex:
    """Stands in for quorumqa.rag.store.RagIndex -- just enough surface
    (.search) for solve_all_rag_gated_presolve, plus call recording so
    tests can assert retrieval happened exactly once per question
    regardless of whether the gate ends up injecting evidence."""

    def __init__(self, results):
        self._results = results
        self.search_calls = []

    def search(self, query, query_vector, k=5):
        self.search_calls.append({"query": query, "query_vector": query_vector, "k": k})
        return self._results[:k]


class RecordingClient:
    def __init__(self, solver_letter="B"):
        self.calls = []
        self._solver_letter = solver_letter

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "system": system, "user": user, "thinking": thinking, "temperature": temperature})
        if role == "solver":
            return JsonCallResult(
                data={"letter": self._solver_letter, "confidence": 0.7, "reasoning": "because"},
                usage=_usage("solver"),
            )
        raise AssertionError(f"unexpected role {role!r} for a unanimous rag_gated_presolve question")


def _results_with_top_score(score):
    return [
        {
            "passage_id": 1, "article_id": "a1", "title": "Photon",
            "text": "A photon is a quantum of electromagnetic radiation carrying energy. " * 5,
            "score": score, "source_url": "https://example.org/Photon", "snapshot_id": "test-snapshot:v1",
        },
        {
            "passage_id": 2, "article_id": "a2", "title": "Electron",
            "text": "An electron is a subatomic particle with negative electric charge. " * 5,
            "score": score - 0.005, "source_url": "https://example.org/Electron", "snapshot_id": "test-snapshot:v1",
        },
    ]


def _rag_config(results, k=5, embedder=None):
    return lever_experiments.RagPresolveConfig(
        index=FakeRagIndex(results), embedder=embedder, k=k, snapshot_id="test-snapshot:v1",
        db_path=lever_experiments.Path("fake_index.sqlite3"),
    )


def _item(question_id="q1", correct_letter="B"):
    return GPQAItem(
        question_id=question_id, question="What carries energy as electromagnetic radiation?",
        choices=["Photon", "Neutron", "Quark", "Proton"], correct_letter=correct_letter,
    )


THRESHOLD = 0.02


# ---------------------------------------------------------------------------
# (a) above-threshold score injects evidence into every solver seat
# ---------------------------------------------------------------------------


def test_above_threshold_score_injects_evidence_into_every_solver_prompt():
    rag = _rag_config(_results_with_top_score(0.03))  # above THRESHOLD
    client = RecordingClient()
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(
            client, None, item, "rag_gated_presolve", rag=rag, rag_gate_threshold=THRESHOLD
        )
    )

    solver_calls = [c for c in client.calls if c["role"] == "solver"]
    assert len(solver_calls) == 3
    for c in solver_calls:
        assert "Relevant reference passages (may or may not be useful):" in c["user"]
        assert "[Photon]" in c["user"]
        assert c["model"] == MECHANICAL_MODEL
        assert c["thinking"] is False

    assert len(rag.index.search_calls) == 1  # retrieval still fires exactly once
    assert result.rag_gate_applied is True
    assert result.rag_gate_top_score == pytest.approx(0.03)


# ---------------------------------------------------------------------------
# (b) below-threshold score: retrieval fires (so the gate has a score), but
#     NO evidence reaches any solver seat -- prompt is byte-identical to the
#     plain no-RAG cheap panel for this one question
# ---------------------------------------------------------------------------


def test_below_threshold_score_yields_plain_prompt_no_evidence():
    rag = _rag_config(_results_with_top_score(0.01))  # below THRESHOLD
    client = RecordingClient()
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(
            client, None, item, "rag_gated_presolve", rag=rag, rag_gate_threshold=THRESHOLD
        )
    )

    solver_calls = [c for c in client.calls if c["role"] == "solver"]
    assert len(solver_calls) == 3
    for c in solver_calls:
        assert "Relevant reference passages" not in c["user"]
        assert c["user"].startswith("Question:")

    # Retrieval still fires -- the gate needs the score even when it decides
    # not to inject.
    assert len(rag.index.search_calls) == 1
    assert result.rag_gate_applied is False
    assert result.rag_gate_top_score == pytest.approx(0.01)


def test_score_exactly_at_threshold_is_treated_as_above(): # >= threshold injects
    rag = _rag_config(_results_with_top_score(THRESHOLD))
    client = RecordingClient()
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(
            client, None, item, "rag_gated_presolve", rag=rag, rag_gate_threshold=THRESHOLD
        )
    )

    solver_calls = [c for c in client.calls if c["role"] == "solver"]
    assert all("Relevant reference passages" in c["user"] for c in solver_calls)
    assert result.rag_gate_applied is True


def test_no_retrieved_results_gates_off_and_yields_plain_prompt():
    rag = _rag_config([])  # nothing retrieved at all
    client = RecordingClient()
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(
            client, None, item, "rag_gated_presolve", rag=rag, rag_gate_threshold=THRESHOLD
        )
    )

    solver_calls = [c for c in client.calls if c["role"] == "solver"]
    for c in solver_calls:
        assert "Relevant reference passages" not in c["user"]
    assert result.rag_gate_applied is False
    assert result.rag_gate_top_score is None


# ---------------------------------------------------------------------------
# (c) missing-config fails loudly, exactly like rag_presolve
# ---------------------------------------------------------------------------


def test_run_question_lever_rag_gated_presolve_without_config_raises_value_error():
    client = RecordingClient()
    item = _item()
    with pytest.raises(ValueError, match="rag_gated_presolve"):
        asyncio.run(lever_experiments.run_question_lever(client, None, item, "rag_gated_presolve"))


# ---------------------------------------------------------------------------
# (d) split panel still escalates through the UNCHANGED shipped tribunal
#     (no R2 -- deliberately, same as rag_presolve/rag_thinking_gate)
# ---------------------------------------------------------------------------


def test_rag_gated_presolve_split_panel_still_escalates_through_shipped_tribunal():
    rag = _rag_config(_results_with_top_score(0.03))

    class SplitThenTribunalClient:
        def __init__(self):
            self.calls = []

        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            self.calls.append({"role": role, "user": user})
            if role == "solver":
                letters = ["B", "B", "D"]
                letter = letters[sum(1 for c in self.calls if c["role"] == "solver") - 1]
                assert "Relevant reference passages" in user
                return JsonCallResult(data={"letter": letter, "confidence": 0.7, "reasoning": "r"}, usage=_usage("solver"))
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
        lever_experiments.run_question_lever(
            client, None, item, "rag_gated_presolve", rag=rag, rag_gate_threshold=THRESHOLD
        )
    )

    assert result.escalated is True
    assert result.plurality_letter == "B"
    assert result.final_letter == "D"
    assert result.correct is True
    assert result.rag_r2_query is None  # no R2 for this lever
    assert len(rag.index.search_calls) == 1
    assert result.rag_gate_applied is True
    assert result.rag_gate_top_score == pytest.approx(0.03)


def test_rag_gated_presolve_below_threshold_split_panel_escalates_with_plain_prompts():
    rag = _rag_config(_results_with_top_score(0.01))

    class SplitThenTribunalClient:
        def __init__(self):
            self.calls = []

        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            self.calls.append({"role": role, "user": user})
            if role == "solver":
                letters = ["B", "B", "D"]
                letter = letters[sum(1 for c in self.calls if c["role"] == "solver") - 1]
                assert "Relevant reference passages" not in user
                return JsonCallResult(data={"letter": letter, "confidence": 0.7, "reasoning": "r"}, usage=_usage("solver"))
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

    item = GPQAItem(question_id="q3", question="What carries energy?", choices=["Photon", "Neutron", "Quark", "Proton"], correct_letter="D")
    client = SplitThenTribunalClient()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(
            client, None, item, "rag_gated_presolve", rag=rag, rag_gate_threshold=THRESHOLD
        )
    )

    assert result.escalated is True
    assert result.final_letter == "D"
    assert result.rag_gate_applied is False


# ---------------------------------------------------------------------------
# (e) output row carries rag="ON" (retrieval always fires), plus the gate
#     verdict/threshold/score -- and the gate fields are absent for every
#     other lever
# ---------------------------------------------------------------------------


def test_output_row_carries_gate_fields_for_rag_gated_presolve():
    rag = _rag_config(_results_with_top_score(0.03), k=5)
    client = RecordingClient()
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(
            client, None, item, "rag_gated_presolve", rag=rag, rag_gate_threshold=THRESHOLD
        )
    )
    row = lever_experiments._build_output_row(result, "rag_gated_presolve", 271, "supergpqa", rag, rag_gate_threshold=THRESHOLD)

    assert row["rag"] == "ON"  # retrieval always fires, firewall label unaffected by gating
    assert row["rag_snapshot_id"] == "test-snapshot:v1"
    assert row["rag_gate_threshold"] == THRESHOLD
    assert row["rag_gate_applied"] == "ON"
    assert row["rag_gate_top_score"] == pytest.approx(0.03)
    assert "rag_r2" not in row


def test_output_row_omits_gate_fields_for_rag_presolve():
    rag = _rag_config(_results_with_top_score(0.03), k=5)
    client = RecordingClient()
    item = _item()

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "rag_presolve", rag=rag))
    row = lever_experiments._build_output_row(result, "rag_presolve", 42, "supergpqa", rag)

    assert row["rag"] == "ON"
    assert "rag_gate_threshold" not in row
    assert "rag_gate_applied" not in row
    assert "rag_gate_top_score" not in row


# ---------------------------------------------------------------------------
# (f) dispatch / argparse / main_live wiring
# ---------------------------------------------------------------------------


def test_rag_gated_presolve_present_in_argparse_choices():
    source = inspect.getsource(lever_experiments)
    assert '"rag_gated_presolve"' in source


def test_rag_gated_presolve_added_to_main_live_rag_dispatch():
    source = inspect.getsource(lever_experiments.main_live)
    assert "rag_gated_presolve" in source


def test_rag_score_threshold_cli_flag_present():
    source = inspect.getsource(lever_experiments)
    assert "--rag-score-threshold" in source
