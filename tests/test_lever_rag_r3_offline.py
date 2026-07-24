"""Offline tests for the rag_r3_targeted lever (benchmark/lever_experiments.py,
docs/reasoning-supercharge-plan.md W6 -- targeted escalation-stage
retrieval) and its relevance-rubric harness
(benchmark/r3_relevance_rubric.md, benchmark/score_r3_relevance.py).
CONDITIONAL lever: built now, run only if W1/W2 screen positive -- these
tests prove the machinery works, nothing here runs a live pilot. No live
API calls, no cost, no real RAG index on disk.

Base = rag_thinking_gate (R1 pre-solve retrieval + thinking_gate panel
shape), completely unchanged. On EVERY escalation (no minority
precondition, unlike tribunal_debate): one extraction call turns the
skeptic's rebuttal into a disputed_claim; one retrieval (top-k=5) against
that claim; the retrieved passages are passed to both the Verifier
(evidence_block) and the Judge (an appended EVIDENCE section). Covers:

  (a) escalated -> extraction called exactly once, retrieval queried with
      the EXTRACTED claim (not the raw question), evidence block reaches
      BOTH the verifier (evidence_block arg via a fake tool session +
      client assertion) and the judge prompt (substring assertion).
  (b) non-escalated -> zero extraction/retrieval calls, byte-identical to
      rag_thinking_gate.
  (c) missing/failing index -> logged fallback, no crash, no evidence
      reaches verifier/judge, r3_query_fired=False.
  (d) note fields populated (disputed_claim/r3_query_fired/r3_passages/
      r3_evidence_used_by); r3_passages carries only title/id/score, never
      full passage text.
  (e) dispatch/argparse: rag_r3_targeted requires a RagPresolveConfig
      (same fail-loud contract as rag_thinking_gate), and is a real
      argparse --lever choice.
  (f) _build_output_row folds the W6 note fields into the row, plus the
      standard rag_presolve firewall fields (rag="ON"/rag_snapshot_id/...).
  (g) rubric harness: the script's prompt matches the rubric file exactly
      (content test, not a hand-duplicated copy); majority-of-3
      aggregation (2/3 on-topic -> on-topic, 1/3 -> off-topic); blinding
      (the built prompt contains the claim + passage, NEVER the original
      question text).

Mirrors the fake-client / FakeRagIndex patterns in
tests/test_lever_rag_thinking_gate_offline.py and
tests/test_lever_rag_recursive_offline.py.
"""

import asyncio
import inspect

import pytest

import benchmark.lever_experiments as lever_experiments
import benchmark.score_r3_relevance as score_r3_relevance
from quorumqa.config import MECHANICAL_MODEL
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


class FakeToolSession:
    async def call(self, tool_name, arguments):
        return {"ok": True, "value": 1.0}


class FakeRagIndex:
    """Stands in for quorumqa.rag.store.RagIndex. Returns R1's canned
    result set on the FIRST search call (question-driven pre-solve
    retrieval) and R3's canned result set on every subsequent call
    (disputed-claim-driven retrieval) -- or raises `raise_on_call` (an
    exception instance) starting from that call index, to simulate a
    failed/unavailable index for the missing-index fallback tests."""

    def __init__(self, r1_results, r3_results=None, raise_from_call=None, raise_exc=None):
        self._r1_results = r1_results
        self._r3_results = r3_results if r3_results is not None else r1_results
        self.search_calls = []
        self._raise_from_call = raise_from_call
        self._raise_exc = raise_exc or FileNotFoundError("RAG index file not found")

    def search(self, query, query_vector, k=5):
        self.search_calls.append({"query": query, "query_vector": query_vector, "k": k})
        call_index = len(self.search_calls)
        if self._raise_from_call is not None and call_index >= self._raise_from_call:
            raise self._raise_exc
        results = self._r1_results if call_index == 1 else self._r3_results
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


def _r3_results():
    return [
        {"passage_id": 5, "article_id": "a5", "title": "Photoelectric effect",
         "text": "The photoelectric effect is the emission of electrons when light shines on a material. " * 5,
         "score": 0.93, "source_url": "https://example.org/Photoelectric_effect", "snapshot_id": "test-snapshot:v1"},
        {"passage_id": 6, "article_id": "a6", "title": "Work function",
         "text": "The work function is the minimum energy needed to remove an electron from a solid. " * 5,
         "score": 0.88, "source_url": "https://example.org/Work_function", "snapshot_id": "test-snapshot:v1"},
    ]


