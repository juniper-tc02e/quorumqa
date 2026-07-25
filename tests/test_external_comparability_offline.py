"""Offline tests for the external-comparability build (no paid API calls,
no live model calls anywhere in this file -- every test uses either a
monkeypatched `load_dataset` fake or a fake QwenClient, same pattern as
tests/test_aj_options_offline.py and tests/test_ifeval_offline.py):

Section 1 -- benchmark/load_supergpqa.py's max_choices generalization
(mirrors the equivalent MMLU-Pro section in tests/test_aj_options_offline.py
almost exactly, since it is the same F7 pattern applied to a second
loader), PLUS one test stronger than that file's own coverage: an explicit
byte-for-byte proof, including RNG CONSUMPTION (not just output), that the
max_choices=4 default reproduces the pre-F7 algorithm exactly.

Section 2 -- benchmark/run_ifeval.py's scoring pipeline (solve_single_ifeval
-> compute_summary) end to end against a fake client, including that the
held-out-subset headline metric is computed over ONLY prompts whose entire
instruction_id_list is drawn from HELD_OUT_INSTRUCTION_TYPES -- proven by
constructing a mix of held-out-only, in-domain, and mixed items and
checking the subset boundary lands exactly where it should. Also covers the
`--arm panel` fail-fast (NotImplementedError, before any dataset load or
client construction) and the retry-with-backoff helper.
"""

from __future__ import annotations

import random as random_module
import string as string_module
import types

import pytest

import benchmark.lever_experiments as LE
import benchmark.run_ifeval as ri
from benchmark.ifeval_verify import HELD_OUT_INSTRUCTION_TYPES
from benchmark.load_gpqa import _shuffle_choices as _real_shuffle_choices
from benchmark.load_ifeval import IFEvalItem
from quorumqa.letters import letters_for
from quorumqa.schemas import CallUsage

# ---------------------------------------------------------------------------
# Section 1 -- benchmark/load_supergpqa.py's max_choices generalization (F7).
# ---------------------------------------------------------------------------


def _fake_sgpqa_row(uuid, question, discipline, difficulty, options, answer_index):
    letter = string_module.ascii_uppercase[answer_index]
    return {
        "uuid": uuid,
        "question": question,
        "discipline": discipline,
        "difficulty": difficulty,
        "options": options,
        "answer_letter": letter,
        "answer": options[answer_index],
    }


def test_load_supergpqa_set_default_still_trims_to_4(monkeypatch):
    import benchmark.load_supergpqa as ls

    fake_rows = [_fake_sgpqa_row("u0", "Q0?", "Science", "hard", [f"o{i}" for i in range(8)], 3)]
    monkeypatch.setattr(ls, "load_dataset", lambda *a, **k: fake_rows)

    items = ls.load_supergpqa_set(n=90, seed=1)
    assert len(items) == 1
    assert len(items[0].choices) == 4
    assert items[0].choices[letters_for(4).index(items[0].correct_letter)] == "o3"


def test_load_supergpqa_set_max_choices_none_keeps_all_options(monkeypatch):
    import benchmark.load_supergpqa as ls

    fake_rows = [_fake_sgpqa_row("u0", "Q0?", "Science", "hard", [f"o{i}" for i in range(8)], 5)]
    monkeypatch.setattr(ls, "load_dataset", lambda *a, **k: fake_rows)

    items = ls.load_supergpqa_set(n=90, seed=1, max_choices=None)
    assert len(items) == 1
    assert len(items[0].choices) == 8
    assert items[0].choices[letters_for(8).index(items[0].correct_letter)] == "o5"


def test_load_supergpqa_set_max_choices_none_skips_rows_over_10_options(monkeypatch):
    import benchmark.load_supergpqa as ls

    fake_rows = [
        _fake_sgpqa_row("u_toomany", "Q?", "Science", "hard", [f"o{i}" for i in range(11)], 0),
        _fake_sgpqa_row("u_ok", "Q2?", "Science", "hard", [f"p{i}" for i in range(4)], 1),
    ]
    monkeypatch.setattr(ls, "load_dataset", lambda *a, **k: fake_rows)

    items = ls.load_supergpqa_set(n=90, seed=1, max_choices=None)
    assert len(items) == 1
    assert items[0].question_id == "u_ok"


