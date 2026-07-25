"""Offline tests for the panel-scaling levers (benchmark/lever_experiments.py,
docs/experiment-spec-book.md section 2, S1-S4) -- no live API calls, no
cost. Covers:

  (a) config.SOLVER_PROCEDURES: exactly 5 entries, additive-only (SOLVER_
      LENSES/SOLVER_TEMPERATURES/N_SOLVERS unchanged from their shipped
      defaults).
  (b) Coprime uniqueness: at N=15, diversified_panel's seats occupy 15
      DISTINCT (procedure, temperature) cells; cycled_panel's do NOT (seat
      i == seat i-3), reproducing the original N=5 confound at any N.
  (c) cycled_panel's 3-seat prefix (--solver-tier cheap, the default) is
      byte-identical in config (model/lens/temperature/thinking) to the
      shipped 3-seat panel (engine.solver.solve_all).
  (d) Vote-only mode (--no-tribunal): runs exactly N solver calls and ZERO
      skeptic/verifier/judge calls, whether the vote is unanimous or split.
      Without --no-tribunal, a split still escalates to the shipped
      tribunal exactly like every other lever.
  (e) seat_answers is logged in seat order with every field
      (seat_index/letter/confidence/procedure_or_lens/temperature/
      permutation); permutation letters map back to canonical (proven with
      a fake client that answers by CONTENT, independent of shuffle
      position).
  (f) --solver-tier selects the right model + thinking for both levers.
  (g) _build_output_row folds seat_answers/unanimous/n_solvers/solver_tier/
      no_tribunal into the row for both levers.
  (h) Both levers, and --n-solvers/--no-tribunal/--solver-tier, are
      registered in the CLI.
  (i) benchmark/analyze_panel_scaling.py: nested-prefix subsampling
      recovers known per-N accuracies from a synthetic harvest JSONL,
      McNemar (b, c) counts and the exact one-sided p-value are correct,
      and --bootstrap produces a CI.
"""

import asyncio
import inspect
import json
import threading

import pytest

import benchmark.analyze_panel_scaling as aps
import benchmark.lever_experiments as lever_experiments
from quorumqa.config import MECHANICAL_MODEL, N_SOLVERS, ORCHESTRATOR_MODEL, SOLVER_LENSES, SOLVER_PROCEDURES, SOLVER_TEMPERATURES
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem, QuestionResult, SolverAnswer


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


# ---------------------------------------------------------------------------
# (a) config.SOLVER_PROCEDURES -- additive, exactly 5 entries
# ---------------------------------------------------------------------------


def test_solver_procedures_has_exactly_five_entries():
    assert len(SOLVER_PROCEDURES) == 5
    assert all(isinstance(p, str) and p.strip() for p in SOLVER_PROCEDURES)
    assert len(set(SOLVER_PROCEDURES)) == 5  # genuinely distinct, no accidental dupes


def test_solver_lenses_temperatures_n_solvers_unchanged():
    # Additive-only guarantee: SOLVER_PROCEDURES must not have disturbed the
    # existing shipped defaults every other lever depends on.
    assert SOLVER_LENSES == [
        "Answer by reasoning from first principles, step by step.",
        "Answer by first eliminating choices you're confident are wrong, then picking among what remains.",
        "Answer by recalling the single most relevant fact, law, or formula, then checking each choice against it.",
    ]
    assert SOLVER_TEMPERATURES == [0.3, 0.6, 0.9]
    assert N_SOLVERS == 3


def test_procedure_names_length_matches_solver_procedures():
    assert len(lever_experiments.PROCEDURE_NAMES) == len(SOLVER_PROCEDURES) == 5
    assert len(set(lever_experiments.PROCEDURE_NAMES)) == 5


# ---------------------------------------------------------------------------
# (b) coprime uniqueness at N=15
# ---------------------------------------------------------------------------


def test_five_and_three_are_coprime_by_construction():
    assert len(SOLVER_PROCEDURES) == 5
    assert len(SOLVER_TEMPERATURES) == 3
    cells = [(i % len(SOLVER_PROCEDURES), i % len(SOLVER_TEMPERATURES)) for i in range(15)]
    assert len(set(cells)) == 15  # gcd(5, 3) == 1 -> every seat is a unique cell


