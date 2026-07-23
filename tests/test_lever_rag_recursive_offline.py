"""Offline tests for the rag_recursive lever (benchmark/lever_experiments.py)
-- the R2 disputed-step retrieval lever (docs/recursive-rag-plan.md section 2,
R2, Bet-2). No live API calls, no cost, no real RAG index on disk. Covers:

  (a) on a split, a SECOND, sharper query is built from the Skeptic's named
      disputed_step (+ argument) plus the solvers' divergent claims, and a
      second retrieval fires (top-k=3, fixed) against the SAME matched-
      encoder RagIndex path R1 already uses -- not the raw question again.
  (b) the retrieved R2 passages reach the Verifier's call as an evidence
      block (verifier.verify()'s new evidence_block parameter), while the
      Verifier's existing MCP tool calls stay available and are exercised
      too (ADDED grounding, not a replacement).
  (c) no escalation (unanimous panel) => only R1's single pre-solve
      retrieval fires; no second retrieval happens at all.
  (d) dispatch: run_question_lever routes lever="rag_recursive" through the
      same solve_all_rag_presolve R1 path as rag_presolve, then through the
      tribunal (skeptic -> R2 retrieval -> verifier -> judge) on a split;
      "rag_recursive" is a real argparse choice.
  (e) output records carry a rag_r2 marker (+ snapshot id) on top of the
      rag_presolve firewall fields (rag="ON", rag_snapshot_id, ...), and
      omit rag_r2 fields for every other lever -- including rag_presolve
      itself, which is R1-only and must never appear to have done R2.
  (f) missing-index / missing-config still fails loud, reusing rag_presolve's
      open_rag_index / build_rag_presolve_config contract unchanged.

Mirrors tests/test_lever_rag_presolve_offline.py's fake-client/fake-index
pattern; the tool session is a FakeToolSession copied from
tests/test_engine_offline.py's pattern.
"""

import asyncio

import pytest

import benchmark.lever_experiments as lever_experiments
from quorumqa.config import MECHANICAL_MODEL
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem, QuestionResult, SkepticRebuttal, SolverAnswer


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class FakeToolSession:
    async def call(self, tool_name, arguments):
        if tool_name == "lookup_constant":
            return {"found": True, "name": arguments.get("name"), "value": 3.14159}
        return {"ok": True, "value": 1.0}


class FakeRagIndex:
    """Stands in for quorumqa.rag.store.RagIndex. Returns R1's canned result
    set on the FIRST search call (the pre-solve, question-driven retrieval)
    and R2's canned result set on every subsequent call (the disputed-step-
    driven retrieval) -- so tests can tell the two retrievals apart by which
    titles come back, and records every call for count/query/k assertions."""

    def __init__(self, r1_results, r2_results=None):
        self._r1_results = r1_results
        self._r2_results = r2_results if r2_results is not None else r1_results
        self.search_calls = []

    def search(self, query, query_vector, k=5):
        self.search_calls.append({"query": query, "query_vector": query_vector, "k": k})
        results = self._r1_results if len(self.search_calls) == 1 else self._r2_results
        return results[:k]


def _r1_results():
    return [
        {"passage_id": 1, "article_id": "a1", "title": "Photon",
         "text": "A photon is a quantum of electromagnetic radiation carrying energy. " * 5,
         "score": 0.9, "source_url": "https://example.org/Photon", "snapshot_id": "test-snapshot:v1"},
        {"passage_id": 2, "article_id": "a2", "title": "Electron",
         "text": "An electron is a subatomic particle with negative electric charge. " * 5,
         "score": 0.8, "source_url": "https://example.org/Electron", "snapshot_id": "test-snapshot:v1"},
    ]


def _r2_results():
    return [
        {"passage_id": 3, "article_id": "a3", "title": "Heat of formation",
         "text": "The heat of formation is the enthalpy change when a compound forms from its elements. " * 5,
         "score": 0.95, "source_url": "https://example.org/Heat_of_formation", "snapshot_id": "test-snapshot:v1"},
        {"passage_id": 4, "article_id": "a4", "title": "Enthalpy",
         "text": "Enthalpy is a thermodynamic property equal to internal energy plus pressure-volume work. " * 5,
         "score": 0.85, "source_url": "https://example.org/Enthalpy", "snapshot_id": "test-snapshot:v1"},
        {"passage_id": 5, "article_id": "a5", "title": "Bond dissociation energy",
         "text": "Bond dissociation energy is the energy required to break a chemical bond homolytically. " * 5,
         "score": 0.80, "source_url": "https://example.org/Bond_dissociation_energy", "snapshot_id": "test-snapshot:v1"},
    ]