def _rag_config(r1=None, r3=None, k=5, embedder=None, raise_from_call=None, raise_exc=None):
    return lever_experiments.RagPresolveConfig(
        index=FakeRagIndex(
            r1 if r1 is not None else _r1_results(), r3 if r3 is not None else _r3_results(),
            raise_from_call=raise_from_call, raise_exc=raise_exc,
        ),
        embedder=embedder, k=k, snapshot_id="test-snapshot:v1",
        db_path=lever_experiments.Path("fake_index.sqlite3"),
    )


def _item(question_id="r3-1", correct_letter="D"):
    return GPQAItem(
        question_id=question_id, question="What emits electrons when light shines on it?",
        choices=["Photon", "Neutron", "Quark", "Metal surface"], correct_letter=correct_letter,
    )


class SplitTribunalClient:
    """Solvers split B/B/D (plurality B, dissent D -- thinking_gate's panel
    shape: seats 1-2 role="solver", seat 3 role="solver_thinking"). Records
    every call so tests can inspect exactly what the extraction/verifier/
    judge each saw. `gate_doubt` is unused here (split panels escalate
    unconditionally) but kept for signature symmetry with other fakes."""

    def __init__(self, disputed_claim="the photoelectric effect requires light above a threshold frequency",
                 verifier_claims=None, judge_letter="D", judge_overturn=True):
        self.calls = []
        self._disputed_claim = disputed_claim
        self._verifier_claims = verifier_claims if verifier_claims is not None else []
        self._judge_letter = judge_letter
        self._judge_overturn = judge_overturn
        self._verifier_call_count = 0

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "system": system, "user": user, "thinking": thinking})
        if role in ("solver", "solver_thinking"):
            letters = ["B", "B", "D"]
            idx = sum(1 for c in self.calls if c["role"] in ("solver", "solver_thinking")) - 1
            return JsonCallResult(
                data={"letter": letters[idx], "confidence": 0.7, "reasoning": f"reasoning-{letters[idx]}"},
                usage=_usage(role),
            )
        if role == "skeptic":
            return JsonCallResult(
                data={"target_letter": "B", "disputed_step": "whether light frequency matters",
                      "argument": "the photoelectric effect needs light above a threshold frequency"},
                usage=_usage("skeptic"),
            )
        if role == "r3_extract":
            return JsonCallResult(data={"disputed_claim": self._disputed_claim}, usage=_usage("r3_extract"))
        if role == "verifier":
            self._verifier_call_count += 1
            if self._verifier_call_count == 1:
                return JsonCallResult(data={"claims": self._verifier_claims}, usage=_usage("verifier"))
            findings = [{"claim": c["claim"], "supports_claim": True, "explanation": "checked"} for c in self._verifier_claims]
            return JsonCallResult(data={"findings": findings}, usage=_usage("verifier"))
        if role == "judge":
            return JsonCallResult(
                data={"final_letter": self._judge_letter, "decisive_reasoning": "judge ruled",
                      "dissent": None, "overturned_plurality": self._judge_overturn, "confidence": "high"},
                usage=_usage("judge"),
            )
        raise AssertionError(f"unexpected role {role!r} (calls so far: {self.calls})")


class UnanimousGateClient:
    """All three seats agree; gate always flags doubt, forcing escalation
    with NO natural minority (mirrors tribunal_debate's unanimous-gate-fired
    case, but W6 still runs extraction/retrieval on ANY escalation)."""

    def __init__(self, letter="B", disputed_claim="claim text"):
        self.calls = []
        self._letter = letter
        self._disputed_claim = disputed_claim

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "system": system, "user": user, "thinking": thinking})
        if role in ("solver", "solver_thinking"):
            return JsonCallResult(data={"letter": self._letter, "confidence": 0.7, "reasoning": "because"}, usage=_usage(role))
        if role == "gate":
            return JsonCallResult(data={"doubt": True, "reason": "not fully convinced"}, usage=_usage("gate"))
        if role == "skeptic":
            return JsonCallResult(
                data={"target_letter": self._letter, "disputed_step": "step", "argument": "argument"},
                usage=_usage("skeptic"),
            )
        if role == "r3_extract":
            return JsonCallResult(data={"disputed_claim": self._disputed_claim}, usage=_usage("r3_extract"))
        if role == "verifier":
            return JsonCallResult(data={"claims": []}, usage=_usage("verifier"))
        if role == "judge":
            return JsonCallResult(
                data={"final_letter": self._letter, "decisive_reasoning": "confirmed", "dissent": None,
                      "overturned_plurality": False, "confidence": "high"},
                usage=_usage("judge"),
            )
        raise AssertionError(f"unexpected role {role!r}")


