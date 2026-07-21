"""Loads an MMLU-Pro benchmark question set. HuggingFace dataset
TIGER-Lab/MMLU-Pro, split=test, public, ungated. 14 academic/professional
disciplines (Math, Physics, Chemistry, Law, Health, Engineering, Psychology,
Economics, and more), ~12,032 questions.

Schema verified live before writing this loader: `options` is a NATIVE list
column (not stringified like LEXam's), `answer_index` is a 0-indexed int
into that list, `category` gives the subject.

IMPORTANT TRADEOFF, stated plainly: MMLU-Pro questions carry up to 10
options each (vs. GPQA-Diamond/LEXam's fixed 4), which is part of its
appeal -- more distractors mechanically creates more room for solvers to
scatter and for a split-vote scenario to occur. QuorumQA's engine, however,
is hardcoded around exactly 4 choices (A-D) in every role's prompt
(solver.py, skeptic.py, judge.py, the gate). Extending every role to handle
a variable A-J choice set is a real engine change, not attempted here. This
loader instead trims each question down to 4 choices (the correct answer +
3 randomly sampled incorrect ones, reshuffled), matching the exact pattern
this repo's own load_gpqa.py already uses in its MMLU-Pro fallback path.
This means the pilot below is NOT testing MMLU-Pro's full 10-way
discrimination difficulty -- only a 4-way-trimmed version of it. Worth
knowing before comparing these numbers to any published MMLU-Pro score,
which is always computed on the untrimmed question.

Usage:
  from benchmark.load_mmlu_pro import load_mmlu_pro_set
  items = load_mmlu_pro_set(n=90, seed=42)
"""

import logging
import random

from datasets import load_dataset

from quorumqa.schemas import GPQAItem

from benchmark.load_gpqa import _shuffle_choices

log = logging.getLogger(__name__)

DATASET_ID = "TIGER-Lab/MMLU-Pro"


def load_mmlu_pro_set(n: int = 90, seed: int = 42, category: str | None = None) -> list[GPQAItem]:
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

        options = row["options"]
        answer_index = row["answer_index"]
        if not isinstance(options, list) or len(options) < 4 or not (0 <= answer_index < len(options)):
            continue

        correct = options[answer_index]
        incorrect_pool = [o for j, o in enumerate(options) if j != answer_index]
        incorrect = rng.sample(incorrect_pool, 3)

        shuffled, correct_letter = _shuffle_choices(rng, correct, incorrect)
        items.append(
            GPQAItem(
                question_id=str(row.get("question_id", i)),
                question=row["question"],
                choices=shuffled,
                correct_letter=correct_letter,
                subject=row.get("category"),
            )
        )

    log.info("Loaded %d MMLU-Pro items (category=%s, seed=%d, trimmed to 4 choices)", len(items), category, seed)
    return items
