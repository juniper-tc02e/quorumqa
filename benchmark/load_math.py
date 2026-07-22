"""Loads a MATH benchmark question set -- the second FREE-FORM-ANSWER math
benchmark this engine has been pointed at. See load_gsm8k.py for the shared
schema-mismatch problem (MATH's answers are open-answer, not the A-D
choices QuorumQA's engine is hardcoded around) and the shared distractor-
synthesis helper (`_numeric_distractors`) this loader reuses unchanged.

DATASET RESOLVED, verified live via the HF datasets-server API and then
confirmed with a full download (500-row test split) before writing this
loader: `HuggingFaceH4/MATH-500` -- the 500-problem curated *test* subset
of Hendrycks et al.'s MATH competition dataset. This is a different,
smaller, eval-only HF entry from the full ~12,500-problem
`hendrycks/competition_math` train+test set; MATH-500 is the subset most
2024+ model cards actually report "MATH" accuracy against, which is why it
was picked here over the full set. Ungated, public, single "test" split,
500 rows, columns: `problem` (str), `solution` (str, full worked
derivation -- unused here), `answer` (str, final answer only, open
format), `subject` (str, one of 7 MATH topic areas), `level` (int, 1-5),
`unique_id` (str, e.g. "test/precalculus/807.json", used as question_id).

DIFFICULTY FILTER, same rationale as load_supergpqa.py -- see
benchmark/results/mmlu_pro_findings.md: the flagship needs real headroom to
be wrong, or escalation has nothing to recover. Live level counts across
all 500 rows (verified by full download, not just the datasets-server
histogram, which merges levels 4 and 5 into one bucket and would have been
misleading here): level 1=43, 2=90, 3=105, 4=128, 5=134. Defaults to
level=5, the hardest label MATH-500's own authors assign, for the same
reason SuperGPQA defaults to difficulty="hard". Pass level=None to disable
the filter, or 1/2/3/4 for an easier band.

THE SECOND, MATH-SPECIFIC PROBLEM -- ANSWER-FORMAT HETEROGENEITY, disclosed
because it directly limits what this loader can responsibly claim: unlike
GSM8K (100% plain integers), MATH answers come in wildly different shapes.
A live classification of all 500 answers found only 366/500 (73%, stable
73-79% within every individual level) fall into a shape a generic numeric
perturbation can safely handle -- plain integers, LaTeX fractions
(`\\frac{a}{b}` or `\\dfrac{a}{b}`), and plain decimals. The other 134/500
(27%) are answers like algebraic expressions ("p - q"), complex numbers
("6 - 5i"), coordinate tuples ("(6,31,-1)"), intervals ("(3,4]"),
multi-valued answers ("1,-2", "1 \\pm \\sqrt{19}"), degree/angle values
("145^\\circ"), dollar-formatted amounts ("\\$32,\\!348"), pi-multiples
("12\\pi"), bare square roots ("2\\sqrt{5}"), equations ("y = 2x + 3"),
matrices, sets, and polynomials. At level=5 specifically (the default
filter): 98/134 (73%) eligible -- int=74, frac=23, decimal=1 -- and 36/134
(27%) excluded expression-shaped answers.

DECISION -- this is the "(B), flag and skip" case called out in the project
brief, applied per-item rather than to the whole dataset: for those
expression-shaped answers, this loader does NOT attempt distractor
synthesis. Generating a "wrong" algebraic expression, complex number, or
coordinate tuple that is (a) plausible, (b) actually mathematically wrong
and not just a different-notation form of the SAME correct answer (e.g.
"2\\pi + 18" vs "18+2\\pi" -- textually different, mathematically
identical), and (c) not accidentally a valid alternate correct answer to a
multi-valued question, needs a type-aware generator per answer-shape --
categorically less reliable than the numeric case, and wrong in a way that
would silently corrupt results rather than fail loudly. Those rows are
filtered out before sampling, not distractor-synthesized. Practical effect:
this loader's level=5 sample is a further-filtered "numeric-answer subset
of MATH-500's hardest tier" -- a live check found the exclusion skews away
from Intermediate Algebra/Precalculus (heavier on expression-shaped
answers: 10 and 8 of level=5's 36 exclusions respectively) and toward
Prealgebra/Number Theory/Counting & Probability (heavier on plain
int/fraction answers) relative to the full level-5 population. Eyeball the
subject spread in a real run before trusting a subject-level breakdown.

DISTRACTOR-SYNTHESIS METHOD for the 73% that ARE numeric-shaped (seeded off
the loader's own `random.Random(seed)`, same reproducibility contract as
every other loader here):
  - int / decimal answers: reuses load_gsm8k.py's `_numeric_distractors`
    unchanged (order-of-magnitude slip, sign flip, near-miss delta).
    Decimals are re-rendered at the same number of decimal places as the
    source string.
  - LaTeX fraction answers: three fraction-specific common errors instead
    -- (1) reciprocal swap (flipped numerator/denominator -- a very common
    fraction-inversion mistake), (2) sign flip, (3) a numerator-or-
    denominator near-miss (+/-1 or +/-2). Re-rendered with the same LaTeX
    command (\\frac vs \\dfrac) as the source; any negative sign is
    normalized onto the numerator (mathematically identical, consistent
    rendering) so a distractor never surfaces as e.g. "\\frac{3}{-56}".
As with load_gsm8k.py: the resulting accuracy numbers are NOT comparable to
any published MATH/MATH-500 score (open-answer there, 4-choice-synthetic
here) -- and here that non-comparability is compounded by the answer-shape
filter above, so this is a narrower slice of "MATH-500, hardest tier" than
"level 5" alone would suggest.

Usage:
  from benchmark.load_math import load_math_set
  items = load_math_set(n=90, seed=42)                  # level 5, numeric-eligible only (default)
  items = load_math_set(n=90, seed=42, level=None)      # all levels, numeric-eligible only
  items = load_math_set(n=90, seed=42, level=3)          # level 3 only, numeric-eligible only
"""

