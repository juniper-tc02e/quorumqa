"""Loads AIME (American Invitational Mathematics Examination) 2024 + 2025 as
open-answer items -- the genuinely-hard-math surface MATH-500 could not
provide.

WHY: two independent open-answer pilots established MATH-500 level 5 is
SATURATED for modern thinking-enabled Qwen models at BOTH tiers (flash 96.6%,
flagship 96.6%, 0% escalation -- see math_open_pilot_findings.md), so it
cannot test whether deliberation helps: there is no cheap-to-flagship gap to
exploit. AIME is the regime the unanimous-wrong-rate thesis actually predicts
deliberation could help -- competition problems where cheap models are
genuinely weak (flash historically ~10-40%) while the flagship is meaningfully
better (~50-70%), i.e. a LARGE cheap-to-flagship gap and real headroom.

Two datasets, both public/ungated, both with integer answers (0-999) that the
equivalence grader handles with zero false-positive risk (no interval/set/pm
edge cases):
  - Maxwell-Jia/AIME_2024 (train, 30): cols ID/Problem/Solution/Answer.
  - yentinglin/aime_2025  (train, 30): cols id/problem/answer/solution/...
Combined = 60 problems. AIME has only 30 problems/year, so n is inherently
small -- a pilot, not a validation-bar run.

Usage:
  from benchmark.load_aime import load_aime_set
  items = load_aime_set(n=60, seed=42)              # both years, shuffled
  items = load_aime_set(n=30, seed=42, years=(2024,))
"""

import logging
import random

from benchmark.load_math_open import MathItem

log = logging.getLogger(__name__)


def load_aime_set(n: int = 60, seed: int = 42, years: tuple[int, ...] = (2024, 2025)) -> list[MathItem]:
    from datasets import load_dataset

    items: list[MathItem] = []
    if 2024 in years:
        ds = load_dataset("Maxwell-Jia/AIME_2024", split="train")
        for r in ds:
            items.append(MathItem(
                question_id=f"aime2024-{r['ID']}",
                problem=str(r["Problem"]),
                gold_answer=str(r["Answer"]).strip(),
                subject="AIME-2024",
                level=None,
            ))
    if 2025 in years:
        ds = load_dataset("yentinglin/aime_2025", split="train")
        for r in ds:
            items.append(MathItem(
                question_id=f"aime2025-{r['id']}",
                problem=str(r["problem"]),
                gold_answer=str(r["answer"]).strip(),
                subject="AIME-2025",
                level=None,
            ))

    rng = random.Random(seed)
    rng.shuffle(items)
    items = items[:n]
    log.info("Loaded %d AIME items (years=%s, seed=%d) -- integer open answers", len(items), years, seed)
    return items