class FixedLetterClient:
    """Always answers the same letter regardless of prompt content -- used
    when the test only cares about the CONFIG each seat was called with
    (model/system/temperature/thinking), not the vote outcome."""

    def __init__(self, letter="A"):
        self._letter = letter
        self.calls = []
        self._lock = threading.Lock()

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        with self._lock:
            self.calls.append({
                "model": model, "system": system, "user": user, "role": role,
                "temperature": temperature, "thinking": thinking,
            })
        if role not in ("solver", "solver_thinking"):
            raise AssertionError(f"unexpected role {role!r} -- vote-only mode must never call the tribunal")
        return JsonCallResult(
            data={"letter": self._letter, "confidence": 0.6, "reasoning": "r"}, usage=_usage(role),
        )


def test_diversified_panel_seat_answers_occupy_unique_procedure_temperature_cells_at_n15():
    client = FixedLetterClient("A")
    solver_pairs, seat_answers = asyncio.run(
        lever_experiments.solve_all_diversified_panel(
            client, "Q?", ["1", "2", "3", "4"], seed=42, question_id="dp1", n=15, tier="cheap",
        )
    )
    assert len(seat_answers) == 15
    cells = [(s["procedure_or_lens"], s["temperature"]) for s in seat_answers]
    assert len(set(cells)) == 15  # no two seats share a (procedure, temperature) cell


def test_cycled_panel_seat_answers_repeat_procedure_temperature_cells_at_n15():
    client = FixedLetterClient("A")
    solver_pairs, seat_answers = asyncio.run(
        lever_experiments.solve_all_cycled_panel(client, "Q?", ["1", "2", "3", "4"], n=15, tier="cheap")
    )
    assert len(seat_answers) == 15
    cells = [(s["procedure_or_lens"], s["temperature"]) for s in seat_answers]
    assert len(set(cells)) == 3  # only 3 distinct cells across 15 seats (period-3 cycling)
    # seat i is a byte-identical config to seat i-3, by construction.
    for i in range(3, 15):
        assert cells[i] == cells[i - 3]
        assert seat_answers[i]["permutation"] is None  # cycled_panel never shuffles choices


# ---------------------------------------------------------------------------
# (c) cycled_panel's 3-seat prefix is byte-identical config to the shipped panel
# ---------------------------------------------------------------------------


def test_cycled_panel_cheap_tier_three_seat_prefix_matches_shipped_panel_config():
    client_cycled = FixedLetterClient("A")
    client_shipped = FixedLetterClient("A")

    asyncio.run(lever_experiments.solve_all_cycled_panel(client_cycled, "Q?", ["1", "2", "3", "4"], n=3, tier="cheap"))
    from quorumqa.engine.solver import solve_all
    asyncio.run(solve_all(client_shipped, "Q?", ["1", "2", "3", "4"], n=3))

    def _normalize(calls):
        return sorted(
            (c["model"], c["system"], c["temperature"], c["thinking"], c["role"]) for c in calls
        )

    assert _normalize(client_cycled.calls) == _normalize(client_shipped.calls)
    assert len(client_cycled.calls) == 3
    assert all(c["model"] == MECHANICAL_MODEL and c["thinking"] is False for c in client_cycled.calls)


def test_cycled_panel_flagship_tier_uses_orchestrator_model_and_thinking():
    client = FixedLetterClient("A")
    asyncio.run(lever_experiments.solve_all_cycled_panel(client, "Q?", ["1", "2", "3", "4"], n=3, tier="flagship"))
    assert len(client.calls) == 3
    assert all(c["model"] == ORCHESTRATOR_MODEL and c["thinking"] is True for c in client.calls)
    assert all(c["role"] == "solver_thinking" for c in client.calls)


# ---------------------------------------------------------------------------
# (d) vote-only mode: exactly N solver calls, ZERO tribunal calls
# ---------------------------------------------------------------------------


