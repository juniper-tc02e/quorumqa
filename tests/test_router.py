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

from quorumqa.engine import calibration as calibration_module
from quorumqa.engine import profiles
from quorumqa.engine import router as router_module
from quorumqa.engine.calibration import CalibrationEntry
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
# Rule 2: SuperGPQA hard-subset disciplines -> single-call (cheap) /
# flagship_panel (balanced+quality) -- CORRECTED per moo_m1_corrected_
# findings.md. moo_m1_findings.md's honest-negative diagnosis: the OLD rule
# (rag_thinking_gate at cheap/balanced) sent this bucket to the escalation-
# heavy stack that is BOTH less accurate and pricier than flagship_panel
# here (measured: flagship_panel 84.6%@9553tok vs rag_thinking_gate's
# 73.3%@17719tok, calibration table, n=26-30) -- "the escalation-heavy
# 'cheap' stacks are the EXPENSIVE ones on hard STEM; flagship_panel is
# both more accurate AND cheaper there."
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("subject", ["Science", "Engineering"])
def test_supergpqa_hard_stem_uses_single_call_at_cheap_budget(subject):
    assert route(_item(subject), budget="cheap") == "single-call"


@pytest.mark.parametrize("subject", ["Science", "Engineering"])
@pytest.mark.parametrize("budget", ["balanced", "quality"])
def test_supergpqa_hard_stem_uses_flagship_panel_above_cheap_budget(subject, budget):
    assert route(_item(subject), budget=budget) == "flagship_panel"


def test_supergpqa_hard_stem_no_longer_routes_to_rag_thinking_gate():
    # The bug moo_m1_findings.md diagnosed: rag_thinking_gate was BOTH less
    # accurate and pricier than flagship_panel on this bucket -- confirm
    # the corrected router never picks it here at any budget.
    for budget in BUDGETS:
        assert route(_item("Science"), budget=budget) != "rag_thinking_gate"
        assert route(_item("Engineering"), budget=budget) != "rag_thinking_gate"


# ---------------------------------------------------------------------------
# Rule 3: GPQA physics/chem-hard subdomains (excluding Organic Chemistry,
# its own separate rule) -> single-call (cheap) / flagship_panel (balanced+
# quality), never a RAG profile -- CORRECTED per moo_m1_corrected_
# findings.md. OLD rule routed here to stem-max, which on this bucket is
# byte-identical to thinking_gate's panel (profiles.py: stem-max only
# overrides Organic Chemistry) -- moo_m1_findings.md's per-bucket table
# measured that choice WORSE and costlier than flagship_panel on the
# coarser gpqa_hard workload bucket (85%@14426 vs 93%@12248). The router-
# bucket-level calibration sample here is thin (n=4-5/profile) -- too small
# to trust standalone -- so this fix leans on the coarser, more robust
# gpqa_hard-bucket evidence plus consistency with the supergpqa_hard_stem
# fix, not an independently robust fine-grained result (see the corrected
# findings doc's honesty note).
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
def test_gpqa_hard_stem_uses_single_call_at_cheap_budget(subject):
    assert route(_item(subject), budget="cheap") == "single-call"


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
@pytest.mark.parametrize("budget", ["balanced", "quality"])
def test_gpqa_hard_stem_uses_flagship_panel_above_cheap_budget(subject, budget):
    assert route(_item(subject), budget=budget) == "flagship_panel"


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


# ---------------------------------------------------------------------------
# The cost-aware tie-break (moo_m1_corrected_findings.md item 2c): the two
# corrected hard-STEM rules above resolve through
# quorumqa.engine.calibration.cheapest_within_margin over
# _default_calibration_table(), NOT a bare hardcoded string -- these tests
# prove that wiring by swapping in a synthetic table (monkeypatch, offline,
# no filesystem dependency) and checking the routing decision follows it.
# ---------------------------------------------------------------------------


