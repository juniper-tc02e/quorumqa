import asyncio

from quorumqa.config import N_SOLVERS, SOLVER_LENSES, SOLVER_MODEL, SOLVER_MODELS, SOLVER_TEMPERATURES
from quorumqa.letters import choice_block, letter_hint, parse_letter
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import CallUsage, SolverAnswer

SOLVER_SYSTEM = (
    "You are one independent solver in a panel of experts answering a hard, "
    "graduate-level multiple-choice science question. Answer on your own "
    "reasoning -- you cannot see any other solver's answer. Be honest about "
    "uncertainty in your confidence score."
)


def _solve_one(client: QwenClient, question: str, choices: list[str], lens: str, model: str = SOLVER_MODEL, temperature: float = 0.4) -> tuple[SolverAnswer, CallUsage]:
    n_choices = len(choices)
    choice_block_str = choice_block(choices)
    user = (
        f"Question: {question}\n\nChoices:\n{choice_block_str}\n\n"
        f'JSON shape: {{"letter": "{letter_hint(n_choices)}", "confidence": 0.0-1.0, "reasoning": "..."}}\n'
        "Keep reasoning to at most 3 sentences -- your answer letter matters more than showing full working."
    )
    result = client.chat_json(model=model, system=f"{SOLVER_SYSTEM}\n\n{lens}", user=user, role="solver", thinking=False, temperature=temperature, retries=2)
    answer = SolverAnswer(
        letter=parse_letter(result.data.get("letter", ""), n_choices),
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
    models = (SOLVER_MODELS * ((n // len(SOLVER_MODELS)) + 1))[:n] if SOLVER_MODELS else [SOLVER_MODEL] * n
    temps = (SOLVER_TEMPERATURES * ((n // len(SOLVER_TEMPERATURES)) + 1))[:n]
    tasks = [
        asyncio.to_thread(_solve_one, client, question, choices, lens, model, temp)
        for lens, model, temp in zip(lenses, models, temps)
    ]
    return list(await asyncio.gather(*tasks))
