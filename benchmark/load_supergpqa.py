"""Loads a SuperGPQA benchmark question set. HuggingFace dataset
m-a-p/SuperGPQA, split=train (the only split), public and ungated,
26,529 graduate-level questions spanning 13 disciplines and 285 highly
specialized subfields (paper: arXiv:2502.14739).

Schema verified live via the HF datasets-server API before writing this
loader (info/statistics/rows endpoints -- no full download for the
verification step):
  - `options` is a NATIVE list column, but variable length -- typically 10
    entries; a spot-check sample also turned up 5, 8, and 9 (never below 4
    in anything sampled). `answer_letter` is a single uppercase letter
    (A-J observed) that indexes 0-based into that same `options` list;
    spot-checked against `answer` (the correct option's full text) and
    they agreed, but the loader re-verifies this per-row rather than
    trusting it blindly (see below).
  - `difficulty` is a string label with exactly three values, whole-dataset
    counts (26,529 total): hard=7,050, middle=11,748, easy=7,731.
  - `discipline` has 13 values, dominated by Science (9,838) and
    Engineering (7,892); the smallest is Sociology (143).
  - No gating: HF API reports gated=False, private=False; no HF_TOKEN
    needed (unlike load_gpqa.py's GPQA-Diamond).

THE PROJECT FINDING THIS LOADER IS BUILT AROUND (see
benchmark/results/mmlu_pro_findings.md): QuorumQA's escalation only earns
its keep when the flagship model itself has real headroom to be wrong. On
both prior non-GPQA pilots (LEXam, MMLU-Pro) the flagship baseline landed
86-94% and the engine underperformed it, because a near-ceiling baseline
leaves too few real mistakes for escalation to recover, and too many of
the mistakes that do happen are confident-unanimous-wrong -- the one
failure mode this architecture cannot catch by construction. A flat random
SuperGPQA draw would pull mostly "easy" and "middle" questions (7,731 +
11,748 = 18,479 of 26,529, ~70% of the dataset) and risk repeating that
same pattern. This loader instead filters to difficulty="hard" by default
-- the ~26.6% of the dataset SuperGPQA's own authors label hardest --
specifically to give the flagship model real room to be wrong before the
panel ever gets involved. Pass difficulty=None to disable the filter, or
"middle"/"easy" for the other two labels.

IMPORTANT TRADEOFF, same pattern and same reasoning as load_mmlu_pro.py:
SuperGPQA questions carry up to 10 options (native), but QuorumQA's engine
is hardcoded to exactly 4 choices (A-D) in every role's prompt (solver.py,
skeptic.py, judge.py, the gate). Extending every role to a variable A-J
choice set is a real engine change, not attempted here. This loader trims
each question down to 4 choices (the correct answer + 3 randomly sampled
incorrect ones, reshuffled) instead. This means results from this loader
are NOT comparable to published SuperGPQA scores, which are always
computed on the untrimmed (up to 10-way) question -- worth knowing before
comparing these numbers to any leaderboard.

Usage:
  from benchmark.load_supergpqa import load_supergpqa_set
  items = load_supergpqa_set(n=90, seed=42)                  # hard only (default)
  items = load_supergpqa_set(n=90, seed=42, difficulty=None)  # no filter
  items = load_supergpqa_set(n=90, seed=42, difficulty="middle")
"""

import logging
import random
import string

from datasets import load_dataset

from quorumqa.schemas import GPQAItem

from benchmark.load_gpqa import _shuffle_choices

log = logging.getLogger(__name__)

DATASET_ID = "m-a-p/SuperGPQA"

_LETTER_INDEX = {c: i for i, c in enumerate(string.ascii_uppercase)}


def load_supergpqa_set(n: int = 90, seed: int = 42, difficulty: str | None = "hard") -> list[GPQAItem]:
    ds = load_dataset(DATASET_ID, split="train")
    rng = random.Random(seed)

    rows = list(range(len(ds)))
    rng.shuffle(rows)

    items: list[GPQAItem] = []
    for i in rows:
        if len(items) >= n:
            break
        row = ds[i]
        if difficulty is not None and row.get("difficulty") != difficulty:
            continue

        options = row["options"]
        if not isinstance(options, list) or len(options) < 4:
            continue

        letter = row.get("answer_letter")
        answer_index = _LETTER_INDEX.get(letter, -1) if letter else -1
        if not (0 <= answer_index < len(options)) or options[answer_index] != row.get("answer"):
            # answer_letter either didn't index cleanly into this row's
            # options list, or disagreed with the answer text -- fall back
            # to locating the answer by text match rather than silently
            # trusting a possibly-misaligned letter.
            try:
                answer_index = options.index(row["answer"])
            except ValueError:
                log.warning("SuperGPQA row %s: could not locate answer text in options, skipping", row.get("uuid", i))
                continue

        correct = options[answer_index]
        incorrect_pool = [o for j, o in enumerate(options) if j != answer_index]
        incorrect = rng.sample(incorrect_pool, 3)

        shuffled, correct_letter = _shuffle_choices(rng, correct, incorrect)
        items.append(
            GPQAItem(
                question_id=str(row.get("uuid", i)),
                question=row["question"],
                choices=shuffled,
                correct_letter=correct_letter,
                subject=row.get("discipline"),
            )
        )

    log.info(
        "Loaded %d SuperGPQA items (difficulty=%s, seed=%d, trimmed to 4 choices)",
        len(items), difficulty, seed,
    )
    return items
