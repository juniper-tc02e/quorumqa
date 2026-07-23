"""Ablation harness for the four architecture levers proposed to close the
accuracy gap to the flagship baseline. Reuses the real solver/skeptic/
verifier/judge functions unchanged -- this file only varies HOW they are
called, never their prompts or models. Writes to benchmark/results/lever_*,
never touches full_run2.jsonl or summary.md (the frozen submission data).

Levers:
  gate        -- cheap universal second-opinion call before accepting any
                 unanimous answer; escalates to the full tribunal on doubt.
  thinking    -- seat 3 runs with thinking=True instead of the uniform
                 thinking=False, same model (qwen3.6-flash).
  subject     -- force escalation for Organic Chemistry regardless of
                 unanimity. Must be run against a FRESH seed (not 42), since
                 it was derived by looking at seed=42's errors -- testing it
                 on seed=42 would be circular.
  five        -- N_SOLVERS=5 instead of 3 (already-supported config knob;
                 lenses/temperatures cycle since only 3 of each are defined).
  smart_gate  -- like thinking_gate, but seat 3 only pays the thinking
                 premium on Organic Chemistry questions; universal doubt-gate
                 otherwise. Tested at seed 123 (fresh): underperformed both
                 thinking_gate AND the plain baseline, including on Organic
                 Chemistry itself (72.2% vs 77.8% baseline) -- see
                 lever_findings.md, "Third-seed validation" section. Kept in
                 the harness as a documented negative result, not a
                 candidate for shipping.
  qwen38_judge -- identical to the shipped engine (3 flash solvers, flash
                 skeptic, flash verifier, escalate only on disagreement)
                 EXCEPT the Judge call goes to qwen3.8-max-preview via the
                 Token Plan Anthropic-Messages transport instead of
                 qwen3.7-max via QwenClient/DashScope. Same judge system/
                 user prompt and JSON contract as the shipped judge -- only
                 the model and transport differ. See adjudicate_qwen38().
  qwen38_panel -- all THREE solver seats run qwen3.8-max-preview via the
                 Token Plan Anthropic-Messages transport (same transport
                 pattern as adjudicate_qwen38 / benchmark/qwen38_baseline.py)
                 instead of the shipped MECHANICAL_MODEL. Same SOLVER_SYSTEM
                 + lens + JSON contract as _solve_one_thinking -- only the
                 model and transport differ. Skeptic/Verifier/Judge are
                 UNCHANGED from the shipped engine (flash skeptic, flash
                 verifier, qwen3.7-max judge via QwenClient) -- solver tier
                 is the ONLY variable vs the shipped engine, and vs
                 flagship_panel (all-qwen3.7-max solvers) the only variable
                 is the solver model: 3.7-max -> 3.8-max-preview.
                 qwen3.8-max-preview thinks by default on this transport --
                 no attempt is made to disable it (unlike the cheap-tier
                 _solve_one, which explicitly sets thinking=False). See
                 _solve_one_qwen38() / solve_all_qwen38_panel(). This lever
                 was not tuned or validated on any prior seed, so the
                 FRESH-SEED discipline that applies to seed-derived levers
                 above does not apply the same way here -- seed 42 remains
                 fine to use as the standard comparison seed (e.g. for
                 SuperGPQA reference points); the orchestrator picks pilot
                 seeds.
  chem_thinking_gate -- stacks the two validated winners together: Organic
                 Chemistry questions get chem_flagship_gate's three-
                 flagship-thinking panel; every OTHER subject gets
                 thinking_gate's thinking-seat panel (seats 1-2 plain flash,
                 seat 3 thinking=True flash); the universal
                 second_opinion_gate doubt-check applies to unanimous
                 answers everywhere, as both parents do. Escalation
                 machinery (skeptic/verifier/judge) is untouched. MUST be
                 run against a FRESH seed only -- seeds 42/7/123/555/777/888
                 are all burned for this lever, having already been spent
                 tuning/validating thinking_gate and chem_flagship_gate
                 individually; reusing any of them here would double-count
                 that evidence rather than testing the stack honestly.
  rag_presolve -- docs/recursive-rag-plan.md section 2, R1 (pre-solve
                 retrieval). Identical to the shipped cheap engine (3 flash
                 solvers, flash skeptic/verifier, qwen3.7-max judge,
                 escalate only on split) EXCEPT before the solvers run,
                 top-k passages are retrieved ONCE per question from the
                 pre-embedded STEM-Wikipedia RAG index (docs/rag-corpus-
                 notes.md) and prepended as a compact evidence block to
                 every solver seat's user prompt. Solver system prompt and
                 JSON contract are byte-for-byte unchanged; skeptic/
                 verifier/judge/escalation trigger are untouched. Tests
                 Bet 1: does cheap-panel + retrieval close the unanimous-
                 wrong knowledge gap without paying for a flagship tier.
                 Fails loudly at startup if the index DB doesn't exist (see
                 open_rag_index) -- retrieval is the whole point of this
                 lever, so it must never silently run without it. Index
                 path/k are overridable via --rag-db/--rag-k or the
                 QUORUMQA_RAG_DB env var. Firewall (section 4): every
                 output row records rag="ON" and the exact rag_snapshot_id
                 read from the open index (see _build_output_row).
  rag_recursive -- docs/recursive-rag-plan.md section 2, R2 (disputed-step
                 retrieval, the first RECURSION -- Bet 2). rag_presolve's R1
                 pre-solve retrieval, PLUS, on escalation only: the Skeptic's
                 named disputed_step + argument, and the divergent solver
                 claims (plurality + dissent), become a second, sharper
                 query (build_disputed_step_query); a second retrieval
                 (fixed top-k=3, RAG_R2_K) fires against the SAME
                 matched-encoder index R1 used; the results are injected as
                 an evidence block into the Verifier's context (verify()'s
                 new evidence_block parameter) ALONGSIDE its existing
                 lookup_constant/safe_calculate MCP tool calls -- retrieval
                 is ADDED grounding, never a replacement. Unanimous
                 (non-escalated) questions never trigger R2 -- only R1 ran,
                 identical to rag_presolve. Skeptic/Judge and the escalation
                 trigger itself are completely untouched. Same fail-loud
                 missing-index contract as rag_presolve (same RagPresolveConfig,
                 same open_rag_index). Firewall: every output row carries
                 rag_presolve's rag="ON"/rag_snapshot_id fields PLUS
                 rag_r2="ON"/"OFF" (whether R2 actually fired for that
                 question), rag_r2_snapshot_id, rag_r2_query, rag_r2_titles
                 (see _build_output_row).

Usage:
  python -m benchmark.lever_experiments --lever gate --n 90 --seed 42
  python -m benchmark.lever_experiments --lever thinking --n 90 --seed 42
  python -m benchmark.lever_experiments --lever five --n 90 --seed 42
  python -m benchmark.lever_experiments --lever subject --n 90 --seed 7
  python -m benchmark.lever_experiments --lever control --n 90 --seed 7   # fresh-seed control for subject
  python -m benchmark.lever_experiments --lever qwen38_judge --n 90 --seed 42
  python -m benchmark.lever_experiments --lever qwen38_panel --n 90 --seed 42
  python -m benchmark.lever_experiments --lever chem_thinking_gate --n 90 --seed <FRESH>  # never 42/7/123/555/777/888
  python -m benchmark.lever_experiments --lever rag_presolve --n 90 --seed 42 --dataset supergpqa --rag-k 5
  python -m benchmark.lever_experiments --lever rag_recursive --n 90 --seed 42 --dataset supergpqa --rag-k 5
  python -m benchmark.lever_experiments --lever gate-replay             # cheap replay against frozen data
"""