class RecordingUnanimousClient:
    """All three seats agree, gate never doubts -- accepted without ever
    escalating. Any call beyond the 3 solver calls + 1 gate call raises
    AssertionError, proving no R3 machinery runs."""

    def __init__(self, letter="B"):
        self.calls = []
        self._letter = letter

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "system": system, "user": user, "thinking": thinking})
        if role in ("solver", "solver_thinking"):
            return JsonCallResult(data={"letter": self._letter, "confidence": 0.7, "reasoning": "because"}, usage=_usage(role))
        if role == "gate":
            return JsonCallResult(data={"doubt": False, "reason": ""}, usage=_usage("gate"))
        raise AssertionError(f"unexpected role {role!r} for a non-escalated question")


# ---------------------------------------------------------------------------
# (a) escalated: extraction fires once, retrieval uses the EXTRACTED claim,
#     evidence reaches both the verifier and the judge
# ---------------------------------------------------------------------------


def test_escalated_extraction_fires_once_with_disputed_claim():
    rag = _rag_config()
    claim = "the photoelectric effect requires light above a threshold frequency"
    client = SplitTribunalClient(disputed_claim=claim)
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_r3_targeted", rag=rag)
    )

    assert result.escalated is True
    extract_calls = [c for c in client.calls if c["role"] == "r3_extract"]
    assert len(extract_calls) == 1
    assert extract_calls[0]["model"] == MECHANICAL_MODEL
    assert extract_calls[0]["thinking"] is False
    assert "whether light frequency matters" in extract_calls[0]["user"]

    # Exactly 2 searches: R1 (question-driven) then R3 (claim-driven) -- not
    # once per solver seat.
    assert len(rag.index.search_calls) == 2
    r1_call, r3_call = rag.index.search_calls
    assert r1_call["query"] == item.question
    assert r3_call["query"] == claim  # R3 queries the EXTRACTED claim, not the raw question
    assert r3_call["k"] == lever_experiments.RAG_R3_K == 5

    assert note["disputed_claim"] == claim


def test_r3_evidence_reaches_verifier_via_evidence_block():
    rag = _rag_config()
    claims = [{"claim": "the work function of the metal is 2 eV", "tool": "lookup_constant", "arguments": {"name": "work_function"}}]
    client = SplitTribunalClient(verifier_claims=claims)
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_r3_targeted", rag=rag)
    )

    verifier_calls = [c for c in client.calls if c["role"] == "verifier"]
    assert len(verifier_calls) == 2  # extract + finalize
    for c in verifier_calls:
        assert "Relevant reference passages" in c["user"]
        assert "Photoelectric effect" in c["user"] or "Work function" in c["user"]
    # R1's titles must NOT leak into the R3 evidence block passed to the verifier.
    assert "Photon" not in verifier_calls[0]["user"]
    assert "Electron" not in verifier_calls[0]["user"]

    assert len(result.verifier_findings) == 1
    assert result.verifier_findings[0].supports_claim is True
    assert "verifier" in note["r3_evidence_used_by"]
    assert "judge" in note["r3_evidence_used_by"]


def test_r3_evidence_reaches_judge_prompt_as_evidence_section():
    rag = _rag_config()
    client = SplitTribunalClient()
    item = _item()

    asyncio.run(lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_r3_targeted", rag=rag))

    judge_calls = [c for c in client.calls if c["role"] == "judge"]
    assert len(judge_calls) == 1
    assert "EVIDENCE (retrieved for the disputed claim)" in judge_calls[0]["user"]
    assert "Photoelectric effect" in judge_calls[0]["user"]


# ---------------------------------------------------------------------------
# (b) non-escalated: zero extraction/retrieval calls, byte-identical to
#     rag_thinking_gate
# ---------------------------------------------------------------------------


def test_non_escalated_zero_extraction_and_retrieval_calls():
    rag = _rag_config()
    client = RecordingUnanimousClient(letter="B")
    item = _item(correct_letter="B")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_r3_targeted", rag=rag)
    )

    assert result.escalated is False
    assert result.final_letter == "B"
    # Only R1's single pre-solve retrieval fired -- no R3 retrieval at all.
    assert len(rag.index.search_calls) == 1
    assert rag.index.search_calls[0]["query"] == item.question
    assert not any(c["role"] == "r3_extract" for c in client.calls)
    # Non-escalated note stays whatever rag_thinking_gate would log (plain
    # string or None) -- not the W6 dict shape.
    assert not isinstance(note, dict) or note is None