def test_load_supergpqa_set_max_choices_custom_int_trims_to_that_count(monkeypatch):
    import benchmark.load_supergpqa as ls

    fake_rows = [_fake_sgpqa_row("u0", "Q0?", "Science", "hard", [f"o{i}" for i in range(8)], 2)]
    monkeypatch.setattr(ls, "load_dataset", lambda *a, **k: fake_rows)

    items = ls.load_supergpqa_set(n=90, seed=1, max_choices=6)
    assert len(items) == 1
    assert len(items[0].choices) == 6
    assert items[0].choices[letters_for(6).index(items[0].correct_letter)] == "o2"


def test_load_supergpqa_set_max_choices_out_of_range_raises(monkeypatch):
    import benchmark.load_supergpqa as ls

    fake_rows = [_fake_sgpqa_row("u0", "Q0?", "Science", "hard", [f"o{i}" for i in range(8)], 0)]
    monkeypatch.setattr(ls, "load_dataset", lambda *a, **k: fake_rows)

    with pytest.raises(ValueError):
        ls.load_supergpqa_set(n=90, seed=1, max_choices=1)
    with pytest.raises(ValueError):
        ls.load_supergpqa_set(n=90, seed=1, max_choices=11)


def test_load_supergpqa_full_set_delegates_with_max_choices_none(monkeypatch):
    import benchmark.load_supergpqa as ls

    fake_rows = [_fake_sgpqa_row("u0", "Q0?", "Engineering", "hard", [f"o{i}" for i in range(10)], 9)]
    monkeypatch.setattr(ls, "load_dataset", lambda *a, **k: fake_rows)

    items = ls.load_supergpqa_full_set(n=90, seed=1)
    assert len(items) == 1
    assert len(items[0].choices) == 10
    assert items[0].choices[letters_for(10).index(items[0].correct_letter)] == "o9"


def test_dataset_loaders_has_supergpqa_full_entry(monkeypatch):
    import benchmark.load_supergpqa as ls

    fake_rows = [_fake_sgpqa_row("u0", "Q0?", "Science", "hard", [f"o{i}" for i in range(10)], 0)]
    monkeypatch.setattr(ls, "load_dataset", lambda *a, **k: fake_rows)

    assert "supergpqa_full" in LE.DATASET_LOADERS
    items = LE.DATASET_LOADERS["supergpqa_full"](90, 1, False)
    assert len(items) == 1
    assert len(items[0].choices) == 10


def test_supergpqa_full_present_in_argparse_choices():
    # Same check as test_aj_options_offline.py's mmlu_pro_full equivalent:
    # confirms --dataset's argparse choices are built from
    # list(DATASET_LOADERS.keys()) (so a future entry can't be forgotten)
    # and that "supergpqa_full" actually flows through it.
    import inspect

    source = inspect.getsource(LE)
    assert "choices=list(DATASET_LOADERS.keys())" in source
    assert "supergpqa_full" in LE.DATASET_LOADERS


# --- byte-for-byte / rng-consumption proof, stronger than the above -------


