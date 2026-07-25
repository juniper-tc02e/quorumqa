"""The SimpleQA factuality engine: retrieve -> answer -> verify-against-
evidence -> ABSTAIN if unsupported. docs/capability-roadmap.md section 3.12
is authoritative on the thesis (unbounded free-text answer space means
hallucinating seats rarely coincide, so unanimity is a near-sufficient
correctness signal -- the exact inverse of 4-choice MC) and on the build
honesty note: this is a SECOND engine path, not an extension of the shipped
GPQA engine. `schemas.py`'s `QuestionResult`/`JudgeVerdict` hard-require a
`final_letter: str` with no abstain sentinel and every prompt in the shipped
engine formats choices with `zip("ABCD", ...)` -- none of that applies to
free text, so this module builds its own dataclass-free dict-row contract
(mirrors benchmark/math_open_engine.py's dict-row style, the closest
existing precedent: also a fork off the 4-choice engine, also open-answer).

THREE required pieces, in the order a question actually flows through them:

  1. solve_single_factual -- the required single-agent baseline: one
     flagship call, JSON {"answer", "abstain", "reasoning"}.
  2. solve_panel_factual -- N solvers propose free-text answers (optionally
     given retrieved evidence); answers are clustered by normalized-string
     equivalence (normalize_answer -- see its docstring for the DELIBERATE
     limitation: no semantic clustering, conservative string normalization
     only); a clear-margin cluster wins outright, otherwise a flagship judge
     (judge_factual) adjudicates or abstains directly; whatever candidate
     answer survives is then run through verify_claim_against_evidence
     against the SAME retrieved passages -- unsupported flips the item to
     ABSTAIN as a genuine terminal state, never scored as correct.
  3. grade_simpleqa / exact_match_normalized / compute_simpleqa_metrics --
     BUILD 3: the official model grader (fallible, verbatim published
     prompt) and the deterministic zero-cost floor. See the "GRADING"
     section below for the headline-vs-floor distinction; also documented
     in benchmark/results/simpleqa_build_notes.md.

RETRIEVAL: reuses benchmark.lever_experiments' existing RAG plumbing
(RagPresolveConfig, retrieve_rag_evidence, build_evidence_block,
build_rag_presolve_config, resolve_rag_db_path) rather than reinventing it --
same pre-embedded STEM/US-law-Wikipedia index every rag_* lever already
opens. The one deliberate CONTRACT DIFFERENCE from rag_presolve/rag_recursive
(which fail loudly at startup if the index is missing, because retrieval IS
the point of those levers): this engine's missing-index behavior is to log
and proceed WITHOUT evidence, never crash -- see try_open_factuality_rag.
Retrieval here is part of the architecture bet, not a hard precondition for
the panel to run at all; whether it should be treated as a hard precondition
for a HEADLINE ACCURACY CLAIM is a separate, larger question (the corpus is
STEM/US-law Wikipedia, SimpleQA asks broad general trivia -- see
simpleqa_build_notes.md's retrieval-gate section, mirroring the exact
corpus-mismatch failure LEXam already measured).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time

from quorumqa.config import JUDGE_MODEL, MECHANICAL_MODEL, ORCHESTRATOR_MODEL, SOLVER_TEMPERATURES
from quorumqa.engine.solver import _lenses_for
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import CallUsage

from benchmark.lever_experiments import (
    RagPresolveConfig,
    build_evidence_block,
    build_rag_presolve_config,
    resolve_rag_db_path,
    retrieve_rag_evidence,
)
from benchmark.load_simpleqa import SimpleQAItem

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retrieval -- reused plumbing, opposite missing-index contract from
# rag_presolve/rag_recursive (log-and-degrade, not fail-loud). See module
# docstring.
# ---------------------------------------------------------------------------


def try_open_factuality_rag(db_path=None, k: int = 5) -> RagPresolveConfig | None:
    """Best-effort index open. Returns None (never raises) if the index is
    missing, unreadable, or its embedding deps are unavailable -- every
    failure mode is caught broadly on purpose, because "log and proceed
    without evidence" must hold regardless of WHICH thing about the index
    went wrong, not just a missing file. Callers pass the returned
    RagPresolveConfig (or None) straight into solve_panel_factual's `rag`
    parameter."""
    resolved = resolve_rag_db_path(db_path)
    try:
        return build_rag_presolve_config(resolved, k=k)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad, see docstring
        log.warning(
            "factuality engine: RAG index unavailable at %s (%s: %s) -- proceeding WITHOUT evidence",
            resolved, type(exc).__name__, exc,
        )
        return None


# ---------------------------------------------------------------------------
# 1. Single-agent baseline.
# ---------------------------------------------------------------------------

BASELINE_SYSTEM = (
    "You are answering a short, factual trivia-style question with a single "
    "known correct answer. If you know the answer with reasonable "
    "confidence, give it concisely. If you are NOT confident you know the "
    "correct answer, abstain honestly instead of guessing -- a wrong guess "
    "is worse than admitting you don't know."
)


def solve_single_factual(client: QwenClient, item: SimpleQAItem, model: str = ORCHESTRATOR_MODEL, thinking: bool = True) -> dict:
    """The required single-agent BASELINE: one flagship-tier call, JSON
    contract {"answer", "abstain", "reasoning"}. `correct` is graded via the
    deterministic exact_match_normalized floor (see the GRADING section) --
    NOT the official model grader, which is a separate, explicit re-grading
    pass (grade_simpleqa) a caller runs over the same rows afterward; see
    simpleqa_build_notes.md for why the two are not interchangeable."""
    start = time.monotonic()
    user = (
        f"Question: {item.question}\n\n"
        'JSON shape: {"answer": "...", "abstain": true|false, "reasoning": "..."}\n'
        "Set abstain=true and leave answer empty if you do not know or are not "
        "reasonably confident; otherwise give your single best concise answer "
        "(a short phrase, not a full sentence)."
    )
    result = client.chat_json(model=model, system=BASELINE_SYSTEM, user=user, role="baseline", thinking=thinking, temperature=0.3, retries=2)
    abstained = bool(result.data.get("abstain", False))
    answer = "" if abstained else str(result.data.get("answer", "")).strip()
    reasoning = str(result.data.get("reasoning", ""))
    correct = (not abstained) and exact_match_normalized(item.gold_answer, answer)
    return {
        "question_id": item.question_id,
        "gold_answer": item.gold_answer,
        "final_answer": answer,
        "abstained": abstained,
        "correct": correct,
        "reasoning": reasoning,
        "calls": [result.usage.model_dump()],
        "latency_s": time.monotonic() - start,
    }


# ---------------------------------------------------------------------------
# 2. Panel -- free-text clustering (conservative normalizer, no semantic
# clustering), escalation on no-clear-margin, citation-check gate before
# any answer is accepted.
# ---------------------------------------------------------------------------

_ARTICLE_RE = re.compile(r"\b(a|an|the)\b")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_answer(s: str) -> str:
    """Conservative free-text normalizer for clustering: casefold, strip
    punctuation, strip English articles (a/an/the) as whole words, collapse
    whitespace. DELIBERATE LIMITATION, stated per the build spec: this does
    NOT attempt semantic clustering with a model -- "JFK" and "John F.
    Kennedy" normalize to two different strings and will NOT cluster
    together, even though a human (and the official grader, grade_simpleqa)
    would call them the same answer. That is a real source of both false
    escalations (a genuine unanimous answer split into look-alike singleton
    clusters purely by surface form) and, more importantly, of UNDER-
    counted plurality margins -- never inflated ones, since this normalizer
    only ever MERGES answers that are already string-close, never merges
    answers that are semantically equal but written differently. See
    simpleqa_build_notes.md for the honest accounting of this limitation
    against the headline metric."""
    if not s:
        return ""
    s = s.casefold()
    s = _PUNCT_RE.sub(" ", s)
    s = _ARTICLE_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def _cluster_free_text(answers: list[str]) -> list[list[int]]:
    """Union-find clustering: answers i and j land in the same cluster iff
    normalize_answer(answers[i]) == normalize_answer(answers[j]) and that
    normalized string is non-empty (two blank/empty answers are NOT treated
    as agreeing with each other). Returns clusters sorted largest-first."""
    n = len(answers)
    normed = [normalize_answer(a) for a in answers]
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
            if normed[i] == normed[j] and normed[i] != "":
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=len, reverse=True)


SOLVER_SYSTEM = (
    "You are one independent solver in a panel answering a short factual "
    "trivia-style question. Give your single best concise answer (a short "
    "phrase, not a full sentence) with an honest confidence score -- you "
    "cannot see any other solver's answer."
)


def _solve_one_factual(
    client: QwenClient, question: str, evidence_block: str, lens: str, model: str, temperature: float, thinking: bool,
) -> tuple[str, float, str, CallUsage]:
    evidence_prefix = f"{evidence_block}\n\n" if evidence_block else ""
    user = (
        f"{evidence_prefix}Question: {question}\n\n"
        'JSON shape: {"answer": "...", "confidence": 0.0-1.0, "reasoning": "..."}\n'
        "Keep reasoning to at most 2 sentences; the answer field must be a "
        "short factual phrase, not a full sentence."
    )
    result = client.chat_json(model=model, system=f"{SOLVER_SYSTEM}\n\n{lens}", user=user, role="solver", thinking=thinking, temperature=temperature, retries=2)
    answer = str(result.data.get("answer", "")).strip()
    confidence = float(result.data.get("confidence", 0.5))
    reasoning = str(result.data.get("reasoning", ""))
    return answer, confidence, reasoning, result.usage


async def _solve_panel_answers_async(
    client: QwenClient, question: str, evidence_block: str, lenses: list[str], solver_model: str, solver_thinking: bool,
) -> list[tuple[str, float, str, CallUsage]]:
    tasks = [
        asyncio.to_thread(
            _solve_one_factual, client, question, evidence_block, lenses[i],
            solver_model, SOLVER_TEMPERATURES[i % len(SOLVER_TEMPERATURES)], solver_thinking,
        )
        for i in range(len(lenses))
    ]
    return list(await asyncio.gather(*tasks))


JUDGE_SYSTEM = (
    "You are the final adjudicator reviewing independent solvers who gave "
    "DISAGREEING free-text answers to a short factual trivia-style "
    "question. Decide the single best answer, or abstain if none of the "
    "given answers look right and you are not confident of the correct one "
    "yourself. A confident wrong guess is worse than an honest abstain."
)


def judge_factual(
    client: QwenClient, question: str, evidence_block: str, solver_answers: list[tuple[str, float, str]], model: str = JUDGE_MODEL,
) -> tuple[str, bool, str, CallUsage]:
    """Adjudicates a no-clear-margin split. `solver_answers` is [(answer,
    confidence, reasoning), ...]. Returns (answer, abstain, reasoning,
    usage) -- same {"answer","abstain","reasoning"} JSON contract as
    solve_single_factual, so a judge that itself doesn't know the answer can
    terminate the item as ABSTAIN directly rather than being forced to pick
    among candidates it does not trust."""
    transcript = "\n\n".join(
        f"Solver {i + 1} answered {answer!r} (confidence {confidence:.2f}): {reasoning}"
        for i, (answer, confidence, reasoning) in enumerate(solver_answers)
    )
    evidence_prefix = f"{evidence_block}\n\n" if evidence_block else ""
    user = (
        f"{evidence_prefix}Question: {question}\n\n"
        f"Independent solvers disagreed:\n\n{transcript}\n\n"
        'JSON shape: {"answer": "...", "abstain": true|false, "reasoning": "..."}\n'
        "Decide the single correct answer yourself, or abstain."
    )
    result = client.chat_json(model=model, system=JUDGE_SYSTEM, user=user, role="judge", thinking=True, temperature=0.3, retries=2)
    abstained = bool(result.data.get("abstain", False))
    answer = "" if abstained else str(result.data.get("answer", "")).strip()
    reasoning = str(result.data.get("reasoning", ""))
    return answer, abstained, reasoning, result.usage


VERIFY_SYSTEM = (
    "You are a strict fact-checker. Given a proposed answer and a set of "
    "retrieved reference passages, decide whether the passages ACTUALLY "
    "SUPPORT the proposed answer -- quote the exact supporting sentence or "
    "fragment if so. If the passages are silent, irrelevant to the "
    "question, or contradict the proposed answer, mark it unsupported. "
    "Judge only by what the passages say -- do not use outside knowledge to "
    "rescue an answer the passages do not actually back up."
)


def verify_claim_against_evidence(
    client: QwenClient, answer: str, passages: list[dict], question: str = "", model: str = MECHANICAL_MODEL,
) -> tuple[bool, str, str, CallUsage | None]:
    """The citation-check step: given the proposed `answer` and the
    retrieved `passages` (the same list[dict] shape retrieve_rag_evidence
    returns -- title/text/score/...), decides {"supported", "quote",
    "reason"}. Returns (supported, quote, reason, usage). If `passages` is
    empty, short-circuits to (False, "", "no evidence passages available to
    verify against", None) WITHOUT a network call -- usage=None signals "no
    live call was made" to a caller. Callers that want "no evidence
    retrieved" to mean "unverified" rather than "unsupported" (this
    engine's own solve_panel_factual does exactly that -- see its
    docstring) must check for empty `passages` themselves BEFORE calling
    this function, since this function's own empty-input fallback returns
    supported=False, not None -- it has no None state of its own; the
    caller's choice of not calling it at all is what produces "unverified"
    at the row level.

    `question` is not in the required minimal signature
    (client, answer, passages) but is accepted as an optional 4th arg since
    "does the evidence support this answer" is not fully well-posed without
    knowing what the answer is claiming to answer."""
    if not passages:
        return False, "", "no evidence passages available to verify against", None
    evidence_block = build_evidence_block(passages)
    question_line = f"Question: {question}\n" if question else ""
    user = (
        f"{question_line}Proposed answer: {answer}\n\n"
        f"{evidence_block}\n\n"
        'JSON shape: {"supported": true|false, "quote": "...", "reason": "..."}'
    )
    result = client.chat_json(model=model, system=VERIFY_SYSTEM, user=user, role="verifier", thinking=False, temperature=0.2, retries=2)
    supported = bool(result.data.get("supported", False))
    quote = str(result.data.get("quote", ""))
    reason = str(result.data.get("reason", ""))
    return supported, quote, reason, result.usage


def solve_panel_factual(
    client: QwenClient,
    item: SimpleQAItem,
    k_retrieval: int = 5,
    solver_model: str = ORCHESTRATOR_MODEL,
    solver_thinking: bool = True,
    n: int = 3,
    margin_threshold: int = 1,
    rag: RagPresolveConfig | None = None,
    verify_model: str = MECHANICAL_MODEL,
) -> dict:
    """The ENGINE. `solver_model`/`solver_thinking` default to the flagship
    (mirrors math_open_engine.solve_panel_math's default: this axis's own
    comparator is "our own flagship", not the shipped cheap-tier engine --
    pass MECHANICAL_MODEL/False for a cheap-tier variant).

    Flow:
      1. If `rag` is given, retrieve top-k_retrieval passages for the
         question ONCE (shared across all N solver seats, same pattern as
         solve_all_rag_presolve) and build one evidence block. Retrieval
         failure here (a broken/degraded index passed in) is caught and
         logged, never raised -- "log and proceed without evidence" holds
         even if the caller's own try_open_factuality_rag call succeeded
         but a later .search() call fails.
      2. N solvers propose free-text (answer, confidence, reasoning),
         optionally given the evidence block.
      3. Cluster by normalize_answer equivalence (_cluster_free_text). The
         top cluster's size minus the runner-up's size is `cluster_margin`.
         margin_threshold=1 mirrors math_open_engine.solve_panel_math's own
         plurality rule at n=3 (>=2-of-3 agreeing wins outright; only a
         full n-way split, margin=0, escalates) -- pass a higher threshold
         (e.g. 2, matching solve_selfconsistency_math's SC@N default) for a
         stricter unanimity-leaning bar, which is the more direct way to
         measure P(wrong | unanimous) on this axis per docs/capability-
         roadmap.md section 3.12.
      4. No clear margin -> escalated=True -> judge_factual reviews all N
         candidates (+ evidence) and either picks one or abstains directly.
         Clear margin -> escalated=False -> the top cluster's representative
         answer is the candidate, no judge call.
      5. Whatever candidate answer survives step 4 (unless the judge itself
         already abstained) is run through verify_claim_against_evidence
         against the SAME retrieved passages. supported=False -> ABSTAIN
         (final_answer="", abstained=True) -- a genuine terminal state,
         never scored as correct. No passages retrieved at all (index
         missing, or this question retrieved zero results) -> verification
         is SKIPPED entirely (supported=None in the output row) rather than
         forced to False -- missing evidence must never be conflated with
         evidence that was checked and found wanting.
      6. `correct` is the deterministic exact_match_normalized floor (see
         GRADING section) -- re-grade the same rows with grade_simpleqa for
         the headline metric.
    """
    start = time.monotonic()

    passages: list[dict] = []
    evidence_block = ""
    if rag is not None:
        try:
            passages = retrieve_rag_evidence(rag, item.question, k=k_retrieval)
            evidence_block = build_evidence_block(passages)
        except Exception as exc:  # noqa: BLE001 -- see try_open_factuality_rag
            log.warning(
                "factuality panel %s: retrieval failed, proceeding WITHOUT evidence: %s: %s",
                item.question_id, type(exc).__name__, exc,
            )
            passages, evidence_block = [], ""
    retrieval_log = [{"title": p["title"], "score": p["score"]} for p in passages]

    lenses = _lenses_for(n)
    triples = asyncio.run(_solve_panel_answers_async(client, item.question, evidence_block, lenses, solver_model, solver_thinking))
    answers = [t[0] for t in triples]
    calls: list[CallUsage] = [t[3] for t in triples]

    groups = _cluster_free_text(answers)
    top = groups[0]
    runner_up_size = len(groups[1]) if len(groups) > 1 else 0
    cluster_margin = len(top) - runner_up_size
    n_clusters = len(groups)

    escalated = cluster_margin < margin_threshold
    judge_reasoning = None
    judge_abstained = False
    if escalated:
        candidate_answer, judge_abstained, judge_reasoning, judge_usage = judge_factual(
            client, item.question, evidence_block, [(t[0], t[1], t[2]) for t in triples],
        )
        calls.append(judge_usage)
    else:
        candidate_answer = triples[top[0]][0]

    supported = None
    verify_quote = verify_reason = None
    if judge_abstained:
        abstained = True
        final_answer = ""
    else:
        if passages:
            supported, verify_quote, verify_reason, verify_usage = verify_claim_against_evidence(
                client, candidate_answer, passages, question=item.question, model=verify_model,
            )
            if verify_usage is not None:
                calls.append(verify_usage)
        abstained = supported is False
        final_answer = "" if abstained else candidate_answer

    correct = (not abstained) and exact_match_normalized(item.gold_answer, final_answer)

    return {
        "question_id": item.question_id,
        "gold_answer": item.gold_answer,
        "final_answer": final_answer,
        "abstained": abstained,
        "correct": correct,
        "supported": supported,
        "n_clusters": n_clusters,
        "cluster_margin": cluster_margin,
        "escalated": escalated,
        "solver_model": solver_model,
        "retrieval": retrieval_log,
        "verify_quote": verify_quote,
        "verify_reason": verify_reason,
        "judge_reasoning": judge_reasoning,
        "solver_answers": [
            {"answer": t[0], "confidence": t[1], "reasoning": t[2], "lens": lens}
            for t, lens in zip(triples, lenses)
        ],
        "calls": [c.model_dump() for c in calls],
        "latency_s": time.monotonic() - start,
    }


# ---------------------------------------------------------------------------
# 3. GRADING (BUILD 3).
#
# Two graders, not interchangeable:
#   - exact_match_normalized: deterministic, zero-cost, ALWAYS available.
#     Reuses normalize_answer (the SAME conservative normalizer clustering
#     uses -- see its docstring). This is a LOWER BOUND on accuracy, not the
#     metric: SimpleQA gold answers and genuinely correct paraphrases
#     routinely differ in surface form ("JFK" vs "John F. Kennedy", "1963"
#     vs "November 22, 1963", "Michelle" vs "Michelle Obama") in ways a
#     string check cannot see, so it UNDER-counts correctness. It never
#     over-counts (a match after this normalization is always a genuine
#     string match).
#   - grade_simpleqa: the OFFICIAL SimpleQA grader -- a MODEL call using
#     OpenAI's published GRADER_TEMPLATE prompt, reproduced verbatim below
#     (fetched directly from openai/simple-evals' simpleqa_eval.py on
#     2026-07-25, MIT license -- see benchmark/results/
#     simpleqa_build_notes.md for the exact source URL and fetch date).
#     This is a MODEL grader, therefore FALLIBLE, unlike
#     benchmark.math_grade.grade's deterministic CAS-equivalence check: its
#     verdict depends on which model is asked to grade and is not
#     guaranteed to reproduce across seeds/runs. SimpleQA's own paper uses
#     GPT-4 as the reference grader; this repo has no access to that model
#     and substitutes ORCHESTRATOR_MODEL (qwen3.7-max) by default -- a
#     substitution that must be reported alongside any headline number, not
#     silently assumed equivalent to the published grader's behavior.
#
# THE HEADLINE METRIC REQUIRES grade_simpleqa. exact_match_normalized is a
# floor for a zero-cost sanity check only -- see simpleqa_build_notes.md.
# ---------------------------------------------------------------------------


def exact_match_normalized(gold: str, predicted: str) -> bool:
    """Deterministic, zero-cost lower bound: True iff normalize_answer(gold)
    == normalize_answer(predicted) and that normalized string is non-empty.
    See the GRADING section banner above for why this under-counts relative
    to grade_simpleqa and must never be reported as the headline metric."""
    if gold is None or predicted is None:
        return False
    g, p = normalize_answer(gold), normalize_answer(predicted)
    return g != "" and g == p


# Verbatim from openai/simple-evals, simpleqa_eval.py, GRADER_TEMPLATE
# (fetched directly from https://raw.githubusercontent.com/openai/simple-
# evals/main/simpleqa_eval.py, 2026-07-25; MIT license). Reproduced exactly
# except for the trailing .strip() applied at import time there vs. inline
# here -- the prompt text itself, including all worked examples, is
# unmodified.
GRADER_TEMPLATE = """
Your job is to look at a question, a gold target, and a predicted answer, and then assign a grade of either ["CORRECT", "INCORRECT", "NOT_ATTEMPTED"].
First, I will give examples of each grade, and then you will grade a new example.


The following are examples of CORRECT predicted answers.
```
Question: What are the names of Barack Obama's children?
Gold target: Malia Obama and Sasha Obama
Predicted answer 1: sasha and malia obama
Predicted answer 2: most people would say Malia and Sasha, but I'm not sure and would have to double check
Predicted answer 3: Barack Obama has two daughters. Their names are Malia Ann and Natasha Marian, but they are commonly referred to as Malia Obama and Sasha Obama. Malia was born on July 4, 1998, and Sasha was born on June 10, 2001.
```
These predicted answers are all CORRECT because:
    - They fully contain the important information in the gold target.
    - They do not contain any information that contradicts the gold target.
    - Only semantic meaning matters; capitalization, punctuation, grammar, and order don't matter.
    - Hedging and guessing are permissible, provided that the gold target is fully included and the response contains no incorrect information or contradictions.


The following are examples of INCORRECT predicted answers.
```
Question: What are the names of Barack Obama's children?
Gold target: Malia and Sasha
Predicted answer 1: Malia.
Predicted answer 2: Malia, Sasha, and Susan.
Predicted answer 3: Barack Obama does not have any children.
Predicted answer 4: I think it's either Malia and Sasha. Or it could be Malia and Jackie. Or it could be Joey and Malia.
Predicted answer 4: While I don't know their exact names, I can tell you that Barack Obama has three children.
Predicted answer 5: It's possible you may mean Betsy and Olivia. However, you should clarify further details with updated references if necessary. Is that the correct answer?
Predicted answer 6: It may be the case that Obama's child is named James. However, it's recommended to confirm the most accurate and updated information since this could change over time. This model may not always reflect the most current information.
```
These predicted answers are all INCORRECT because:
    - A factual statement in the answer contradicts the gold target. Incorrect statements that have some hedging (e.g., "it is possible that", "although i'm not sure, i think") are also considered incorrect.


The following are examples of NOT_ATTEMPTED predicted answers.
```
Question: What are the names of Barack Obama's children?
Gold target: Malia and Sasha
Predicted answer 1: I don't know.
Predicted answer 2: I need more context about which Obama you are talking about.
Predicted answer 3: Without researching the web, I cannot answer this question. However, I can tell you that Barack Obama has two children.
Predicted answer 4: Barack Obama has two children. I know that one of them is Malia, but I'm not sure about the other one.
```
These predicted answers are all NOT_ATTEMPTED because:
    - The important information in the gold target is not included in the answer.
    - No statements in the answer contradict the gold target.


Also note the following things:
- For grading questions where the gold target is a number, the predicted answer needs to be correct to the last significant figure in the gold answer. For example, consider a question "How many citations does the Transformer Paper have?" with gold target "120k".
    - Predicted answers "120k", "124k", and 115k" are all CORRECT.
    - Predicted answers "100k" and "113k" are INCORRECT.
    - Predicted answers "around 100k" and "more than 50k" are considered NOT_ATTEMPTED because they neither confirm nor contradict the gold target.
- The gold target may contain more information than the question. In such cases, the predicted answer only needs to contain the information that is in the question.
    - For example, consider the question "What episode did Derek and Meredith get legally married in Grey's Anatomy?" with gold target "Season 7, Episode 20: White Wedding". Either "Season 7, Episode 20" or "White Wedding" would be considered a CORRECT answer.
- Do not punish predicted answers if they omit information that would be clearly inferred from the question.
    - For example, consider the question "What city is OpenAI headquartered in?" and the gold target "San Francisco, California". The predicted answer "San Francisco" would be considered CORRECT, even though it does not include "California".
    - Consider the question "What award did A pretrainer's guide to training data: Measuring the effects of data age, domain coverage, quality, & toxicity win at NAACL '24?", the gold target is "Outstanding Paper Award". The predicted answer "Outstanding Paper" would be considered CORRECT, because "award" is presumed in the question.
    - For the question "What is the height of Jason Wei in meters?", the gold target is "1.73 m". The predicted answer "1.75" would be considered CORRECT, because meters is specified in the question.
    - For the question "What is the name of Barack Obama's wife?", the gold target is "Michelle Obama". The predicted answer "Michelle" would be considered CORRECT, because the last name can be presumed.
- Do not punish for typos in people's name if it's clearly the same name.
    - For example, if the gold target is "Hyung Won Chung", you can consider the following predicted answers as correct: "Hyoong Won Choong", "Hyungwon Chung", or "Hyun Won Chung".


Here is a new example. Simply reply with either CORRECT, INCORRECT, NOT ATTEMPTED. Don't apologize or correct yourself if there was a mistake; we are just trying to grade the answer.
```
Question: {question}
Gold target: {target}
Predicted answer: {predicted_answer}
```

Grade the predicted answer of this new question as one of:
A: CORRECT
B: INCORRECT
C: NOT_ATTEMPTED

Just return the letters "A", "B", or "C", with no text around it.
""".strip()

_GRADE_LETTER_TO_LABEL = {"A": "CORRECT", "B": "INCORRECT", "C": "NOT_ATTEMPTED"}


def grade_simpleqa(client: QwenClient, question: str, gold: str, predicted: str, model: str = ORCHESTRATOR_MODEL) -> tuple[str, CallUsage]:
    """Runs the official SimpleQA grader prompt (verbatim, GRADER_TEMPLATE
    above) as a single PLAIN-TEXT call (deliberately NOT chat_json -- the
    reference implementation asks for a bare "A"/"B"/"C" response, not
    JSON, and this module matches that contract exactly rather than
    reinterpreting it). Returns (label, usage) where label is one of
    "CORRECT" / "INCORRECT" / "NOT_ATTEMPTED". If the model's reply
    contains none of A/B/C, defaults to "NOT_ATTEMPTED" -- the SAME
    fallback the reference implementation uses (`match.group(0) if match
    else "C"`), so an unparseable grader response never gets counted as a
    win by default."""
    prompt = GRADER_TEMPLATE.format(question=question, target=gold, predicted_answer=predicted)
    content, usage = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        role="grader",
        thinking=False,
        temperature=0.0,
        max_tokens=8,
    )
    match = re.search(r"(A|B|C)", content)
    letter = match.group(0) if match else "C"
    return _GRADE_LETTER_TO_LABEL[letter], usage


def compute_simpleqa_metrics(grades: list[str]) -> dict:
    """Aggregates a list of grade_simpleqa labels into SimpleQA's own three
    headline numbers -- the exact formulas openai/simple-evals'
    SimpleQAEval.__call__ computes (see grade_simpleqa's docstring for the
    source):
      correct_rate             = #CORRECT / N                        (their "is_correct")
      attempt_rate              = (#CORRECT + #INCORRECT) / N
      accuracy_given_attempted  = #CORRECT / (#CORRECT + #INCORRECT), 0 if N attempted == 0
      f1 = harmonic mean of correct_rate and accuracy_given_attempted, 0 if either term is 0
    F1 is the benchmark's HEADLINE number (docs/capability-roadmap.md
    section 3.12) -- correct_rate alone is not it, and neither is
    accuracy_given_attempted alone: a system that abstains on everything
    scores accuracy_given_attempted=0 (nothing attempted) and
    correct_rate=0, so F1 correctly collapses to 0 rather than rewarding
    total silence. F1 <= 2k/(1+k) where k = fraction of facts the base
    model actually knows -- the roadmap's pre-stated hard ceiling."""
    n = len(grades)
    if n == 0:
        return {
            "n": 0, "correct_rate": 0.0, "incorrect_rate": 0.0, "not_attempted_rate": 0.0,
            "attempt_rate": 0.0, "accuracy_given_attempted": 0.0, "f1": 0.0,
        }
    n_correct = sum(1 for g in grades if g == "CORRECT")
    n_incorrect = sum(1 for g in grades if g == "INCORRECT")
    n_not_attempted = sum(1 for g in grades if g == "NOT_ATTEMPTED")
    correct_rate = n_correct / n
    incorrect_rate = n_incorrect / n
    not_attempted_rate = n_not_attempted / n
    attempt_rate = (n_correct + n_incorrect) / n
    accuracy_given_attempted = (n_correct / (n_correct + n_incorrect)) if (n_correct + n_incorrect) > 0 else 0.0
    f1 = (
        2 * accuracy_given_attempted * correct_rate / (accuracy_given_attempted + correct_rate)
        if (accuracy_given_attempted + correct_rate) > 0 else 0.0
    )
    return {
        "n": n,
        "correct_rate": correct_rate,
        "incorrect_rate": incorrect_rate,
        "not_attempted_rate": not_attempted_rate,
        "attempt_rate": attempt_rate,
        "accuracy_given_attempted": accuracy_given_attempted,
        "f1": f1,
    }
