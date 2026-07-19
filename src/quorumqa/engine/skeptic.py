from quorumqa.config import SKEPTIC_MODEL
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import CallUsage, SkepticRebuttal, SolverAnswer

SKEPTIC_SYSTEM = (
    "You are the Skeptic. The solver panel below did NOT reach unanimous "
    "agreement on this question. Your job is narrowly scoped: attack the "
    "PLURALITY answer's weakest inferential step. Name the specific "
    "reasoning step you dispute and why -- a generic 'I'm not sure' "
    "critique is not acceptable. If you genuinely cannot find a flaw, say "
    "so explicitly rather than inventing one."
)


def rebut(
    client: QwenClient,
    question: str,
    choices: list[str],
    plurality_letter: str,
    solver_answers: list[SolverAnswer],
) -> tuple[SkepticRebuttal, CallUsage]:
    choice_block = "\n".join(f"{letter}) {c}" for letter, c in zip("ABCD", choices))
    transcript = "\n\n".join(
        f"[{a.lens}] answered {a.letter} (confidence {a.confidence:.2f}): {a.reasoning}" for a in solver_answers
    )
    user = (
        f"Question: {question}\n\nChoices:\n{choice_block}\n\n"
        f"Plurality answer: {plurality_letter}\n\nSolver transcript:\n{transcript}\n\n"
        'JSON shape: {"target_letter": "the letter you are disputing", '
        '"disputed_step": "the specific inferential step you dispute", '
        '"argument": "your rebuttal argument"}'
    )
    result = client.chat_json(model=SKEPTIC_MODEL, system=SKEPTIC_SYSTEM, user=user, role="skeptic", thinking=False, retries=2)
    rebuttal = SkepticRebuttal(
        target_letter=str(result.data.get("target_letter", plurality_letter)).strip().upper()[:1],
        disputed_step=str(result.data.get("disputed_step", "")),
        argument=str(result.data.get("argument", "")),
    )
    return rebuttal, result.usage
