"""Offline tests for src/quorumqa/engine/router.py -- the M1 router
(docs/mixture-of-orchestrations-plan.md section 3, section 7 "M1"). No live
API calls, no cost: the heuristic path is pure string matching, and the
classifier-call path is exercised against a FakeClassifierClient with canned
JSON, exactly the RecordingClient discipline test_orchestration_profiles.py
already uses for the M0 registry.

Per CLAUDE.md's TDD-over-re-running-benchmarks rule: this suite is the gate
before benchmark/run_moo_eval.py is allowed to spend a single real API call.
"""

import pytest

from quorumqa.engine import profiles
from quorumqa.engine.router import (
    BUDGETS,
    ROUTING_RULES,
    _domain_bucket,
    classify_bucket,
    classify_via_llm,
    route,
)
from quorumqa.schemas import GPQAItem


def _item(subject, question_id="q1"):
    return GPQAItem(
        question_id=question_id,
        question="Some question text?",
        choices=["a", "b", "c", "d"],
        correct_letter="A",
        subject=subject,
    )


# ---------------------------------------------------------------------------
# Rule 1: GPQA Organic Chemistry -> stem-max (chem_thinking_gate, 90.9% mean)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("budget", BUDGETS)
def test_organic_chemistry_routes_to_stem_max_at_every_budget(budget):
    assert route(_item("Organic Chemistry"), budget=budget) == "stem-max"


# ---------------------------------------------------------------------------
# Rule 2: SuperGPQA hard-subset disciplines -> rag_thinking_gate / flagship_panel by budget
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("subject", ["Science", "Engineering"])
def test_supergpqa_hard_stem_uses_rag_thinking_gate_when_not_quality(subject):
    assert route(_item(subject), budget="cheap") == "rag_thinking_gate"
    assert route(_item(subject), budget="balanced") == "rag_thinking_gate"


@pytest.mark.parametrize("subject", ["Science", "Engineering"])
def test_supergpqa_hard_stem_uses_flagship_panel_at_quality_budget(subject):
    assert route(_item(subject), budget="quality") == "flagship_panel"


# ---------------------------------------------------------------------------
# Rule 3: GPQA physics/chem-hard subdomains -> stem-max, never a RAG profile
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subject",
    [
        "Physics (general)",
        "Astrophysics",
        "High-energy particle physics",
        "Condensed Matter Physics",
        "Chemistry (general)",
        "Inorganic Chemistry",
    ],
)
@pytest.mark.parametrize("budget", BUDGETS)
def test_gpqa_physics_chem_subdomains_route_to_stem_max(subject, budget):
    assert route(_item(subject), budget=budget) == "stem-max"


@pytest.mark.parametrize(
    "subject",
    ["Physics (general)", "Astrophysics", "Chemistry (general)", "Organic Chemistry"],
)
def test_gpqa_subjects_never_route_to_a_rag_profile(subject):
    # The GPQA contamination tripwire (rag_r1_findings.md) measured
    # retrieval at -4.7 on GPQA-Diamond -- no budget should ever send a
    # GPQA-flavored subject to a RAG profile.
    for budget in BUDGETS:
        assert route(_item(subject), budget=budget) not in ("rag_presolve", "rag_thinking_gate")


# ---------------------------------------------------------------------------
# Rule 4: MedQA (step1 / step2&3) -> single-call (cheap) / standard-tribunal
# ---------------------------------------------------------------------------


def test_medqa_step1_routes_to_single_call_at_cheap_budget():
    assert route(_item("step1"), budget="cheap") == "single-call"


def test_medqa_step2and3_routes_to_single_call_at_cheap_budget():
    assert route(_item("step2&3"), budget="cheap") == "single-call"


@pytest.mark.parametrize("subject", ["step1", "step2&3"])
@pytest.mark.parametrize("budget", ["balanced", "quality"])
def test_medqa_routes_to_standard_tribunal_above_cheap_budget(subject, budget):
    # Deliberately NOT flagship_panel even at "quality": medqa_findings.md
    # found no diagnosed gap here to buy back with extra spend.
    assert route(_item(subject), budget=budget) == "standard-tribunal"


