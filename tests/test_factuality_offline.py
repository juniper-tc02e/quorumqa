"""Offline tests for benchmark/factuality_engine.py + the mojibake-repair
piece of benchmark/load_simpleqa.py -- no live API calls, no cost, no real
RAG index or SimpleQA download on disk. Fake clients match this repo's real
QwenClient return shapes: chat_json() -> JsonCallResult(data=..., usage=...)
(see quorumqa.qwen_client.JsonCallResult) and chat() -> (text, CallUsage)
tuple. Mirrors the fake-client pattern tests/test_math_open_engine_offline.py
and tests/test_lever_rag_presolve_offline.py already use for this repo's
offline suite; the RAG index is faked (FakeRagIndex) the same way
test_lever_rag_presolve_offline.py does, rather than built for real.

Covers (per the build spec):
  (a) Free-text clustering: case/article/punctuation variants normalize to
      the same string (cluster together); genuinely different answers do
      not -- both as a direct normalize_answer property and end-to-end via
      solve_panel_factual's n_clusters/cluster_margin fields.
  (b) Abstain path: an unsupported answer -> abstained=True, final_answer
      cleared, and NEVER scored as correct even when the pre-abstain
      candidate matched gold exactly.
  (c) Supported path -> answered (not abstained), correct scored normally.
  (d) Panel dispatch: a clear plurality wins outright (no judge call); a
      full split with no margin escalates to judge_factual, which can
      itself terminate the item as ABSTAIN directly.
  (e) exact_match_normalized: positives, negatives, and the documented
      under-counting-on-paraphrase limitation.
  (f) grade_simpleqa: the three official labels from canned plain-text
      judge responses, plus the NOT_ATTEMPTED fallback on an unparseable
      response, plus the prompt actually carries question/gold/predicted.
  (g) compute_simpleqa_metrics: the three-way metric arithmetic.
  (h) Missing/broken RAG index -> no crash, no evidence, a warning is
      logged (both at try_open_factuality_rag and inside solve_panel_factual
      when a passed-in rag object's search() itself raises).
  (i) Retrieval titles/scores are logged on the output row WITHOUT the full
      passage text.
  (j) load_simpleqa._fix_mojibake: detects and repairs the known double-
      encoded-UTF-8 pattern, and leaves already-clean text and non-matching
      strings untouched.
"""

import logging

import benchmark.lever_experiments as lever_experiments
from quorumqa.engine.solver import _lenses_for
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage

from benchmark.factuality_engine import (
    compute_simpleqa_metrics,
    exact_match_normalized,
    grade_simpleqa,
    normalize_answer,
    solve_panel_factual,
    solve_single_factual,
    try_open_factuality_rag,
    verify_claim_against_evidence,
)
from benchmark.load_simpleqa import SimpleQAItem, _fix_mojibake


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


def _item(question_id="q1", gold_answer="Paris", question="What is the capital of France?", topic="Geography", answer_type="Place") -> SimpleQAItem:
    return SimpleQAItem(question_id=question_id, question=question, gold_answer=gold_answer, topic=topic, answer_type=answer_type)


def _answers_by_lens(answers: list[str]) -> dict[str, str]:
    lenses = _lenses_for(len(answers))
    return dict(zip(lenses, answers))


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeRagIndex:
    """Stands in for quorumqa.rag.store.RagIndex -- just .search(), plus
    call recording, matching tests/test_lever_rag_presolve_offline.py's
    FakeRagIndex."""

    def __init__(self, results):
        self._results = results
        self.search_calls = []

    def search(self, query, query_vector, k=5):
        self.search_calls.append({"query": query, "query_vector": query_vector, "k": k})
        return self._results[:k]


class RaisingRagIndex:
    """A RAG index whose .search() always raises -- for the "retrieval
    fails mid-call even though the config itself opened fine" path."""

    def search(self, query, query_vector, k=5):
        raise RuntimeError("index corrupted")


def _canned_passages():
    return [
        {"passage_id": 1, "article_id": "a1", "title": "Photon",
         "text": "A photon is a quantum of electromagnetic radiation carrying energy. " * 5,
         "score": 0.9, "source_url": "https://example.org/Photon", "snapshot_id": "test-snapshot:v1"},
        {"passage_id": 2, "article_id": "a2", "title": "Electron",
         "text": "An electron is a subatomic particle with negative electric charge. " * 5,
         "score": 0.8, "source_url": "https://example.org/Electron", "snapshot_id": "test-snapshot:v1"},
    ]