import argparse
import asyncio
import json
import logging
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import requests

from quorumqa.baseline import solve_single_agent
from quorumqa.config import MECHANICAL_MODEL, N_SOLVERS, ORCHESTRATOR_MODEL, SOLVER_TEMPERATURES, TOKEN_PLAN_API_KEY, TOKEN_PLAN_BASE_URL
from quorumqa.engine.judge import JUDGE_SYSTEM, adjudicate
from quorumqa.engine.skeptic import rebut
from quorumqa.engine.solver import SOLVER_SYSTEM, _lenses_for, _solve_one, solve_all
from quorumqa.engine.verifier import verify
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import CallUsage, GPQAItem, JudgeVerdict, QuestionResult, SkepticRebuttal, SolverAnswer, VerifierFinding
from quorumqa.tools.mcp_client import VerifierToolSession, verifier_tool_session

from benchmark.load_gpqa import load_benchmark_set
from benchmark.load_lexam import load_lexam_set
from benchmark.load_medqa import load_medqa_set
from benchmark.load_mmlu_pro import load_mmlu_pro_set
from benchmark.load_supergpqa import load_supergpqa_set

# Every lever is a pure function of (client, tool_session, item, lever_name)
# -- none of them know or care which benchmark an item came from, since they
# all consume the same GPQAItem shape. This makes every lever automatically
# available on LEXam and MMLU-Pro too, for free, once a dataset is selected
# here -- no lever-specific code needed per dataset.
DATASET_LOADERS = {
    "gpqa": lambda n, seed, skip_huggingface: load_benchmark_set(n=n, seed=seed, skip_huggingface=skip_huggingface),
    "lexam": lambda n, seed, skip_huggingface: load_lexam_set(n=n, seed=seed),
    "mmlu_pro": lambda n, seed, skip_huggingface: load_mmlu_pro_set(n=n, seed=seed),
    "supergpqa": lambda n, seed, skip_huggingface: load_supergpqa_set(n=n, seed=seed, difficulty="hard"),
    "medqa": lambda n, seed, skip_huggingface: load_medqa_set(n=n, seed=seed),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _plurality(answers):
    counts = Counter(a.letter for a in answers)
    top_letter, top_count = counts.most_common(1)[0]
    return top_letter, top_count == len(answers)


def _solve_one_thinking(client, question, choices, lens, model=MECHANICAL_MODEL, temperature=0.4):
    """Identical to solver._solve_one except thinking=True. Same model, same
    prompt -- isolates reasoning depth as the only variable."""
    choice_block = "\n".join(f"{letter}) {c}" for letter, c in zip("ABCD", choices))
    user = (
        f"Question: {question}\n\nChoices:\n{choice_block}\n\n"
        'JSON shape: {"letter": "A|B|C|D", "confidence": 0.0-1.0, "reasoning": "..."}\n'
        "Keep reasoning to at most 3 sentences -- your answer letter matters more than showing full working."
    )
    result = client.chat_json(model=model, system=f"{SOLVER_SYSTEM}\n\n{lens}", user=user, role="solver_thinking", thinking=True, temperature=temperature, retries=2)
    letter = str(result.data.get("letter", "")).strip().upper()[:1]
    answer = SolverAnswer(
        letter=letter if letter in "ABCD" else "A",
        confidence=float(result.data.get("confidence", 0.5)),
        reasoning=str(result.data.get("reasoning", "")),
        lens=lens,
    )
    return answer, result.usage


async def solve_all_thinking_seat(client, question, choices):
    """Seats 1-2 exactly as the shipped engine; seat 3 gets thinking=True."""
    lenses = _lenses_for(3)
    tasks = [
        asyncio.to_thread(_solve_one, client, question, choices, lenses[0], MECHANICAL_MODEL, 0.3),
        asyncio.to_thread(_solve_one, client, question, choices, lenses[1], MECHANICAL_MODEL, 0.6),
        asyncio.to_thread(_solve_one_thinking, client, question, choices, lenses[2], MECHANICAL_MODEL, 0.9),
    ]
    return list(await asyncio.gather(*tasks))


async def solve_all_thinking_all(client, question, choices):
    """All three seats thinking=True, still on the cheap tier. Tests whether
    spreading the Lever-2 gain across every seat compounds further, or
    whether one thinking seat was already capturing most of the value."""
    lenses = _lenses_for(3)
    tasks = [
        asyncio.to_thread(_solve_one_thinking, client, question, choices, lenses[i], MECHANICAL_MODEL, SOLVER_TEMPERATURES[i])
        for i in range(3)
    ]
    return list(await asyncio.gather(*tasks))


async def solve_all_smart_seat(client, question, choices, subject):
    """Like solve_all_thinking_seat, but seat 3 only pays the thinking premium
    on Organic Chemistry -- the one subject the diagnosis found carries a real,
    systematic error rate (18.9% unanimous-wrong vs 0% for every physics
    subject). Everywhere else seat 3 runs exactly as shipped (thinking=False).
    Tests whether thinking_gate's gain can be kept at a fraction of its cost by
    spending the expensive reasoning only where the diagnosis says it pays."""
    lenses = _lenses_for(3)
    seat3_thinking = subject == "Organic Chemistry"
    tasks = [
        asyncio.to_thread(_solve_one, client, question, choices, lenses[0], MECHANICAL_MODEL, 0.3),
        asyncio.to_thread(_solve_one, client, question, choices, lenses[1], MECHANICAL_MODEL, 0.6),
        asyncio.to_thread(_solve_one_thinking, client, question, choices, lenses[2], MECHANICAL_MODEL, 0.9)
        if seat3_thinking else
        asyncio.to_thread(_solve_one, client, question, choices, lenses[2], MECHANICAL_MODEL, 0.9),
    ]
    return list(await asyncio.gather(*tasks))


async def solve_all_chem_flagship(client, question, choices, subject):
    """The direct follow-up to smart_gate's negative result. smart_gate gave
    the SAME model (qwen3.6-flash) more thinking time on Organic Chemistry
    and it made chemistry worse, not better -- evidence the gap is a
    knowledge blind spot, not an effort gap. This lever tests the other half
    of that hypothesis directly: if it's a knowledge gap, does a genuinely
    DIFFERENT, stronger model (qwen3.7-max, the flagship) do better on the
    same questions? All three solver seats switch to the flagship, thinking
    enabled, ONLY for Organic Chemistry; every other subject is untouched,
    identical to the shipped engine. Expensive on chemistry questions (3x
    flagship calls instead of 3x cheap calls, on ~40% of the question set)
    but that is the point -- this is a targeted diagnostic, not a
    cost-optimized lever."""
    lenses = _lenses_for(3)
    if subject == "Organic Chemistry":
        tasks = [
            asyncio.to_thread(_solve_one_thinking, client, question, choices, lenses[i], ORCHESTRATOR_MODEL, SOLVER_TEMPERATURES[i])
            for i in range(3)
        ]
    else:
        tasks = [
            asyncio.to_thread(_solve_one, client, question, choices, lenses[0], MECHANICAL_MODEL, 0.3),
            asyncio.to_thread(_solve_one, client, question, choices, lenses[1], MECHANICAL_MODEL, 0.6),
            asyncio.to_thread(_solve_one, client, question, choices, lenses[2], MECHANICAL_MODEL, 0.9),
        ]
    return list(await asyncio.gather(*tasks))


async def solve_all_chem_thinking_gate(client, question, choices, subject):
    """The chem_thinking_gate lever's solver panel: stacks chem_flagship_gate's
    Organic Chemistry routing on top of thinking_gate's non-chemistry panel --
    the combination of both validated winners, nothing new invented at the
    solver level. Organic Chemistry -> the same three-flagship-thinking panel
    as solve_all_chem_flagship's chemistry branch (routes through that
    function directly, so the two levers can never drift apart on how
    chemistry is solved). Every other subject -> solve_all_thinking_seat's
    panel (seats 1-2 plain MECHANICAL_MODEL, seat 3 thinking=True
    MECHANICAL_MODEL) -- NOT chem_flagship_gate's plain-everywhere-else
    panel, since thinking_gate's whole point was that seat-3 thinking helps
    broadly, not just on chemistry.

    MUST be validated on a FRESH seed only: both parent levers were tuned/
    validated on seeds 42/7/123/555/777/888, so every one of those seeds is
    burned for this lever (reusing one would double-count evidence already
    spent choosing thinking_gate and chem_flagship_gate in the first place).
    """
    if subject == "Organic Chemistry":
        return await solve_all_chem_flagship(client, question, choices, subject)
    return await solve_all_thinking_seat(client, question, choices)


async def solve_all_flagship_panel(client, question, choices):
    """All three seats run on the FLAGSHIP model (qwen3.7-max), thinking
    enabled -- matching how the flagship is used everywhere else in the
    project (baseline, judge). Tests whether deliberation adds value ON TOP
    of the best available model, not just as a cheap-model compensator.
    Skeptic/Verifier/Judge stay exactly as shipped -- only the solver tier
    changes, isolating that one variable."""
    lenses = _lenses_for(3)
    tasks = [
        asyncio.to_thread(_solve_one_thinking, client, question, choices, lenses[i], ORCHESTRATOR_MODEL, SOLVER_TEMPERATURES[i])
        for i in range(3)
    ]
    return list(await asyncio.gather(*tasks))


GATE_SYSTEM = (
    "You are a fast sanity-checker reviewing a panel's UNANIMOUS answer to a "
    "hard graduate-level science question, before it ships without further "
    "review. All three independent solvers agreed, so your default should be "
    "to trust them -- only raise doubt if you spot a concrete, specific flaw "
    "in the shared reasoning (a wrong fact, a skipped case, a common "
    "misconception the question is designed to trap). Do not raise doubt "
    "just because the topic is hard."
)


def second_opinion_gate(client, question, choices, solver_answers, plurality_letter):
    choice_block = "\n".join(f"{letter}) {c}" for letter, c in zip("ABCD", choices))
    transcript = "\n\n".join(f"[{a.lens}] {a.reasoning}" for a in solver_answers)
    user = (
        f"Question: {question}\n\nChoices:\n{choice_block}\n\n"
        f"Panel's unanimous answer: {plurality_letter}\n\nReasoning given:\n{transcript}\n\n"
        'JSON shape: {"doubt": true|false, "reason": "..."} -- reason under 20 words.'
    )
    result = client.chat_json(model=MECHANICAL_MODEL, system=GATE_SYSTEM, user=user, role="gate", thinking=False, temperature=0.2, retries=2)
    doubt = bool(result.data.get("doubt", False))
    return doubt, str(result.data.get("reason", "")), result.usage


QWEN38_JUDGE_MODEL = "qwen3.8-max-preview"
_QWEN38_MESSAGES_URL = TOKEN_PLAN_BASE_URL.rstrip("/") + "/v1/messages"


def adjudicate_qwen38(
    client: QwenClient,  # unused -- kept only so this has the exact same call
                          # signature as quorumqa.engine.judge.adjudicate, so
                          # _tribunal can treat the two adjudicators
                          # interchangeably. This adjudicator bypasses
                          # QwenClient/DashScope entirely; see module note below.
    question: str,
    choices: list[str],
    solver_answers: list[SolverAnswer],
    skeptic_rebuttal: SkepticRebuttal,
    verifier_findings: list[VerifierFinding],
) -> tuple[JudgeVerdict, CallUsage]:
    """The qwen38_judge lever's judge call: qwen3.8-max-preview via the Token
    Plan's Anthropic-Messages-API-compatible endpoint, copying the transport
    pattern from benchmark/qwen38_baseline.py exactly (requests.post to
    {TOKEN_PLAN_BASE_URL}/v1/messages, x-api-key header, anthropic-version
    2023-06-01, 300s timeout, text extracted after skipping any non-text
    content block such as "thinking").

    JUDGE_SYSTEM is imported directly from quorumqa.engine.judge (it's a
    module-level constant there) so the system prompt can never drift. The
    user-prompt construction below, however, is NOT factored into a
    reusable function in judge.py -- it is a VERBATIM copy of the body of
    judge.adjudicate(). If that prompt ever changes, this copy must change
    with it, or the qwen38_judge lever stops being an apples-to-apples
    judge-model swap (same prompt, same JSON contract, different model/
    transport only). Everything else about this lever -- solvers, skeptic,
    verifier, escalation trigger -- is untouched from the shipped engine.
    """
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

    headers = {
        "x-api-key": TOKEN_PLAN_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": QWEN38_JUDGE_MODEL,
        "max_tokens": 1024,
        "system": JUDGE_SYSTEM,
        "messages": [{"role": "user", "content": user}],
    }
    resp = requests.post(_QWEN38_MESSAGES_URL, headers=headers, json=body, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    # Responses may carry a "thinking" content block before the "text"
    # block -- skip any non-text block rather than assuming content[0] is
    # the answer (same handling as benchmark/qwen38_baseline.py's _ask_once).
    text_blocks = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    text = "\n".join(text_blocks)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"No JSON object found in qwen38 judge response text: {text!r}")
    parsed = json.loads(match.group(0))

    letter = str(parsed.get("final_letter", "")).strip().upper()[:1]
    dissent = parsed.get("dissent") or None
    verdict = JudgeVerdict(
        final_letter=letter if letter in "ABCD" else solver_answers[0].letter,
        decisive_reasoning=str(parsed.get("decisive_reasoning", "")),
        dissent=dissent,
        overturned_plurality=bool(parsed.get("overturned_plurality", False)),
        confidence=str(parsed.get("confidence", "medium")),
    )

    usage_raw = data.get("usage", {})
    usage = CallUsage(
        model=QWEN38_JUDGE_MODEL,
        input_tokens=usage_raw.get("input_tokens", 0) or 0,
        output_tokens=usage_raw.get("output_tokens", 0) or 0,
        # The Token Plan has no published $/token rate (same situation as
        # every other Token Plan call -- see qwen_client.py's chat() and
        # benchmark/qwen38_baseline.py's module docstring). Never fold a
        # fabricated USD number in here: qwen38-judge cost is quota-based
        # and reported separately in tokens (input_tokens/output_tokens
        # above are the real signal).
        cost_usd=0.0,
        role="judge",
    )
    return verdict, usage


def _solve_one_qwen38(client, question, choices, lens, temperature=0.4):
    """One solver seat running qwen3.8-max-preview via the Token Plan's
    Anthropic-Messages-API-compatible endpoint -- same transport pattern as
    adjudicate_qwen38 / benchmark/qwen38_baseline.py (requests.post to
    {TOKEN_PLAN_BASE_URL}/v1/messages, x-api-key header, anthropic-version
    2023-06-01, 300s timeout, text extracted after skipping any non-text
    content block such as "thinking"). `client` is accepted but unused --
    kept only so this has the same call signature shape as
    _solve_one/_solve_one_thinking, letting solve_all_qwen38_panel dispatch
    it via asyncio.to_thread exactly like every other solver helper.

    Same SOLVER_SYSTEM + lens system prompt and JSON contract as
    _solve_one_thinking -- only the model and transport differ. This is a
    VERBATIM copy of _solve_one_thinking's user-prompt construction, not a
    shared helper; if that prompt ever changes, this copy must change with
    it, same caveat as adjudicate_qwen38's docstring.

    qwen3.8-max-preview thinks by default on the Token Plan transport -- no
    attempt is made to disable it (there is no thinking=False knob on this
    transport, unlike QwenClient.chat_json). Any "thinking" content block in
    the response is simply skipped when extracting the answer JSON, same
    handling as adjudicate_qwen38."""
    choice_block = "\n".join(f"{letter}) {c}" for letter, c in zip("ABCD", choices))
    user = (
        f"Question: {question}\n\nChoices:\n{choice_block}\n\n"
        'JSON shape: {"letter": "A|B|C|D", "confidence": 0.0-1.0, "reasoning": "..."}\n'
        "Keep reasoning to at most 3 sentences -- your answer letter matters more than showing full working."
    )
    headers = {
        "x-api-key": TOKEN_PLAN_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": QWEN38_JUDGE_MODEL,
        "max_tokens": 1024,
        "system": f"{SOLVER_SYSTEM}\n\n{lens}",
        "messages": [{"role": "user", "content": user}],
    }
    resp = requests.post(_QWEN38_MESSAGES_URL, headers=headers, json=body, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    text_blocks = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    text = "\n".join(text_blocks)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"No JSON object found in qwen38 solver response text: {text!r}")
    parsed = json.loads(match.group(0))

    letter = str(parsed.get("letter", "")).strip().upper()[:1]
    answer = SolverAnswer(
        letter=letter if letter in "ABCD" else "A",
        confidence=float(parsed.get("confidence", 0.5)),
        reasoning=str(parsed.get("reasoning", "")),
        lens=lens,
    )

    usage_raw = data.get("usage", {})
    usage = CallUsage(
        model=QWEN38_JUDGE_MODEL,
        input_tokens=usage_raw.get("input_tokens", 0) or 0,
        output_tokens=usage_raw.get("output_tokens", 0) or 0,
        # Same quota-billing note as adjudicate_qwen38: the Token Plan has no
        # published $/token rate, so never fold a fabricated USD number in
        # here -- cost is quota-based and reported separately in tokens.
        cost_usd=0.0,
        role="solver",
    )
    return answer, usage


async def solve_all_qwen38_panel(client, question, choices):
    """All three solver seats run qwen3.8-max-preview via the Token Plan
    transport instead of the shipped MECHANICAL_MODEL. Skeptic/Verifier/
    Judge are untouched -- solver tier is the only variable vs the shipped
    engine, and vs solve_all_flagship_panel the only variable is the solver
    model (qwen3.7-max -> qwen3.8-max-preview)."""
    lenses = _lenses_for(3)
    tasks = [
        asyncio.to_thread(_solve_one_qwen38, client, question, choices, lenses[i], SOLVER_TEMPERATURES[i])
        for i in range(3)
    ]
    return list(await asyncio.gather(*tasks))


# ---------------------------------------------------------------------------
# rag_presolve (R1): pre-solve retrieval lever -- docs/recursive-rag-plan.md
# section 2. Identical to the shipped cheap engine EXCEPT each solver seat's
# user prompt is prefixed with a compact evidence block retrieved ONCE per
# question (not once per seat) from the pre-embedded STEM-Wikipedia index
# (docs/rag-corpus-notes.md). Solver system prompt + JSON contract are
# byte-for-byte unchanged from quorumqa.engine.solver._solve_one -- retrieval
# only touches the user turn. Skeptic/Verifier/Judge/escalation trigger are
# completely untouched (this lever never appears in any gate-lever list
# below), isolating "does injecting retrieved evidence before the panel
# answers move the needle" as the only variable vs the shipped engine.
#
# FIREWALL (docs/recursive-rag-plan.md section 4): the index is the G0.5
# STEM-Wikipedia corpus -- general encyclopedia content unrelated to any
# benchmark's question set. Every output row this lever writes records
# rag="ON" plus the exact rag_snapshot_id read from the OPEN index's
# build_progress row (see _build_output_row), so a RAG-assisted number is
# never presented next to a non-RAG baseline as if it were the same mode.
# ---------------------------------------------------------------------------

RAG_DB_ENV = "QUORUMQA_RAG_DB"
DEFAULT_RAG_DB_PATH = Path(__file__).resolve().parent / "data" / "rag_index_preembedded.sqlite3"
DEFAULT_RAG_K = 5
# rag_recursive (R2) only: top-k for the disputed-step retrieval, fixed per
# docs/recursive-rag-plan.md section 2 ("retrieve top-k (k=3) passages") --
# not CLI-overridable like R1's k, since the spec pins this value.
RAG_R2_K = 3
# ~200 words total across ALL retrieved passages, split evenly across
# however many were retrieved -- keeps the extra context lean per
# docs/recursive-rag-plan.md's "keep snippets short" instruction, rather
# than letting k passages each carry a full ~200-word snippet.
RAG_EVIDENCE_WORD_BUDGET = 200

# One RagIndex (+ its in-memory dense-vector cache) per resolved DB path,
# reused for the lifetime of this process -- mirrors quorumqa.tools.
# mcp_server._rag_index_cache's pattern. Unlike that cache, though, this
# lever's missing-DB contract is the OPPOSITE of search_corpus's clean
# no-op: see open_rag_index.
_rag_index_cache: dict = {}


@dataclass
class RagPresolveConfig:
    index: object  # quorumqa.rag.store.RagIndex -- typed loosely so this
                    # module doesn't hard-depend on the rag package at
                    # import time (matches mcp_server.py's lazy-import style)
    embedder: object  # Callable[[str], np.ndarray] | None -- None means
                       # dense deps are unavailable; retrieval degrades to
                       # FTS5-only (same degrade path as mcp_server.search_corpus)
    k: int
    snapshot_id: str
    db_path: Path


def resolve_rag_db_path(cli_value: str | None = None) -> Path:
    """CLI --rag-db wins over the QUORUMQA_RAG_DB env var, which wins over
    the pre-embedded G0.5 corpus (docs/rag-corpus-notes.md) as the default."""
    if cli_value:
        return Path(cli_value)
    env_value = os.environ.get(RAG_DB_ENV)
    return Path(env_value) if env_value else DEFAULT_RAG_DB_PATH


def open_rag_index(db_path: str | Path):
    """Opens (once) and caches the RagIndex at db_path. Raises
    FileNotFoundError immediately if the index doesn't exist -- rag_presolve
    must fail loudly at startup rather than silently running the cheap panel
    without retrieval, which would produce a result file that LOOKS like a
    RAG pilot but isn't one. (Contrast quorumqa.tools.mcp_server.
    search_corpus, whose missing-DB contract is a clean ok:False no-op --
    correct for an OPTIONAL Verifier tool, wrong for a lever whose entire
    point is retrieval.)"""
    from quorumqa.rag import store

    key = str(Path(db_path).resolve())
    cached = _rag_index_cache.get(key)
    if cached is not None:
        return cached
    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"rag_presolve lever requires a built RAG index at {db_path}, but no file exists there. "
            "Refusing to run rag_presolve without retrieval -- build the index first "
            "(see docs/rag-corpus-notes.md, benchmark/build_rag_index_preembedded.py) or point "
            f"--rag-db / the {RAG_DB_ENV} env var at an existing one."
        )
    index = store.RagIndex.open(db_path)
    _rag_index_cache[key] = index
    return index