def _pre_f7_load_supergpqa_algorithm(fake_rows, n, seed, difficulty="hard"):
    """Verbatim reimplementation of load_supergpqa_set's body as it existed
    BEFORE max_choices existed -- i.e. always `rng.sample(pool, 3)` then the
    real `_shuffle_choices`, no branching at all. Used only to prove the new
    max_choices=4 default path reproduces both the old OUTPUT and the old
    RNG CONSUMPTION exactly, per the build spec's explicit requirement."""
    letter_index = {c: i for i, c in enumerate(string_module.ascii_uppercase)}

    rng = random_module.Random(seed)
    rows = list(range(len(fake_rows)))
    rng.shuffle(rows)

    items = []
    for i in rows:
        if len(items) >= n:
            break
        row = fake_rows[i]
        if difficulty is not None and row.get("difficulty") != difficulty:
            continue
        options = row["options"]
        if not isinstance(options, list) or len(options) < 4:
            continue
        letter = row.get("answer_letter")
        answer_index = letter_index.get(letter, -1) if letter else -1
        if not (0 <= answer_index < len(options)) or options[answer_index] != row.get("answer"):
            try:
                answer_index = options.index(row["answer"])
            except ValueError:
                continue
        correct = options[answer_index]
        incorrect_pool = [o for j, o in enumerate(options) if j != answer_index]
        incorrect = rng.sample(incorrect_pool, 3)
        shuffled, correct_letter = _real_shuffle_choices(rng, correct, incorrect)
        items.append((str(row.get("uuid", i)), row["question"], tuple(shuffled), correct_letter, row.get("discipline")))
    return items, rng.getstate()


class _TrackedRandom(random_module.Random):
    """Subclasses random.Random purely to record every instance created, so
    a test can inspect the loader's own internal RNG's final getstate()."""

    instances: list = []

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _TrackedRandom.instances.append(self)


def test_supergpqa_default_max_choices_is_byte_identical_to_pre_f7(monkeypatch):
    import benchmark.load_supergpqa as ls

    fake_rows = [
        _fake_sgpqa_row(
            f"u{i}", f"Q{i}?",
            "Science" if i % 2 == 0 else "Engineering",
            "hard" if i % 3 != 0 else "easy",  # exercises the difficulty-filter skip path too
            [f"o{i}_{j}" for j in range(4 + (i % 5))],  # option counts 4..8
            i % 4,
        )
        for i in range(30)
    ]
    monkeypatch.setattr(ls, "load_dataset", lambda *a, **k: fake_rows)

    old_items, old_state = _pre_f7_load_supergpqa_algorithm(fake_rows, n=90, seed=42)

    _TrackedRandom.instances.clear()
    monkeypatch.setattr(ls, "random", types.SimpleNamespace(Random=_TrackedRandom))
    new_items = ls.load_supergpqa_set(n=90, seed=42)  # default max_choices=4 -- must match exactly

    assert len(_TrackedRandom.instances) == 1, "load_supergpqa_set must construct exactly one Random instance"
    assert _TrackedRandom.instances[0].getstate() == old_state, "RNG consumption diverged from the pre-F7 algorithm"

    assert len(new_items) == len(old_items) > 0
    for new_item, (qid, question, choices, correct_letter, discipline) in zip(new_items, old_items):
        assert new_item.question_id == qid
        assert new_item.question == question
        assert tuple(new_item.choices) == choices
        assert new_item.correct_letter == correct_letter
        assert new_item.subject == discipline


# ---------------------------------------------------------------------------
# Section 2 -- benchmark/run_ifeval.py's scoring pipeline.
# ---------------------------------------------------------------------------


class _FakeChatClient:
    """Fakes QwenClient.chat() only (never chat_json -- solve_single_ifeval
    deliberately never calls it, see run_ifeval.py's module docstring).
    Responses are looked up by the exact prompt text sent as the sole user
    message, so this works whether items are solved sequentially or
    concurrently (main() runs them concurrently via asyncio.gather)."""

    def __init__(self, responses_by_prompt: dict[str, str]):
        self._responses = responses_by_prompt
        self.calls: list[dict] = []

    def chat(self, model, messages, role, temperature=0.4, max_tokens=1024, thinking=True, seed=None, thinking_budget=None):
        assert len(messages) == 1 and messages[0]["role"] == "user", "solve_single_ifeval must send a bare user message, no system prompt"
        prompt = messages[0]["content"]
        self.calls.append({"model": model, "prompt": prompt, "role": role, "thinking": thinking})
        content = self._responses[prompt]
        usage = CallUsage(model=model, input_tokens=5, output_tokens=5, cost_usd=0.0, role=role)
        return content, usage