# ---------------------------------------------------------------------------
# Rule 5: saturated/easy MMLU-Pro categories -> single-call, budget-independent
# ---------------------------------------------------------------------------


_SATURATED_CATEGORIES = [
    "math", "economics", "business", "physics", "biology", "health",
    "psychology", "computer science", "philosophy", "history", "other",
]


@pytest.mark.parametrize("subject", _SATURATED_CATEGORIES)
@pytest.mark.parametrize("budget", BUDGETS)
def test_saturated_mmlu_pro_categories_always_route_to_single_call(subject, budget):
    assert route(_item(subject), budget=budget) == "single-call"


def test_flagged_lossy_mmlu_pro_categories_are_not_treated_as_saturated():
    # engineering/chemistry/law were the ONLY categories that regressed in
    # the mmlu_pro_findings.md pilot -- they must not silently fall into
    # the saturated_easy bucket via the same lowercase category string.
    assert _domain_bucket("engineering") == "unknown"
    assert _domain_bucket("law") == "unknown"
    # "chemistry" (lowercase, MMLU-Pro) is genuinely ambiguous with the
    # GPQA chem/physic substring rule (it contains "chem") -- confirm it
    # resolves there rather than to saturated_easy, i.e. gets treated as
    # hard-STEM, the conservative direction.
    assert _domain_bucket("chemistry") == "gpqa_hard_stem"


# ---------------------------------------------------------------------------
# Case-sensitivity: no accidental cross-benchmark collisions
# ---------------------------------------------------------------------------


def test_gpqa_title_case_fallback_subjects_do_not_hit_saturated_easy():
    # If a GPQA row's Subdomain were ever missing, load_gpqa.py falls back
    # to the Title-Case High-level-domain field ("Physics"/"Biology"/
    # "Chemistry"). Those must NOT collide with MMLU-Pro's lowercase
    # "physics"/"biology" saturated-easy categories.
    assert _domain_bucket("Physics") == "gpqa_hard_stem"
    assert _domain_bucket("Biology") == "unknown"
    assert _domain_bucket("Chemistry") == "gpqa_hard_stem"


def test_supergpqa_title_case_subjects_do_not_collide_with_saturated_categories():
    # SuperGPQA disciplines "Economics"/"Philosophy"/"History" are
    # Title-Case; MMLU-Pro's matching categories are lowercase. Exact
    # case-sensitive matching means these fall to "unknown", not
    # saturated_easy.
    for subject in ("Economics", "Philosophy", "History"):
        assert _domain_bucket(subject) == "unknown"


# ---------------------------------------------------------------------------
# Unknown / unlabeled subjects: asymmetric-loss budget-scaled default
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "budget,expected",
    [("cheap", "standard-tribunal"), ("balanced", "thinking_gate"), ("quality", "flagship_panel")],
)
def test_unknown_subject_uses_budget_scaled_default(budget, expected):
    assert route(_item(None), budget=budget) == expected
    assert route(_item("Some Totally Unrecognized Subject"), budget=budget) == expected


def test_empty_string_subject_treated_as_unknown():
    assert _domain_bucket("") == "unknown"
    assert _domain_bucket("   ") == "unknown"


# ---------------------------------------------------------------------------
# Signature / validation
# ---------------------------------------------------------------------------


def test_default_budget_is_balanced():
    assert route(_item("Organic Chemistry")) == route(_item("Organic Chemistry"), budget="balanced")


def test_invalid_budget_raises_value_error():
    with pytest.raises(ValueError):
        route(_item("Organic Chemistry"), budget="ultra-premium")


def test_use_classifier_without_client_raises():
    with pytest.raises(ValueError):
        route(_item("Organic Chemistry"), use_classifier=True)


