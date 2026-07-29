import time
from collections import Counter

from quorumqa.config import BASELINE_MODEL, N_SOLVERS, SOLVER_MODEL
from quorumqa.letters import choice_block, letter_hint, parse_letter
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import BaselineResult, GPQAItem

BASELINE_SYSTEM = (
    "You are an expert answering a hard, graduate-level multiple-choice "
    "science question. Answer with your best single choice."
)


def _ask_once(client: QwenClient, model: str, item: GPQAItem, role: str, thinking: bool = True):
    # A-J generalized (docs/capability-roadmap.md F7), completing the sweep that
    # covered the four engine roles and the levers. This site was the BLOCKING
    # gap: every accuracy claim is a delta against this single-agent baseline, so
    # on a >4-choice item (mmlu_pro_full, MedXpertQA) the old zip("ABCD", choices)
    # would have silently truncated the baseline's prompt to the first 4 options
    # while the engine saw all of them -- the baseline would have been answering
    # an easier question, and the comparison would have been invalid rather than
    # merely noisy. quorumqa.letters is byte-identical at 4 choices by
    # construction, so every published baseline number is unaffected.
    n = len(item.choices)
    user = (
        f"Question: {item.question}\n\nChoices:\n{choice_block(item.choices)}\n\n"
        f'JSON shape: {{"letter": "{letter_hint(n)}", "reasoning": "..."}}\n'
        "Keep reasoning to at most 3 sentences."
    )
    result = client.chat_json(model=model, system=BASELINE_SYSTEM, user=user, role=role, thinking=thinking)
    return parse_letter(result.data.get("letter", ""), n), result.usage


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


def solve_compute_matched_control(client: QwenClient, item: GPQAItem) -> BaselineResult:
    """The compute-matched control `capability-roadmap.md` mandates for every
    whole-pipeline swap and that `flagship_panel` never received: N_SOLVERS
    (3) independent flagship-tier (BASELINE_MODEL) calls, majority vote, no
    tribunal. Same tier and same call count as flagship_panel's three solver
    seats -- the only difference is the vote is text-majority over
    independent samples rather than plurality-then-escalate-on-split. Without
    this arm, flagship_panel's +4.1/+10 headline cannot be told apart from
    plain self-consistency (Self-MoA, ICML 2025), which is exactly the gap
    docs/FINDINGS.md flags as open.

    thinking=True to match solve_single_agent's default (flagship_panel's
    solver seats also run thinking=True) -- this is a fair-tier match, not
    the cheap-tier match solve_self_consistency5 targets below.
    """
    start = time.monotonic()
    letters = []
    calls = []
    for _ in range(N_SOLVERS):
        letter, usage = _ask_once(client, BASELINE_MODEL, item, role="baseline", thinking=True)
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


def solve_self_consistency5(client: QwenClient, item: GPQAItem) -> BaselineResult:
    """Stretch-goal baseline: 5x samples on the SAME tier the engine's
    Solvers use, majority vote, no debate/judge. Matching the tier isolates
    the value of escalation/adjudication itself rather than a model-tier
    difference."""
    start = time.monotonic()
    letters = []
    calls = []
    for _ in range(5):
        # thinking=False to mirror the engine's Solver configuration exactly
        letter, usage = _ask_once(client, SOLVER_MODEL, item, role="baseline", thinking=False)
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
