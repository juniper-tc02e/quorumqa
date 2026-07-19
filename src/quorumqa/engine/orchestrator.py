import asyncio
import time
from collections import Counter

from quorumqa.engine.judge import adjudicate
from quorumqa.engine.skeptic import rebut
from quorumqa.engine.solver import solve_all
from quorumqa.engine.verifier import verify
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import GPQAItem, QuestionResult
from quorumqa.tools.mcp_client import VerifierToolSession


def _plurality(answers) -> tuple[str, bool]:
    counts = Counter(a.letter for a in answers)
    top_letter, top_count = counts.most_common(1)[0]
    return top_letter, top_count == len(answers)


async def run_question(client: QwenClient, tool_session: VerifierToolSession, item: GPQAItem) -> QuestionResult:
    start = time.monotonic()

    solver_pairs = await solve_all(client, item.question, item.choices)
    solver_answers = [a for a, _ in solver_pairs]
    calls = [u for _, u in solver_pairs]

    plurality_letter, unanimous = _plurality(solver_answers)

    if unanimous:
        return QuestionResult(
            item=item,
            solver_answers=solver_answers,
            plurality_letter=plurality_letter,
            escalated=False,
            final_letter=plurality_letter,
            correct=(plurality_letter == item.correct_letter),
            calls=calls,
            latency_s=time.monotonic() - start,
        )

    skeptic_rebuttal, skeptic_usage = await asyncio.to_thread(
        rebut, client, item.question, item.choices, plurality_letter, solver_answers
    )
    calls.append(skeptic_usage)

    verifier_findings, verifier_usages = await verify(client, tool_session, item.question, solver_answers)
    calls.extend(verifier_usages)

    verdict, judge_usage = await asyncio.to_thread(
        adjudicate, client, item.question, item.choices, solver_answers, skeptic_rebuttal, verifier_findings
    )
    calls.append(judge_usage)

    false_escalation = (verdict.final_letter == plurality_letter) and not verdict.overturned_plurality

    return QuestionResult(
        item=item,
        solver_answers=solver_answers,
        plurality_letter=plurality_letter,
        escalated=True,
        skeptic_rebuttal=skeptic_rebuttal,
        verifier_findings=verifier_findings,
        verdict=verdict,
        final_letter=verdict.final_letter,
        correct=(verdict.final_letter == item.correct_letter),
        false_escalation=false_escalation,
        calls=calls,
        latency_s=time.monotonic() - start,
    )
