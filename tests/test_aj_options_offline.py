"""Offline tests for the A-J generalization (docs/capability-roadmap.md item
F7 / section 3.6): the engine's solver/skeptic/verifier/judge/gate prompts
used to hardcode exactly 4 choices (A-D) at ~28 call sites across
src/quorumqa/engine/*.py and benchmark/lever_experiments.py, which is why
benchmark/load_mmlu_pro.py trimmed MMLU-Pro's up-to-10-option questions down
to 4 and why a 10-option benchmark (MedXpertQA) could never run through this
engine at all. quorumqa.letters (letters_for/choice_block/letter_hint/
parse_letter) is now the ONE place that renders a choice list, builds the
JSON-shape letter hint, and parses a returned letter, for 2-10 choices.

No live API calls anywhere in this file -- every test uses a fake
QwenClient (chat_json) or a monkeypatched requests.post (for the two
Token-Plan-transport qwen38 functions), same pattern as
tests/test_engine_offline.py and tests/test_lever_qwen38_judge_offline.py.

THE NON-NEGOTIABLE CONSTRAINT this file exists to prove, not merely assert:
every 4-choice prompt this engine sends must be BYTE-IDENTICAL to what it
sent before this refactor -- every committed benchmark result was produced
by the old hardcoded "ABCD" prompts, and a single changed character would
silently invalidate cross-run comparisons.

test_full_call_fingerprints_match_pre_refactor_baseline is the proof: it
re-runs the EXACT SAME capture routine (_capture_fingerprints below) that
produced tests/fixtures/aj_options_baseline_fingerprints.json -- captured
from this repo's pre-refactor HEAD, before quorumqa.letters existed, via
scratch/dump_fingerprints.py (not part of this repo; a one-off generator
run once to freeze the fixture) -- against the CURRENT (post-refactor) code,
and asserts the two are equal key-for-key, byte-for-byte. If a single
character of any 4-choice prompt in solver.py/skeptic.py/judge.py or any of
the twelve lever_experiments.py prompt-building functions changes, this
test fails.
"""

import json as json_module
from pathlib import Path

import pytest

from quorumqa.config import SOLVER_LENSES
from quorumqa.engine.judge import adjudicate
from quorumqa.engine.orchestrator import run_question
from quorumqa.engine.skeptic import rebut
from quorumqa.engine.solver import _solve_one
from quorumqa.letters import choice_block, letter_hint, letters_for, parse_letter
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem, SkepticRebuttal, SolverAnswer, VerifierFinding

import benchmark.lever_experiments as LE

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "aj_options_baseline_fingerprints.json"


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


# ---------------------------------------------------------------------------
# Section 1 -- the full-call-fingerprint equivalence proof
# ---------------------------------------------------------------------------


def _fake_data_for_role(role):
    if role in ("solver", "solver_thinking"):
        return {"letter": "B", "confidence": 0.6, "reasoning": "because reasons"}
    if role in ("judge", "post_debate_judge"):
        return {
            "final_letter": "B", "decisive_reasoning": "decisive", "dissent": None,
            "overturned_plurality": False, "confidence": "medium",
        }
    if role == "gate":
        return {"doubt": False, "reason": "looks fine"}
    if role == "verified_gate_flaw":
        return {"flaw_found": False, "flaw": "", "confidence": 0.5}
    if role == "verified_gate_cas":
        return {"checkable": False, "relation": "", "candidate": ""}
    if role == "minority_rebuttal":
        return {"concede": True, "reason": "convinced", "counter_argument": ""}
    return {}


class RecordingClient:
    """Records every chat_json call's full (model, system, user, role,
    temperature, max_tokens, retries, thinking, seed, thinking_budget)
    tuple -- the complete call fingerprint."""

    def __init__(self):
        self.calls = []

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1,
                   thinking=True, seed=None, thinking_budget=None):
        rec = {
            "model": model, "system": system, "user": user, "role": role,
            "temperature": temperature, "max_tokens": max_tokens, "retries": retries,
            "thinking": thinking, "seed": seed, "thinking_budget": thinking_budget,
        }
        self.calls.append(rec)
        data = _fake_data_for_role(role)
        return JsonCallResult(data=data, usage=CallUsage(model=model, input_tokens=1, output_tokens=1, cost_usd=0.0, role=role))


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


