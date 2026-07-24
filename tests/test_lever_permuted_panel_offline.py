"""Offline tests for the permuted_panel and method_panel levers
(benchmark/lever_experiments.py, docs/reasoning-supercharge-plan.md W2
Arm 0 / Arm 1) -- no live API calls, no cost. Covers:

  (a) _permute_choices is seeded exactly as specified
      (random.Random(f"{seed}:{question_id}:{seat_index}")), so it is
      reproducible run-to-run and differs per seat.
  (b) solve_all_permuted_panel maps a solver's shuffled-position letter
      back to the CANONICAL letter correctly -- proven with a fake client
      that answers by CONTENT (always picks the choice text "42" wherever
      the shuffle put it), independent of run_question_lever.
  (c) run_question_lever(..., "permuted_panel") votes on canonical letters
      (unanimous accept) and logs seat_permutations; a split still
      escalates to the shipped tribunal exactly like every other lever.
  (d) _build_output_row folds seat_permutations into the row.
  (e) solve_all_method_panel hits the fake client with three genuinely
      distinct METHOD system prompts, and records which method each seat
      used via SolverAnswer.lens; run_question_lever("method_panel") wires
      it through with no gate call.
  (f) Both levers are registered in the CLI's --lever choices.
"""

import asyncio
import inspect
import random

import pytest

import benchmark.lever_experiments as lever_experiments
from quorumqa.qwen_client import JsonCallResult
from quorumqa.schemas import CallUsage, GPQAItem, QuestionResult, SolverAnswer


def _usage(role: str) -> CallUsage:
    return CallUsage(model="fake-model", input_tokens=10, output_tokens=10, cost_usd=0.0001, role=role)


# ---------------------------------------------------------------------------
# (a) _permute_choices seeding
# ---------------------------------------------------------------------------


def test_permute_choices_matches_documented_seeding_scheme():
    choices = ["w", "x", "y", "z"]
    expected_perm = list(range(4))
    random.Random("42:qp:0").shuffle(expected_perm)

    shuffled, perm = lever_experiments._permute_choices(choices, seed=42, question_id="qp", seat_index=0)

    assert perm == expected_perm
    assert shuffled == [choices[i] for i in expected_perm]


def test_permute_choices_is_reproducible_for_same_seed_question_seat():
    choices = ["w", "x", "y", "z"]
    shuffled1, perm1 = lever_experiments._permute_choices(choices, seed=7, question_id="qp2", seat_index=1)
    shuffled2, perm2 = lever_experiments._permute_choices(choices, seed=7, question_id="qp2", seat_index=1)
    assert perm1 == perm2
    assert shuffled1 == shuffled2


def test_permute_choices_differs_per_seat_index():
    choices = ["w", "x", "y", "z"]
    perms = [
        tuple(lever_experiments._permute_choices(choices, seed=42, question_id="qp3", seat_index=i)[1])
        for i in range(3)
    ]
    # Each seat gets an INDEPENDENT shuffle (decorrelation by construction) --
    # all three permutations for this fixed seed+question should differ.
    assert len(set(perms)) == 3


def test_permute_choices_differs_per_question_id_for_same_seed_and_seat():
    choices = ["w", "x", "y", "z"]
    _, perm_a = lever_experiments._permute_choices(choices, seed=42, question_id="qA", seat_index=0)
    _, perm_b = lever_experiments._permute_choices(choices, seed=42, question_id="qB", seat_index=0)
    assert perm_a != perm_b


# ---------------------------------------------------------------------------
# (b) letters map back to canonical, proven via a content-picking fake client
# ---------------------------------------------------------------------------


class ContentPickingClient:
    """A fake client whose solver ALWAYS picks whichever position in the
    presented choice_block contains a fixed target substring. This proves
    the shuffled-position letter the model returns gets mapped back to the
    correct CANONICAL letter, independent of where the permutation put the
    target answer for that seat."""

    def __init__(self, target_text):
        self._target = target_text
        self.seen_user_prompts = []

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        assert role == "solver"
        self.seen_user_prompts.append(user)
        letter = None
        for line in user.splitlines():
            stripped = line.strip()
            if len(stripped) >= 3 and stripped[0] in "ABCD" and stripped[1] == ")" and self._target in stripped:
                letter = stripped[0]
                break
        assert letter is not None, f"target {self._target!r} not found in any choice line of:\n{user}"
        return JsonCallResult(
            data={"letter": letter, "confidence": 0.9, "reasoning": f"picked {self._target}"},
            usage=_usage("solver"),
        )


