"""Loads OpenAI's SimpleQA -- short-form factuality questions with a single
gold answer and NO multiple-choice framing, the surface docs/capability-
roadmap.md section 3.12 identifies as the structurally cleanest fit for this
repo's retrieve -> answer -> verify -> ABSTAIN architecture: on free text the
wrong-answer space is unbounded, so two hallucinating seats essentially never
coincide, and unanimity becomes a near-sufficient correctness signal (the
exact inverse of 4-choice MC, where agreement is manufactured by chance).

DATASET: `basicv8vc/SimpleQA` (HuggingFace Hub), `test` split, 4326 rows,
columns `problem` (question), `answer` (free-text gold answer), `metadata`
(a Python-literal-encoded dict string: `topic`, `answer_type`, `urls`).
Verified LIVE 2026-07-25 against the official OpenAI release --
`https://openaipublic.blob.core.windows.net/simple-evals/simple_qa_test_set.csv`
was fetched directly and diffed: same 4326 rows, same columns, MIT license
(`basicv8vc/SimpleQA`'s HF dataset-card `license: mit`, matching OpenAI's own
`simple-evals` repo license for this release). Both sources load byte-for-
byte the same `answer` values for every row checked. This loader defaults to
the HF Hub mirror (via `datasets.load_dataset`, the same mechanism every
sibling loader in this file uses -- see benchmark/load_aime.py,
benchmark/load_math_open.py) rather than a bundled CSV, so it stays live
against Hub updates instead of a frozen local copy.

LICENSE: MIT (OpenAI, "SimpleQA: Measuring short-form factuality in large
language models", https://cdn.openai.com/papers/simpleqa.pdf).

TRADEOFF: SimpleQA ships as a single eval-only split -- there is no held-out
dev/train slice to tune the panel's prompts or the ABSTAIN threshold against
without spending real eval items, the same tradeoff this repo already
accepts for AIME and the MATH-500-open pilot (both eval-only surfaces too).
`n`/`seed` below select a reproducible SUBSET of the 4326 rows rather than
carving out a permanent held-out split -- callers choosing an unburned seed
for tuning vs. a separate one for the validation run is a discipline this
loader does not enforce (see the seed-hygiene rule in docs/capability-
roadmap.md section 1.5).

`urls` (inside `metadata`) is the list of source URLs SimpleQA's own authors
used to write each gold answer. It is DELIBERATELY DROPPED here and never
carried into `SimpleQAItem` or any downstream index: docs/capability-
roadmap.md section 4's firewall bars ever indexing a benchmark's own answer
sources, because doing so would let retrieval trivially look up the gold
answer instead of testing the engine's real retrieve/verify/abstain behavior
against an INDEPENDENT corpus (this repo's STEM/US-law Wikipedia RAG index,
built from a wholly separate snapshot -- see benchmark/build_rag_index_
preembedded.py). `topic`/`answer_type` (both small controlled vocabularies:
10 topics, 5 answer types) are kept, since they are benign slicing metadata,
not answer sources.

KNOWN GOTCHA (per the roadmap, "some distributions of this file have double-
encoded UTF-8" -- e.g. "JÃ³hanna SigurÃ°ardÃ³ttir" where "Jóhanna
Sigurðardóttir" belongs, the classic UTF-8-bytes-decoded-as-cp1252-then-
re-encoded-as-UTF-8 mojibake pattern): checked LIVE on both sources named
above, 2026-07-25 -- 0/4326 rows in `basicv8vc/SimpleQA`'s `test` split, and
0/4326 rows in the raw official CSV, matched the mojibake pattern (verified
directly against row 8's answer, "Jóhanna Sigurðardóttir" -- codepoints
U+004A,U+00F3,... confirm it is ALREADY correctly decoded, not "JÃ³..."). So
this specific gotcha did not reproduce against either source as loaded
today. Per the roadmap's own phrasing ("some distributions"), a clean check
today is not a guarantee against every mirror or a future revision, so
`_fix_mojibake` below still runs defensively on every `question`/
`gold_answer` string on every load; it is a no-op unless the pattern is
actually present, and `load_simpleqa_set` logs how many rows it touched (0
on this load) so a future regression is visible in the log rather than
silently miscounted at grading time.

Usage:
  from benchmark.load_simpleqa import load_simpleqa_set
  items = load_simpleqa_set(n=300, seed=42)   # FA-0's pre-registered size
  items = load_simpleqa_set(n=4326, seed=42)  # the full eval set
"""

