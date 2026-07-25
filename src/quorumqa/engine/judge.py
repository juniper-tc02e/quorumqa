from typing import Optional

from quorumqa.config import JUDGE_MODEL
from quorumqa.letters import choice_block, letter_hint, parse_letter
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import CallUsage, JudgeVerdict, SkepticRebuttal, SolverAnswer, VerifierFinding

JUDGE_SYSTEM = (
    "You are the Judge adjudicating a contested exam question. Weigh "
    "ARGUMENTS, not headcounts: an unrefuted minority position beats a "
    "conforming majority. You are given independent solver rationales, a "
    "skeptic's rebuttal of the plurality answer, and tool-grounded verifier "
    "findings (treat these as ground truth where they directly address a "
    "claim). Rule on the single best answer letter, state the specific "
    "argument that was decisive, and report any unresolved dissent -- do "
    "not manufacture false consensus."
)


def adjudicate(
    client: QwenClient,
    question: str,
    choices: list[str],
    solver_answers: list[SolverAnswer],
    skeptic_rebuttal: SkepticRebuttal,
    verifier_findings: list[VerifierFinding],
) -> tuple[JudgeVerdict, CallUsage]:
    n_choices = len(choices)
    choice_block_str = choice_block(choices)
    transcript = "\n\n".join(
        f"[{a.lens}] answered {a.letter} (confidence {a.confidence:.2f}): {a.reasoning}" for a in solver_answers
    )
    findings_block = "\n".join(
        f"- claim: {f.claim} | tool: {f.tool_used}({f.tool_query}) -> {f.tool_result} | supports claim: {f.supports_claim}"
        for f in verifier_findings
    ) or "(no checkable claims were raised)"

    user = (
        f"Question: {question}\n\nChoices:\n{choice_block_str}\n\n"
        f"Solver transcript:\n{transcript}\n\n"
        f"Skeptic's rebuttal (targeting {skeptic_rebuttal.target_letter}): "
        f"disputed step: {skeptic_rebuttal.disputed_step}\nargument: {skeptic_rebuttal.argument}\n\n"
        f"Verifier findings:\n{findings_block}\n\n"
        f'JSON shape: {{"final_letter": "{letter_hint(n_choices)}", "decisive_reasoning": "...", '
        '"dissent": "unresolved objection, or null if none", '
        '"overturned_plurality": true/false, "confidence": "high|medium|low"}'
    )
    result = client.chat_json(model=JUDGE_MODEL, system=JUDGE_SYSTEM, user=user, role="judge")
    dissent: Optional[str] = result.data.get("dissent") or None
    verdict = JudgeVerdict(
        final_letter=parse_letter(result.data.get("final_letter", ""), n_choices, fallback=solver_answers[0].letter),
        decisive_reasoning=str(result.data.get("decisive_reasoning", "")),
        dissent=dissent,
        overturned_plurality=bool(result.data.get("overturned_plurality", False)),
        confidence=str(result.data.get("confidence", "medium")),
    )
    return verdict, result.usage