def _content_letter(user: str, target: str) -> str:
    """Scans a solver user prompt's choice_block for the line whose choice
    TEXT contains `target`, returning that line's letter. Works regardless
    of whether the choices were shuffled (diversified_panel) or not
    (cycled_panel), since it always resolves the letter from CONTENT, never
    from call order or position."""
    for line in user.splitlines():
        stripped = line.strip()
        if len(stripped) >= 3 and stripped[0] in "ABCD" and stripped[1] == ")" and target in stripped:
            return stripped[0]
    raise AssertionError(f"target {target!r} not found in any choice line of:\n{user}")


def _fixed_content_client(target):
    """Every seat picks whichever position holds `target`'s text -- the
    CANONICAL letter is therefore the same for every seat regardless of
    each seat's independent shuffle (diversified_panel) or the absence of
    one (cycled_panel), giving a genuinely unanimous vote at the canonical
    level."""
    calls = []
    lock = threading.Lock()

    def chat_json(model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        letter = _content_letter(user, target)
        with lock:
            calls.append({"model": model, "role": role, "thinking": thinking})
        if role not in ("solver", "solver_thinking"):
            raise AssertionError(f"unexpected role {role!r} -- vote-only mode must never call the tribunal")
        return JsonCallResult(data={"letter": letter, "confidence": 0.6, "reasoning": f"picked {target}"}, usage=_usage(role))

    client = type("FixedContentClient", (), {"chat_json": staticmethod(chat_json), "calls": calls})()
    return client


def _split_content_client(target_a, target_b):
    """Alternates which CANONICAL choice each seat picks (by content, lock-
    protected -- asyncio.to_thread calls land on a real thread pool, so a
    naive unlocked counter would race). Guarantees a genuinely non-unanimous
    vote at the CANONICAL level for N>=2, regardless of each seat's
    independent shuffle (diversified_panel) or the lack of one
    (cycled_panel), and regardless of which physical seat's task happens to
    run first."""
    state = {"n": 0}
    lock = threading.Lock()
    calls = []

    def chat_json(model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        with lock:
            state["n"] += 1
            target = target_a if state["n"] % 2 == 0 else target_b
        letter = _content_letter(user, target)
        with lock:
            calls.append({"model": model, "role": role, "thinking": thinking})
        if role not in ("solver", "solver_thinking"):
            raise AssertionError(f"unexpected role {role!r} -- vote-only mode must never call the tribunal")
        return JsonCallResult(data={"letter": letter, "confidence": 0.5, "reasoning": f"picked {target}"}, usage=_usage(role))

    client = type("SplitContentClient", (), {"chat_json": staticmethod(chat_json), "calls": calls})()
    return client


@pytest.mark.parametrize("lever", ["diversified_panel", "cycled_panel"])
def test_no_tribunal_vote_only_mode_runs_exactly_n_solver_calls_unanimous(lever):
    choices = ["10", "20", "42", "99"]  # canonical C = "42"
    item = GPQAItem(question_id="np1", question="Q?", choices=choices, correct_letter="C")
    client = _fixed_content_client("42")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(
            client, None, item, lever, seed=7, n_solvers=15, no_tribunal=True, solver_tier="cheap",
        )
    )

    assert len(client.calls) == 15  # exactly N solver calls
    assert all(c["role"] in ("solver", "solver_thinking") for c in client.calls)
    assert result.escalated is False
    assert result.final_letter == "C"
    assert result.correct is True
    assert note["no_tribunal"] is True
    assert note["n_solvers"] == 15
    assert note["unanimous"] is True
    assert len(note["seat_answers"]) == 15


@pytest.mark.parametrize("lever", ["diversified_panel", "cycled_panel"])
def test_no_tribunal_vote_only_mode_runs_exactly_n_solver_calls_on_a_split(lever):
    choices = ["10", "20", "42", "99"]  # canonical B = "20", C = "42"
    item = GPQAItem(question_id="np2", question="Q?", choices=choices, correct_letter="B")
    client = _split_content_client("20", "42")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(
            client, None, item, lever, seed=7, n_solvers=9, no_tribunal=True, solver_tier="cheap",
        )
    )

    assert len(client.calls) == 9  # exactly N solver calls, split or not
    assert all(c["role"] in ("solver", "solver_thinking") for c in client.calls)
    # never escalates in vote-only mode, even though the vote is split
    assert result.escalated is False
    assert note["no_tribunal"] is True
    assert note["unanimous"] is False


