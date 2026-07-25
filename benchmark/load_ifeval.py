"""Loads IFEval (`google/IFEval` on HuggingFace) -- instruction-following
compliance, decidable by a deterministic Python predicate rather than a
model judge.

WHY THIS EXISTS: docs/capability-roadmap.md section 3.11 (F6/IF-1) --
IFEval was demoted from the funded portfolio not because the underlying
idea is weak (the roadmap calls it "the strongest structural case in the
portfolio") but because FATAL 2 held: this repo had no grader and no
loader for it at all. This is the loader half of the fix; the grader half
is benchmark/ifeval_verify.py.

SCHEMA, verified live against the cached HF dataset (not guessed): loading
`google/IFEval` with `datasets.load_dataset` exposes a single `train` split
of 541 rows with exactly four columns:
  - `key` (int): a stable per-prompt id, e.g. 1000.
  - `prompt` (str): the natural-language instruction-following prompt.
  - `instruction_id_list` (list[str]): e.g.
    ["punctuation:no_comma", "length_constraints:number_words"] -- the
    instruction families this prompt is graded against. 25 distinct
    families appear across the 541 rows (enumerated once during the build
    of this module; see benchmark/results/ifeval_scorer_validation.md for
    the full per-family count table).
  - `kwargs` (list[dict]): one dict per entry in instruction_id_list,
    carrying that instruction's concrete parameters (e.g.
    {"num_words": 300, "relation": "at least", ...}). Every dict in the
    list shares the SAME superset of ~23 keys (HuggingFace's
    Sequence(dict) column type requires a uniform schema across rows), so
    most keys are None for any given instruction -- only the keys that
    instruction's checker actually needs are populated. Consumers must
    tolerate the padding (benchmark/ifeval_verify.py does, via dict.get()
    rather than the official package's stricter **kwargs unpacking, which
    breaks on the padded dict -- verified live, see the validation doc).

TRADEOFF, matching this repo's other loaders: no distractor synthesis, no
answer-shape filtering -- IFEval has no gold "answer" to synthesize against
in the first place; grading is a live property of the (response,
instruction_id_list, kwargs) triple checked by ifeval_verify.verify_all,
not a stored field on the item. This loader's job is only to sample and
shuffle prompts deterministically, matching the seeded-shuffle convention
in load_math_open.py / load_aime.py.

Usage:
  from benchmark.load_ifeval import load_ifeval_set
  items = load_ifeval_set(n=60, seed=42)              # IF-2 gap-probe size
  items = load_ifeval_set(n=541, seed=42)              # full set
"""

import logging
import random
from dataclasses import dataclass, field

from datasets import load_dataset

log = logging.getLogger(__name__)

DATASET_ID = "google/IFEval"


@dataclass
class IFEvalItem:
    key: int
    prompt: str
    instruction_id_list: list[str]
    kwargs: list[dict] = field(default_factory=list)


def load_ifeval_set(n: int = 541, seed: int = 42) -> list[IFEvalItem]:
    ds = load_dataset(DATASET_ID, split="train")
    rng = random.Random(seed)

    rows = list(range(len(ds)))
    rng.shuffle(rows)

    items: list[IFEvalItem] = []
    for i in rows:
        if len(items) >= n:
            break
        row = ds[i]
        items.append(
            IFEvalItem(
                key=row["key"],
                prompt=row["prompt"],
                instruction_id_list=list(row["instruction_id_list"]),
                kwargs=list(row["kwargs"]),
            )
        )

    log.info(
        "Loaded %d IFEval items (seed=%d) from %s -- instruction compliance "
        "graded live by benchmark/ifeval_verify.py, no gold answer stored on the item",
        len(items), seed, DATASET_ID,
    )
    return items