def test_solve_all_permuted_panel_maps_shuffled_letter_back_to_canonical():
    choices = ["10", "20", "42", "99"]  # canonical C = "42"
    client = ContentPickingClient("42")

    solver_pairs, seat_permutations = asyncio.run(
        lever_experiments.solve_all_permuted_panel(client, "What is 6*7?", choices, seed=42, question_id="qp4")
    )

    answers = [a for a, _ in solver_pairs]
    assert len(answers) == 3
    # Every seat picked the canonical letter for "42" regardless of which
    # shuffled position it landed at for that seat.
    assert all(a.letter == "C" for a in answers)

    assert len(seat_permutations) == 3
    for i, record in enumerate(seat_permutations):
        assert record["seat_index"] == i
        assert record["canonical_letter"] == "C"
        assert sorted(record["shuffled_order"]) == [0, 1, 2, 3]
        # The shuffled letter the model actually saw/picked corresponds to
        # position perm.index(2) (2 = canonical index of "42") in ITS order.
        expected_shuffled_index = record["shuffled_order"].index(2)
        assert record["shuffled_letter"] == "ABCD"[expected_shuffled_index]


def test_solve_all_permuted_panel_choice_block_is_actually_shuffled_per_seat():
    # Sanity check that seats really do see DIFFERENT orderings (not just
    # that the remap logic would handle it if they did).
    choices = ["10", "20", "42", "99"]
    client = ContentPickingClient("42")
    asyncio.run(lever_experiments.solve_all_permuted_panel(client, "Q?", choices, seed=42, question_id="qp5"))
    assert len(set(client.seen_user_prompts)) == 3  # 3 distinct prompts (distinct orders)


# ---------------------------------------------------------------------------
# (c) run_question_lever("permuted_panel"): canonical-letter voting +
#     seat_permutations logging; split still escalates like the shipped engine
# ---------------------------------------------------------------------------


def test_permuted_panel_lever_votes_on_canonical_letters_and_accepts_unanimous():
    item = GPQAItem(question_id="qp6", question="What is 6*7?", choices=["10", "20", "42", "99"], correct_letter="C")
    client = ContentPickingClient("42")

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "permuted_panel", seed=7))

    assert result.escalated is False
    assert result.plurality_letter == "C"
    assert result.final_letter == "C"
    assert result.correct is True
    assert "seat_permutations" in note
    assert len(note["seat_permutations"]) == 3


def test_permuted_panel_lever_split_escalates_to_shipped_tribunal():
    # Two seats see the shuffle put "20" in a position they name distinctly
    # from the third seat's pick of "42" -- forcing genuine disagreement on
    # CANONICAL letters (B vs C), which must still escalate exactly like
    # the shipped engine's split-plurality path.
    item = GPQAItem(question_id="qp7", question="Q?", choices=["10", "20", "42", "99"], correct_letter="B")

    calls = {"n": 0}

    class SplitClient:
        def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
            if role == "solver":
                calls["n"] += 1
                # First two solver calls pick "20", the third picks "42" --
                # by CONTENT, so the canonical outcome is B,B,C regardless
                # of shuffle position.
                target = "20" if calls["n"] <= 2 else "42"
                for line in user.splitlines():
                    stripped = line.strip()
                    if len(stripped) >= 3 and stripped[0] in "ABCD" and stripped[1] == ")" and target in stripped:
                        return JsonCallResult(
                            data={"letter": stripped[0], "confidence": 0.6, "reasoning": f"picked {target}"},
                            usage=_usage("solver"),
                        )
                raise AssertionError(f"target {target!r} not found in {user}")
            if role == "skeptic":
                return JsonCallResult(
                    data={"target_letter": "B", "disputed_step": "s", "argument": "a"}, usage=_usage("skeptic"),
                )
            if role == "verifier":
                return JsonCallResult(data={"claims": []}, usage=_usage("verifier"))
            if role == "judge":
                return JsonCallResult(
                    data={
                        "final_letter": "B", "decisive_reasoning": "d", "dissent": None,
                        "overturned_plurality": False, "confidence": "high",
                    },
                    usage=_usage("judge"),
                )
            raise AssertionError(f"unexpected role {role!r}")

    result, note = asyncio.run(
        lever_experiments.run_question_lever(SplitClient(), None, item, "permuted_panel", seed=7)
    )

    assert result.escalated is True
    assert result.plurality_letter == "B"
    assert result.final_letter == "B"
    assert result.correct is True
    assert len(note["seat_permutations"]) == 3