def test_diversified_panel_without_no_tribunal_split_escalates_to_shipped_tribunal():
    # Default mode (no_tribunal=False): a split falls through to the
    # existing shipped tribunal path exactly like every other lever.
    item = GPQAItem(question_id="np3", question="Q?", choices=["1", "2", "3", "4"], correct_letter="B")
    calls = {"n": 0}

    class TribunalClient:
        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            if role in ("solver", "solver_thinking"):
                calls["n"] += 1
                letter = "A" if calls["n"] <= 2 else "B"
                return JsonCallResult(data={"letter": letter, "confidence": 0.5, "reasoning": "r"}, usage=_usage(role))
            if role == "skeptic":
                return JsonCallResult(data={"target_letter": "B", "disputed_step": "s", "argument": "a"}, usage=_usage("skeptic"))
            if role == "verifier":
                return JsonCallResult(data={"claims": []}, usage=_usage("verifier"))
            if role == "judge":
                return JsonCallResult(
                    data={"final_letter": "B", "decisive_reasoning": "d", "dissent": None,
                          "overturned_plurality": False, "confidence": "high"},
                    usage=_usage("judge"),
                )
            raise AssertionError(f"unexpected role {role!r}")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(
            TribunalClient(), None, item, "diversified_panel", seed=7, n_solvers=3, no_tribunal=False,
        )
    )
    assert result.escalated is True
    assert result.final_letter == "B"
    assert result.correct is True
    assert note["seat_answers"] is not None and len(note["seat_answers"]) == 3


# ---------------------------------------------------------------------------
# (e) seat_answers ordering/fields + permutation maps back to canonical
# ---------------------------------------------------------------------------


class ContentPickingClient:
    """Same technique as tests/test_lever_permuted_panel_offline.py: always
    picks whichever position in the presented choice_block contains a fixed
    target substring, independent of where the per-seat permutation put it."""

    def __init__(self, target_text):
        self._target = target_text
        self.seen_user_prompts = []
        self._lock = threading.Lock()

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        with self._lock:
            self.seen_user_prompts.append(user)
        assert role in ("solver", "solver_thinking")
        letter = None
        for line in user.splitlines():
            stripped = line.strip()
            if len(stripped) >= 3 and stripped[0] in "ABCD" and stripped[1] == ")" and self._target in stripped:
                letter = stripped[0]
                break
        assert letter is not None, f"target {self._target!r} not found in any choice line of:\n{user}"
        return JsonCallResult(data={"letter": letter, "confidence": 0.9, "reasoning": f"picked {self._target}"}, usage=_usage(role))


def test_diversified_panel_seat_answers_map_shuffled_letters_back_to_canonical():
    choices = ["10", "20", "42", "99"]  # canonical C = "42"
    client = ContentPickingClient("42")

    solver_pairs, seat_answers = asyncio.run(
        lever_experiments.solve_all_diversified_panel(client, "What is 6*7?", choices, seed=42, question_id="dp2", n=6, tier="cheap")
    )

    assert len(seat_answers) == 6
    answers = [a for a, _ in solver_pairs]
    assert all(a.letter == "C" for a in answers)  # every seat picked canonical "42" regardless of shuffle

    for i, rec in enumerate(seat_answers):
        assert rec["seat_index"] == i
        assert rec["letter"] == "C"
        assert rec["procedure_or_lens"] == lever_experiments.PROCEDURE_NAMES[i % 5]
        assert rec["temperature"] == SOLVER_TEMPERATURES[i % 3]
        perm = rec["permutation"]
        assert perm is not None
        assert sorted(perm["shuffled_order"]) == [0, 1, 2, 3]
        assert perm["canonical_letter"] == "C"
        expected_shuffled_index = perm["shuffled_order"].index(2)  # canonical index of "42"
        assert perm["shuffled_letter"] == "ABCD"[expected_shuffled_index]

    # Distinct seats really do see distinct shuffles (decorrelation by
    # construction, same as permuted_panel).
    assert len(set(client.seen_user_prompts)) > 1