def _rag_config(index=None, results=None, k=5):
    return lever_experiments.RagPresolveConfig(
        index=index if index is not None else FakeRagIndex(results if results is not None else _canned_passages()),
        embedder=None, k=k, snapshot_id="test-snapshot:v1",
        db_path=lever_experiments.Path("fake_index.sqlite3"),
    )


class FakePanelClient:
    """Configurable fake for the whole panel: solver seats (keyed by lens
    embedded in the system prompt, same pattern as test_math_open_engine_
    offline.FakePanelClient), the judge, and the verifier."""

    def __init__(
        self, answers_by_lens: dict[str, str],
        judge_answer: str = "", judge_abstain: bool = False, judge_reasoning: str = "judged",
        verify_supported: bool = True, verify_quote: str = "the quote", verify_reason: str = "matches",
    ):
        self._answers_by_lens = answers_by_lens
        self._judge_answer = judge_answer
        self._judge_abstain = judge_abstain
        self._judge_reasoning = judge_reasoning
        self._verify_supported = verify_supported
        self._verify_quote = verify_quote
        self._verify_reason = verify_reason
        self.solver_calls = 0
        self.judge_calls = 0
        self.verify_calls = 0
        self.calls: list[dict] = []

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"role": role, "model": model, "system": system, "user": user, "thinking": thinking})
        if role == "solver":
            self.solver_calls += 1
            lens = next(l for l in self._answers_by_lens if l in system)
            answer = self._answers_by_lens[lens]
            return JsonCallResult(data={"answer": answer, "confidence": 0.7, "reasoning": f"because of {lens!r}"}, usage=_usage("solver"))
        if role == "judge":
            self.judge_calls += 1
            return JsonCallResult(
                data={"answer": self._judge_answer, "abstain": self._judge_abstain, "reasoning": self._judge_reasoning},
                usage=_usage("judge"),
            )
        if role == "verifier":
            self.verify_calls += 1
            return JsonCallResult(
                data={"supported": self._verify_supported, "quote": self._verify_quote, "reason": self._verify_reason},
                usage=_usage("verifier"),
            )
        raise AssertionError(f"unexpected role {role!r}")


class _SingleFactualClient:
    def __init__(self, answer: str, abstain: bool, reasoning: str = "r"):
        self.answer, self.abstain, self.reasoning = answer, abstain, reasoning
        self.calls: list[dict] = []

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"model": model, "role": role, "thinking": thinking})
        if role != "baseline":
            raise AssertionError(f"unexpected role {role!r}")
        return JsonCallResult(data={"answer": self.answer, "abstain": self.abstain, "reasoning": self.reasoning}, usage=_usage("baseline"))


class _VerifyOnlyClient:
    def __init__(self, supported: bool, quote: str = "the quote", reason: str = "matches"):
        self.supported, self.quote, self.reason = supported, quote, reason
        self.calls: list[dict] = []

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"model": model, "role": role, "user": user})
        if role != "verifier":
            raise AssertionError(f"unexpected role {role!r}")
        return JsonCallResult(data={"supported": self.supported, "quote": self.quote, "reason": self.reason}, usage=_usage("verifier"))


class _GraderClient:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls: list[dict] = []

    def chat(self, model, messages, role, temperature=0.4, max_tokens=1024, thinking=True, seed=None, thinking_budget=None):
        self.calls.append({"model": model, "messages": messages, "role": role, "temperature": temperature, "max_tokens": max_tokens, "thinking": thinking})
        return self.response_text, _usage(role)


# ---------------------------------------------------------------------------
# (a) Free-text clustering
# ---------------------------------------------------------------------------


def test_normalize_answer_case_article_punctuation_insensitive():
    assert normalize_answer("The Eiffel Tower") == normalize_answer("eiffel tower!")
    assert normalize_answer("A cat") == normalize_answer("CAT.")
    assert normalize_answer("  Paris,   France  ") == normalize_answer("paris france")


def test_normalize_answer_genuinely_different_answers_do_not_match():
    assert normalize_answer("Paris") != normalize_answer("London")
    assert normalize_answer("Albert Einstein") != normalize_answer("Isaac Newton")


def test_normalize_answer_documents_the_paraphrase_limitation():
    # DELIBERATE limitation stated in the docstring: no semantic clustering.
    # A genuinely correct paraphrase does NOT normalize to the same string.
    assert normalize_answer("JFK") != normalize_answer("John F. Kennedy")


def test_panel_variant_answers_cluster_together_via_n_clusters():
    client = FakePanelClient(_answers_by_lens(["The Eiffel Tower", "eiffel tower!", "EIFFEL TOWER."]))
    item = _item(gold_answer="The Eiffel Tower", question="What is the tallest structure in Paris?")

    result = solve_panel_factual(client, item, rag=None)

    assert result["n_clusters"] == 1
    assert result["cluster_margin"] == 3
    assert result["escalated"] is False
    assert client.judge_calls == 0


