"""Loads an MMLU-Pro benchmark question set. HuggingFace dataset
TIGER-Lab/MMLU-Pro, split=test, public, ungated. 14 academic/professional
disciplines (Math, Physics, Chemistry, Law, Health, Engineering, Psychology,
Economics, and more), ~12,032 questions.

Schema verified live before writing this loader: `options` is a NATIVE list
column (not stringified like LEXam's), `answer_index` is a 0-indexed int
into that list, `category` gives the subject.

IMPORTANT TRADEOFF, stated plainly -- NOW OPTIONAL (docs/capability-roadmap.md
item F7 / section 3.6): MMLU-Pro questions carry up to 10 options each (vs.
GPQA-Diamond/LEXam's fixed 4), which is part of its appeal -- more
distractors mechanically creates more room for solvers to scatter and for a
split-vote scenario to occur. QuorumQA's engine USED TO BE hardcoded around
exactly 4 choices (A-D) in every role's prompt (solver.py, skeptic.py,
judge.py, the gate); it now supports any A-J (2-10) choice set via
quorumqa.letters. This loader still TRIMS to 4 choices BY DEFAULT (the
correct answer + 3 randomly sampled incorrect ones, reshuffled), matching
the exact pattern this repo's own load_gpqa.py already uses in its MMLU-Pro
fallback path -- this is load-bearing for every existing caller/result:
`load_mmlu_pro_set`/`load_mmlu_pro_stem_set` with no `max_choices` argument,
and the "mmlu_pro"/"mmlu_pro_stem" DATASET_LOADERS entries in
benchmark/lever_experiments.py, all stay byte-identical to every number this
repo has already published. Passing `max_choices=None` (or calling the new
`load_mmlu_pro_full_set` / the "mmlu_pro_full" DATASET_LOADERS entry) keeps
EVERY one of a question's native options instead. The trimmed and untrimmed
variants are NOT comparable to each other: more options mechanically lowers
chance accuracy and gives solvers more room to scatter, so an accuracy delta
between them conflates option count with item difficulty, not engine
capability. Only the untrimmed variant is comparable to a published
MMLU-Pro score, which is always computed on the full question.

Usage:
  from benchmark.load_mmlu_pro import load_mmlu_pro_set, load_mmlu_pro_full_set
  items = load_mmlu_pro_set(n=90, seed=42)               # trimmed to 4, as always
  full_items = load_mmlu_pro_full_set(n=90, seed=42)      # F7: every native option kept
"""

import logging
import random

from datasets import load_dataset

from quorumqa.letters import letters_for
from quorumqa.schemas import GPQAItem

from benchmark.load_gpqa import _shuffle_choices

log = logging.getLogger(__name__)

DATASET_ID = "TIGER-Lab/MMLU-Pro"


# The hard-STEM core of MMLU-Pro's 14 categories, used for the flagship_panel
# reasoning-generalization pilot: these are the disciplines where the cheap
# tier's unanimous-wrong rate runs highest (the condition under which
# deliberation demonstrably helps, per the GPQA-hard + SuperGPQA-hard finding).
# Deliberately excludes the softer/knowledge-recall categories (law, history,
# health, psychology, business, economics, philosophy, other).
STEM_CATEGORIES = frozenset({"physics", "chemistry", "math", "engineering", "computer science", "biology"})


def _shuffle_all_choices(rng: random.Random, correct: str, incorrect: list[str]) -> tuple[list[str], str]:
    """Like benchmark.load_gpqa._shuffle_choices, but supports 2-10 total
    choices instead of exactly 4 -- that module's `_LETTERS` is hardcoded to
    `string.ascii_uppercase[:4]`, so it cannot safely index a 5th+ choice.
    Same shuffle mechanics (order the indices, take correct_index's letter),
    just resolved against quorumqa.letters.letters_for's shared A-J
    vocabulary. At exactly 4 choices this produces the identical letter
    load_gpqa._shuffle_choices would (both index into "ABCD"), but callers
    that need byte-identical behavior at n=4 (the default trim) still call
    the real _shuffle_choices directly -- see load_mmlu_pro_set below."""
    choices = [correct, *incorrect]
    order = list(range(len(choices)))
    rng.shuffle(order)
    shuffled = [choices[i] for i in order]
    correct_index = order.index(0)
    return shuffled, letters_for(len(choices))[correct_index]


