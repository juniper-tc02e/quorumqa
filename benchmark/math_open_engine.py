"""The open-answer math engine -- tests whether multi-solver deliberation
beats a single flagship call on genuinely hard OPEN-ANSWER math (MATH-500
level 5), where the shipped engine's distractor-MC framing saturates the
flagship at ~100% and cannot discriminate (benchmark/load_math.py,
benchmark/results/math500_hard_pilot_seed42.log). This module is the
engine half of that test; benchmark/load_math_open.py is the loader half.

Both `solve_single_math` (the required single-agent baseline) and
`solve_one_math` (the panel's per-seat solver) run on ORCHESTRATOR_MODEL
(the flagship, qwen3.7-max) with thinking=True -- the baseline is not a
cheap-tier call here, unlike the shipped GPQA engine's Solver seats,
because the whole point of this track is "does deliberation help ON TOP OF
the best available model" (mirrors benchmark/lever_experiments.py's
solve_all_flagship_panel, which asks the same question on GPQA/SuperGPQA).

JSON contract for every solver/judge call: {"reasoning": "...", "answer":
"\\boxed{...}"} -- same shape family as the shipped engine's solver/judge
contracts (a `reasoning` field plus a decisive field), just swapping
"letter" for a boxed LaTeX answer. `extract_boxed` pulls the final answer
out of the `answer` field (falling back to the `reasoning` field, and then
to the whole string) so a model that forgets to wrap its answer in
\\boxed{} in the `answer` field, but states it plainly elsewhere, still
yields a gradable answer instead of an empty one.

Grading is ALWAYS via benchmark.math_grade.grade -- for both the panel's
internal answer-clustering (two solver answers are "the same" iff `grade`
says so, e.g. "\\frac{1}{2}" and "0.5") and final scoring against gold.
Never reimplemented here.
"""

from __future__ import annotations

import asyncio
import re
import time

from quorumqa.config import MECHANICAL_MODEL, ORCHESTRATOR_MODEL, SOLVER_TEMPERATURES
from quorumqa.engine.solver import _lenses_for
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import CallUsage

from benchmark.load_math_open import MathItem
from benchmark.math_grade import grade

# ---------------------------------------------------------------------------
# extract_boxed -- deterministic, no network. Reuses the exact brace-
# matching approach benchmark/math_grade._strip_boxed uses (walk forward
# from the opening brace, tracking depth, stop when depth returns to 0) --
# but, unlike _strip_boxed (which strips the FIRST \boxed{} and keeps
# everything else), this pulls the CONTENT of the LAST \boxed{} occurrence,
# since a model's final answer is the last one it commits to after showing
# its work, and multi-step reasoning often has intermediate \boxed{} uses
# (e.g. boxing a sub-result) before the real final one.
# ---------------------------------------------------------------------------

_BOXED_OPEN_RE = re.compile(r"\\boxed\s*\{")


def extract_boxed(text: str) -> str:
    """Pulls the final answer out of `text`: the content of the LAST
    \\boxed{...} occurrence (brace-matched, so nested braces like
    \\boxed{\\frac{1}{2}} are handled correctly), or -- if there is no
    \\boxed{} at all -- the last non-empty line, or -- if the whole string
    is empty/whitespace -- the empty string."""
    if not text:
        return ""
    matches = list(_BOXED_OPEN_RE.finditer(text))
    if matches:
        m = matches[-1]
        start = m.end()  # first char inside the brace
        depth = 1
        i = start
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        return text[start:i].strip()

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        return lines[-1]
    return text.strip()


# ---------------------------------------------------------------------------
# Solver call -- one flagship call, thinking=True.
# ---------------------------------------------------------------------------

SOLVER_SYSTEM = (
    "You are an expert mathematician solving a genuinely hard competition math "
    "problem (MATH benchmark, difficulty level 5 -- the hardest tier). Work "
    "through the problem with concise but complete step-by-step reasoning, "
    "then give the final answer in LaTeX, wrapped in \\boxed{}."
)