def test_panel_genuinely_different_answers_do_not_cluster():
    client = FakePanelClient(_answers_by_lens(["Paris", "London", "Berlin"]), judge_answer="Paris")
    item = _item(gold_answer="Paris")

    result = solve_panel_factual(client, item, rag=None)

    assert result["n_clusters"] == 3
    assert result["cluster_margin"] == 0
    assert result["escalated"] is True  # no margin -> escalation, per (d) below


# ---------------------------------------------------------------------------
# (b)/(c) verify_claim_against_evidence: supported vs unsupported, and the
# no-passages short-circuit (no network call, usage=None).
# ---------------------------------------------------------------------------


def test_verify_claim_against_evidence_supported_returns_true_and_usage():
    client = _VerifyOnlyClient(supported=True, quote="Paris is the capital of France.")
    supported, quote, reason, usage = verify_claim_against_evidence(client, "Paris", _canned_passages(), question="What is the capital of France?")

    assert supported is True
    assert quote == "Paris is the capital of France."
    assert usage is not None
    assert usage.role == "verifier"
    assert len(client.calls) == 1


def test_verify_claim_against_evidence_unsupported_returns_false():
    client = _VerifyOnlyClient(supported=False, reason="passages never mention this")
    supported, quote, reason, usage = verify_claim_against_evidence(client, "Paris", _canned_passages())

    assert supported is False
    assert reason == "passages never mention this"


def test_verify_claim_against_evidence_no_passages_short_circuits_without_a_call():
    client = _VerifyOnlyClient(supported=True)
    supported, quote, reason, usage = verify_claim_against_evidence(client, "Paris", [])

    assert supported is False
    assert usage is None
    assert client.calls == []  # zero-cost: no network call was made


# ---------------------------------------------------------------------------
# (b)/(c) end-to-end through solve_panel_factual: ABSTAIN is a real terminal
# state, distinct from (and never scored as) a wrong answer, and distinct
# from an ordinary answered/correct row.
# ---------------------------------------------------------------------------


def test_panel_unsupported_candidate_triggers_abstain_even_though_it_matched_gold():
    rag = _rag_config()
    client = FakePanelClient(_answers_by_lens(["Paris", "paris", "London"]), verify_supported=False, verify_reason="evidence silent on this")
    item = _item(gold_answer="Paris")  # the clustered candidate WOULD be correct if accepted

    result = solve_panel_factual(client, item, rag=rag)

    assert result["escalated"] is False  # plurality still won the clustering step
    assert client.verify_calls == 1
    assert result["supported"] is False
    assert result["abstained"] is True
    assert result["final_answer"] == ""
    assert result["correct"] is False  # ABSTAIN is never scored correct, even post-hoc


def test_panel_supported_candidate_is_answered_not_abstained():
    rag = _rag_config()
    client = FakePanelClient(_answers_by_lens(["Paris", "paris", "London"]), verify_supported=True, verify_quote="Paris is the capital of France.")
    item = _item(gold_answer="Paris")

    result = solve_panel_factual(client, item, rag=rag)

    assert result["supported"] is True
    assert result["abstained"] is False
    assert result["final_answer"] != ""
    assert result["correct"] is True
    assert result["verify_quote"] == "Paris is the capital of France."


def test_panel_judge_can_abstain_directly_on_a_full_split():
    client = FakePanelClient(_answers_by_lens(["Paris", "London", "Berlin"]), judge_abstain=True, judge_reasoning="none of these look right")
    item = _item(gold_answer="Rome")

    result = solve_panel_factual(client, item, rag=None)

    assert result["escalated"] is True
    assert result["abstained"] is True
    assert result["final_answer"] == ""
    assert result["correct"] is False
    assert client.verify_calls == 0  # abstained pre-verification -- nothing left to check


# ---------------------------------------------------------------------------
# (d) Panel dispatch: clear plurality -> that answer, no judge call;
#     no margin -> escalation to judge_factual, judge's answer becomes final.
# ---------------------------------------------------------------------------


def test_panel_clear_plurality_wins_without_escalation():
    client = FakePanelClient(_answers_by_lens(["Paris", "paris!", "London"]))
    item = _item(gold_answer="Paris")

    result = solve_panel_factual(client, item, rag=None)

    assert result["escalated"] is False
    assert client.judge_calls == 0
    assert result["cluster_margin"] == 1  # 2 vs 1
    assert result["correct"] is True
    assert result["solver_model"] is not None
    assert len(result["solver_answers"]) == 3