# ---------------------------------------------------------------------------
# (c) missing/failing index: logged fallback, no crash, no evidence used
# ---------------------------------------------------------------------------


def test_r3_retrieval_failure_logs_fallback_no_crash_no_evidence(caplog):
    # R1's retrieval (call #1) succeeds; R3's retrieval (call #2 onward)
    # raises, simulating an index that became unavailable between R1 and R3.
    rag = _rag_config(raise_from_call=2, raise_exc=FileNotFoundError("index file missing"))
    client = SplitTribunalClient()
    item = _item()

    with caplog.at_level("WARNING"):
        result, note = asyncio.run(
            lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_r3_targeted", rag=rag)
        )

    # No crash: the question still completes and escalates normally.
    assert result.escalated is True
    assert note["r3_query_fired"] is False
    assert note["r3_passages"] == []
    assert note["r3_evidence_used_by"] == []
    assert "R3 retrieval failed" in caplog.text

    verifier_calls = [c for c in client.calls if c["role"] == "verifier"]
    judge_calls = [c for c in client.calls if c["role"] == "judge"]
    assert "Relevant reference passages" not in verifier_calls[0]["user"]
    assert "EVIDENCE (retrieved for the disputed claim)" not in judge_calls[0]["user"]


def test_retrieve_r3_evidence_helper_returns_fired_false_on_exception():
    rag = _rag_config(raise_from_call=1, raise_exc=RuntimeError("boom"))
    results, fired = lever_experiments.retrieve_r3_evidence(rag, "some claim", k=5)
    assert results == []
    assert fired is False


def test_retrieve_r3_evidence_helper_returns_fired_true_on_success():
    rag = _rag_config()
    results, fired = lever_experiments.retrieve_r3_evidence(rag, "some claim", k=5)
    assert fired is True
    assert len(results) == 2


# ---------------------------------------------------------------------------
# (d) note fields populated; r3_passages carries titles/ids/scores only
# ---------------------------------------------------------------------------


def test_note_fields_populated_and_passages_carry_no_full_text():
    rag = _rag_config()
    client = SplitTribunalClient()
    item = _item()

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_r3_targeted", rag=rag)
    )

    assert set(note.keys()) == {"disputed_claim", "r3_query_fired", "r3_passages", "r3_evidence_used_by"}
    assert note["r3_query_fired"] is True
    assert len(note["r3_passages"]) == 2
    for p in note["r3_passages"]:
        assert set(p.keys()) == {"title", "id", "score"}
        assert isinstance(p["title"], str)
        # No full passage text anywhere in the logged record.
        assert "text" not in p


def test_unanimous_gate_fired_escalation_still_runs_r3_no_minority_precondition():
    # Unlike W4 (tribunal_debate), W6 has NO minority precondition -- R3
    # fires on every escalation, including a unanimous-but-gate-forced one.
    rag = _rag_config()
    client = UnanimousGateClient(letter="B")
    item = _item(correct_letter="B")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_r3_targeted", rag=rag)
    )

    assert result.escalated is True
    assert result.plurality_letter == "B"
    extract_calls = [c for c in client.calls if c["role"] == "r3_extract"]
    assert len(extract_calls) == 1
    assert note["r3_query_fired"] is True
    assert len(note["r3_passages"]) == 2


# ---------------------------------------------------------------------------
# (e) dispatch/argparse
# ---------------------------------------------------------------------------