def _rag_config(r1=None, r2=None, k=5, embedder=None):
    return lever_experiments.RagPresolveConfig(
        index=FakeRagIndex(r1 if r1 is not None else _r1_results(), r2 if r2 is not None else _r2_results()),
        embedder=embedder, k=k, snapshot_id="test-snapshot:v1",
        db_path=lever_experiments.Path("fake_index.sqlite3"),
    )


def _item(question_id="q1", correct_letter="D"):
    return GPQAItem(
        question_id=question_id, question="What is the heat of formation of methane?",
        choices=["Photon", "Neutron", "Quark", "Enthalpy X"], correct_letter=correct_letter,
    )


class UnanimousClient:
    """All three solver seats agree -- records calls, raises on any role
    other than "solver" (a unanimous rag_recursive question must never
    reach skeptic/verifier/judge, and therefore never fire R2 retrieval)."""

    def __init__(self, solver_letter="B"):
        self.calls = []
        self._solver_letter = solver_letter

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "system": system, "user": user})
        if role == "solver":
            return JsonCallResult(
                data={"letter": self._solver_letter, "confidence": 0.7, "reasoning": "because"},
                usage=_usage("solver"),
            )
        raise AssertionError(f"unexpected role {role!r} for a unanimous rag_recursive question")


class SplitTribunalClient:
    """Solvers split B/B/D (plurality B, dissent D). Records every call so
    tests can inspect exactly what the skeptic/verifier/judge each saw --
    in particular, whether the R2 evidence block (built from the disputed
    step) reached the verifier's user prompt, and whether the verifier's
    existing tool-call machinery still fires alongside it."""

    def __init__(self, verifier_claims=None, judge_letter="D", judge_overturn=True):
        self.calls = []
        self._verifier_claims = verifier_claims if verifier_claims is not None else []
        self._judge_letter = judge_letter
        self._judge_overturn = judge_overturn
        self._verifier_call_count = 0

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "system": system, "user": user})
        if role == "solver":
            letters = ["B", "B", "D"]
            idx = sum(1 for c in self.calls if c["role"] == "solver") - 1
            return JsonCallResult(
                data={"letter": letters[idx], "confidence": 0.7, "reasoning": f"reasoning-{letters[idx]}"},
                usage=_usage("solver"),
            )
        if role == "skeptic":
            return JsonCallResult(
                data={
                    "target_letter": "B",
                    "disputed_step": "the heat of formation sign convention",
                    "argument": "the sign was flipped when combining bond energies",
                },
                usage=_usage("skeptic"),
            )
        if role == "verifier":
            self._verifier_call_count += 1
            if self._verifier_call_count == 1:
                return JsonCallResult(data={"claims": self._verifier_claims}, usage=_usage("verifier"))
            findings = [
                {"claim": c["claim"], "supports_claim": True, "explanation": "checked"} for c in self._verifier_claims
            ]
            return JsonCallResult(data={"findings": findings}, usage=_usage("verifier"))
        if role == "judge":
            return JsonCallResult(
                data={
                    "final_letter": self._judge_letter, "decisive_reasoning": "judge ruled",
                    "dissent": None, "overturned_plurality": self._judge_overturn, "confidence": "high",
                },
                usage=_usage("judge"),
            )
        raise AssertionError(f"unexpected role {role!r}")


# ---------------------------------------------------------------------------
# (a) on a split, the disputed-step query is built from the skeptic's named
#     step + the divergent solver claims, and retrieves top-k=3
# ---------------------------------------------------------------------------


def test_rag_recursive_disputed_step_query_built_and_retrieves_top3():
    rag = _rag_config(k=5)
    client = SplitTribunalClient()
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "rag_recursive", rag=rag)
    )

    assert result.escalated is True
    # Exactly 2 searches total: R1 (once, question-driven) + R2 (once,
    # disputed-step-driven) -- never once per solver seat, never per tool.
    assert len(rag.index.search_calls) == 2
    r1_call, r2_call = rag.index.search_calls

    assert r1_call["query"] == item.question
    assert r1_call["k"] == 5  # R1 uses the configured rag.k

    assert r2_call["k"] == 3  # R2 is fixed top-k=3 per docs/recursive-rag-plan.md section 2
    # R2's query is built from the skeptic's named disputed step + argument...
    assert "heat of formation sign convention" in r2_call["query"]
    assert "the sign was flipped when combining bond energies" in r2_call["query"]
    # ...plus the divergent solver claims (plurality B + dissent D), not
    # just the raw question again.
    assert "reasoning-B" in r2_call["query"]
    assert "reasoning-D" in r2_call["query"]
    assert r2_call["query"] != item.question

    # The output record captures exactly what R2 retrieved.
    assert result.rag_r2_query is not None
    assert "heat of formation sign convention" in result.rag_r2_query
    assert result.rag_r2_titles == ["Heat of formation", "Enthalpy", "Bond dissociation energy"]