# ---------------------------------------------------------------------------
# (d) _build_output_row folds seat_permutations into the row
# ---------------------------------------------------------------------------


def test_build_output_row_includes_seat_permutations_for_permuted_panel():
    item = GPQAItem(question_id="qp8", question="Q", choices=["1", "2", "3", "4"], correct_letter="A")
    solver_answers = [SolverAnswer(letter="A", confidence=0.7, reasoning="r", lens="l") for _ in range(3)]
    result = QuestionResult(
        item=item, solver_answers=solver_answers, plurality_letter="A", escalated=False,
        final_letter="A", correct=True, calls=[_usage("solver")],
    )
    note = {
        "seat_permutations": [
            {"seat_index": 0, "shuffled_order": [1, 0, 2, 3], "shuffled_letter": "A", "canonical_letter": "B"},
        ]
    }

    row = lever_experiments._build_output_row(result, "permuted_panel", 42, "gpqa", None, None, note)

    assert row["lever"] == "permuted_panel"
    assert row["seat_permutations"] == note["seat_permutations"]
    assert "arm" not in row  # verified_gate-only fields must not leak in


# ---------------------------------------------------------------------------
# (e) method_panel: three distinct METHOD system prompts
# ---------------------------------------------------------------------------


class RecordingClient:
    """A fake client that records every (role, system) pair it was called
    with and always answers a fixed letter."""

    def __init__(self, letter="A"):
        self._letter = letter
        self.seen = []  # (role, system)

    def chat_json(self, model, system, user, role, temperature=0.4, max_tokens=1024, retries=1, thinking=True):
        self.seen.append((role, system))
        if role == "solver":
            return JsonCallResult(
                data={"letter": self._letter, "confidence": 0.6, "reasoning": "r"}, usage=_usage("solver"),
            )
        raise AssertionError(f"unexpected role {role!r}")


def test_solve_all_method_panel_uses_three_distinct_method_prompts():
    client = RecordingClient()

    solver_pairs = asyncio.run(lever_experiments.solve_all_method_panel(client, "Q?", ["1", "2", "3", "4"]))

    assert len(solver_pairs) == 3
    systems = [s for role, s in client.seen if role == "solver"]
    assert len(systems) == 3
    assert len(set(systems)) == 3  # three genuinely distinct system prompts

    for sysprompt in systems:
        assert lever_experiments.SOLVER_SYSTEM in sysprompt
    for method_prompt in lever_experiments.METHOD_PROMPTS:
        assert any(method_prompt in s for s in systems)

    # The method NAME (not the shipped lens text) is logged via
    # SolverAnswer.lens, so downstream analysis can see which method each
    # seat used.
    answers = [a for a, _ in solver_pairs]
    assert {a.lens for a in answers} == set(lever_experiments.METHOD_NAMES)


def test_method_panel_lever_routes_through_run_question_lever_with_no_gate():
    item = GPQAItem(question_id="qm1", question="Q?", choices=["1", "2", "3", "4"], correct_letter="B")
    client = RecordingClient(letter="B")

    result, note = asyncio.run(lever_experiments.run_question_lever(client, None, item, "method_panel"))

    assert result.escalated is False
    assert result.final_letter == "B"
    assert result.correct is True
    solver_calls = [c for c in client.seen if c[0] == "solver"]
    assert len(solver_calls) == 3
    # method_panel has no gate step -- exactly 3 calls total for a
    # unanimous question.
    assert len(client.seen) == 3


# ---------------------------------------------------------------------------
# (f) both levers registered in the CLI's --lever choices
# ---------------------------------------------------------------------------


def test_permuted_and_method_panel_levers_present_in_argparse_choices():
    source = inspect.getsource(lever_experiments)
    assert '"permuted_panel"' in source
    assert '"method_panel"' in source