# The baseline's framing -- deliberately generic (no panel-style lens), since
# the baseline is the single-agent comparison point, not one seat of a panel.
BASELINE_LENS = (
    "Work through the problem directly and carefully, double-checking your "
    "algebra and arithmetic before committing to a final answer."
)


def solve_one_math(client: QwenClient, problem: str, lens: str, temperature: float = 0.4, model: str = ORCHESTRATOR_MODEL, thinking: bool = True) -> tuple[str, str, CallUsage]:
    """One solver call solving `problem` under the given lens/temperature.
    `model` defaults to the flagship (ORCHESTRATOR_MODEL); pass MECHANICAL_MODEL
    for the cheap-tier variant that mirrors the SHIPPED engine's actual solver
    tier (flash solvers, flagship escalation). `thinking` defaults True; the
    SHIPPED engine runs its cheap voter seats with thinking=False (fast, cheap,
    and weak enough to genuinely disagree -- which is what triggers escalation),
    so the cheap tier passes thinking=False here. Returns (answer_str,
    reasoning, usage). `answer_str` is already run through `extract_boxed`, so
    callers never need to re-parse it."""
    user = (
        f"Problem: {problem}\n\n"
        'JSON shape: {"reasoning": "...", "answer": "\\\\boxed{...}"}\n'
        "Show the key steps in reasoning, but keep it concise. The answer field "
        "must end with the final result wrapped in \\boxed{}."
    )
    result = client.chat_json(
        model=model,
        system=f"{SOLVER_SYSTEM}\n\n{lens}",
        user=user,
        role="solver",
        thinking=thinking,
        temperature=temperature,
        max_tokens=2048,
        retries=2,
    )
    reasoning = str(result.data.get("reasoning", ""))
    raw_answer = str(result.data.get("answer", ""))
    answer = extract_boxed(raw_answer) or extract_boxed(reasoning)
    return answer, reasoning, result.usage


def solve_single_math(client: QwenClient, item: MathItem) -> dict:
    """The required single-agent BASELINE: one flagship-tier call, zero-shot
    (well, one-lens) reasoning, graded via benchmark.math_grade.grade
    against item.gold_answer."""
    start = time.monotonic()
    answer, reasoning, usage = solve_one_math(client, item.problem, BASELINE_LENS, temperature=0.3)
    correct = grade(item.gold_answer, answer)
    return {
        "question_id": item.question_id,
        "gold_answer": item.gold_answer,
        "final_answer": answer,
        "correct": correct,
        "reasoning": reasoning,
        "calls": [usage.model_dump()],
        "latency_s": time.monotonic() - start,
    }


# ---------------------------------------------------------------------------
# Panel -- 3 flagship solvers, distinct lenses + SOLVER_TEMPERATURES
# (mirrors benchmark/lever_experiments.py's solve_all_flagship_panel), then
# plurality-cluster by grade() equivalence, escalating to a judge only when
# all three are mutually inequivalent.
# ---------------------------------------------------------------------------

JUDGE_SYSTEM = (
    "You are the final adjudicator reviewing three independent expert solvers "
    "who gave three MUTUALLY DISAGREEING answers to a hard competition math "
    "problem. Work the problem yourself from scratch -- use their reasoning "
    "only as a reference, not as a shortcut -- and decide the correct final "
    "answer. Show concise reasoning, then give the final answer in LaTeX, "
    "wrapped in \\boxed{}."
)


def judge_math(client: QwenClient, problem: str, solver_answers: list[tuple[str, str]], temperature: float = 0.3) -> tuple[str, str, CallUsage]:
    """Adjudicates a 3-way split. `solver_answers` is [(answer, reasoning),
    ...] for the 3 solver seats. Returns (answer_str, reasoning, usage),
    same JSON contract and extract_boxed handling as solve_one_math."""
    transcript = "\n\n".join(
        f"Solver {i + 1} answered {answer!r}. Reasoning: {reasoning}"
        for i, (answer, reasoning) in enumerate(solver_answers)
    )
    user = (
        f"Problem: {problem}\n\n"
        f"Three independent solvers disagreed:\n\n{transcript}\n\n"
        'JSON shape: {"reasoning": "...", "answer": "\\\\boxed{...}"}\n'
        "Work the problem yourself and decide the single correct final answer."
    )
    result = client.chat_json(
        model=ORCHESTRATOR_MODEL,
        system=JUDGE_SYSTEM,
        user=user,
        role="judge",
        thinking=True,
        temperature=temperature,
        retries=2,
    )
    reasoning = str(result.data.get("reasoning", ""))
    raw_answer = str(result.data.get("answer", ""))
    answer = extract_boxed(raw_answer) or extract_boxed(reasoning)
    return answer, reasoning, result.usage


