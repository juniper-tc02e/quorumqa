from typing import Optional

from quorumqa.config import JUDGE_MODEL
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
    choice_block = "\n".join(f"{letter}) {c}" for letter, c in zip("ABCD", choices))
    transcript = "\n\n".join(
        f"[{a.lens}] answered {a.letter} (confidence {a.confidence:.2f}): {a.reasoning}" for a in solver_answers
    )
    findings_block = "\n".join(
        f"- claim: {f.claim} | tool: {f.tool_used}({f.tool_query}) -> {f.tool_result} | supports claim: {f.supports_claim}"
        for f in verifier_findings
    ) or "(no checkable claims were raised)"

    user = (
        f"Question: {question}\n\nChoices:\n{choice_block}\n\n"
        f"Solver transcript:\n{transcript}\n\n"
        f"Skeptic's rebuttal (targeting {skeptic_rebuttal.target_letter}): "
        f"disputed step: {skeptic_rebuttal.disputed_step}\nargument: {skeptic_rebuttal.argument}\n\n"
        f"Verifier findings:\n{findings_block}\n\n"
        'JSON shape: {"final_letter": "A|B|C|D", "decisive_reasoning": "...", '
        '"dissent": "unresolved objection, or null if none", '
        '"overturned_plurality": true/false, "confidence": "high|medium|low"}'
    )
    result = client.chat_json(model=JUDGE_MODEL, system=JUDGE_SYSTEM, user=user, role="judge")
    letter = str(result.data.get("final_letter", "")).strip().upper()[:1]
    dissent: Optional[str] = result.data.get("dissent") or None
    verdict = JudgeVerdict(
        final_letter=letter if letter in "ABCD" else solver_answers[0].letter,
        decisive_reasoning=str(result.data.get("decisive_reasoning", "")),
        dissent=dissent,
        overturned_plurality=bool(result.data.get("overturned_plurality", False)),
        confidence=str(result.data.get("confidence", "medium")),
    )
    return verdict, result.usage