def test_diversified_panel_seat_answers_fields_are_json_serializable():
    client = FixedLetterClient("B")
    _pairs, seat_answers = asyncio.run(
        lever_experiments.solve_all_diversified_panel(client, "Q?", ["1", "2", "3", "4"], seed=1, question_id="dp3", n=4, tier="cheap")
    )
    json.dumps(seat_answers)  # must not raise
    for rec in seat_answers:
        assert set(rec.keys()) == {"seat_index", "letter", "confidence", "procedure_or_lens", "temperature", "permutation"}


def test_cycled_panel_seat_answers_fields_are_json_serializable_and_permutation_null():
    client = FixedLetterClient("B")
    _pairs, seat_answers = asyncio.run(
        lever_experiments.solve_all_cycled_panel(client, "Q?", ["1", "2", "3", "4"], n=4, tier="cheap")
    )
    json.dumps(seat_answers)
    for rec in seat_answers:
        assert set(rec.keys()) == {"seat_index", "letter", "confidence", "procedure_or_lens", "temperature", "permutation"}
        assert rec["permutation"] is None


# ---------------------------------------------------------------------------
# (f) --solver-tier selects the right model + thinking
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier,expected_model,expected_thinking", [
    ("cheap", MECHANICAL_MODEL, False),
    ("flagship", ORCHESTRATOR_MODEL, True),
])
def test_diversified_panel_solver_tier_selects_model_and_thinking(tier, expected_model, expected_thinking):
    client = FixedLetterClient("A")
    asyncio.run(lever_experiments.solve_all_diversified_panel(client, "Q?", ["1", "2", "3", "4"], seed=1, question_id="dp4", n=5, tier=tier))
    assert len(client.calls) == 5
    assert all(c["model"] == expected_model for c in client.calls)
    assert all(c["thinking"] is expected_thinking for c in client.calls)


@pytest.mark.parametrize("tier,expected_model,expected_thinking", [
    ("cheap", MECHANICAL_MODEL, False),
    ("flagship", ORCHESTRATOR_MODEL, True),
])
def test_cycled_panel_solver_tier_selects_model_and_thinking(tier, expected_model, expected_thinking):
    client = FixedLetterClient("A")
    asyncio.run(lever_experiments.solve_all_cycled_panel(client, "Q?", ["1", "2", "3", "4"], n=5, tier=tier))
    assert len(client.calls) == 5
    assert all(c["model"] == expected_model for c in client.calls)
    assert all(c["thinking"] is expected_thinking for c in client.calls)


def test_main_live_rejects_unknown_solver_tier():
    with pytest.raises(ValueError):
        asyncio.run(lever_experiments.main_live(
            "diversified_panel", 1, 1, 1, __import__("pathlib").Path("unused.jsonl"), True, "supergpqa",
            None, 5, 0.0, 3, True, "not-a-real-tier",
        ))


# ---------------------------------------------------------------------------
# (g) _build_output_row folds the new fields in
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lever", ["diversified_panel", "cycled_panel"])
def test_build_output_row_includes_seat_answers_fields(lever):
    item = GPQAItem(question_id="dp5", question="Q", choices=["1", "2", "3", "4"], correct_letter="A")
    solver_answers = [SolverAnswer(letter="A", confidence=0.7, reasoning="r", lens="l") for _ in range(3)]
    result = QuestionResult(
        item=item, solver_answers=solver_answers, plurality_letter="A", escalated=False,
        final_letter="A", correct=True, calls=[_usage("solver")],
    )
    note = {
        "seat_answers": [{"seat_index": 0, "letter": "A", "confidence": 0.7, "procedure_or_lens": "solve_forward", "temperature": 0.3, "permutation": None}],
        "unanimous": True, "n_solvers": 3, "solver_tier": "cheap", "no_tribunal": True,
    }

    row = lever_experiments._build_output_row(result, lever, 42, "gpqa", None, None, note)

    assert row["lever"] == lever
    assert row["seat_answers"] == note["seat_answers"]
    assert row["unanimous"] is True
    assert row["n_solvers"] == 3
    assert row["solver_tier"] == "cheap"
    assert row["no_tribunal"] is True
    assert "arm" not in row  # verified_gate-only fields must not leak in


# ---------------------------------------------------------------------------
# (h) CLI registration
# ---------------------------------------------------------------------------


