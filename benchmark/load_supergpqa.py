"""Loads a SuperGPQA benchmark question set. HuggingFace dataset
m-a-p/SuperGPQA, split=train (the only split), public and ungated,
26,529 graduate-level questions spanning 13 disciplines and 285 highly
specialized subfields (paper: arXiv:2502.14739).

Schema verified live via the HF datasets-server API before writing this
loader (info/statistics/rows endpoints -- no full download for the
verification step):
  - `options` is a NATIVE list column, but variable length. UPDATED
    (docs/capability-roadmap.md item F7 / section 3.6): the earlier
    "typically 10, spot-check also saw 5/8/9, never below 4" note was a
    sample, not a census -- this was re-verified against a FULL download
    of all 26,529 rows before writing the max_choices generalization
    below, not guessed. Exact whole-dataset distribution of native option
    count: 4=438, 5=204, 6=280, 7=441, 8=683, 9=1,325, 10=23,158 (87.3% of
    the dataset). Minimum is 4, maximum is 10 -- so SuperGPQA's own
    ceiling happens to equal quorumqa.letters' A-J vocabulary limit
    exactly. `answer_letter` is a single uppercase letter (A-J observed)
    that indexes 0-based into that same `options` list; spot-checked
    against `answer` (the correct option's full text) and they agreed, but
    the loader re-verifies this per-row rather than trusting it blindly
    (see below).
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

IMPORTANT TRADEOFF, stated plainly -- NOW OPTIONAL (docs/capability-
roadmap.md item F7 / section 3.6), same pattern as load_mmlu_pro.py: this
loader USED TO always trim SuperGPQA's up-to-10-option questions down to 4
choices, back when QuorumQA's engine was hardcoded around exactly 4
choices (A-D) in every role's prompt (solver.py, skeptic.py, judge.py, the
gate). The engine now supports any A-J (2-10) choice set via
quorumqa.letters, so this loader still TRIMS to 4 choices BY DEFAULT (the
correct answer + 3 randomly sampled incorrect ones, reshuffled), matching
the exact pattern load_mmlu_pro.py's own default trim uses -- this is
load-bearing for every existing caller/result: `load_supergpqa_set` with
no `max_choices` argument, and the "supergpqa" DATASET_LOADERS entry in
benchmark/lever_experiments.py, all stay byte-identical to every number
this repo has already published (same rng call order: `rng.sample(pool,
3)` then the real `_shuffle_choices`, unchanged). Passing
`max_choices=None` (or calling the new `load_supergpqa_full_set` / the
"supergpqa_full" DATASET_LOADERS entry) keeps EVERY one of a question's
native options instead. The trimmed and untrimmed variants are NOT
comparable to each other: more options mechanically lowers chance accuracy
and gives solvers more room to scatter, so an accuracy delta between them
conflates option count with item difficulty, not engine capability. Only
the untrimmed variant is comparable to a published SuperGPQA score, which
is always computed on the native (up to 10-way) question.

Usage:
  from benchmark.load_supergpqa import load_supergpqa_set, load_supergpqa_full_set
  items = load_supergpqa_set(n=90, seed=42)                   # hard only, trimmed to 4 (default)
  items = load_supergpqa_set(n=90, seed=42, difficulty=None)   # no difficulty filter
  items = load_supergpqa_set(n=90, seed=42, difficulty="middle")
  full_items = load_supergpqa_full_set(n=90, seed=42)          # F7: every native option kept
"""

import logging
import random
import string

from datasets import load_dataset

from quorumqa.letters import letters_for
from quorumqa.schemas import GPQAItem

from benchmark.load_gpqa import _shuffle_choices

log = logging.getLogger(__name__)

DATASET_ID = "m-a-p/SuperGPQA"

_LETTER_INDEX = {c: i for i, c in enumerate(string.ascii_uppercase)}


def _shuffle_all_choices(rng: random.Random, correct: str, incorrect: list[str]) -> tuple[list[str], str]:
    """Like benchmark.load_gpqa._shuffle_choices, but supports 2-10 total
    choices instead of exactly 4 -- mirrors benchmark/load_mmlu_pro.py's own
    helper of the same name exactly (same mechanics: order the indices,
    take correct_index's letter), resolved against quorumqa.letters'
    shared A-J vocabulary. At exactly 4 choices this produces the identical
    letter load_gpqa._shuffle_choices would (both index into "ABCD"), but
    callers that need byte-identical behavior at max_choices=4 (the default
    trim) still call the real _shuffle_choices directly -- see
    load_supergpqa_set below."""
    choices = [correct, *incorrect]
    order = list(range(len(choices)))
    rng.shuffle(order)
    shuffled = [choices[i] for i in order]
    correct_index = order.index(0)
    return shuffled, letters_for(len(choices))[correct_index]


def load_supergpqa_set(
    n: int = 90,
    seed: int = 42,
    difficulty: str | None = "hard",
    max_choices: int | None = 4,
) -> list[GPQAItem]:
    """`max_choices` (F7, docs/capability-roadmap.md section 3.6):
      - 4 (the DEFAULT -- byte-identical to this loader's original,
        pre-F7 behavior, and to every existing caller/DATASET_LOADERS entry
        that omits this argument): trims to the correct answer + 3 randomly
        sampled incorrect ones, exactly as before.
      - None: keep ALL of the row's native options (see
        load_supergpqa_full_set below) -- capped at 10 (quorumqa.letters'
        A-J range, also SuperGPQA's own measured max, see module
        docstring); a row with more than 10 options is skipped rather than
        crashing the run, the same defensive posture as the `len(options)
        < 4` check below (never actually observed to fire against the real
        dataset, since 10 is already its ceiling, but kept for safety
        against a future dataset refresh).
      - any other int in 2-10: trims to that many choices instead (correct +
        max_choices-1 randomly sampled incorrect), generalizing the default.

    Rows that can't satisfy the requested choice count (too few incorrect
    options to trim to, or too many to keep whole) are skipped."""
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
                question_id=str(row.get("uuid", i)),
                question=row["question"],
                choices=shuffled,
                correct_letter=correct_letter,
                subject=row.get("discipline"),
            )
        )

    log.info(
        "Loaded %d SuperGPQA items (difficulty=%s, seed=%d, max_choices=%s)",
        len(items), difficulty, seed, max_choices,
    )
    return items


def load_supergpqa_full_set(n: int = 90, seed: int = 42, difficulty: str | None = "hard") -> list[GPQAItem]:
    """F7's untrimmed SuperGPQA variant: keeps every one of a question's
    native options (measured max 10, measured min 4 -- see module
    docstring) instead of trimming to 4. NOT comparable to
    load_supergpqa_set's numbers -- see the module docstring. `difficulty`
    still defaults to "hard" (load_supergpqa_set's own default) -- only the
    choice-count trim is disabled here, not the difficulty filter; pass
    difficulty=None for SuperGPQA's full, unfiltered protocol. Use this to
    measure QuorumQA against SuperGPQA's actual published protocol; use
    load_supergpqa_set to keep continuity with this project's existing
    4-way results."""
    return load_supergpqa_set(n=n, seed=seed, difficulty=difficulty, max_choices=None)