def test_rag_recursive_r2_query_built_from_disputed_step_helper_directly():
    rebuttal = SkepticRebuttal(target_letter="B", disputed_step="disputed step text", argument="argument text")
    answers = [
        SolverAnswer(letter="B", confidence=0.7, reasoning="plurality reasoning", lens="lens1"),
        SolverAnswer(letter="B", confidence=0.6, reasoning="plurality reasoning 2", lens="lens2"),
        SolverAnswer(letter="D", confidence=0.5, reasoning="dissent reasoning", lens="lens3"),
    ]
    query = lever_experiments.build_disputed_step_query(rebuttal, answers)
    assert "disputed step text" in query
    assert "argument text" in query
    assert "plurality reasoning" in query
    assert "dissent reasoning" in query


# ---------------------------------------------------------------------------
# (b) retrieved R2 passages reach the Verifier's call as an evidence block;
#     the Verifier's existing MCP tool calls still fire alongside it
# ---------------------------------------------------------------------------


def test_rag_recursive_r2_evidence_reaches_verifier_not_r1_titles():
    rag = _rag_config()
    client = SplitTribunalClient()
    item = _item()

    asyncio.run(lever_experiments.run_question_lever(client, None, item, "rag_recursive", rag=rag))

    verifier_calls = [c for c in client.calls if c["role"] == "verifier"]
    assert len(verifier_calls) >= 1
    extract_call_user = verifier_calls[0]["user"]

    assert "Relevant reference passages" in extract_call_user
    assert "Heat of formation" in extract_call_user
    assert "Enthalpy" in extract_call_user
    # R1's titles must NOT leak into the R2 evidence block passed to the
    # verifier -- they were retrieved for a different (pre-solve) purpose.
    assert "Photon" not in extract_call_user
    assert "Electron" not in extract_call_user


def test_rag_recursive_verifier_tool_calls_still_fire_alongside_evidence():
    """ADDED grounding, not a replacement: a claim the Verifier proposes a
    real tool call for must still be executed and finalized exactly as the
    shipped engine does, evidence block or not."""
    rag = _rag_config()
    claims = [{"claim": "pi is about 3.14", "tool": "lookup_constant", "arguments": {"name": "pi"}}]
    client = SplitTribunalClient(verifier_claims=claims)
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_recursive", rag=rag)
    )

    assert len(result.verifier_findings) == 1
    assert result.verifier_findings[0].tool_used == "lookup_constant"
    assert result.verifier_findings[0].supports_claim is True

    verifier_calls = [c for c in client.calls if c["role"] == "verifier"]
    assert len(verifier_calls) == 2  # extract + finalize
    # Both the extraction call and the finalize call saw the R2 evidence
    # block -- it's injected as grounding context throughout the Verifier's
    # work, not just at claim-extraction time.
    for c in verifier_calls:
        assert "Relevant reference passages" in c["user"]
        assert "Heat of formation" in c["user"]


# ---------------------------------------------------------------------------
# (c) no escalation => only R1's single pre-solve retrieval fires
# ---------------------------------------------------------------------------


def test_rag_recursive_unanimous_no_r2_retrieval():
    rag = _rag_config()
    client = UnanimousClient()
    item = _item(correct_letter="B")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "rag_recursive", rag=rag)
    )

    assert result.escalated is False
    assert result.final_letter == "B"
    # Only R1's ONE retrieval fired -- no second (R2) retrieval on a
    # unanimous panel.
    assert len(rag.index.search_calls) == 1
    assert rag.index.search_calls[0]["query"] == item.question
    assert result.rag_r2_query is None
    assert result.rag_r2_titles == []


# ---------------------------------------------------------------------------
# (d) dispatch: rag_recursive routes through solve_all_rag_presolve for R1,
#     then the tribunal (skeptic -> R2 -> verifier -> judge) on a split
# ---------------------------------------------------------------------------


def test_rag_recursive_r1_solver_prompts_carry_evidence_like_rag_presolve():
    rag = _rag_config()
    client = SplitTribunalClient()
    item = _item()

    asyncio.run(lever_experiments.run_question_lever(client, None, item, "rag_recursive", rag=rag))

    solver_calls = [c for c in client.calls if c["role"] == "solver"]
    assert len(solver_calls) == 3
    assert all(c["model"] == MECHANICAL_MODEL for c in solver_calls)
    for c in solver_calls:
        assert "Relevant reference passages (may or may not be useful):" in c["user"]
        assert "[Photon]" in c["user"]  # R1's titles, injected before ANY solver runs