# Four items exercising exactly the held-out-only / in-domain / mixed split
# compute_summary's held_out_subset must respect:
#   A: held-out-only (startend:quotation), satisfied      -> held-out subset, strict True
#   B: held-out-only (keywords:letter_frequency), violated -> held-out subset, strict False
#   C: in-domain only (punctuation:no_comma), satisfied    -> NOT in held-out subset
#   D: mixed (startend:quotation + punctuation:no_comma), both satisfied -> NOT in held-out subset
_ITEM_A = IFEvalItem(key=1, prompt="PROMPT_A", instruction_id_list=["startend:quotation"], kwargs=[{}])
_ITEM_B = IFEvalItem(
    key=2, prompt="PROMPT_B", instruction_id_list=["keywords:letter_frequency"],
    kwargs=[{"letter": "z", "let_frequency": 5, "let_relation": "at least"}],
)
_ITEM_C = IFEvalItem(key=3, prompt="PROMPT_C", instruction_id_list=["punctuation:no_comma"], kwargs=[{}])
_ITEM_D = IFEvalItem(
    key=4, prompt="PROMPT_D", instruction_id_list=["startend:quotation", "punctuation:no_comma"],
    kwargs=[{}, {}],
)

_RESPONSES = {
    "PROMPT_A": '"This response is fully wrapped in quotes."',  # starts/ends with " -> followed
    "PROMPT_B": "buzz",  # only 2 z's, need >= 5 -> violated
    "PROMPT_C": "This response has no forbidden punctuation mark in it at all.",  # no comma -> followed
    "PROMPT_D": '"This response is quoted and has zero forbidden marks inside it."',  # quoted AND no comma -> both followed
}


def test_solve_single_ifeval_scores_strict_and_loose_and_flags_held_out_only():
    client = _FakeChatClient(_RESPONSES)

    row_a = ri.solve_single_ifeval(client, _ITEM_A, model="test-model", thinking=False)
    row_b = ri.solve_single_ifeval(client, _ITEM_B, model="test-model", thinking=False)
    row_c = ri.solve_single_ifeval(client, _ITEM_C, model="test-model", thinking=False)
    row_d = ri.solve_single_ifeval(client, _ITEM_D, model="test-model", thinking=False)

    assert row_a["strict_followed"] is True and row_a["is_held_out_only"] is True
    assert row_b["strict_followed"] is False and row_b["is_held_out_only"] is True
    assert row_c["strict_followed"] is True and row_c["is_held_out_only"] is False
    assert row_d["strict_followed"] is True and row_d["is_held_out_only"] is False

    # loose_followed must also be present and boolean (verify_all_loose was
    # actually invoked, not skipped) for every row.
    for row in (row_a, row_b, row_c, row_d):
        assert isinstance(row["loose_followed"], bool)
        assert row["calls"][0]["role"] == "single"
        assert row["arm"] == "single"

    # Only one call was made per item -- no accidental extra client.chat calls.
    assert len(client.calls) == 4
    assert all(c["thinking"] is False for c in client.calls)


def test_compute_summary_held_out_subset_excludes_in_domain_and_mixed_items():
    client = _FakeChatClient(_RESPONSES)
    rows = [ri.solve_single_ifeval(client, item, model="test-model", thinking=False) for item in (_ITEM_A, _ITEM_B, _ITEM_C, _ITEM_D)]

    summary = ri.compute_summary(rows)

    assert summary["n_total"] == 4
    # full_vocabulary covers all 4: A=True, B=False, C=True, D=True -> 3/4.
    assert summary["full_vocabulary"]["n"] == 4
    assert summary["full_vocabulary"]["strict_accuracy"] == pytest.approx(0.75)

    # held_out_subset must contain ONLY A and B (the two held-out-only
    # items) -- C (in-domain) and D (mixed) must be excluded even though D
    # contains a held-out instruction type.
    assert summary["held_out_subset"]["n"] == 2
    assert summary["held_out_subset"]["strict_accuracy"] == pytest.approx(0.5)  # A True, B False
    assert "note" in summary["held_out_subset"]

    families = summary["per_instruction_family"]
    assert families["startend:quotation"]["n"] == 2  # occurs in A and D
    assert families["startend:quotation"]["strict_accuracy"] == pytest.approx(1.0)
    assert families["startend:quotation"]["held_out"] is True

    assert families["keywords:letter_frequency"]["n"] == 1  # occurs only in B
    assert families["keywords:letter_frequency"]["strict_accuracy"] == pytest.approx(0.0)
    assert families["keywords:letter_frequency"]["held_out"] is True

    assert families["punctuation:no_comma"]["n"] == 2  # occurs in C and D
    assert families["punctuation:no_comma"]["strict_accuracy"] == pytest.approx(1.0)
    assert families["punctuation:no_comma"]["held_out"] is False


