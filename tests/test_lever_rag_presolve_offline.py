"""Offline tests for the rag_presolve lever (benchmark/lever_experiments.py)
-- no live API calls, no cost, no real RAG index on disk. Covers:
  (a) rag_presolve retrieves ONCE per question and injects the evidence
      block into every solver seat's user prompt (system prompt/JSON
      contract untouched).
  (b) a missing index DB fails loudly (open_rag_index / build_rag_presolve_
      config raise FileNotFoundError; run_question_lever raises ValueError
      if dispatched without a RagPresolveConfig at all) -- this lever must
      never silently run the cheap panel without retrieval.
  (c) dispatch: run_question_lever routes lever="rag_presolve" through
      solve_all_rag_presolve (not the plain solve_all path), while
      skeptic/verifier/judge/escalation stay on the shipped path.
  (d) output records carry rag="ON" + rag_snapshot_id (and omit them for
      every other lever) -- the firewall labeling requirement.

Mirrors the fake-client pattern in tests/test_engine_offline.py and
tests/test_lever_qwen38_panel_offline.py; the RAG index itself is faked
(FakeRagIndex) rather than built for real, matching tests/test_rag_store.py's
"hand-built, predictable" style but without needing sentence-transformers.
"""

import asyncio

import pytest

import benchmark.lever_experiments as lever_experiments
from quorumqa.config import MECHANICAL_MODEL
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem, QuestionResult, SolverAnswer


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class FakeRagIndex:
    """Stands in for quorumqa.rag.store.RagIndex -- just enough surface
    (.search) for solve_all_rag_presolve, plus call recording so tests can
    assert retrieval happened exactly once per question (not once per
    solver seat)."""

    def __init__(self, results):
        self._results = results
        self.search_calls = []

    def search(self, query, query_vector, k=5):
        self.search_calls.append({"query": query, "query_vector": query_vector, "k": k})
        return self._results[:k]


class RecordingClient:
    """Records every chat_json call's (role, model, system, user, thinking).
    Raises on any role other than "solver" -- a unanimous rag_presolve
    question should never reach skeptic/verifier/judge."""

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
        raise AssertionError(f"unexpected role {role!r} for a unanimous rag_presolve question")


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


def _item(question_id="q1", correct_letter="B"):
    return GPQAItem(
        question_id=question_id, question="What carries energy as electromagnetic radiation?",
        choices=["Photon", "Neutron", "Quark", "Proton"], correct_letter=correct_letter,
    )


# ---------------------------------------------------------------------------
# (a) retrieval fires once, evidence block reaches every solver's user
#     prompt, system prompt/JSON contract untouched
# ---------------------------------------------------------------------------


def test_rag_presolve_injects_evidence_block_into_every_solver_prompt():
    rag = _rag_config()
    client = RecordingClient()
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, None, item, "rag_presolve", rag=rag)
    )

    solver_calls = [c for c in client.calls if c["role"] == "solver"]
    assert len(solver_calls) == 3
    assert all(c["model"] == MECHANICAL_MODEL for c in solver_calls)
    assert all(c["thinking"] is False for c in solver_calls)  # shipped-engine solver default, unchanged

    for c in solver_calls:
        assert "Relevant reference passages (may or may not be useful):" in c["user"]
        assert "[Photon]" in c["user"]
        assert "[Electron]" in c["user"]
        assert "Question: What carries energy" in c["user"]
        # System prompt (SOLVER_SYSTEM + lens) and JSON contract must be
        # byte-for-byte unchanged from the shipped engine.
        assert lever_experiments.SOLVER_SYSTEM in c["system"]
        assert '"letter": "A|B|C|D"' in c["user"]

    # Distinct lenses used across the 3 seats (panel diversity preserved).
    assert len({c["system"] for c in solver_calls}) == 3

    # Retrieval happened exactly ONCE for the question, not once per seat.
    assert len(rag.index.search_calls) == 1
    assert rag.index.search_calls[0]["k"] == 5
    assert rag.index.search_calls[0]["query"] == item.question

    assert result.escalated is False
    assert result.final_letter == "B"
    assert result.correct is True


def test_rag_presolve_evidence_snippets_are_word_budgeted():
    long_text = "word " * 500
    results = [
        {"passage_id": 1, "article_id": "a1", "title": "LongArticle", "text": long_text,
         "score": 0.9, "source_url": None, "snapshot_id": "test-snapshot:v1"},
    ]
    block = lever_experiments.build_evidence_block(results, word_budget=200)
    # One passage gets the whole budget (200 words) -- must not just dump
    # the full 500-word passage in verbatim.
    body = block.split("] ", 1)[1]
    assert len(body.split()) <= 201  # 200 words + trailing "..."


def test_rag_presolve_no_results_yields_empty_block_and_unmodified_prompt():
    rag = _rag_config(results=[])
    client = RecordingClient()
    item = _item()

    asyncio.run(lever_experiments.run_question_lever(client, None, item, "rag_presolve", rag=rag))

    solver_calls = [c for c in client.calls if c["role"] == "solver"]
    for c in solver_calls:
        assert "Relevant reference passages" not in c["user"]
        assert c["user"].startswith("Question:")