from __future__ import annotations

import ast
import logging
import random
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)

DATASET_ID = "basicv8vc/SimpleQA"

# Classic UTF-8-decoded-as-cp1252-then-re-encoded-as-UTF-8 mojibake:
# "Ã©" for "é" (0xC3 0xA9 misread byte-by-byte as two Latin-1-range chars),
# "â€™" for a curly apostrophe (the 3-byte UTF-8 sequence for U+2019 misread
# under cp1252, which -- unlike strict Latin-1 -- assigns printable glyphs to
# the 0x80-0x9F range, so cp1252 is the correct repair target rather than
# plain 'latin1'). Deliberately narrow (only the highest-confidence mojibake
# lead-in bytes) so a legitimate string that happens to contain a literal
# "Ã" is never mistaken for garbled text.
_MOJIBAKE_RE = re.compile(r"Ã[\x80-\xBF]|â€[\x80-\x9F]|Â[\xA0-\xBF]")


def _fix_mojibake(s: str) -> tuple[str, bool]:
    """Detects and repairs double-encoded UTF-8. Returns (text, was_fixed).
    Fails closed on every axis: no suspicious pattern -> returned unchanged;
    pattern present but the cp1252->utf-8 round-trip raises -> returned
    unchanged; round-trip succeeds but the result STILL matches the
    mojibake pattern (i.e. the "fix" didn't actually fix anything, so it was
    a false-positive trigger) -> returned unchanged. Only a clean repair
    that removes the pattern is accepted."""
    if not s or not _MOJIBAKE_RE.search(s):
        return s, False
    try:
        fixed = s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s, False
    if _MOJIBAKE_RE.search(fixed):
        return s, False
    return fixed, True


@dataclass
class SimpleQAItem:
    question_id: str
    question: str
    gold_answer: str
    topic: str | None
    answer_type: str | None


def load_simpleqa_set(n: int = 300, seed: int = 42) -> list[SimpleQAItem]:
    """Loads up to `n` items from a seeded shuffle of the full 4326-row test
    split. `question_id` is derived from the ROW'S ORIGINAL POSITION in the
    (unshuffled) dataset ("simpleqa-{i}"), not its position after shuffling
    -- so the same item has the same id across different `n`/`seed` calls,
    the same stability property benchmark/load_aime.py's dataset-native ids
    give for free (SimpleQA has no native id column to reuse instead)."""
    from datasets import load_dataset

    ds = load_dataset(DATASET_ID, split="test")

    items: list[SimpleQAItem] = []
    mojibake_fixed = 0
    metadata_parse_failures = 0
    for i, row in enumerate(ds):
        question, q_fixed = _fix_mojibake(str(row["problem"]))
        gold_answer, a_fixed = _fix_mojibake(str(row["answer"]))
        if q_fixed or a_fixed:
            mojibake_fixed += 1

        topic = answer_type = None
        try:
            # NOT json.loads -- this column is a Python dict repr (single-
            # quoted keys/strings), not valid JSON. ast.literal_eval is the
            # standard-library safe parser for exactly that shape (no code
            # execution, unlike eval()).
            metadata = ast.literal_eval(row["metadata"])
            if isinstance(metadata, dict):
                topic = metadata.get("topic")
                answer_type = metadata.get("answer_type")
                # metadata["urls"] exists here but is intentionally never
                # read -- see the module docstring's firewall note.
        except (ValueError, SyntaxError):
            metadata_parse_failures += 1

        items.append(
            SimpleQAItem(
                question_id=f"simpleqa-{i}",
                question=question,
                gold_answer=gold_answer,
                topic=topic,
                answer_type=answer_type,
            )
        )

    if mojibake_fixed:
        log.warning("SimpleQA loader: repaired double-encoded UTF-8 in %d/%d rows", mojibake_fixed, len(items))
    else:
        log.info("SimpleQA loader: 0/%d rows matched the known double-encoded-UTF-8 pattern (no fix needed on this load)", len(items))
    if metadata_parse_failures:
        log.warning("SimpleQA loader: %d/%d rows had an unparseable metadata column (topic/answer_type left None)", metadata_parse_failures, len(items))

    rng = random.Random(seed)
    rng.shuffle(items)
    items = items[:n]
    log.info("Loaded %d SimpleQA items (seed=%d) -- free-text gold answers, no MC framing, urls column never read", len(items), seed)
    return items