# ---------------------------------------------------------------------------
# Every rule's every budget resolves to a REAL registered profile
# ---------------------------------------------------------------------------


def test_every_rule_resolves_to_a_registered_profile():
    for rule in ROUTING_RULES:
        for budget in BUDGETS:
            profile_name = rule.profile_by_budget[budget]
            assert profile_name in profiles.REGISTRY, (
                f"rule {rule.bucket!r} at budget {budget!r} resolves to "
                f"{profile_name!r}, not in REGISTRY"
            )


def test_routing_rules_table_is_fully_documented():
    for rule in ROUTING_RULES:
        assert rule.bucket
        assert rule.match
        assert rule.finding, f"rule {rule.bucket!r} has no citing finding"
        assert set(rule.profile_by_budget) == set(BUDGETS)


# ---------------------------------------------------------------------------
# R1 classifier-call path (offline, FakeClient -- no network)
# ---------------------------------------------------------------------------


class _JsonResult:
    def __init__(self, data):
        self.data = data


class FakeClassifierClient:
    """Mirrors QwenClient.chat_json's signature just enough for
    classify_via_llm; records the call for assertions, returns a canned
    classification dict."""

    def __init__(self, classification: dict):
        self._classification = classification
        self.calls = []

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.calls.append({"model": model, "system": system, "user": user, "role": role, "thinking": thinking})
        return _JsonResult(data=self._classification)


def test_classify_via_llm_calls_mechanical_model_with_thinking_off():
    from quorumqa.config import MECHANICAL_MODEL

    client = FakeClassifierClient({"domain": "medicine", "difficulty": "medium", "checkability": "retrievable", "is_agentic": False})
    result = classify_via_llm(client, _item("step1"))
    assert result["domain"] == "medicine"
    assert len(client.calls) == 1
    assert client.calls[0]["model"] == MECHANICAL_MODEL
    assert client.calls[0]["thinking"] is False
    assert client.calls[0]["role"] == "router_classifier"


@pytest.mark.parametrize(
    "classification,expected_bucket",
    [
        ({"domain": "organic_chemistry", "difficulty": "hard", "checkability": "search_proof", "is_agentic": False}, "gpqa_organic_chem"),
        ({"domain": "medicine", "difficulty": "medium", "checkability": "retrievable", "is_agentic": False}, "medicine"),
        ({"domain": "history", "difficulty": "easy", "checkability": "retrievable", "is_agentic": False}, "saturated_easy"),
        ({"domain": "chemistry", "difficulty": "hard", "checkability": "retrievable", "is_agentic": False}, "supergpqa_hard_stem"),
        ({"domain": "physics", "difficulty": "hard", "checkability": "search_proof", "is_agentic": False}, "gpqa_hard_stem"),
        ({"domain": "underwater_basket_weaving", "difficulty": "hard", "checkability": "retrievable", "is_agentic": False}, "unknown"),
    ],
)
def test_classify_bucket_maps_onto_heuristic_bucket_vocabulary(classification, expected_bucket):
    assert classify_bucket(classification) == expected_bucket


def test_route_with_use_classifier_true_dispatches_through_classify_bucket():
    client = FakeClassifierClient({"domain": "organic_chemistry", "difficulty": "hard", "checkability": "search_proof", "is_agentic": False})
    assert route(_item(None), budget="balanced", use_classifier=True, client=client) == "stem-max"
    assert len(client.calls) == 1


def test_route_with_use_classifier_true_never_invents_a_bucket_outside_registry():
    for classification in (
        {"domain": "law", "difficulty": "hard", "checkability": "retrievable", "is_agentic": False},
        {"domain": "", "difficulty": "", "checkability": "", "is_agentic": False},
    ):
        client = FakeClassifierClient(classification)
        for budget in BUDGETS:
            client2 = FakeClassifierClient(classification)
            profile_name = route(_item(None), budget=budget, use_classifier=True, client=client2)
            assert profile_name in profiles.REGISTRY
