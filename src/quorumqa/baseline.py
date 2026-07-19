import time
from collections import Counter

from quorumqa.config import BASELINE_MODEL, SOLVER_MODEL
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import BaselineResult, GPQAItem

BASELINE_SYSTEM = (
    "You are an expert answering a hard, graduate-level multiple-choice "
    "science question. Answer with your best single choice."
)


def _ask_once(client: QwenClient, model: str, item: GPQAItem, role: str):
    choice_block = "\n".join(f"{letter}) {c}" for letter, c in zip("ABCD", item.choices))
    user = (
        f"Question: {item.question}\n\nChoices:\n{choice_block}\n\n"
        'JSON shape: {"letter": "A|B|C|D", "reasoning": "..."}'
    )
    result = client.chat_json(model=model, system=BASELINE_SYSTEM, user=user, role=role)
    letter = str(result.data.get("letter", "")).strip().upper()[:1]
    return (letter if letter in "ABCD" else "A"), result.usage


def solve_single_agent(client: QwenClient, item: GPQAItem) -> BaselineResult:
    """The required single-agent baseline: one flagship-tier call, zero-shot."""
    start = time.monotonic()
    letter, usage = _ask_once(client, BASELINE_MODEL, item, role="baseline")
    return BaselineResult(
        item=item,
        answer_letter=letter,
        correct=(letter == item.correct_letter),
        calls=[usage],
        latency_s=time.monotonic() - start,
    )


def solve_self_consistency5(client: QwenClient, item: GPQAItem) -> BaselineResult:
    """Stretch-goal baseline: 5x samples on the SAME tier the engine's
    Solvers use, majority vote, no debate/judge. Matching the tier isolates
    the value of escalation/adjudication itself rather than a model-tier
    difference."""
    start = time.monotonic()
    letters = []
    calls = []
    for _ in range(5):
        letter, usage = _ask_once(client, SOLVER_MODEL, item, role="baseline")
        letters.append(letter)
        calls.append(usage)
    final_letter = Counter(letters).most_common(1)[0][0]
    return BaselineResult(
        item=item,
        answer_letter=final_letter,
        correct=(final_letter == item.correct_letter),
        calls=calls,
        latency_s=time.monotonic() - start,
    )