# ---------------------------------------------------------------------------
# (b) missing-DB / missing-config fails loudly -- never a silent no-op
# ---------------------------------------------------------------------------


def test_open_rag_index_missing_db_raises_file_not_found(tmp_path):
    missing = tmp_path / "no_such_index.sqlite3"
    with pytest.raises(FileNotFoundError) as exc_info:
        lever_experiments.open_rag_index(missing)
    assert str(missing) in str(exc_info.value)


def test_build_rag_presolve_config_missing_db_raises_file_not_found(tmp_path):
    missing = tmp_path / "no_such_index.sqlite3"
    with pytest.raises(FileNotFoundError):
        lever_experiments.build_rag_presolve_config(missing)


def test_run_question_lever_rag_presolve_without_config_raises_value_error():
    client = RecordingClient()
    item = _item()
    with pytest.raises(ValueError, match="rag_presolve"):
        asyncio.run(lever_experiments.run_question_lever(client, None, item, "rag_presolve"))


def test_resolve_rag_db_path_cli_wins_over_env(monkeypatch):
    monkeypatch.setenv(lever_experiments.RAG_DB_ENV, "/env/path.sqlite3")
    resolved = lever_experiments.resolve_rag_db_path("/cli/path.sqlite3")
    assert resolved == lever_experiments.Path("/cli/path.sqlite3")


def test_resolve_rag_db_path_env_wins_over_default(monkeypatch):
    monkeypatch.setenv(lever_experiments.RAG_DB_ENV, "/env/path.sqlite3")
    resolved = lever_experiments.resolve_rag_db_path(None)
    assert resolved == lever_experiments.Path("/env/path.sqlite3")


def test_resolve_rag_db_path_default_is_preembedded_corpus(monkeypatch):
    monkeypatch.delenv(lever_experiments.RAG_DB_ENV, raising=False)
    resolved = lever_experiments.resolve_rag_db_path(None)
    assert resolved == lever_experiments.DEFAULT_RAG_DB_PATH
    assert resolved.name == "rag_index_preembedded.sqlite3"


# ---------------------------------------------------------------------------
# (c) dispatch: rag_presolve routes through solve_all_rag_presolve; a split
#     panel still escalates through the UNCHANGED shipped tribunal
# ---------------------------------------------------------------------------


def test_rag_presolve_split_panel_still_escalates_through_shipped_tribunal():
    rag = _rag_config()

    class SplitThenTribunalClient:
        def __init__(self):
            self.calls = []

        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            self.calls.append({"role": role, "user": user})
            if role == "solver":
                letters = ["B", "B", "D"]
                letter = letters[sum(1 for c in self.calls if c["role"] == "solver") - 1]
                assert "Relevant reference passages" in user  # evidence reached the split solvers too
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
        lever_experiments.run_question_lever(client, None, item, "rag_presolve", rag=rag)
    )

    assert result.escalated is True
    assert result.plurality_letter == "B"
    assert result.final_letter == "D"
    assert result.verdict.decisive_reasoning == "judge ruled"
    assert result.correct is True
    # Retrieval still only fired once for the whole question (shared by the
    # 3 solver seats), not once per seat and not again for the tribunal.
    assert len(rag.index.search_calls) == 1


def test_rag_presolve_present_in_argparse_choices():
    import inspect

    source = inspect.getsource(lever_experiments)
    assert '"rag_presolve"' in source


# ---------------------------------------------------------------------------
# (d) output records carry rag="ON" + rag_snapshot_id for rag_presolve, and
#     omit them entirely for every other lever
# ---------------------------------------------------------------------------


def _fake_result(correct_letter="B"):
    item = _item(correct_letter=correct_letter)
    return QuestionResult(
        item=item,
        solver_answers=[SolverAnswer(letter="B", confidence=0.8, reasoning="r", lens="lens")],
        plurality_letter="B", escalated=False, final_letter="B", correct=True,
    )


def test_output_row_carries_rag_on_and_snapshot_id_for_rag_presolve():
    rag = _rag_config(k=5)
    result = _fake_result()

    row = lever_experiments._build_output_row(result, "rag_presolve", 42, "supergpqa", rag)

    assert row["rag"] == "ON"
    assert row["rag_snapshot_id"] == "test-snapshot:v1"
    assert row["rag_k"] == 5
    assert row["rag_db"] == "fake_index.sqlite3"
    assert row["lever"] == "rag_presolve"
    assert row["seed"] == 42
    assert row["dataset"] == "supergpqa"
    assert row["engine"]["correct"] is True


def test_output_row_omits_rag_fields_for_every_other_lever():
    result = _fake_result()
    row = lever_experiments._build_output_row(result, "gate", 42, "gpqa", None)
    assert "rag" not in row
    assert "rag_snapshot_id" not in row
    assert "rag_k" not in row
    assert "rag_db" not in row