def build_rag_presolve_config(db_path: str | Path, k: int = DEFAULT_RAG_K) -> RagPresolveConfig:
    """Opens the index (fail-loud, see open_rag_index) and resolves the
    query embedder matching whichever embedding model the index was
    actually built with -- the same quorumqa.rag.embeddings.get_query_embedder
    dispatch quorumqa.tools.mcp_server.search_corpus uses, so the mxbai
    encoder is picked automatically for the G0.5 pre-embedded corpus rather
    than assuming the from-scratch build's default bge-small."""
    from quorumqa.rag import store
    from quorumqa.rag.embeddings import get_query_embedder

    index = open_rag_index(db_path)
    embedding_model = store.get_progress(index.conn).get("embedding_model")
    try:
        embedder = get_query_embedder(embedding_model)
    except ImportError:
        # Dense deps (sentence-transformers/torch) missing -- degrade to
        # FTS5-only, same as mcp_server.search_corpus, rather than failing
        # the whole lever over an optional dependency.
        log.warning("rag_presolve: dense embedding deps unavailable, degrading to FTS5-only retrieval")
        embedder = None
    snapshot_id = store.get_progress(index.conn).get("snapshot_id") or "unknown"
    return RagPresolveConfig(index=index, embedder=embedder, k=k, snapshot_id=snapshot_id, db_path=Path(db_path))