def test_run_question_lever_rag_r3_targeted_without_config_raises_value_error():
    client = SplitTribunalClient()
    item = _item()
    with pytest.raises(ValueError, match="rag_r3_targeted"):
        asyncio.run(lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_r3_targeted"))


def test_rag_r3_targeted_present_in_argparse_choices():
    source = inspect.getsource(lever_experiments)
    assert '"rag_r3_targeted"' in source


def test_rag_r3_targeted_added_to_main_live_rag_dispatch():
    source = inspect.getsource(lever_experiments.main_live)
    assert "rag_r3_targeted" in source


# ---------------------------------------------------------------------------
# (f) _build_output_row folds W6 fields + standard rag firewall fields
# ---------------------------------------------------------------------------


def test_build_output_row_folds_r3_fields_and_rag_firewall():
    rag = _rag_config(k=5)
    client = SplitTribunalClient()
    item = _item()
    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_r3_targeted", rag=rag)
    )

    row = lever_experiments._build_output_row(result, "rag_r3_targeted", 42, "supergpqa", rag, None, note)

    assert row["rag"] == "ON"
    assert row["rag_snapshot_id"] == "test-snapshot:v1"
    assert row["rag_k"] == 5
    assert row["disputed_claim"] == note["disputed_claim"]
    assert row["r3_query_fired"] is True
    assert len(row["r3_passages"]) == 2
    assert row["r3_evidence_used_by"] == ["verifier", "judge"]
    assert "rag_r2" not in row  # rag_r3_targeted never does R2


def test_build_output_row_omits_r3_fields_for_non_escalated_row():
    rag = _rag_config(k=5)
    client = RecordingUnanimousClient(letter="B")
    item = _item(correct_letter="B")
    result, note = asyncio.run(
        lever_experiments.run_question_lever(client, FakeToolSession(), item, "rag_r3_targeted", rag=rag)
    )

    row = lever_experiments._build_output_row(result, "rag_r3_targeted", 42, "supergpqa", rag, None, note)
    assert row["rag"] == "ON"  # R1 firewall fields still present
    assert "disputed_claim" not in row  # no note dict to fold, byte-identical to rag_thinking_gate


# ---------------------------------------------------------------------------
# (g) rubric harness: script prompt == rubric file, majority-of-3, blinding
# ---------------------------------------------------------------------------


def test_rubric_prompt_loaded_from_file_matches_frozen_markers():
    raw = score_r3_relevance.load_rubric_prompt()
    text = score_r3_relevance.RUBRIC_PATH.read_text(encoding="utf-8")
    start = text.index(score_r3_relevance._PROMPT_START_MARKER) + len(score_r3_relevance._PROMPT_START_MARKER)
    end = text.index(score_r3_relevance._PROMPT_END_MARKER)
    assert raw == text[start:end].strip("\n")
    assert "on_topic" in raw
    assert "SYSTEM:" in raw and "USER:" in raw


def test_rubric_system_and_user_prompt_reads_exactly_from_file_content():
    system = score_r3_relevance.rubric_system_prompt()
    user_prompt = score_r3_relevance.build_rubric_user_prompt("claim X", "passage Y")
    raw = score_r3_relevance.load_rubric_prompt()
    assert system in raw
    assert "claim X" in user_prompt
    assert "passage Y" in user_prompt
    # The user prompt is built from the SAME template text committed in the
    # rubric file -- not a hand-duplicated copy.
    assert "JSON shape:" in user_prompt


def test_majority_of_3_two_on_topic_one_off_topic_yields_on_topic():
    votes_queue = [
        JsonCallResult(data={"on_topic": True, "reason": "relevant"}, usage=_usage("r3_relevance")),
        JsonCallResult(data={"on_topic": True, "reason": "relevant"}, usage=_usage("r3_relevance")),
        JsonCallResult(data={"on_topic": False, "reason": "not relevant"}, usage=_usage("r3_relevance")),
    ]

    class FakeRubricClient:
        def __init__(self):
            self.calls = []

        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            self.calls.append({"model": model, "system": system, "user": user, "role": role, "temperature": temperature})
            return votes_queue[len(self.calls) - 1]

    client = FakeRubricClient()
    on_topic, votes = score_r3_relevance.score_passage_relevance(client, "disputed claim text", "passage text")

    assert on_topic is True
    assert len(votes) == 3
    assert len(client.calls) == 3
    assert all(c["role"] == "r3_relevance" for c in client.calls)
    assert all(c["temperature"] == 0.0 for c in client.calls)


def test_majority_of_3_one_on_topic_two_off_topic_yields_off_topic():
    votes_queue = [
        JsonCallResult(data={"on_topic": False, "reason": "no"}, usage=_usage("r3_relevance")),
        JsonCallResult(data={"on_topic": True, "reason": "yes"}, usage=_usage("r3_relevance")),
        JsonCallResult(data={"on_topic": False, "reason": "no"}, usage=_usage("r3_relevance")),
    ]

    class FakeRubricClient:
        def __init__(self):
            self.calls = []

        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            self.calls.append(1)
            return votes_queue[len(self.calls) - 1]

    client = FakeRubricClient()
    on_topic, votes = score_r3_relevance.score_passage_relevance(client, "claim", "passage")
    assert on_topic is False