def test_diversified_and_cycled_panel_levers_present_in_argparse_choices():
    source = inspect.getsource(lever_experiments)
    assert '"diversified_panel"' in source
    assert '"cycled_panel"' in source
    assert "--n-solvers" in source
    assert "--no-tribunal" in source
    assert "--solver-tier" in source


# ---------------------------------------------------------------------------
# (i) benchmark/analyze_panel_scaling.py -- offline, synthetic JSONL
# ---------------------------------------------------------------------------


def _seat(idx, letter, procedure="solve_forward", temp=0.3, perm=None):
    return {"seat_index": idx, "letter": letter, "confidence": 0.8, "procedure_or_lens": procedure, "temperature": temp, "permutation": perm}


def _make_row(qid, correct_letter, seat_letters, lever="diversified_panel"):
    """Builds one synthetic diversified_panel-shaped JSONL row (as
    benchmark/lever_experiments.py's _build_output_row would write it) from
    an explicit list of per-seat letters."""
    seat_answers = [_seat(i, letter) for i, letter in enumerate(seat_letters)]
    return {
        "engine": {
            "item": {"question_id": qid, "question": "Q", "choices": ["1", "2", "3", "4"], "correct_letter": correct_letter, "subject": None},
            "solver_answers": [{"letter": s["letter"], "confidence": 0.8, "reasoning": "r", "lens": None} for s in seat_answers],
            "plurality_letter": seat_letters[0], "escalated": False, "final_letter": seat_letters[0],
            "correct": seat_letters[0] == correct_letter, "calls": [], "latency_s": 0.1,
        },
        "lever": lever, "seed": 42, "dataset": "supergpqa",
        "seat_answers": seat_answers, "unanimous": len(set(seat_letters)) == 1,
        "n_solvers": len(seat_letters), "solver_tier": "cheap", "no_tribunal": True,
    }


def _write_jsonl(tmp_path, rows, name="harvest.jsonl"):
    path = tmp_path / name
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return path


def test_prefix_subsampling_recovers_known_accuracy_at_n3_and_n15(tmp_path):
    # 10 items. First 3 seats are always WRONG ("A", gold "B") -> N=3
    # plurality accuracy = 0/10. Seats 4-15 are all "B" (correct), so by
    # N=15 all 15 seats vote 12 "B" vs 3 "A" -> plurality = "B" -> N=15
    # accuracy = 10/10.
    rows = []
    for i in range(10):
        seat_letters = ["A", "A", "A"] + ["B"] * 12
        rows.append(_make_row(f"q{i}", correct_letter="B", seat_letters=seat_letters))
    path = _write_jsonl(tmp_path, rows)

    result = aps.analyze(path)

    assert result["n_items"] == 10
    assert result["ns"] == [3, 5, 7, 9, 11, 13, 15]
    assert result["metrics"][3]["plurality_accuracy"] == 0.0
    assert result["metrics"][15]["plurality_accuracy"] == 1.0
    # unanimous at N=3 (all "A"), all wrong -> unanimous_wrong_rate@3 == 1.0
    assert result["metrics"][3]["unanimous_wrong_rate"] == 1.0
    # coverage@3: gold "B" never appears among the first 3 seats -> 0
    assert result["metrics"][3]["coverage"] == 0.0
    # coverage@15: "B" appears -> 1.0
    assert result["metrics"][15]["coverage"] == 1.0


def test_prefix_subsampling_coverage_can_exceed_plurality_accuracy(tmp_path):
    # 1 seat "A" (wrong, gold "B"), 1 seat "B" (correct), 1 seat "C" (wrong)
    # at N=3 -> plurality is a 3-way tie, Counter.most_common(1) picks the
    # first-inserted letter ("A") -> wrong. But "B" (gold) is present among
    # the votes -> covered.
    row = _make_row("qx", correct_letter="B", seat_letters=["A", "B", "C"] + ["A"] * 12)
    path = _write_jsonl(tmp_path, [row])
    result = aps.analyze(path)
    per_item = result["metrics"][3]["per_item"]["qx"]
    assert per_item["plurality_letter"] == "A"
    assert per_item["plurality_correct"] is False
    assert per_item["coverage_correct"] is True