def load_mmlu_pro_set(
    n: int = 90,
    seed: int = 42,
    category: str | None = None,
    categories: frozenset[str] | None = None,
    max_choices: int | None = 4,
) -> list[GPQAItem]:
    """`max_choices` (F7, docs/capability-roadmap.md section 3.6):
      - 4 (the DEFAULT -- byte-identical to this loader's original,
        pre-F7 behavior, and to every existing caller/DATASET_LOADERS entry
        that omits this argument): trims to the correct answer + 3 randomly
        sampled incorrect ones, exactly as before.
      - None: keep ALL of the row's native options (see load_mmlu_pro_full_set
        below) -- capped at 10 (quorumqa.letters' A-J range, also MMLU-Pro's
        own documented max); a row with more than 10 options is skipped
        rather than crashing the run, the same defensive posture as the
        `len(options) < 4` check below.
      - any other int in 2-10: trims to that many choices instead (correct +
        max_choices-1 randomly sampled incorrect), generalizing the default.

    Rows that can't satisfy the requested choice count (too few incorrect
    options to trim to, or too many to keep whole) are skipped."""
    ds = load_dataset(DATASET_ID, split="test")
    rng = random.Random(seed)

    rows = list(range(len(ds)))
    rng.shuffle(rows)

    items: list[GPQAItem] = []
    for i in rows:
        if len(items) >= n:
            break
        row = ds[i]
        if category is not None and row.get("category") != category:
            continue
        if categories is not None and row.get("category") not in categories:
            continue

        options = row["options"]
        answer_index = row["answer_index"]
        if not isinstance(options, list) or len(options) < 4 or not (0 <= answer_index < len(options)):
            continue

        correct = options[answer_index]
        incorrect_pool = [o for j, o in enumerate(options) if j != answer_index]

        if max_choices == 4:
            # Byte-identical to this loader's original (pre-F7) behavior --
            # same rng.sample call, same real _shuffle_choices function.
            incorrect = rng.sample(incorrect_pool, 3)
            shuffled, correct_letter = _shuffle_choices(rng, correct, incorrect)
        elif max_choices is None:
            if len(options) > 10:
                continue
            shuffled, correct_letter = _shuffle_all_choices(rng, correct, incorrect_pool)
        else:
            if not (2 <= max_choices <= 10):
                raise ValueError(f"max_choices must be None, or an int between 2 and 10, got {max_choices!r}")
            if len(incorrect_pool) < max_choices - 1:
                continue
            incorrect = rng.sample(incorrect_pool, max_choices - 1)
            shuffled, correct_letter = _shuffle_all_choices(rng, correct, incorrect)

        items.append(
            GPQAItem(
                question_id=str(row.get("question_id", i)),
                question=row["question"],
                choices=shuffled,
                correct_letter=correct_letter,
                subject=row.get("category"),
            )
        )

    log.info(
        "Loaded %d MMLU-Pro items (category=%s, categories=%s, seed=%d, max_choices=%s)",
        len(items), category, categories, seed, max_choices,
    )
    return items


def load_mmlu_pro_stem_set(n: int = 90, seed: int = 42) -> list[GPQAItem]:
    """MMLU-Pro restricted to the hard-STEM core (STEM_CATEGORIES). Used for the
    flagship_panel reasoning-generalization pilot — the third hard-STEM
    benchmark after GPQA-hard and SuperGPQA-hard. Always trims to 4 choices
    (max_choices is not exposed here) -- byte-identical to pre-F7 behavior."""
    return load_mmlu_pro_set(n=n, seed=seed, categories=STEM_CATEGORIES)


def load_mmlu_pro_full_set(
    n: int = 90,
    seed: int = 42,
    category: str | None = None,
    categories: frozenset[str] | None = None,
) -> list[GPQAItem]:
    """F7's untrimmed MMLU-Pro variant: keeps every one of a question's
    native options (up to MMLU-Pro's own max of 10) instead of trimming to
    4. NOT comparable to load_mmlu_pro_set/load_mmlu_pro_stem_set's numbers
    -- see the module docstring. Use this to measure QuorumQA against
    MMLU-Pro's actual published protocol; use the trimmed loaders to keep
    continuity with this project's existing 4-way results."""
    return load_mmlu_pro_set(n=n, seed=seed, category=category, categories=categories, max_choices=None)