def test_panel_no_margin_escalates_and_judge_answer_becomes_final():
    client = FakePanelClient(_answers_by_lens(["Paris", "London", "Berlin"]), judge_answer="Paris", judge_reasoning="Paris is correct")
    item = _item(gold_answer="Paris")

    result = solve_panel_factual(client, item, rag=None)

    assert result["escalated"] is True
    assert client.judge_calls == 1
    assert result["final_answer"] == "Paris"
    assert result["correct"] is True
    assert result["judge_reasoning"] == "Paris is correct"
    assert len(result["calls"]) == 4  # 3 solvers + 1 judge, no verify (no passages)


# ---------------------------------------------------------------------------
# (e) exact_match_normalized
# ---------------------------------------------------------------------------


def test_exact_match_normalized_positive_case_article_punct_insensitive():
    assert exact_match_normalized("The Eiffel Tower", "eiffel tower!") is True
    assert exact_match_normalized("Paris", "  PARIS  ") is True


def test_exact_match_normalized_negative_on_genuine_mismatch():
    assert exact_match_normalized("Paris", "London") is False


def test_exact_match_normalized_documents_paraphrase_undercount():
    # honest limitation: a genuinely correct paraphrase is scored False by
    # the deterministic floor -- this is exactly why it is a FLOOR, not the
    # headline metric (see grade_simpleqa / simpleqa_build_notes.md).
    assert exact_match_normalized("John F. Kennedy", "JFK") is False


def test_exact_match_normalized_none_inputs_are_false():
    assert exact_match_normalized(None, "Paris") is False
    assert exact_match_normalized("Paris", None) is False


def test_exact_match_normalized_empty_after_normalization_never_matches():
    assert exact_match_normalized("", "") is False
    assert exact_match_normalized("the a an", "") is False


# ---------------------------------------------------------------------------
# solve_single_factual: baseline JSON contract, ABSTAIN as terminal state
# ---------------------------------------------------------------------------


def test_solve_single_factual_answers_when_confident():
    client = _SingleFactualClient(answer="Paris", abstain=False, reasoning="well-known capital")
    item = _item(gold_answer="Paris")

    result = solve_single_factual(client, item)

    assert result["abstained"] is False
    assert result["final_answer"] == "Paris"
    assert result["correct"] is True
    assert result["calls"][0]["role"] == "baseline"


def test_solve_single_factual_abstains_directly_and_is_never_scored_correct():
    client = _SingleFactualClient(answer="", abstain=True, reasoning="not confident enough")
    item = _item(gold_answer="Paris")

    result = solve_single_factual(client, item)

    assert result["abstained"] is True
    assert result["final_answer"] == ""
    assert result["correct"] is False


# ---------------------------------------------------------------------------
# (f) grade_simpleqa: the three official labels, plus the NOT_ATTEMPTED
#     fallback, plus the prompt actually carries question/gold/predicted.
# ---------------------------------------------------------------------------


def test_grade_simpleqa_returns_correct():
    label, usage = grade_simpleqa(_GraderClient("A"), "Q?", "gold", "pred")
    assert label == "CORRECT"
    assert usage.role == "grader"


def test_grade_simpleqa_returns_incorrect():
    label, _ = grade_simpleqa(_GraderClient("B"), "Q?", "gold", "pred")
    assert label == "INCORRECT"


def test_grade_simpleqa_returns_not_attempted():
    label, _ = grade_simpleqa(_GraderClient("C"), "Q?", "gold", "pred")
    assert label == "NOT_ATTEMPTED"


def test_grade_simpleqa_unparseable_response_defaults_to_not_attempted():
    label, _ = grade_simpleqa(_GraderClient("I refuse to grade this."), "Q?", "gold", "pred")
    assert label == "NOT_ATTEMPTED"


def test_grade_simpleqa_call_is_plain_text_not_json_and_thinking_disabled():
    client = _GraderClient("A")
    grade_simpleqa(client, "Q?", "gold", "pred")
    assert client.calls[0]["thinking"] is False


def test_grade_simpleqa_prompt_carries_question_gold_and_predicted():
    client = _GraderClient("A")
    grade_simpleqa(client, "What is 2+2?", "Four", "4")

    prompt = client.calls[0]["messages"][0]["content"]
    assert "What is 2+2?" in prompt
    assert "Four" in prompt
    assert prompt.count("4") >= 1
    assert "CORRECT" in prompt and "INCORRECT" in prompt and "NOT_ATTEMPTED" in prompt


# ---------------------------------------------------------------------------
# (g) compute_simpleqa_metrics
# ---------------------------------------------------------------------------