def _cluster_answers(answers: list[str]) -> list[list[int]]:
    """Groups answer indices into equivalence clusters: index i and j land
    in the same cluster iff grade(answers[i], answers[j]) is True. Uses a
    simple union-find over the (small, n<=3 in practice) pairwise grade()
    comparisons -- grade() is a heuristic equivalence check, not guaranteed
    perfectly transitive on adversarial input, but union-find over the
    actual pairwise results is the correct, symmetric way to turn "some
    pairs agree" into disjoint groups regardless."""
    n = len(answers)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            if grade(answers[i], answers[j]):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


async def _solve_panel_answers_async(client: QwenClient, problem: str, lenses: list[str], solver_model: str, solver_thinking: bool) -> list[tuple[str, str, CallUsage]]:
    """Mirrors solve_all_flagship_panel's async gather structure: 3 solver
    seats, distinct lenses, SOLVER_TEMPERATURES, all on `solver_model`,
    dispatched concurrently via asyncio.to_thread."""
    tasks = [
        asyncio.to_thread(solve_one_math, client, problem, lenses[i], SOLVER_TEMPERATURES[i], solver_model, solver_thinking)
        for i in range(3)
    ]
    return list(await asyncio.gather(*tasks))


def solve_panel_math(client: QwenClient, item: MathItem, solver_model: str = ORCHESTRATOR_MODEL, solver_thinking: bool = True) -> dict:
    """The ENGINE: 3 solvers (distinct lenses + SOLVER_TEMPERATURES, mirroring
    solve_all_flagship_panel), clustered by grade() equivalence. If the largest
    cluster has >=2 members, its answer is final and escalated=False. If all
    three are mutually inequivalent (3 singleton clusters), escalated=True and
    a JUDGE call (always the flagship, ORCHESTRATOR_MODEL) decides the final
    answer.

    `solver_model` defaults to the flagship. Pass MECHANICAL_MODEL for the
    cheap-solver variant that mirrors the SHIPPED engine's real tier structure
    (cheap solvers, flagship escalation) -- on hard math the weaker solvers
    disagree far more, so escalation actually fires (unlike the all-flagship
    panel, which never split -> 0% escalation)."""
    start = time.monotonic()
    lenses = _lenses_for(3)
    triples = asyncio.run(_solve_panel_answers_async(client, item.problem, lenses, solver_model, solver_thinking))

    answers = [t[0] for t in triples]
    calls: list[CallUsage] = [t[2] for t in triples]

    groups = _cluster_answers(answers)
    largest = max(groups, key=len)
    escalated = len(largest) < 2

    judge_reasoning = None
    if escalated:
        judge_answer, judge_reasoning, judge_usage = judge_math(
            client, item.problem, [(t[0], t[1]) for t in triples]
        )
        calls.append(judge_usage)
        final_answer = judge_answer
    else:
        final_answer = answers[largest[0]]

    correct = grade(item.gold_answer, final_answer)
    return {
        "question_id": item.question_id,
        "gold_answer": item.gold_answer,
        "final_answer": final_answer,
        "solver_model": solver_model,
        "escalated": escalated,
        "correct": correct,
        "solver_answers": [
            {"answer": t[0], "reasoning": t[1], "lens": lens, "temperature": temp}
            for t, lens, temp in zip(triples, lenses, SOLVER_TEMPERATURES)
        ],
        "judge_reasoning": judge_reasoning,
        "calls": [c.model_dump() for c in calls],
        "latency_s": time.monotonic() - start,
    }
