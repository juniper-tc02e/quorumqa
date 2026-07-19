import asyncio

from quorumqa.config import N_SOLVERS, SOLVER_LENSES, SOLVER_MODEL
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import CallUsage, SolverAnswer

SOLVER_SYSTEM = (
    "You are one independent solver in a panel of experts answering a hard, "
    "graduate-level multiple-choice science question. Answer on your own "
    "reasoning -- you cannot see any other solver's answer. Be honest about "
    "uncertainty in your confidence score."
)


def _solve_one(client: QwenClient, question: str, choices: list[str], lens: str) -> tuple[SolverAnswer, CallUsage]:
    choice_block = "\n".join(f"{letter}) {c}" for letter, c in zip("ABCD", choices))
    user = (
        f"Question: {question}\n\nChoices:\n{choice_block}\n\n"
        'JSON shape: {"letter": "A|B|C|D", "confidence": 0.0-1.0, "reasoning": "..."}\n'
        "Keep reasoning to at most 3 sentences -- your answer letter matters more than showing full working."
    )
    result = client.chat_json(model=SOLVER_MODEL, system=f"{SOLVER_SYSTEM}\n\n{lens}", user=user, role="solver", thinking=False)
    letter = str(result.data.get("letter", "")).strip().upper()[:1]
    answer = SolverAnswer(
        letter=letter if letter in "ABCD" else "A",
        confidence=float(result.data.get("confidence", 0.5)),
        reasoning=str(result.data.get("reasoning", "")),
        lens=lens,
    )
    return answer, result.usage


def _lenses_for(n: int) -> list[str]:
    if n <= len(SOLVER_LENSES):
        return SOLVER_LENSES[:n]
    reps = (n // len(SOLVER_LENSES)) + 1
    return (SOLVER_LENSES * reps)[:n]


async def solve_all(client: QwenClient, question: str, choices: list[str], n: int = N_SOLVERS) -> list[tuple[SolverAnswer, CallUsage]]:
    lenses = _lenses_for(n)
    tasks = [asyncio.to_thread(_solve_one, client, question, choices, lens) for lens in lenses]
    return list(await asyncio.gather(*tasks))