def test_compute_simpleqa_metrics_all_correct():
    m = compute_simpleqa_metrics(["CORRECT"] * 5)
    assert m["correct_rate"] == 1.0
    assert m["accuracy_given_attempted"] == 1.0
    assert m["f1"] == 1.0


def test_compute_simpleqa_metrics_empty_list():
    m = compute_simpleqa_metrics([])
    assert m["n"] == 0
    assert m["f1"] == 0.0


def test_compute_simpleqa_metrics_total_abstention_scores_zero_not_undefined():
    m = compute_simpleqa_metrics(["NOT_ATTEMPTED"] * 5)
    assert m["attempt_rate"] == 0.0
    assert m["accuracy_given_attempted"] == 0.0  # defined as 0, not a ZeroDivisionError
    assert m["f1"] == 0.0  # total silence must not score as a win


def test_compute_simpleqa_metrics_matches_the_roadmaps_ceiling_formula():
    # F1 <= 2k/(1+k) where k = fraction correct out of ALL items; a
    # perfectly-calibrated abstainer (never wrong, only correct or
    # not-attempted) hits the ceiling exactly.
    grades = ["CORRECT"] * 4 + ["NOT_ATTEMPTED"] * 6
    m = compute_simpleqa_metrics(grades)
    k = 0.4
    assert abs(m["f1"] - (2 * k / (1 + k))) < 1e-9


# ---------------------------------------------------------------------------
# (h) Missing/broken RAG index -> no crash, no evidence, logged.
# ---------------------------------------------------------------------------


def test_try_open_factuality_rag_missing_index_returns_none_and_logs(tmp_path, caplog):
    missing = tmp_path / "no_such_index.sqlite3"
    with caplog.at_level(logging.WARNING):
        rag = try_open_factuality_rag(db_path=missing)

    assert rag is None
    assert "proceeding WITHOUT evidence" in caplog.text


def test_solve_panel_factual_with_no_rag_never_crashes_and_logs_no_evidence():
    client = FakePanelClient(_answers_by_lens(["Paris", "paris", "London"]))
    item = _item()

    result = solve_panel_factual(client, item, rag=None)

    assert result["retrieval"] == []
    assert result["supported"] is None
    assert client.verify_calls == 0


def test_solve_panel_factual_retrieval_exception_is_caught_logged_and_degrades(caplog):
    rag = _rag_config(index=RaisingRagIndex())
    client = FakePanelClient(_answers_by_lens(["Paris", "paris", "London"]))
    item = _item()

    with caplog.at_level(logging.WARNING):
        result = solve_panel_factual(client, item, rag=rag)

    assert result["retrieval"] == []
    assert result["supported"] is None
    assert result["correct"] is True  # the panel itself still ran and answered correctly
    assert "proceeding WITHOUT evidence" in caplog.text


# ---------------------------------------------------------------------------
# (i) Retrieval titles/scores logged WITHOUT full passage text.
# ---------------------------------------------------------------------------


def test_retrieval_log_carries_only_title_and_score():
    rag = _rag_config()
    client = FakePanelClient(_answers_by_lens(["Paris", "paris", "London"]), verify_supported=True)
    item = _item()

    result = solve_panel_factual(client, item, rag=rag)

    assert result["retrieval"] == [
        {"title": "Photon", "score": 0.9},
        {"title": "Electron", "score": 0.8},
    ]
    for row in result["retrieval"]:
        assert "text" not in row
    assert len(rag.index.search_calls) == 1  # retrieval fires once per question, not once per seat


# ---------------------------------------------------------------------------
# (j) load_simpleqa._fix_mojibake -- pure function, no network/dataset load.
# ---------------------------------------------------------------------------


def test_fix_mojibake_repairs_the_known_double_encoded_utf8_pattern():
    garbled = "JÃ³hanna SigurÃ°ardÃ³ttir"
    fixed, was_fixed = _fix_mojibake(garbled)

    assert was_fixed is True
    assert fixed == "Jóhanna Sigurðardóttir"


def test_fix_mojibake_leaves_already_clean_text_untouched():
    clean = "Jóhanna Sigurðardóttir"
    fixed, was_fixed = _fix_mojibake(clean)

    assert was_fixed is False
    assert fixed == clean


def test_fix_mojibake_leaves_plain_ascii_untouched():
    plain = "Michio Sugeno"
    fixed, was_fixed = _fix_mojibake(plain)

    assert was_fixed is False
    assert fixed == plain


def test_fix_mojibake_leaves_empty_string_untouched():
    fixed, was_fixed = _fix_mojibake("")
    assert fixed == ""
    assert was_fixed is False