def test_compute_summary_empty_held_out_subset_does_not_divide_by_zero():
    client = _FakeChatClient(_RESPONSES)
    rows = [ri.solve_single_ifeval(client, _ITEM_C, model="test-model", thinking=False)]  # in-domain only

    summary = ri.compute_summary(rows)
    assert summary["held_out_subset"]["n"] == 0
    assert summary["held_out_subset"]["strict_accuracy"] == 0.0
    assert summary["held_out_subset"]["loose_accuracy"] == 0.0


# --- main() end-to-end against a fake client + monkeypatched loader -------


@pytest.mark.asyncio
async def test_main_end_to_end_writes_jsonl_and_summary(tmp_path, monkeypatch):
    client = _FakeChatClient(_RESPONSES)
    monkeypatch.setattr(ri, "QwenClient", lambda: client)
    monkeypatch.setattr(ri, "load_ifeval_set", lambda n, seed: [_ITEM_A, _ITEM_B, _ITEM_C, _ITEM_D])

    out_path = tmp_path / "ifeval_test_run.jsonl"
    await ri.main(n=4, seed=42, concurrency=4, out_path=out_path, model="test-model", thinking=False, arm="single")

    assert out_path.exists()
    lines = [line for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 4

    import json as json_module
    rows = [json_module.loads(line) for line in lines]
    assert {r["key"] for r in rows} == {1, 2, 3, 4}

    summary_path = out_path.with_suffix(".summary.json")
    assert summary_path.exists()
    summary = json_module.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["n_total"] == 4
    assert summary["held_out_subset"]["n"] == 2
    assert summary["full_vocabulary"]["n"] == 4


@pytest.mark.asyncio
async def test_main_panel_arm_raises_before_any_dataset_load_or_client_construction(tmp_path, monkeypatch):
    def _must_not_be_called(*a, **k):
        raise AssertionError("panel arm must fail before load_ifeval_set/QwenClient are ever touched")

    monkeypatch.setattr(ri, "load_ifeval_set", _must_not_be_called)
    monkeypatch.setattr(ri, "QwenClient", _must_not_be_called)

    with pytest.raises(NotImplementedError):
        await ri.main(n=4, seed=42, concurrency=4, out_path=tmp_path / "x.jsonl", model="test-model", thinking=False, arm="panel")


# --- retry-with-backoff -----------------------------------------------------


@pytest.mark.asyncio
async def test_attempt_with_retries_recovers_after_transient_failures(monkeypatch):
    sleeps: list[float] = []

    async def _fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(ri.asyncio, "sleep", _fake_sleep)

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    import asyncio as asyncio_module

    result = await ri._attempt_with_retries("test", _ITEM_A, asyncio_module.Semaphore(1), flaky)
    assert result == "ok"
    assert calls["n"] == 3
    assert sleeps == [5, 10]  # two retries before success -> two backoffs


@pytest.mark.asyncio
async def test_attempt_with_retries_drops_after_max_attempts(monkeypatch):
    async def _fake_sleep(seconds):
        return None

    monkeypatch.setattr(ri.asyncio, "sleep", _fake_sleep)

    def always_fails():
        raise TimeoutError("still transient")

    import asyncio as asyncio_module

    result = await ri._attempt_with_retries("test", _ITEM_A, asyncio_module.Semaphore(1), always_fails)
    assert result is None