def _fake_table(*entries: CalibrationEntry) -> dict:
    return {(e.profile, e.bucket): e for e in entries}


def test_supergpqa_hard_stem_follows_the_calibration_table_not_a_hardcoded_pick(monkeypatch):
    # Flip which profile the calibration table says is the accuracy/cost
    # winner for supergpqa_hard_stem -- the router's balanced-budget pick
    # must follow it, proving _profile_for_bucket dispatches through
    # cheapest_within_margin rather than a bare "return 'flagship_panel'".
    fake_table = _fake_table(
        CalibrationEntry("flagship_panel", "supergpqa_hard_stem", 30, 0.70, 9000, 0.1),
        CalibrationEntry("rag_thinking_gate", "supergpqa_hard_stem", 30, 0.95, 4000, 0.1),
    )
    monkeypatch.setattr(router_module, "_default_calibration_table", lambda: fake_table)
    assert route(_item("Science"), budget="balanced") == "rag_thinking_gate"


def test_gpqa_hard_stem_follows_the_calibration_table_not_a_hardcoded_pick(monkeypatch):
    fake_table = _fake_table(
        CalibrationEntry("flagship_panel", "gpqa_hard_stem", 30, 0.70, 9000, 0.1),
        CalibrationEntry("single-call", "gpqa_hard_stem", 30, 0.92, 2000, 0.0),
    )
    monkeypatch.setattr(router_module, "_default_calibration_table", lambda: fake_table)
    assert route(_item("Physics (general)"), budget="balanced") == "single-call"


def test_hard_stem_buckets_fall_back_to_flagship_panel_when_calibration_unavailable(monkeypatch):
    # No calibration data at all (fresh clone before the table is built, or
    # the CSV is missing) -- must still resolve to a real, registered
    # profile via the hardcoded fallback, not crash or return None.
    monkeypatch.setattr(router_module, "_default_calibration_table", lambda: {})
    assert route(_item("Science"), budget="balanced") == "flagship_panel"
    assert route(_item("Physics (general)"), budget="balanced") == "flagship_panel"


def test_hard_stem_buckets_fall_back_to_flagship_panel_when_calibration_sample_too_thin(monkeypatch):
    # Data present but n below cheapest_within_margin's min_n guard (e.g.
    # gpqa_hard_stem's real n=4-5/profile) -- must fall back, not act on noise.
    fake_table = _fake_table(
        CalibrationEntry("single-call", "gpqa_hard_stem", 3, 1.0, 100, 0.0),
    )
    monkeypatch.setattr(router_module, "_default_calibration_table", lambda: fake_table)
    assert route(_item("Physics (general)"), budget="balanced") == "flagship_panel"


def test_default_calibration_table_loads_the_real_committed_csv():
    # No live calls, no network: benchmark/results/moo_calibration_table.csv
    # is checked into the repo (built offline by benchmark/build_moo_
    # calibration.py from the already-recorded moo_m1_eval.jsonl). Confirms
    # the router's default loader actually reads it rather than silently
    # falling back to {} in the real, non-monkeypatched environment.
    router_module._default_calibration_table.cache_clear()
    table = router_module._default_calibration_table()
    assert ("flagship_panel", "supergpqa_hard_stem") in table
    assert table[("flagship_panel", "supergpqa_hard_stem")].n >= 20


def test_supergpqa_hard_stem_resolves_to_flagship_panel_via_the_real_committed_calibration_table():
    # End-to-end with the real checked-in CSV (not a monkeypatched fake):
    # confirms the corrected rule actually lands where moo_m1_corrected_
    # findings.md claims, driven by the measured data, not a coincidence of
    # the hardcoded fallback (supergpqa_hard_stem's real n=26-30 clears the
    # min_n guard, so this exercises the live tie-break path).
    router_module._default_calibration_table.cache_clear()
    assert route(_item("Science"), budget="balanced") == "flagship_panel"
    assert route(_item("Engineering"), budget="balanced") == "flagship_panel"