def test_blinding_prompt_contains_claim_and_passage_not_question_text():
    question_text = "What is the boiling point of water at sea level in a laboratory setting today?"
    user_prompt = score_r3_relevance.build_rubric_user_prompt(
        "water boils at 100 C at 1 atm", "Water's boiling point depends on atmospheric pressure.",
    )
    assert "water boils at 100 C at 1 atm" in user_prompt
    assert "Water's boiling point depends on atmospheric pressure." in user_prompt
    assert question_text not in user_prompt
    # The rubric's own frozen text never mentions "exam question" content --
    # only instructs the model not to assume it.
    system = score_r3_relevance.rubric_system_prompt()
    assert question_text not in system


def test_off_topic_kill_threshold_matches_plan_pre_registration():
    assert score_r3_relevance.OFF_TOPIC_KILL_THRESHOLD == 0.50


def test_score_r3_result_file_end_to_end_with_fake_lookup():
    records = [
        {
            "lever": "rag_r3_targeted", "engine": {"item": {"question_id": "q1"}},
            "disputed_claim": "claim A", "r3_query_fired": True,
            "r3_passages": [{"title": "T1", "id": 1, "score": 0.9}, {"title": "T2", "id": 2, "score": 0.8}],
            "rag_db": "fake.sqlite3",
        },
        {
            "lever": "rag_r3_targeted", "engine": {"item": {"question_id": "q2"}},
            "disputed_claim": None, "r3_query_fired": False, "r3_passages": [], "rag_db": "fake.sqlite3",
        },
        {"lever": "rag_thinking_gate", "engine": {"item": {"question_id": "q3"}}},
    ]

    # Always-on-topic fake client (3 votes true per call).
    class AlwaysOnTopicClient:
        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            return JsonCallResult(data={"on_topic": True, "reason": "relevant"}, usage=_usage(role))

    def _lookup(claim, passage):
        return f"full text of {passage['title']}"

    report = score_r3_relevance.score_r3_result_file(AlwaysOnTopicClient(), records, _lookup)

    assert report["total_passages"] == 2  # only q1's two passages -- q2 never fired, q3 isn't rag_r3_targeted
    assert report["off_topic_count"] == 0
    assert report["off_topic_rate"] == 0.0
    assert report["killed"] is False
    assert report["threshold"] == 0.50


def test_score_r3_result_file_kill_fires_above_threshold():
    records = [{
        "lever": "rag_r3_targeted", "engine": {"item": {"question_id": "q1"}},
        "disputed_claim": "claim A", "r3_query_fired": True,
        "r3_passages": [{"title": "T1", "id": 1, "score": 0.9}, {"title": "T2", "id": 2, "score": 0.8}],
        "rag_db": "fake.sqlite3",
    }]

    class AlwaysOffTopicClient:
        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            return JsonCallResult(data={"on_topic": False, "reason": "irrelevant"}, usage=_usage(role))

    def _lookup(claim, passage):
        return f"full text of {passage['title']}"

    report = score_r3_relevance.score_r3_result_file(AlwaysOffTopicClient(), records, _lookup)
    assert report["off_topic_rate"] == 1.0
    assert report["killed"] is True


def test_extract_r3_claim_passage_rows_filters_correctly():
    records = [
        {"lever": "rag_r3_targeted", "r3_query_fired": True, "r3_passages": [{"title": "T1"}], "disputed_claim": "c1", "rag_db": "x", "engine": {"item": {"question_id": "q1"}}},
        {"lever": "rag_r3_targeted", "r3_query_fired": False, "r3_passages": [], "disputed_claim": None, "engine": {"item": {}}},
        {"lever": "rag_r3_targeted", "r3_query_fired": True, "r3_passages": [], "disputed_claim": "c3", "engine": {"item": {}}},
        {"lever": "rag_thinking_gate", "r3_query_fired": True, "r3_passages": [{"title": "T4"}], "engine": {"item": {}}},
    ]
    rows = score_r3_relevance.extract_r3_claim_passage_rows(records)
    assert len(rows) == 1
    assert rows[0]["disputed_claim"] == "c1"
    assert rows[0]["question_id"] == "q1"