_QUESTION = "What is the boiling point of water at sea level, in degrees Celsius?"
_CHOICES = ["50", "100", "150", "200"]
_LENS = "Answer by reasoning from first principles, step by step."
_PLURALITY = "B"


def _sa(letter, lens_, conf=0.6):
    return SolverAnswer(letter=letter, confidence=conf, reasoning="because reasons", lens=lens_)


_SOLVER_ANSWERS = [_sa("A", "lensA"), _sa("B", "lensB"), _sa("B", "lensC")]
_SKEPTIC_REBUTTAL = SkepticRebuttal(target_letter="B", disputed_step="step X", argument="argument Y")
_VERIFIER_FINDINGS = [
    VerifierFinding(claim="2+2=4", tool_used="safe_calculate", tool_query="{'expression': '2+2'}", tool_result="4", supports_claim=True)
]


def _capture_fingerprints():
    """Calls every 4-choice prompt-building function this refactor touched,
    with FIXED deterministic inputs, and records the exact (system, user,
    ...) fingerprint each one sends. Identical routine to the one-off
    scratch/dump_fingerprints.py script that produced FIXTURE_PATH from
    pre-refactor HEAD -- see this module's docstring."""
    out = {}

    c = RecordingClient()
    _solve_one(c, _QUESTION, _CHOICES, _LENS, model="qwen3.6-flash", temperature=0.3)
    out["solve_one"] = c.calls[0]

    c = RecordingClient()
    rebut(c, _QUESTION, _CHOICES, _PLURALITY, _SOLVER_ANSWERS)
    out["skeptic_rebut"] = c.calls[0]

    c = RecordingClient()
    adjudicate(c, _QUESTION, _CHOICES, _SOLVER_ANSWERS, _SKEPTIC_REBUTTAL, _VERIFIER_FINDINGS)
    out["judge_adjudicate"] = c.calls[0]

    c = RecordingClient()
    LE._solve_one_thinking(c, _QUESTION, _CHOICES, _LENS, model="qwen3.6-flash", temperature=0.9)
    out["solve_one_thinking"] = c.calls[0]

    c = RecordingClient()
    LE.second_opinion_gate(c, _QUESTION, _CHOICES, _SOLVER_ANSWERS, _PLURALITY)
    out["second_opinion_gate"] = c.calls[0]

    c = RecordingClient()
    LE.flaw_finder_gate_check(c, _QUESTION, _CHOICES, _SOLVER_ANSWERS, _PLURALITY)
    out["flaw_finder_gate_check"] = c.calls[0]

    c = RecordingClient()
    LE.cas_gate_check(c, _QUESTION, _CHOICES, _SOLVER_ANSWERS, _PLURALITY)
    out["cas_gate_check"] = c.calls[0]

    c = RecordingClient()
    answer, usage, perm_record = LE._solve_one_permuted(
        c, _QUESTION, _CHOICES, _LENS, seed=42, question_id="q1", seat_index=0,
        model="qwen3.6-flash", temperature=0.4, thinking=False,
    )
    rec = dict(c.calls[0])
    rec["_permutation_record"] = perm_record
    rec["_canonical_letter"] = answer.letter
    out["solve_one_permuted"] = rec

    c = RecordingClient()
    LE._solve_one_method(c, _QUESTION, _CHOICES, LE.METHOD_FORWARD, LE.METHOD_NAMES[0], model="qwen3.6-flash", temperature=0.3)
    out["solve_one_method"] = c.calls[0]

    c = RecordingClient()
    LE._solve_one_rag(c, _QUESTION, _CHOICES, _LENS, "", model="qwen3.6-flash", temperature=0.3, thinking=False)
    out["solve_one_rag_no_evidence"] = c.calls[0]

    c = RecordingClient()
    LE._solve_one_rag(
        c, _QUESTION, _CHOICES, _LENS,
        "Relevant reference passages (may or may not be useful):\n[Water] Water boils at 100C at sea level...",
        model="qwen3.6-flash", temperature=0.9, thinking=True,
    )
    out["solve_one_rag_with_evidence"] = c.calls[0]

    c = RecordingClient()
    minority = _sa("A", "lensA")
    LE.minority_rebuttal_check(c, _QUESTION, _CHOICES, minority, _PLURALITY, "[lensB] reasoning\n\n[lensC] reasoning", _VERIFIER_FINDINGS)
    out["minority_rebuttal_check"] = c.calls[0]

    c = RecordingClient()
    debate_exchanges = [{"letter": "A", "concede": True, "reason": "convinced", "counter_argument": ""}]
    LE.adjudicate_post_debate(c, _QUESTION, _CHOICES, _SOLVER_ANSWERS, _SKEPTIC_REBUTTAL, _VERIFIER_FINDINGS, debate_exchanges)
    out["adjudicate_post_debate"] = c.calls[0]

    c = RecordingClient()
    LE.adjudicate_with_r3_evidence(c, _QUESTION, _CHOICES, _SOLVER_ANSWERS, _SKEPTIC_REBUTTAL, _VERIFIER_FINDINGS, "Evidence text here")
    out["adjudicate_with_r3_evidence"] = c.calls[0]

    posted = []

    def fake_post(url, headers=None, json=None, timeout=None):
        posted.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        idx = len(posted) - 1
        if idx == 0:  # adjudicate_qwen38
            payload = {
                "final_letter": "B", "decisive_reasoning": "decisive", "dissent": None,
                "overturned_plurality": False, "confidence": "medium",
            }
        else:  # _solve_one_qwen38
            payload = {"letter": "B", "confidence": 0.6, "reasoning": "because"}
        return FakeResponse({
            "content": [{"type": "text", "text": json_module.dumps(payload)}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    orig_post = LE.requests.post
    LE.requests.post = fake_post
    try:
        c = RecordingClient()
        LE.adjudicate_qwen38(c, _QUESTION, _CHOICES, _SOLVER_ANSWERS, _SKEPTIC_REBUTTAL, _VERIFIER_FINDINGS)
        out["adjudicate_qwen38"] = {
            "system": posted[0]["json"]["system"],
            "user": posted[0]["json"]["messages"][0]["content"],
            "model": posted[0]["json"]["model"],
        }

        LE._solve_one_qwen38(c, _QUESTION, _CHOICES, _LENS, temperature=0.6)
        out["solve_one_qwen38"] = {
            "system": posted[1]["json"]["system"],
            "user": posted[1]["json"]["messages"][0]["content"],
            "model": posted[1]["json"]["model"],
        }
    finally:
        LE.requests.post = orig_post

    return out


def test_full_call_fingerprints_match_pre_refactor_baseline():
    expected = json_module.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    actual = _capture_fingerprints()
    assert set(actual.keys()) == set(expected.keys())
    for key in expected:
        assert actual[key] == expected[key], f"fingerprint drift in {key!r}: prompt/call shape changed from the pre-refactor baseline"


def test_fixture_actually_covers_every_prompt_building_site():
    # Guards against the fixture silently going stale if a new call site is
    # added later without updating both _capture_fingerprints and the fixture.
    expected = json_module.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert len(expected) == 16
    # Every fixture entry that has a JSON-shape "letter" hint must show the
    # untouched 4-choice literal -- this is the one string a silent
    # regression would most likely corrupt.
    for key, rec in expected.items():
        text = rec.get("user", "")
        if '"letter"' in text or '"final_letter"' in text:
            assert "A|B|C|D" in text, f"{key} lost its 4-choice JSON hint"
            assert "A|B|C|D|E" not in text, f"{key} leaked a >4-choice hint into a 4-choice fixture"


# ---------------------------------------------------------------------------
# Section 2 -- quorumqa.letters unit tests
# ---------------------------------------------------------------------------


def test_letters_for_returns_prefix_of_a_to_j():
    assert letters_for(2) == "AB"
    assert letters_for(4) == "ABCD"
    assert letters_for(6) == "ABCDEF"
    assert letters_for(10) == "ABCDEFGHIJ"


@pytest.mark.parametrize("n", [-3, -1, 0, 1, 11, 12, 100])
def test_letters_for_raises_outside_2_to_10(n):
    with pytest.raises(ValueError):
        letters_for(n)


def test_choice_block_byte_identical_to_old_hardcoded_pattern_at_n4():
    choices = ["fifty", "one hundred", "one fifty", "two hundred"]
    # The exact expression every prompt builder used to inline, kept here
    # literally so this test does not depend on choice_block's own
    # implementation to describe what "correct" means.
    expected = "\n".join(f"{letter}) {c}" for letter, c in zip("ABCD", choices))
    assert choice_block(choices) == expected == "A) fifty\nB) one hundred\nC) one fifty\nD) two hundred"


def test_choice_block_at_n10():
    choices = [f"opt{i}" for i in range(10)]
    result = choice_block(choices)
    lines = result.split("\n")
    assert len(lines) == 10
    assert lines[0] == "A) opt0"
    assert lines[9] == "J) opt9"


def test_letter_hint_exact_strings():
    assert letter_hint(4) == "A|B|C|D"
    assert letter_hint(10) == "A|B|C|D|E|F|G|H|I|J"
    assert letter_hint(2) == "A|B"


@pytest.mark.parametrize(
    "raw,n,fallback,expected",
    [
        ("B", 4, "A", "B"),
        ("b", 4, "A", "B"),  # lowercase accepted, same as the old .upper() sites
        (" C ", 4, "A", "C"),  # whitespace stripped, same as the old .strip() sites
        ("D_extra_text", 4, "A", "D"),  # only the first char after strip/upper, same as [:1]
        ("Z", 4, "A", "A"),  # invalid (non-empty) at n=4 -> default fallback "A"
        ("Z", 4, "D", "D"),  # invalid -> custom fallback (the judge-style call sites)
        ("J", 10, "A", "J"),  # valid at n=10 but would have been invalid at n=4
        ("K", 10, "A", "A"),  # 11th letter is never valid, even at the n=10 ceiling
    ],
)
def test_parse_letter_matches_old_fallback_semantics(raw, n, fallback, expected):
    assert parse_letter(raw, n, fallback=fallback) == expected


def test_parse_letter_preserves_the_old_empty_string_quirk():
    # A DELIBERATELY PRESERVED QUIRK, not a new bug: Python's `in` operator
    # on strings is a substring check, and "" is a substring of every
    # string ("" in "ABCD" is True) -- so the ORIGINAL hardcoded call sites'
    # `letter if letter in "ABCD" else "A"` never actually fell back to "A"
    # for a missing/empty letter field; it silently returned "" instead. The
    # task's instruction ("preserve fallback behavior, do not improve it
    # silently") applies to this too -- parse_letter must reproduce it
    # exactly, fallback= is only reached for a non-empty invalid letter.
    assert parse_letter("", 4, fallback="A") == ""
    assert parse_letter("", 4, fallback="Q") == ""


def test_parse_letter_default_fallback_is_a():
    # Every original hardcoded solver-style call site defaulted to "A" on an
    # unparseable letter -- parse_letter's default must match without the
    # caller having to pass fallback= explicitly.
    assert parse_letter("nonsense", 4) == "A"


# ---------------------------------------------------------------------------
# Section 3 -- n=10 end-to-end: the shipped engine must work past "D"
# ---------------------------------------------------------------------------


def _item10(correct_letter: str, question_id: str = "q10") -> GPQAItem:
    choices = [f"choice_{letter}" for letter in letters_for(10)]
    return GPQAItem(question_id=question_id, question="Ten-way question?", choices=choices, correct_letter=correct_letter)


class Fake10ChoiceClient:
    """Same shape as tests/test_engine_offline.py's FakeQwenClient, extended
    to answer with any letter A-J (not just A-D)."""

    def __init__(self, solver_letters, skeptic_target, verifier_claims, judge_verdict):
        self._solver_letters = solver_letters
        self._skeptic_target = skeptic_target
        self._verifier_claims = verifier_claims
        self._judge_verdict = judge_verdict
        self._verifier_call_count = 0
        self.solver_prompts = []

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        if role == "solver":
            lens = next(l for l in SOLVER_LENSES if l in system)
            self.solver_prompts.append(user)
            return JsonCallResult(
                data={"letter": self._solver_letters[lens], "confidence": 0.7, "reasoning": "because"},
                usage=_usage("solver"),
            )
        if role == "skeptic":
            return JsonCallResult(
                data={"target_letter": self._skeptic_target, "disputed_step": "step X", "argument": "argument Y"},
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
            return JsonCallResult(data=self._judge_verdict, usage=_usage("judge"))
        raise AssertionError(f"unexpected role {role!r}")


@pytest.mark.asyncio
async def test_ten_choice_unanimous_accepts_letter_past_d():
    letters = {lens: "J" for lens in SOLVER_LENSES}
    client = Fake10ChoiceClient(letters, skeptic_target="J", verifier_claims=[], judge_verdict={})

    result = await run_question(client, _FakeToolSession(), _item10(correct_letter="J"))

    assert result.escalated is False
    assert result.final_letter == "J"
    assert result.correct is True
    assert len(result.calls) == 3  # solvers only, no escalation

    # Every solver prompt must show all 10 choices and the full A-J JSON hint.
    for prompt in client.solver_prompts:
        assert "J) choice_J" in prompt
        assert 'JSON shape: {"letter": "A|B|C|D|E|F|G|H|I|J"' in prompt


@pytest.mark.asyncio
async def test_ten_choice_split_escalates_and_judge_can_pick_a_letter_past_d():
    lenses = SOLVER_LENSES
    letters = {lenses[0]: "B", lenses[1]: "B", lenses[2]: "H"}
    client = Fake10ChoiceClient(
        letters,
        skeptic_target="B",
        verifier_claims=[],
        judge_verdict={
            "final_letter": "H",
            "decisive_reasoning": "the minority solver's derivation held up",
            "dissent": None,
            "overturned_plurality": True,
            "confidence": "high",
        },
    )

    result = await run_question(client, _FakeToolSession(), _item10(correct_letter="H"))

    assert result.escalated is True
    assert result.plurality_letter == "B"
    assert result.final_letter == "H"
    assert result.correct is True  # judge overturned a wrong plurality to a letter past D
    assert result.false_escalation is False


class _FakeToolSession:
    async def call(self, tool_name, arguments):
        return {"ok": True, "value": 1.0}


def test_solve_one_permuted_canonical_remap_works_past_d():
    # Direct unit check of the permutation/canonical-letter-remap logic
    # (benchmark.lever_experiments._solve_one_permuted) at n=10 -- the
    # trickiest of the twelve lever_experiments.py call sites, since it does
    # its OWN letter<->index arithmetic instead of just building a prompt.
    choices = [f"choice_{letter}" for letter in letters_for(10)]

    class FixedLetterClient:
        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1,
                       thinking=True, seed=None, thinking_budget=None):
            return JsonCallResult(
                data={"letter": "F", "confidence": 0.6, "reasoning": "..."},
                usage=_usage(role),
            )

    answer, usage, perm_record = LE._solve_one_permuted(
        FixedLetterClient(), "Q?", choices, "lens", seed=7, question_id="qp10", seat_index=2,
        model="qwen3.6-flash", temperature=0.4, thinking=False,
    )
    letters = letters_for(10)
    shuffled_index = letters.index("F")
    expected_canonical_index = perm_record["shuffled_order"][shuffled_index]
    expected_canonical_letter = letters[expected_canonical_index]
    assert answer.letter == expected_canonical_letter == perm_record["canonical_letter"]
    assert perm_record["shuffled_letter"] == "F"


# ---------------------------------------------------------------------------
# Section 4 -- benchmark/load_mmlu_pro.py's max_choices generalization
# ---------------------------------------------------------------------------


def _fake_row(qid, question, category, options, answer_index):
    return {"question_id": qid, "question": question, "category": category, "options": options, "answer_index": answer_index}


def test_load_mmlu_pro_set_default_still_trims_to_4(monkeypatch):
    import benchmark.load_mmlu_pro as lm

    fake_rows = [_fake_row("q0", "Q0?", "physics", [f"o{i}" for i in range(8)], 3)]
    monkeypatch.setattr(lm, "load_dataset", lambda *a, **k: fake_rows)

    items = lm.load_mmlu_pro_set(n=90, seed=1)
    assert len(items) == 1
    assert len(items[0].choices) == 4
    assert items[0].choices[letters_for(4).index(items[0].correct_letter)] == "o3"


def test_load_mmlu_pro_set_max_choices_none_keeps_all_options(monkeypatch):
    import benchmark.load_mmlu_pro as lm

    fake_rows = [_fake_row("q0", "Q0?", "physics", [f"o{i}" for i in range(8)], 5)]
    monkeypatch.setattr(lm, "load_dataset", lambda *a, **k: fake_rows)

    items = lm.load_mmlu_pro_set(n=90, seed=1, max_choices=None)
    assert len(items) == 1
    assert len(items[0].choices) == 8
    assert items[0].choices[letters_for(8).index(items[0].correct_letter)] == "o5"


def test_load_mmlu_pro_set_max_choices_none_skips_rows_over_10_options(monkeypatch):
    import benchmark.load_mmlu_pro as lm

    fake_rows = [
        _fake_row("q_toomany", "Q?", "physics", [f"o{i}" for i in range(11)], 0),
        _fake_row("q_ok", "Q2?", "physics", [f"p{i}" for i in range(4)], 1),
    ]
    monkeypatch.setattr(lm, "load_dataset", lambda *a, **k: fake_rows)

    items = lm.load_mmlu_pro_set(n=90, seed=1, max_choices=None)
    assert len(items) == 1
    assert items[0].question_id == "q_ok"


def test_load_mmlu_pro_set_max_choices_custom_int_trims_to_that_count(monkeypatch):
    import benchmark.load_mmlu_pro as lm

    fake_rows = [_fake_row("q0", "Q0?", "physics", [f"o{i}" for i in range(8)], 2)]
    monkeypatch.setattr(lm, "load_dataset", lambda *a, **k: fake_rows)

    items = lm.load_mmlu_pro_set(n=90, seed=1, max_choices=6)
    assert len(items) == 1
    assert len(items[0].choices) == 6
    assert items[0].choices[letters_for(6).index(items[0].correct_letter)] == "o2"


def test_load_mmlu_pro_set_max_choices_out_of_range_raises(monkeypatch):
    import benchmark.load_mmlu_pro as lm

    fake_rows = [_fake_row("q0", "Q0?", "physics", [f"o{i}" for i in range(8)], 0)]
    monkeypatch.setattr(lm, "load_dataset", lambda *a, **k: fake_rows)

    with pytest.raises(ValueError):
        lm.load_mmlu_pro_set(n=90, seed=1, max_choices=1)
    with pytest.raises(ValueError):
        lm.load_mmlu_pro_set(n=90, seed=1, max_choices=11)


def test_load_mmlu_pro_full_set_delegates_with_max_choices_none(monkeypatch):
    import benchmark.load_mmlu_pro as lm

    fake_rows = [_fake_row("q0", "Q0?", "chemistry", [f"o{i}" for i in range(10)], 9)]
    monkeypatch.setattr(lm, "load_dataset", lambda *a, **k: fake_rows)

    items = lm.load_mmlu_pro_full_set(n=90, seed=1)
    assert len(items) == 1
    assert len(items[0].choices) == 10
    assert items[0].choices[letters_for(10).index(items[0].correct_letter)] == "o9"


def test_dataset_loaders_has_mmlu_pro_full_entry(monkeypatch):
    import benchmark.load_mmlu_pro as lm

    fake_rows = [_fake_row("q0", "Q0?", "physics", [f"o{i}" for i in range(10)], 0)]
    monkeypatch.setattr(lm, "load_dataset", lambda *a, **k: fake_rows)

    assert "mmlu_pro_full" in LE.DATASET_LOADERS
    items = LE.DATASET_LOADERS["mmlu_pro_full"](90, 1, False)
    assert len(items) == 1
    assert len(items[0].choices) == 10


def test_mmlu_pro_full_present_in_argparse_choices():
    # The --dataset argparse choices are built as list(DATASET_LOADERS.keys())
    # -- confirm that wiring is live (not a hardcoded list someone could
    # forget to extend) and that "mmlu_pro_full" actually flows through it.
    import inspect

    source = inspect.getsource(LE)
    assert "choices=list(DATASET_LOADERS.keys())" in source
    assert "mmlu_pro_full" in LE.DATASET_LOADERS