def retrieve_rag_evidence(rag: RagPresolveConfig, question: str, k: int | None = None) -> list[dict]:
    """`k` overrides `rag.k` for this one call (used by rag_recursive's R2
    retrieval, which is always top-3 regardless of R1's configured k); omit
    it to keep R1's existing behavior (search at rag.k) unchanged."""
    query_vector = rag.embedder(question) if rag.embedder is not None else None
    return rag.index.search(question, query_vector, k=k if k is not None else rag.k)


def build_evidence_block(results: list[dict], word_budget: int = RAG_EVIDENCE_WORD_BUDGET) -> str:
    """"Relevant reference passages (may or may not be useful):\\n[title]
    snippet...\\n..." per docs/recursive-rag-plan.md's R1 spec. Snippets are
    truncated to an even share of `word_budget` across however many
    passages were retrieved, so total injected context stays bounded
    regardless of k."""
    if not results:
        return ""
    per_passage_budget = max(1, word_budget // len(results))
    lines = ["Relevant reference passages (may or may not be useful):"]
    for r in results:
        snippet = " ".join(r["text"].split()[:per_passage_budget])
        lines.append(f"[{r['title']}] {snippet}...")
    return "\n".join(lines)


def _solve_one_rag(client, question, choices, lens, evidence_block, model=MECHANICAL_MODEL, temperature=0.4):
    """Identical to solver._solve_one -- same system prompt (SOLVER_SYSTEM +
    lens), same model/thinking/temperature defaults, same JSON contract --
    except the user turn is prefixed with the retrieved-evidence block (if
    any). Verbatim copy of _solve_one's user-prompt construction plus the
    prefix, same caveat as every other lever's copied solver helper in this
    file: if solver.py's user-prompt shape ever changes, this copy must
    change with it."""
    choice_block = "\n".join(f"{letter}) {c}" for letter, c in zip("ABCD", choices))
    evidence_prefix = f"{evidence_block}\n\n" if evidence_block else ""
    user = (
        f"{evidence_prefix}Question: {question}\n\nChoices:\n{choice_block}\n\n"
        'JSON shape: {"letter": "A|B|C|D", "confidence": 0.0-1.0, "reasoning": "..."}\n'
        "Keep reasoning to at most 3 sentences -- your answer letter matters more than showing full working."
    )
    result = client.chat_json(model=model, system=f"{SOLVER_SYSTEM}\n\n{lens}", user=user, role="solver", thinking=False, temperature=temperature, retries=2)
    letter = str(result.data.get("letter", "")).strip().upper()[:1]
    answer = SolverAnswer(
        letter=letter if letter in "ABCD" else "A",
        confidence=float(result.data.get("confidence", 0.5)),
        reasoning=str(result.data.get("reasoning", "")),
        lens=lens,
    )
    return answer, result.usage


def build_disputed_step_query(skeptic_rebuttal: SkepticRebuttal, solver_answers: list[SolverAnswer]) -> str:
    """The R2 query (docs/recursive-rag-plan.md section 2): the Skeptic's
    NAMED disputed step (plus its argument) and the solvers' divergent
    claims -- the plurality and dissenting letters/reasoning already sitting
    in solver_answers on a split -- concatenated into one query far sharper
    than the raw question R1 retrieved against. This is the "recursive"
    step: retrieval driven by deliberation state, not the original prompt."""
    parts = [skeptic_rebuttal.disputed_step]
    if skeptic_rebuttal.argument:
        parts.append(skeptic_rebuttal.argument)
    parts.extend(f"{a.letter}: {a.reasoning}" for a in solver_answers if a.reasoning)
    return " ".join(p for p in parts if p).strip()


async def solve_all_rag_presolve(client, question, choices, rag: RagPresolveConfig):
    """Retrieves top-k passages for the QUESTION ONCE (not once per solver
    seat), builds one evidence block, and gives every one of the three
    shipped-tier solver seats (same model/lenses/temperatures as solve_all)
    the same evidence block. Returns (solver_pairs, retrieved_titles) -- the
    titles are for logging only (see run_question_lever), not part of the
    QuestionResult schema."""
    results = await asyncio.to_thread(retrieve_rag_evidence, rag, question)
    evidence_block = build_evidence_block(results)
    titles = [r["title"] for r in results]
    lenses = _lenses_for(3)
    tasks = [
        asyncio.to_thread(_solve_one_rag, client, question, choices, lenses[i], evidence_block, MECHANICAL_MODEL, SOLVER_TEMPERATURES[i])
        for i in range(3)
    ]
    solver_pairs = list(await asyncio.gather(*tasks))
    return solver_pairs, titles


async def _tribunal(client, tool_session, item, solver_answers, plurality_letter, calls, start, adjudicator=adjudicate, rag: "RagPresolveConfig | None" = None):
    """The shipped escalation path (skeptic -> verifier -> judge), unchanged
    -- except WHICH function adjudicates is now a parameter, and (new, for
    rag_recursive) an optional `rag` config triggers R2 disputed-step
    retrieval (docs/recursive-rag-plan.md section 2) between the skeptic and
    verifier calls. `adjudicator` defaults to the shipped adjudicate()
    (qwen3.7-max via QwenClient/DashScope); the qwen38_judge lever passes
    adjudicate_qwen38 instead (qwen3.8-max-preview via the Token Plan
    transport). `rag` defaults to None, in which case this function behaves
    byte-for-byte as before (verify() gets evidence_block="", every existing
    caller -- the shipped engine, gate-replay, qwen38_judge -- is
    unaffected). Skeptic is untouched either way; Verifier gains ONLY the
    evidence_block grounding when rag is given -- its MCP tool calls still
    fire exactly as shipped."""
    skeptic_rebuttal, skeptic_usage = await asyncio.to_thread(
        rebut, client, item.question, item.choices, plurality_letter, solver_answers
    )
    calls.append(skeptic_usage)

    evidence_block = ""
    r2_query = None
    r2_titles: list[str] = []
    if rag is not None:
        r2_query = build_disputed_step_query(skeptic_rebuttal, solver_answers)
        r2_results = await asyncio.to_thread(retrieve_rag_evidence, rag, r2_query, RAG_R2_K)
        evidence_block = build_evidence_block(r2_results)
        r2_titles = [r["title"] for r in r2_results]
        log.info(
            "%s: rag_recursive R2 disputed-step query=%r retrieved %d passage(s): %s",
            item.question_id, r2_query, len(r2_titles), r2_titles,
        )

    verifier_findings, verifier_usages = await verify(
        client, tool_session, item.question, solver_answers, evidence_block=evidence_block
    )
    calls.extend(verifier_usages)
    verdict, judge_usage = await asyncio.to_thread(
        adjudicator, client, item.question, item.choices, solver_answers, skeptic_rebuttal, verifier_findings
    )
    calls.append(judge_usage)
    false_escalation = (verdict.final_letter == plurality_letter) and not verdict.overturned_plurality
    return QuestionResult(
        item=item, solver_answers=solver_answers, plurality_letter=plurality_letter,
        escalated=True, skeptic_rebuttal=skeptic_rebuttal, verifier_findings=verifier_findings,
        verdict=verdict, final_letter=verdict.final_letter, correct=(verdict.final_letter == item.correct_letter),
        false_escalation=false_escalation, calls=calls, latency_s=time.monotonic() - start,
        rag_r2_query=r2_query, rag_r2_titles=r2_titles,
    )


async def run_question_lever(client, tool_session, item: GPQAItem, lever: str, rag: "RagPresolveConfig | None" = None):
    start = time.monotonic()

    if lever in ("thinking", "combined", "thinking_gate"):
        solver_pairs = await solve_all_thinking_seat(client, item.question, item.choices)
    elif lever == "smart_gate":
        solver_pairs = await solve_all_smart_seat(client, item.question, item.choices, item.subject)
    elif lever == "chem_flagship_gate":
        solver_pairs = await solve_all_chem_flagship(client, item.question, item.choices, item.subject)
    elif lever == "chem_thinking_gate":
        solver_pairs = await solve_all_chem_thinking_gate(client, item.question, item.choices, item.subject)
    elif lever == "thinking_all":
        solver_pairs = await solve_all_thinking_all(client, item.question, item.choices)
    elif lever == "five":
        solver_pairs = await solve_all(client, item.question, item.choices, n=5)
    elif lever in ("flagship_panel", "flagship_panel_combined"):
        solver_pairs = await solve_all_flagship_panel(client, item.question, item.choices)
    elif lever == "qwen38_panel":
        solver_pairs = await solve_all_qwen38_panel(client, item.question, item.choices)
    elif lever in ("rag_presolve", "rag_recursive"):
        # rag_recursive's R1 pre-solve step is IDENTICAL to rag_presolve's --
        # same solve_all_rag_presolve call, same evidence block, same
        # solver seats. The only difference between the two levers is what
        # happens on escalation (see the tribunal dispatch below).
        if rag is None:
            raise ValueError(
                f"lever '{lever}' requires a RagPresolveConfig -- pass rag=... "
                "(see main_live/build_rag_presolve_config); refusing to silently run the cheap "
                "panel without retrieval"
            )
        solver_pairs, retrieved_titles = await solve_all_rag_presolve(client, item.question, item.choices, rag)
        log.info("%s: %s retrieved %d passage(s) (R1 pre-solve): %s", item.question_id, lever, len(retrieved_titles), retrieved_titles)
    else:
        solver_pairs = await solve_all(client, item.question, item.choices)

    solver_answers = [a for a, _ in solver_pairs]
    calls = [u for _, u in solver_pairs]
    plurality_letter, unanimous = _plurality(solver_answers)

    force_escalate = False
    gate_note = None
    if unanimous:
        if lever in ("subject", "combined", "flagship_panel_combined") and item.subject == "Organic Chemistry":
            force_escalate = True
            gate_note = "subject-forced"
        elif lever in ("gate", "thinking_gate", "smart_gate", "chem_flagship_gate", "chem_thinking_gate"):
            doubt, reason, gate_usage = second_opinion_gate(client, item.question, item.choices, solver_answers, plurality_letter)
            calls.append(gate_usage)
            if doubt:
                force_escalate = True
                gate_note = f"gate-flagged: {reason}"

    if unanimous and not force_escalate:
        return QuestionResult(
            item=item, solver_answers=solver_answers, plurality_letter=plurality_letter,
            escalated=False, final_letter=plurality_letter, correct=(plurality_letter == item.correct_letter),
            calls=calls, latency_s=time.monotonic() - start,
        ), gate_note

    if lever == "qwen38_judge":
        result = await _tribunal(
            client, tool_session, item, solver_answers, plurality_letter, calls, start,
            adjudicator=adjudicate_qwen38,
        )
    elif lever == "rag_recursive":
        # The R2 recursion: rag is passed through so _tribunal retrieves a
        # SECOND time from the skeptic's disputed step before the verifier
        # runs. rag is guaranteed non-None here -- the dispatch above
        # already raised ValueError if it were missing.
        result = await _tribunal(client, tool_session, item, solver_answers, plurality_letter, calls, start, rag=rag)
    else:
        result = await _tribunal(client, tool_session, item, solver_answers, plurality_letter, calls, start)
    return result, gate_note


async def _run_one(client, tool_session, item, semaphore, lever, rag: "RagPresolveConfig | None" = None):
    try:
        async with semaphore:
            result, note = await run_question_lever(client, tool_session, item, lever, rag)
    except Exception:
        log.exception("%s: DROPPED after unrecoverable error", item.question_id)
        return None
    log.info(
        "%s [%s]: final=%s(%s, escalated=%s%s) cost=$%.5f",
        item.question_id, lever, result.final_letter,
        "correct" if result.correct else "wrong", result.escalated,
        f", {note}" if note else "",
        result.total_cost_usd,
    )
    return result


def _build_output_row(result, lever: str, seed: int, dataset: str, rag_config: "RagPresolveConfig | None" = None) -> dict:
    """The per-question JSONL row every lever writes. For rag_presolve and
    rag_recursive, also carries the firewall labeling required by docs/
    recursive-rag-plan.md section 4: rag="ON" plus the exact rag_snapshot_id
    read from the OPEN index's build_progress row at run start (see
    build_rag_presolve_config) -- never fabricated, never presented next
    to a non-RAG number as if it were the same mode. rag_recursive ADDS a
    second marker on top: rag_r2="ON"/"OFF" records whether the R2
    disputed-step retrieval actually fired for THIS question (only escalated
    questions ever trigger it -- see _tribunal), plus the R2 query/titles it
    retrieved when it did. Every other lever's row shape is completely
    unchanged (no "rag"/"rag_r2" keys at all)."""
    row = {"engine": result.model_dump(), "lever": lever, "seed": seed, "dataset": dataset}
    if lever in ("rag_presolve", "rag_recursive"):
        row["rag"] = "ON"
        row["rag_snapshot_id"] = rag_config.snapshot_id if rag_config else None
        row["rag_k"] = rag_config.k if rag_config else None
        row["rag_db"] = str(rag_config.db_path) if rag_config else None
    if lever == "rag_recursive":
        r2_fired = bool(result.rag_r2_query)
        row["rag_r2"] = "ON" if r2_fired else "OFF"
        row["rag_r2_snapshot_id"] = (rag_config.snapshot_id if rag_config else None) if r2_fired else None
        row["rag_r2_k"] = RAG_R2_K
        row["rag_r2_query"] = result.rag_r2_query
        row["rag_r2_titles"] = result.rag_r2_titles
    return row


async def main_live(lever: str, n: int, seed: int, concurrency: int, out_path: Path, skip_huggingface: bool, dataset: str = "gpqa", rag_db: str | None = None, rag_k: int = DEFAULT_RAG_K):
    items = DATASET_LOADERS[dataset](n, seed, skip_huggingface)
    log.info("Loaded %d %s questions (seed=%d) for lever=%s", len(items), dataset, seed, lever)

    client = QwenClient()
    semaphore = asyncio.Semaphore(concurrency)

    rag_config = None
    if lever in ("rag_presolve", "rag_recursive"):
        # Fail loudly HERE, before any solver call is made, if the index
        # doesn't exist -- see open_rag_index's docstring. rag_recursive
        # reuses the exact same R1 index/config as rag_presolve; R2's
        # top-k=3 is fixed (RAG_R2_K), not derived from rag_k.
        resolved_rag_db = resolve_rag_db_path(rag_db)
        rag_config = build_rag_presolve_config(resolved_rag_db, k=rag_k)
        log.info(
            "%s: index=%s snapshot=%s k=%d dense=%s",
            lever, resolved_rag_db, rag_config.snapshot_id, rag_k, rag_config.embedder is not None,
        )

    results = []
    async with verifier_tool_session() as tool_session:
        tasks = [asyncio.ensure_future(_run_one(client, tool_session, item, semaphore, lever, rag_config)) for item in items]
        for coro in asyncio.as_completed(tasks):
            outcome = await coro
            if outcome is not None:
                results.append(outcome)

    dropped = len(items) - len(results)
    if dropped:
        log.warning("%d/%d questions dropped due to unrecoverable errors", dropped, len(items))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(_build_output_row(r, lever, seed, dataset, rag_config)) + "\n")
    log.info("Wrote %d results to %s", len(results), out_path)