import logging
import random
import re

from datasets import load_dataset

from quorumqa.schemas import GPQAItem

from benchmark.load_gpqa import _shuffle_choices
from benchmark.load_gsm8k import _numeric_distractors

log = logging.getLogger(__name__)

DATASET_ID = "HuggingFaceH4/MATH-500"

_INT_RE = re.compile(r"^(-?\d+)$")
_DECIMAL_RE = re.compile(r"^(-?\d+\.\d+)$")
_FRAC_RE = re.compile(r"^(-?)\\(d?frac)\{(-?\d+)\}\{(-?\d+)\}$")


def _classify_answer(answer: str):
    """Returns a tagged tuple describing the eligible numeric shape of
    `answer` -- ("int", value) / ("decimal", value, ndigits) /
    ("frac", command, num, den) -- or None if `answer` is one of the
    expression-shaped forms this loader deliberately does not attempt to
    distractor-synthesize (see module docstring)."""
    a = answer.strip().replace(" ", "")
    m = _INT_RE.fullmatch(a)
    if m:
        return ("int", int(m.group(1)))
    m = _DECIMAL_RE.fullmatch(a)
    if m:
        ndigits = len(m.group(1).split(".")[1])
        return ("decimal", float(m.group(1)), ndigits)
    m = _FRAC_RE.fullmatch(a)
    if m:
        lead_sign, command, num_s, den_s = m.groups()
        num = int(num_s) * (-1 if lead_sign == "-" else 1)
        den = int(den_s)
        return ("frac", command, num, den)
    return None


def _format_frac(command: str, num: int, den: int) -> str:
    if den < 0:
        num, den = -num, -den
    sign = "-" if num < 0 else ""
    return f"{sign}\\{command}{{{abs(num)}}}{{{den}}}"


def _frac_distractors(rng: random.Random, num: int, den: int) -> list[tuple[int, int]]:
    """Three fraction-specific common errors: reciprocal swap, sign flip,
    numerator/denominator near-miss -- each guaranteed a valid (nonzero
    denominator) fraction distinct from the original and from each other."""
    candidates: list[tuple[int, int]] = []

    def add(n, d):
        if d != 0 and (n, d) != (num, den) and (n, d) not in candidates:
            candidates.append((n, d))

    add(den, num)   # reciprocal swap
    add(-num, den)  # sign flip

    attempts = 0
    while len(candidates) < 3 and attempts < 20:
        attempts += 1
        delta = rng.choice([-2, -1, 1, 2])
        if rng.random() < 0.5:
            add(num + delta, den)
        else:
            add(num, den + delta)

    offset = 1
    while len(candidates) < 3:
        add(num + offset, den)
        add(num, den + offset)
        offset += 1

    return candidates[:3]


def load_math_set(n: int = 90, seed: int = 42, level: int | None = 5) -> list[GPQAItem]:
    ds = load_dataset(DATASET_ID, split="test")
    rng = random.Random(seed)

    rows = list(range(len(ds)))
    rng.shuffle(rows)

    items: list[GPQAItem] = []
    skipped_expression = 0
    for i in rows:
        if len(items) >= n:
            break
        row = ds[i]
        if level is not None and row["level"] != level:
            continue

        tag = _classify_answer(row["answer"])
        if tag is None:
            skipped_expression += 1
            continue

        kind = tag[0]
        if kind == "frac":
            _, command, num, den = tag
            correct = _format_frac(command, num, den)
            incorrect = [_format_frac(command, n, d) for n, d in _frac_distractors(rng, num, den)]
        elif kind == "decimal":
            _, gold, ndigits = tag
            correct = f"{gold:.{ndigits}f}"
            incorrect = [f"{v:.{ndigits}f}" for v in _numeric_distractors(rng, gold)]
        else:  # int
            _, gold = tag
            correct = str(gold)
            incorrect = [str(v) for v in _numeric_distractors(rng, gold)]

        shuffled, correct_letter = _shuffle_choices(rng, correct, incorrect)
        items.append(
            GPQAItem(
                question_id=row["unique_id"],
                question=row["problem"],
                choices=shuffled,
                correct_letter=correct_letter,
                subject=row.get("subject"),
            )
        )

    log.info(
        "Loaded %d MATH-500 items (level=%s, seed=%d, numeric-eligible subset only -- "
        "%d rows skipped for expression-shaped answers; NOT comparable to "
        "published MATH/MATH-500 open-answer accuracy)",
        len(items), level, seed, skipped_expression,
    )
    return items