def test_mcnemar_counts_and_p_value_correct(tmp_path):
    # 5 items flip from wrong@N=3 to correct@N=15 (gains, b=5), 0 losses
    # (c=0) -> exact one-sided p = 0.5**5 = 0.03125 (docs/experiment-spec-
    # book.md section 1's own worked example for the +5 floor).
    rows = []
    for i in range(5):
        rows.append(_make_row(f"gain{i}", correct_letter="B", seat_letters=["A", "A", "A"] + ["B"] * 12))
    for i in range(7):
        # stays correct at both N -- not discordant, doesn't touch b or c.
        rows.append(_make_row(f"stable{i}", correct_letter="B", seat_letters=["B"] * 15))
    path = _write_jsonl(tmp_path, rows)

    result = aps.analyze(path)
    mc15 = result["mcnemar_vs_n3"][15]
    assert mc15["b"] == 5
    assert mc15["c"] == 0
    assert mc15["p_one_sided"] == pytest.approx(0.5 ** 5)


def test_mcnemar_exact_one_sided_matches_spec_book_worked_examples():
    # docs/experiment-spec-book.md section 1: +3 net (zero losses) -> 0.125,
    # +4 -> 0.0625, +5 -> 0.03125.
    assert aps.mcnemar_exact_one_sided(3, 0) == pytest.approx(0.125)
    assert aps.mcnemar_exact_one_sided(4, 0) == pytest.approx(0.0625)
    assert aps.mcnemar_exact_one_sided(5, 0) == pytest.approx(0.03125)
    assert aps.mcnemar_exact_one_sided(0, 0) == 1.0


def test_bootstrap_ci_is_produced(tmp_path):
    rows = []
    for i in range(8):
        rows.append(_make_row(f"q{i}", correct_letter="B", seat_letters=["A", "A", "A"] + ["B"] * 12))
    path = _write_jsonl(tmp_path, rows)

    result = aps.analyze(path, bootstrap=True, n_bootstrap=30, bootstrap_seed=0)

    assert result["bootstrap"] is not None
    for n in result["ns"]:
        bs = result["bootstrap"][n]
        assert bs["n_bootstrap"] == 30
        assert 0.0 <= bs["ci_low"] <= bs["mean"] <= bs["ci_high"] <= 1.0


def test_bootstrap_reproducible_for_same_seed(tmp_path):
    rows = [_make_row(f"q{i}", correct_letter="B", seat_letters=["A", "B"] * 7 + ["A"]) for i in range(6)]
    path = _write_jsonl(tmp_path, rows)
    r1 = aps.analyze(path, bootstrap=True, n_bootstrap=20, bootstrap_seed=5)
    r2 = aps.analyze(path, bootstrap=True, n_bootstrap=20, bootstrap_seed=5)
    assert r1["bootstrap"][3] == r2["bootstrap"][3]


def test_load_panel_rows_skips_rows_without_seat_answers(tmp_path):
    good = _make_row("q1", "B", ["B"] * 15)
    bad = {"engine": {"item": {"question_id": "q2"}}, "lever": "control", "seed": 42, "dataset": "supergpqa"}
    path = _write_jsonl(tmp_path, [good, bad])
    rows = aps.load_panel_rows(path)
    assert len(rows) == 1
    assert aps.question_id(rows[0]) == "q1"


def test_analyze_raises_on_empty_or_no_panel_rows(tmp_path):
    path = _write_jsonl(tmp_path, [{"lever": "control", "seed": 42}])
    with pytest.raises(ValueError):
        aps.analyze(path)


def test_analyze_includes_escalation_table(tmp_path):
    rows = [_make_row(f"q{i}", "B", ["A", "A", "A"] + ["B"] * 12) for i in range(4)]
    path = _write_jsonl(tmp_path, rows)
    result = aps.analyze(path)
    assert len(result["escalation_table"]) > 0
    # every N gets the full 18-combination policy grid
    ns_seen = {entry["n"] for entry in result["escalation_table"]}
    assert ns_seen == set(result["ns"])
    n3_entries = [e for e in result["escalation_table"] if e["n"] == 3]
    assert len(n3_entries) == 18
