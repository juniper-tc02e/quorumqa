"""Loads a MedQA benchmark question set -- the first medicine/biology
domain this engine has been pointed at (Mixture of Orchestrations domain
coverage). HuggingFace dataset GBaker/MedQA-USMLE-4-options, split=test,
public and ungated (checked live via the HF dataset-info API: gated=False,
private=False, disabled=False -- no HF_TOKEN needed). 1,273 USMLE-style
4-option clinical-vignette questions (train has another 10,178, NOT used
here -- test only, per the loader contract).

Schema verified live via the HF datasets-server API before writing this
loader (info/rows/statistics endpoints -- no full download for the
verification step):
  - `options` is a NATIVE dict column keyed "A"/"B"/"C"/"D" (not a list,
    and not stringified like LEXam's) -- exactly 4 options on every row,
    so no trimming is needed here (unlike load_supergpqa.py/
    load_mmlu_pro.py, which trim down from more than 4).
  - `answer_idx` is a single letter ("A"-"D") that indexes into `options`;
    spot-checked against `answer` (the correct option's full text) on a
    3-row sample and they agreed. The loader re-verifies this per-row
    (falls back to locating the answer by text match) rather than
    trusting the letter blindly, matching the discipline load_supergpqa.py
    uses for its own answer_letter field.
  - `meta_info` is a per-row categorical field with exactly two values in
    the test split: "step1" (679 rows) and "step2&3" (594 rows) -- this is
    the USMLE exam step the question is drawn from, NOT a clinical
    specialty/subject like cardiology or pharmacology (this dataset has no
    such per-row field). Used as the `subject` value below since it's the
    only per-row category that exists; documented here so nobody mistakes
    "step1"/"step2&3" for a medical subdomain when reading results.
  - No native question-id column exists on this dataset -- `question_id`
    below is the row's index into the (pre-shuffle) test split.

Usage:
  from benchmark.load_medqa import load_medqa_set
  items = load_medqa_set(n=90, seed=42)
"""

import logging
import random

from datasets import load_dataset

from quorumqa.schemas import GPQAItem

from benchmark.load_gpqa import _shuffle_choices

log = logging.getLogger(__name__)

DATASET_ID = "GBaker/MedQA-USMLE-4-options"

_LETTERS = ("A", "B", "C", "D")


def load_medqa_set(n: int = 90, seed: int = 42) -> list[GPQAItem]:
    ds = load_dataset(DATASET_ID, split="test")
    rng = random.Random(seed)

    rows = list(range(len(ds)))
    rng.shuffle(rows)

    items: list[GPQAItem] = []
    for i in rows:
        if len(items) >= n:
            break
        row = ds[i]

        options = row.get("options")
        if not isinstance(options, dict) or any(letter not in options for letter in _LETTERS):
            log.warning("MedQA row %s: options missing A-D keys, skipping", i)
            continue

        letter = row.get("answer_idx")
        answer_text = options.get(letter) if letter else None
        if answer_text is None or answer_text != row.get("answer"):
            # answer_idx either wasn't one of A-D, or its text disagreed
            # with the answer field -- fall back to locating the answer by
            # text match rather than silently trusting a possibly-
            # misaligned letter.
            matches = [ltr for ltr in _LETTERS if options.get(ltr) == row.get("answer")]
            if len(matches) != 1:
                log.warning("MedQA row %s: could not uniquely locate answer text in options, skipping", i)
                continue
            letter = matches[0]

        correct = options[letter]
        incorrect = [options[ltr] for ltr in _LETTERS if ltr != letter]

        shuffled, correct_letter = _shuffle_choices(rng, correct, incorrect)
        items.append(
            GPQAItem(
                question_id=str(i),
                question=row["question"],
                choices=shuffled,
                correct_letter=correct_letter,
                subject=row.get("meta_info"),
            )
        )

    log.info("Loaded %d MedQA items (seed=%d, native 4-option, no trimming)", len(items), seed)
    return items
