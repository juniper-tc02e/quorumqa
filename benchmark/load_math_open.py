"""Loads MATH-500's hardest tier as genuinely OPEN-ANSWER items -- no
distractor synthesis, no 4-choice MC framing.

WHY THIS EXISTS: benchmark/load_math.py already loads MATH-500 level-5, but
synthesizes 3 wrong choices per item and forces the question into the
engine's A-D schema (see that module's docstring). That MC framing
SATURATES the flagship (100%, see benchmark/results/math500_hard_pilot_
seed42.log) because a plausible-but-wrong distractor is trivially
eliminable even when the model could not have produced the right answer
cold -- it can't discriminate whether deliberation helps. This loader keeps
MATH-500's raw open `answer` field untouched (gold_answer), so
benchmark/math_open_engine.py can ask the flagship to produce the answer
from scratch and grade it with benchmark/math_grade.grade's equivalence
checker instead of a letter match.

Same dataset id, level filter, and row fields as load_math.py:
`HuggingFaceH4/MATH-500`, test split, columns `problem`/`answer`/`subject`/
`level`/`unique_id`. Unlike load_math.py, there is no answer-shape
classification or expression-shaped-answer exclusion here -- an open-answer
grader doesn't need the answer to be numeric-perturbable, so every row at
the requested level is kept (no `_classify_answer` filtering, no skipped
count). level=5 is the default (MATH-500's own hardest label), matching
load_math.py's rationale for needing real headroom for the flagship to be
wrong.

Usage:
  from benchmark.load_math_open import load_math_open_set
  items = load_math_open_set(n=90, seed=42)                # level 5 (default)
  items = load_math_open_set(n=90, seed=42, level=None)     # all levels
  items = load_math_open_set(n=90, seed=42, level=3)        # level 3 only
"""

import logging
import random
from dataclasses import dataclass

from datasets import load_dataset

log = logging.getLogger(__name__)

DATASET_ID = "HuggingFaceH4/MATH-500"


@dataclass
class MathItem:
    question_id: str
    problem: str
    gold_answer: str
    subject: str | None
    level: int | None


def load_math_open_set(n: int = 90, seed: int = 42, level: int | None = 5) -> list[MathItem]:
    ds = load_dataset(DATASET_ID, split="test")
    rng = random.Random(seed)

    rows = list(range(len(ds)))
    rng.shuffle(rows)

    items: list[MathItem] = []
    for i in rows:
        if len(items) >= n:
            break
        row = ds[i]
        if level is not None and row["level"] != level:
            continue
        items.append(
            MathItem(
                question_id=row["unique_id"],
                problem=row["problem"],
                gold_answer=str(row["answer"]),
                subject=row.get("subject"),
                level=row.get("level"),
            )
        )

    log.info(
        "Loaded %d MATH-500 OPEN-answer items (level=%s, seed=%d) -- raw open "
        "`answer` kept as gold_answer, no distractor synthesis, no MC framing",
        len(items), level, seed,
    )
    return items