async def _run_one_baseline(client, item, semaphore):
    try:
        async with semaphore:
            baseline = await asyncio.to_thread(solve_single_agent, client, item)
    except Exception:
        log.exception("%s: DROPPED after unrecoverable error", item.question_id)
        return None
    log.info("%s [baseline]: %s(%s) cost=$%.5f", item.question_id, baseline.answer_letter,
              "correct" if baseline.correct else "wrong", baseline.total_cost_usd)
    return baseline


async def main_baseline(n: int, seed: int, concurrency: int, out_path: Path, skip_huggingface: bool, dataset: str = "gpqa"):
    """Fresh-seed flagship baseline -- needed because the frozen baseline
    number only covers seed=42, and Lever 3/2 replication at seed=7 needs its
    own fair comparison point, not a cross-seed borrow."""
    items = DATASET_LOADERS[dataset](n, seed, skip_huggingface)
    client = QwenClient()
    semaphore = asyncio.Semaphore(concurrency)
    results = []
    tasks = [asyncio.ensure_future(_run_one_baseline(client, item, semaphore)) for item in items]
    for coro in asyncio.as_completed(tasks):
        outcome = await coro
        if outcome is not None:
            results.append(outcome)
    dropped = len(items) - len(results)
    if dropped:
        log.warning("%d/%d questions dropped", dropped, len(items))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({"baseline": r.model_dump(), "seed": seed}) + "\n")
    log.info("Wrote %d baseline results to %s", len(results), out_path)


