"""Loads a LEXam benchmark question set -- the first non-GPQA benchmark this
engine has been pointed at. Swiss/international law exam MCQs, HuggingFace
dataset LEXam-Benchmark/LEXam, config mcq_4_choices (4,696 questions across
four configs total; this loader only uses the 4-choice one, to keep the
existing A-D engine machinery unchanged).

Two things verified live before writing this loader, not assumed:
  - `choices` is a Python-repr'd list STORED AS A STRING (e.g.
    "['i und iii', 'iii', ...]"), not a native list column -- needs
    ast.literal_eval, or every question silently becomes unparseable.
  - The dataset is bilingual: 1,036 German-language questions vs. 619
    English, out of 1,655 in mcq_4_choices (confirmed via the HF
    datasets-server statistics endpoint). Defaults to English-only to avoid
    conflating "hard law" with "the model's German-language ability" --
    pass language=None to include everything.

`gold` is a 0-indexed int into the (already-fixed-order) `choices` list.
Re-shuffled through the same _shuffle_choices helper GPQA-Diamond uses,
with our own seeded RNG, rather than trusting the source ordering wasn't
itself biased toward any position.

Usage:
  from benchmark.load_lexam import load_lexam_set
  items = load_lexam_set(n=90, seed=42)
"""

import ast
import logging
import random

from datasets import load_dataset

from quorumqa.schemas import GPQAItem

from benchmark.load_gpqa import _shuffle_choices

log = logging.getLogger(__name__)

DATASET_ID = "LEXam-Benchmark/LEXam"


def load_lexam_set(n: int = 90, seed: int = 42, config: str = "mcq_4_choices", language: str | None = "en") -> list[GPQAItem]:
    ds = load_dataset(DATASET_ID, config, split="test")
    rng = random.Random(seed)

    rows = list(range(len(ds)))
    rng.shuffle(rows)

    items: list[GPQAItem] = []
    for i in rows:
        if len(items) >= n:
            break
        row = ds[i]
        if language is not None and row.get("language") != language:
            continue

        try:
            choices_list = ast.literal_eval(row["choices"])
        except (ValueError, SyntaxError):
            log.warning("LEXam row %s: unparseable choices field, skipping", row.get("id", i))
            continue
        gold = row["gold"]
        if not isinstance(choices_list, list) or not (0 <= gold < len(choices_list)):
            log.warning("LEXam row %s: gold index out of range for choices, skipping", row.get("id", i))
            continue

        correct = choices_list[gold]
        incorrect = [c for j, c in enumerate(choices_list) if j != gold]
        if len(incorrect) != 3:
            # mcq_4_choices should always be exactly 4 options; skip anything
            # malformed rather than silently running a 3- or 5-way question
            # through a 4-option (A-D) engine.
            continue

        shuffled, correct_letter = _shuffle_choices(rng, correct, incorrect)
        items.append(
            GPQAItem(
                question_id=str(row.get("id", i)),
                question=row["question"],
                choices=shuffled,
                correct_letter=correct_letter,
                subject=row.get("area"),
            )
        )

    log.info("Loaded %d LEXam items (config=%s, language=%s, seed=%d)", len(items), config, language, seed)
    return items