def test_rag_recursive_without_config_raises_value_error():
    client = SplitTribunalClient()
    item = _item()
    with pytest.raises(ValueError, match="rag_recursive"):
        asyncio.run(lever_experiments.run_question_lever(client, None, item, "rag_recursive"))


def test_rag_recursive_present_in_argparse_choices():
    import inspect

    source = inspect.getsource(lever_experiments)
    assert '"rag_recursive"' in source


def test_rag_recursive_judge_overturn_and_correctness_unaffected_by_r2_plumbing():
    rag = _rag_config()
    client = SplitTribunalClient(judge_letter="D", judge_overturn=True)
    item = _item(correct_letter="D")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "rag_recursive", rag=rag)
    )

    assert result.plurality_letter == "B"
    assert result.final_letter == "D"
    assert result.verdict.overturned_plurality is True
    assert result.correct is True
    assert result.false_escalation is False


# ---------------------------------------------------------------------------
# (e) output records carry a rag_r2 marker (+ snapshot id) on top of the
#     rag_presolve firewall fields; every other lever (incl. rag_presolve
#     itself) omits rag_r2 fields entirely
# ---------------------------------------------------------------------------


def _fake_result(rag_r2_query=None, rag_r2_titles=None, correct_letter="B", escalated=False):
    item = _item(question_id="q1", correct_letter=correct_letter)
    return QuestionResult(
        item=item,
        solver_answers=[SolverAnswer(letter="B", confidence=0.8, reasoning="r", lens="lens")],
        plurality_letter="B", escalated=escalated, final_letter="B", correct=True,
        rag_r2_query=rag_r2_query, rag_r2_titles=rag_r2_titles or [],
    )


def test_output_row_carries_rag_r2_on_when_r2_fired():
    rag = _rag_config(k=5)
    result = _fake_result(rag_r2_query="disputed step text plurality dissent", rag_r2_titles=["Heat of formation"], escalated=True)

    row = lever_experiments._build_output_row(result, "rag_recursive", 42, "supergpqa", rag)

    # R1 firewall fields, identical shape to rag_presolve.
    assert row["rag"] == "ON"
    assert row["rag_snapshot_id"] == "test-snapshot:v1"
    assert row["rag_k"] == 5
    # R2 marker.
    assert row["rag_r2"] == "ON"
    assert row["rag_r2_snapshot_id"] == "test-snapshot:v1"
    assert row["rag_r2_k"] == lever_experiments.RAG_R2_K
    assert row["rag_r2_query"] == "disputed step text plurality dissent"
    assert row["rag_r2_titles"] == ["Heat of formation"]
    assert row["lever"] == "rag_recursive"


def test_output_row_carries_rag_r2_off_when_unanimous_no_r2():
    rag = _rag_config(k=5)
    result = _fake_result(rag_r2_query=None, rag_r2_titles=[], escalated=False)

    row = lever_experiments._build_output_row(result, "rag_recursive", 42, "supergpqa", rag)

    assert row["rag"] == "ON"  # R1 always ran
    assert row["rag_r2"] == "OFF"  # R2 never fired on this (unanimous) question
    assert row["rag_r2_query"] is None
    assert row["rag_r2_titles"] == []


def test_output_row_omits_rag_r2_fields_for_rag_presolve():
    rag = _rag_config(k=5)
    result = _fake_result()
    row = lever_experiments._build_output_row(result, "rag_presolve", 42, "supergpqa", rag)
    assert row["rag"] == "ON"  # rag_presolve still carries its own R1 marker
    assert "rag_r2" not in row
    assert "rag_r2_snapshot_id" not in row
    assert "rag_r2_titles" not in row


def test_output_row_omits_all_rag_fields_for_unrelated_lever():
    result = _fake_result()
    row = lever_experiments._build_output_row(result, "gate", 42, "gpqa", None)
    assert "rag" not in row
    assert "rag_r2" not in row
    assert "rag_r2_titles" not in row


# ---------------------------------------------------------------------------
# (f) missing-index / missing-config still fails loud -- rag_recursive reuses
#     rag_presolve's fail-loud contract unchanged
# ---------------------------------------------------------------------------


def test_open_rag_index_missing_db_raises_file_not_found_still(tmp_path):
    missing = tmp_path / "no_such_index.sqlite3"
    with pytest.raises(FileNotFoundError) as exc_info:
        lever_experiments.open_rag_index(missing)
    assert str(missing) in str(exc_info.value)