async def main_gate_replay(frozen_path: Path, out_path: Path):
    """Cheap validation: replay the second-opinion gate against SAVED solver
    answers from the frozen run (no new solver calls). For unanimous cases
    the gate flags, actually run the tribunal to see if it self-corrects."""
    client = QwenClient()
    records = [json.loads(l) for l in frozen_path.open(encoding="utf-8")]
    unanimous = [r["engine"] for r in records if not r["engine"]["escalated"]]
    log.info("Replaying gate against %d saved unanimous cases (%d wrong, %d correct)",
              len(unanimous), sum(1 for e in unanimous if not e["correct"]), sum(1 for e in unanimous if e["correct"]))

    out = []
    async with verifier_tool_session() as tool_session:
        for e in unanimous:
            item = GPQAItem(**e["item"])
            solver_answers = [SolverAnswer(**s) for s in e["solver_answers"]]
            plurality_letter = e["plurality_letter"]
            was_correct = e["correct"]

            doubt, reason, gate_usage = second_opinion_gate(client, item.question, item.choices, solver_answers, plurality_letter)
            calls = [gate_usage]
            row = {
                "question_id": item.question_id, "subject": item.subject,
                "was_unanimous_correct": was_correct, "plurality_letter": plurality_letter,
                "correct_letter": item.correct_letter, "gate_doubt": doubt, "gate_reason": reason,
                "gate_cost_usd": gate_usage.cost_usd,
            }

            if doubt:
                start = time.monotonic()
                tribunal_result = await _tribunal(client, tool_session, item, solver_answers, plurality_letter, calls, start)
                row["escalated_after_gate"] = True
                row["tribunal_final_letter"] = tribunal_result.final_letter
                row["tribunal_correct"] = tribunal_result.correct
                row["tribunal_cost_usd"] = tribunal_result.total_cost_usd
                log.info("%s: WAS %s -> gate doubt (%s) -> tribunal ruled %s (%s)",
                         item.question_id, "correct" if was_correct else "WRONG", reason,
                         tribunal_result.final_letter, "correct" if tribunal_result.correct else "wrong")
            else:
                row["escalated_after_gate"] = False
                log.info("%s: WAS %s -> gate confident, no escalation", item.question_id, "correct" if was_correct else "WRONG")
            out.append(row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row) + "\n")
    log.info("Wrote %d gate-replay rows to %s", len(out), out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lever", required=True, choices=["gate", "thinking", "subject", "five", "combined", "thinking_all", "thinking_gate", "smart_gate", "chem_flagship_gate", "chem_thinking_gate", "flagship_panel", "flagship_panel_combined", "qwen38_judge", "qwen38_panel", "rag_presolve", "rag_recursive", "control", "baseline", "gate-replay"])
    parser.add_argument("--n", type=int, default=90)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--skip-huggingface", action="store_true")
    parser.add_argument("--dataset", type=str, default="gpqa", choices=list(DATASET_LOADERS.keys()),
                         help="Which question set to run the lever against. Every lever works on every "
                              "dataset unchanged -- they only vary HOW a question already loaded as a "
                              "GPQAItem gets answered, not where it came from.")
    parser.add_argument("--rag-db", type=str, default=None,
                         help=f"rag_presolve/rag_recursive only: RAG index sqlite3 DB path (default: ${RAG_DB_ENV} env "
                              f"var if set, else {DEFAULT_RAG_DB_PATH})")
    parser.add_argument("--rag-k", type=int, default=DEFAULT_RAG_K,
                         help=f"rag_presolve/rag_recursive only: top-k passages retrieved per question for R1 "
                              f"pre-solve retrieval (default {DEFAULT_RAG_K}). rag_recursive's R2 disputed-step "
                              f"retrieval is always top-{RAG_R2_K}, fixed, not controlled by this flag.")
    args = parser.parse_args()

    if args.lever == "gate-replay":
        out_path = Path(args.out) if args.out else RESULTS_DIR / "lever_gate_replay.jsonl"
        asyncio.run(main_gate_replay(RESULTS_DIR / "full_run2.jsonl", out_path))
    elif args.lever == "baseline":
        out_path = Path(args.out) if args.out else RESULTS_DIR / f"lever_baseline_{args.dataset}_seed{args.seed}.jsonl"
        asyncio.run(main_baseline(args.n, args.seed, args.concurrency, out_path, args.skip_huggingface, args.dataset))
    else:
        out_path = Path(args.out) if args.out else RESULTS_DIR / f"lever_{args.lever}_{args.dataset}_seed{args.seed}.jsonl"
        asyncio.run(main_live(args.lever, args.n, args.seed, args.concurrency, out_path, args.skip_huggingface, args.dataset, args.rag_db, args.rag_k))
