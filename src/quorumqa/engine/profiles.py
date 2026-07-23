"""The M0 orchestration-profile registry
(docs/mixture-of-orchestrations-plan.md section 2, section 7 "M0 -- Profile
registry refactor").

This module turns the lever zoo in benchmark/lever_experiments.py into DATA:
an OrchestrationProfile is a declarative description of a panel + acceptance
policy + tribunal + retrieval config, and run_profile() is the ONE engine
path that interprets that data and executes it. This is a pure structural
refactor -- every solver/skeptic/verifier/judge/retrieval function it calls
is imported unchanged from quorumqa.engine.* and benchmark.lever_experiments
and reused exactly as those levers already call it. NOTHING here rewrites
prompts, models, or escalation logic; profiles.py only decides WHICH of the
existing helpers to call, based on a profile's declared fields, instead of a
lever-name string dispatch ladder.

Equivalence is proven offline, per profile, in
tests/test_orchestration_profiles.py: for every registry entry, running the
corresponding lever (or, for "standard-tribunal"/"single-call", the shipped
orchestrator/baseline function) and running run_profile() against two
separately-instrumented fake clients produces the exact same multiset of
downstream chat_json calls (role, model, thinking, temperature, system,
user). No paid API calls were made to produce this deliverable -- see the
plan's "benchmark firewall" discipline below and CLAUDE.md's TDD-over-
re-running-benchmarks rule.

Import direction note: this module imports several helpers (second_opinion_
gate, _solve_one_thinking, _solve_one_rag, RagPresolveConfig + its retrieval
helpers, _tribunal, adjudicate_qwen38) from benchmark.lever_experiments,
because that is the ONLY place they are currently defined -- they were built
as ablation-harness code, not shipped engine code. That makes this shipped
src/ module depend on the benchmark/ ablation harness at runtime, which is
backwards for a normal src->benchmark dependency direction. M0 was scoped as
"do not touch lever_experiments.py, reuse it as-is" (see the task that
produced this module), so the honest fix -- promoting those helpers into
quorumqa.engine.* so benchmark/ depends on src/ instead of the reverse -- is
left as a follow-up, not done here.

-----------------------------------------------------------------------------
The benchmark firewall (plan section 5 / 5.1, "The benchmark firewall")
-----------------------------------------------------------------------------
"Product mode: memory ON. Benchmark mode: memory OFF, always." Episodic
("case law") and calibration memory don't exist yet (M2/M4 in the plan's
phasing) -- there is nothing today that actually reads memory. This section
is therefore a FORWARD GUARD: a place for that future code to plug into, so
the firewall is enforced by construction rather than by convention the day
memory lands, instead of being bolted on after the fact.

  - BENCHMARK_MODE (module-global, via set_benchmark_mode/is_benchmark_mode)
    is the single flag a benchmark runner sets once, per plan section 5's
    "the runner sets a single flag" line.
  - assert_benchmark_mode_no_memory() is what every future memory-read call
    site MUST call first. It hard-raises MemoryFirewallError whenever
    BENCHMARK_MODE is on, so a benchmark run can never silently read memory
    of prior runs on the same benchmark.
  - read_calibration_memory()/read_episodic_memory() are documented stubs
    marking where the M2 calibration-memory store and the M4 episodic
    case-law store will attach. Today they always raise: the firewall check
    runs FIRST (MemoryFirewallError in benchmark mode), and only THEN do
    they raise NotImplementedError in product mode, because the actual
    store doesn't exist yet. That ordering is asserted directly in
    tests/test_orchestration_profiles.py.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from quorumqa.baseline import solve_single_agent
from quorumqa.config import MECHANICAL_MODEL, ORCHESTRATOR_MODEL
from quorumqa.engine.judge import adjudicate
from quorumqa.engine.solver import SOLVER_TEMPERATURES, _lenses_for, _solve_one
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import GPQAItem, QuestionResult, SolverAnswer
from quorumqa.tools.mcp_client import VerifierToolSession

# Reused verbatim from the ablation harness -- see the module docstring's
# "Import direction note" for why these live in benchmark/, not quorumqa/,
# today.
from benchmark.lever_experiments import (
    DEFAULT_RAG_K,
    RagPresolveConfig,
    _solve_one_rag,
    _solve_one_thinking,
    _tribunal,
    adjudicate_qwen38,
    build_evidence_block,
    retrieve_rag_evidence,
    second_opinion_gate,
)

log = logging.getLogger(__name__)

_STANDARD_TEMPS = (0.3, 0.6, 0.9)


# ---------------------------------------------------------------------------
# The declarative dimensions (plan section 2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeatSpec:
    """One panel seat: plan section 2's "per-seat (model, thinking on/off,
    temperature, reasoning lens)". `lens_index` indexes into
    quorumqa.engine.solver._lenses_for(len(panel)) -- conventionally 0..n-1
    in seat order for every profile in REGISTRY today, but left as an
    explicit field (rather than implied by list position) so a future
    profile can reuse or reorder lenses across seats."""

    model: str
    thinking: bool
    temperature: float
    lens_index: int


@dataclass(frozen=True)
class AcceptancePolicy:
    """What ends the question at the panel stage (plan section 2).

    kind: "unanimity" | "unanimity+gate" | "always_escalate" | "never_escalate"
      - "unanimity": accept a unanimous plurality outright, no gate call.
      - "unanimity+gate": run second_opinion_gate on a unanimous plurality;
        doubt forces escalation. A split ALWAYS escalates regardless of
        acceptance_policy -- this dimension only governs the unanimous case.
      - "always_escalate": force the tribunal even on a unanimous plurality.
        Not used by any REGISTRY profile today (the lever zoo's closest
        analog, the "subject" lever, forces escalation only for one subject,
        which is a narrower conditional than a blanket policy -- see the M0
        report's flagged ambiguities). run_profile supports it structurally.
      - "never_escalate": the panel's vote is final, the tribunal never
        runs. Only the "single-call" profile (empty panel) exercises this
        today -- run_profile raises NotImplementedError if a NON-empty panel
        declares never_escalate, since no lever ever needed "run a real
        panel, then don't adjudicate a split" and reproducing that
        untested behavior would mean inventing new logic, not reusing it.

    gate_model / gate_prompt_ref are DESCRIPTIVE ONLY: benchmark.
    lever_experiments.second_opinion_gate hardcodes MECHANICAL_MODEL and
    GATE_SYSTEM internally and takes no model/prompt parameter, so there is
    currently no way to actually route a different gate model through it.
    run_profile guards this: a profile requesting a gate_model other than
    MECHANICAL_MODEL/None raises NotImplementedError rather than silently
    ignoring the request.
    """

    kind: str
    gate_model: str | None = None
    gate_prompt_ref: str | None = None

    def __post_init__(self):
        if self.kind not in ("unanimity", "unanimity+gate", "always_escalate", "never_escalate"):
            raise ValueError(f"AcceptancePolicy.kind must be one of unanimity/unanimity+gate/always_escalate/never_escalate, got {self.kind!r}")
        if self.kind == "unanimity+gate" and self.gate_model is None:
            object.__setattr__(self, "gate_model", MECHANICAL_MODEL)


@dataclass(frozen=True)
class TribunalSpec:
    """Skeptic/verifier/judge roster (plan section 2). All REGISTRY
    profiles today keep skeptic and verifier ON with the shipped models --
    _tribunal (benchmark.lever_experiments) has no on/off switch for either
    stage, so run_profile reuses it wholesale for escalation rather than
    reimplementing its QuestionResult-construction logic (false_escalation,
    rag_r2 passthrough, latency) by hand. A profile that actually needs
    skeptic_enabled=False or verifier_enabled=False is therefore NOT
    supported by run_profile in M0 -- it raises NotImplementedError rather
    than silently running the tribunal anyway."""

    skeptic_enabled: bool = True
    skeptic_model: str | None = MECHANICAL_MODEL
    verifier_enabled: bool = True
    verifier_model: str | None = MECHANICAL_MODEL
    # "default" = safe_calculate + lookup_constant (quorumqa.tools.mcp_server),
    # the only toolset that exists today. Plan section 2's per-domain packs
    # (statute-lookup, SymPy, code runners) are a build item, not wired here.
    verifier_toolset: str = "default"
    judge_model: str | None = ORCHESTRATOR_MODEL
    # "qwen_client" = quorumqa.engine.judge.adjudicate (QwenClient/Token
    # Plan transport, qwen3.7-max). "token_plan_messages" =
    # benchmark.lever_experiments.adjudicate_qwen38 (raw Anthropic-Messages
    # transport, qwen3.8-max-preview) -- the qwen38_judge lever's judge
    # swap. Not required by the M0 minimum registry (qwen38_judge is not a
    # VALIDATED profile per the plan doc), but wired since _tribunal already
    # exposes `adjudicator` as a swap point for exactly this.
    judge_transport: str = "qwen_client"

    def __post_init__(self):
        if self.judge_transport not in ("qwen_client", "token_plan_messages"):
            raise ValueError(f"TribunalSpec.judge_transport must be qwen_client or token_plan_messages, got {self.judge_transport!r}")
        if self.verifier_toolset != "default":
            raise ValueError(f"TribunalSpec.verifier_toolset {self.verifier_toolset!r} is not implemented -- only 'default' exists today")


@dataclass(frozen=True)
class RetrievalSpec:
    """Plan section 2: none | pre_solve{k, db} | pre_solve+disputed_step.

    mode:
      - "none": no retrieval (most profiles).
      - "pre_solve": rag_presolve's R1 -- one retrieval call per question,
        injected into every solver seat.
      - "pre_solve+disputed_step": R1 PLUS rag_recursive's R2 (a second,
        disputed-step-driven retrieval fired inside the tribunal). No
        REGISTRY profile uses this today -- rag_recursive is a documented
        NEGATIVE in the plan (section 2, "Registry updates"), so it is
        deliberately not promoted into the registry. run_profile supports
        the wiring (passes `rag` through to _tribunal) but it is untested
        by the M0 equivalence suite since nothing in REGISTRY exercises it.

    k/db are the R1 retrieval parameters; db=None defers to benchmark.
    lever_experiments.resolve_rag_db_path's default chain (CLI flag -> env
    var -> the pre-embedded G0.5 corpus). Callers of run_profile must build
    the matching RagPresolveConfig themselves (via build_rag_presolve_config)
    and pass it as `rag=` -- run_profile does not open the index itself, the
    same contract lever_experiments.run_question_lever already has.

    corpus_domains records which domains the configured corpus snapshot
    covers (plan section 2's "Two new router inputs" -- corpus coverage).
    The pre-embedded STEM-Wikipedia index covers STEM only; it moves
    nothing on e.g. Swiss law (LEXam G3 probe finding) because the shelf
    has no statutes. Informational -- not enforced by run_profile in M0
    (there is no law-domain RAG profile yet to guard against misuse).
    """

    mode: str = "none"
    k: int | None = None
    db: str | None = None
    corpus_domains: tuple[str, ...] = ()

    def __post_init__(self):
        if self.mode not in ("none", "pre_solve", "pre_solve+disputed_step"):
            raise ValueError(f"RetrievalSpec.mode must be none/pre_solve/pre_solve+disputed_step, got {self.mode!r}")


@dataclass(frozen=True)
class OrchestrationProfile:
    """One declarative orchestration (plan section 2). `panel=[]` is the
    single-call sentinel: run_profile bypasses the panel/tribunal machinery
    entirely and dispatches straight to quorumqa.baseline.solve_single_agent
    -- see __post_init__ for the invariant this implies.

    `subject_overrides` generalizes chem_thinking_gate's per-domain panel
    swap (plan section 2: "stem-max (= chem_thinking_gate generalized)"):
    a dict from item.subject to an alternate panel, checked before falling
    back to `panel`. Only "Organic Chemistry" is populated today (that is
    literally all chem_thinking_gate routes on), but the mechanism itself
    is domain-name-keyed, not chemistry-specific.

    `mode` is plan section 2's deliberation/agent axis. Only "deliberation"
    is executable by run_profile in M0 -- agent mode (the terminal-agent
    tool-loop profile) is explicitly out of scope; run_profile raises
    NotImplementedError for any other mode value. The dataclass itself does
    not forbid constructing an agent-mode profile (it's still valid DATA,
    useful for the registry to describe what M1+ will add), only executing
    one today.
    """

    name: str
    panel: list[SeatSpec]
    acceptance_policy: AcceptancePolicy
    tribunal: TribunalSpec
    retrieval: RetrievalSpec
    mode: str = "deliberation"
    budget_label: str = ""
    description: str = ""
    subject_overrides: dict[str, list[SeatSpec]] | None = None

    def __post_init__(self):
        if self.mode not in ("deliberation", "agent"):
            raise ValueError(f"OrchestrationProfile.mode must be deliberation or agent, got {self.mode!r}")
        if not self.panel:
            if self.acceptance_policy.kind != "never_escalate":
                raise ValueError(
                    f"profile {self.name!r} has an empty panel (single-call sentinel) but "
                    f"acceptance_policy.kind={self.acceptance_policy.kind!r} -- an empty panel only "
                    "makes sense with never_escalate (there is no plurality to adjudicate)"
                )
            if self.subject_overrides is not None:
                raise ValueError(f"profile {self.name!r} has an empty panel but declares subject_overrides -- single-call has no panel to override")
            if self.retrieval.mode != "none":
                raise ValueError(f"profile {self.name!r} has an empty panel but declares retrieval -- single-call never retrieves")
        elif self.acceptance_policy.kind == "never_escalate":
            raise ValueError(
                f"profile {self.name!r} has a non-empty panel with acceptance_policy.kind='never_escalate' -- "
                "this combination ('run a real panel, then never adjudicate a split') has no lever precedent "
                "and is not implemented by run_profile; use an empty panel for the single-call route instead"
            )


# ---------------------------------------------------------------------------
# The benchmark firewall (module docstring above has the full rationale)
# ---------------------------------------------------------------------------


class MemoryFirewallError(RuntimeError):
    """Raised when code attempts to read episodic/calibration memory while
    BENCHMARK_MODE is on. Plan section 5: "Product mode: memory ON.
    Benchmark mode: memory OFF, always."""


_BENCHMARK_MODE = False


def set_benchmark_mode(enabled: bool) -> None:
    """The single flag a benchmark runner sets once before its run loop
    (plan section 5: "The runner sets a single flag")."""
    global _BENCHMARK_MODE
    _BENCHMARK_MODE = bool(enabled)


def is_benchmark_mode() -> bool:
    return _BENCHMARK_MODE


def assert_benchmark_mode_no_memory(memory_kind: str = "memory") -> None:
    """Every future memory-read call site (calibration memory M2, episodic
    case-law memory M4) MUST call this first. Hard-raises whenever
    BENCHMARK_MODE is on."""
    if _BENCHMARK_MODE:
        raise MemoryFirewallError(
            f"benchmark firewall: {memory_kind} read attempted while BENCHMARK_MODE is ON. "
            "Product mode: memory ON. Benchmark mode: memory OFF, always (plan section 5)."
        )


def read_calibration_memory(*args, **kwargs):
    """Forward stub for the plan section 5.1 calibration-memory store
    (per-(profile, domain, difficulty) outcome statistics). Not built yet
    (M2) -- always raises. The firewall check runs FIRST: in benchmark
    mode this raises MemoryFirewallError, never reaching the "not built"
    branch, proving the guard is unconditional rather than incidental."""
    assert_benchmark_mode_no_memory("calibration memory")
    raise NotImplementedError("calibration memory (plan section 5.1) is not built yet -- M2")


def read_episodic_memory(*args, **kwargs):
    """Forward stub for the plan section 5.2 episodic ("case law") memory
    store. Not built yet (M4) -- same firewall-first contract as
    read_calibration_memory."""
    assert_benchmark_mode_no_memory("episodic memory")
    raise NotImplementedError("episodic memory (plan section 5.2) is not built yet -- M4")


# ---------------------------------------------------------------------------
# run_profile: the one engine path
# ---------------------------------------------------------------------------


def _plurality(answers: list[SolverAnswer]) -> tuple[str, bool]:
    from collections import Counter

    counts = Counter(a.letter for a in answers)
    top_letter, top_count = counts.most_common(1)[0]
    return top_letter, top_count == len(answers)


def _resolve_panel(profile: OrchestrationProfile, item: GPQAItem) -> list[SeatSpec]:
    if profile.subject_overrides and item.subject in profile.subject_overrides:
        return profile.subject_overrides[item.subject]
    return profile.panel


async def _resolve_evidence(retrieval: RetrievalSpec, rag: "RagPresolveConfig | None", question: str) -> str:
    if retrieval.mode == "none":
        return ""
    if rag is None:
        raise ValueError(
            f"profile requires retrieval (mode={retrieval.mode!r}) but rag=None was passed to run_profile -- "
            "build a RagPresolveConfig (benchmark.lever_experiments.build_rag_presolve_config) and pass it as rag=..."
        )
    results = await asyncio.to_thread(retrieve_rag_evidence, rag, question)
    return build_evidence_block(results)


async def _solve_panel(client, question, choices, panel: list[SeatSpec], evidence_block: str, retrieval_on: bool):
    lenses = _lenses_for(len(panel))

    def _dispatch(seat: SeatSpec):
        lens = lenses[seat.lens_index]
        if retrieval_on:
            return asyncio.to_thread(_solve_one_rag, client, question, choices, lens, evidence_block, seat.model, seat.temperature, seat.thinking)
        if seat.thinking:
            return asyncio.to_thread(_solve_one_thinking, client, question, choices, lens, seat.model, seat.temperature)
        return asyncio.to_thread(_solve_one, client, question, choices, lens, seat.model, seat.temperature)

    tasks = [_dispatch(seat) for seat in panel]
    return list(await asyncio.gather(*tasks))


async def run_profile(
    client: QwenClient,
    tool_session: "VerifierToolSession | None",
    item: GPQAItem,
    profile: OrchestrationProfile,
    rag: "RagPresolveConfig | None" = None,
    benchmark_mode: bool | None = None,
) -> QuestionResult:
    """The single engine path for every OrchestrationProfile. Dispatches on
    the profile's declarative fields to the SAME underlying solve/gate/
    tribunal/retrieval helpers the lever zoo already calls -- see the module
    docstring for the equivalence-testing strategy that proves this offline.

    `benchmark_mode`, if not None, calls set_benchmark_mode() before doing
    anything else -- the intended usage is a benchmark harness calling
    set_benchmark_mode(True) ONCE before its run loop (plan section 5), not
    per-question; the parameter exists mainly so tests/callers can exercise
    the wiring per-call without reaching into the module global directly.
    """
    if benchmark_mode is not None:
        set_benchmark_mode(benchmark_mode)

    if profile.mode != "deliberation":
        raise NotImplementedError(
            f"run_profile only executes mode='deliberation' profiles in M0 -- {profile.name!r} declares "
            f"mode={profile.mode!r}. Agent-mode profiles (the terminal-agent tool-loop shape) are out of "
            "M0 scope per docs/mixture-of-orchestrations-plan.md section 2."
        )
    if profile.acceptance_policy.gate_model not in (None, MECHANICAL_MODEL):
        raise NotImplementedError(
            f"profile {profile.name!r} requests gate_model={profile.acceptance_policy.gate_model!r}, but "
            "benchmark.lever_experiments.second_opinion_gate hardcodes MECHANICAL_MODEL and has no model "
            "parameter -- not wired in M0"
        )
    # The skeptic/verifier on/off toggle only matters for panel-based
    # profiles that might actually reach the tribunal -- the single-call
    # sentinel (empty panel) legitimately declares both OFF (it never
    # escalates, see OrchestrationProfile.__post_init__) and must not be
    # rejected here for that.
    if profile.panel and not (profile.tribunal.skeptic_enabled and profile.tribunal.verifier_enabled):
        raise NotImplementedError(
            f"profile {profile.name!r} declares skeptic_enabled={profile.tribunal.skeptic_enabled} / "
            f"verifier_enabled={profile.tribunal.verifier_enabled}, but benchmark.lever_experiments._tribunal "
            "has no on/off switch for either stage -- not wired in M0"
        )

    start = time.monotonic()

    if not profile.panel:
        # single-call sentinel (see OrchestrationProfile.__post_init__ for
        # the invariant guaranteeing this only happens for never_escalate
        # profiles with no retrieval/overrides): bypass the panel/tribunal
        # machinery entirely and reuse quorumqa.baseline.solve_single_agent
        # verbatim.
        baseline_result = await asyncio.to_thread(solve_single_agent, client, item)
        # solve_single_agent returns a BaselineResult, a different shape
        # from QuestionResult (no solver_answers/plurality_letter/escalated
        # -- see the M0 report's flagged ambiguity). We synthesize a single
        # SolverAnswer carrying the baseline's letter so QuestionResult's
        # required fields are satisfiable; confidence=1.0 and reasoning=""
        # are PLACEHOLDERS, not genuine model-reported values -- solve_
        # single_agent's underlying _ask_once() discards both.
        solver_answers = [SolverAnswer(letter=baseline_result.answer_letter, confidence=1.0, reasoning="", lens=None)]
        return QuestionResult(
            item=item,
            solver_answers=solver_answers,
            plurality_letter=baseline_result.answer_letter,
            escalated=False,
            final_letter=baseline_result.answer_letter,
            correct=baseline_result.correct,
            calls=baseline_result.calls,
            latency_s=baseline_result.latency_s,
        )

    panel = _resolve_panel(profile, item)
    retrieval_on = profile.retrieval.mode != "none"
    evidence_block = await _resolve_evidence(profile.retrieval, rag, item.question)

    solver_pairs = await _solve_panel(client, item.question, item.choices, panel, evidence_block, retrieval_on)
    solver_answers = [a for a, _ in solver_pairs]
    calls = [u for _, u in solver_pairs]
    plurality_letter, unanimous = _plurality(solver_answers)

    force_escalate = False
    if unanimous:
        if profile.acceptance_policy.kind == "always_escalate":
            force_escalate = True
        elif profile.acceptance_policy.kind == "unanimity+gate":
            doubt, _reason, gate_usage = second_opinion_gate(client, item.question, item.choices, solver_answers, plurality_letter)
            calls.append(gate_usage)
            if doubt:
                force_escalate = True
        elif profile.acceptance_policy.kind == "never_escalate":
            # Guarded unreachable by OrchestrationProfile.__post_init__ (a
            # non-empty panel can never carry never_escalate) -- kept as an
            # explicit branch rather than falling through silently.
            raise NotImplementedError("never_escalate with a non-empty panel is not implemented (see AcceptancePolicy docstring)")
        # "unanimity": no gate, nothing to do.

    if unanimous and not force_escalate:
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

    adjudicator = adjudicate_qwen38 if profile.tribunal.judge_transport == "token_plan_messages" else adjudicate
    r2_rag = rag if profile.retrieval.mode == "pre_solve+disputed_step" else None
    return await _tribunal(
        client, tool_session, item, solver_answers, plurality_letter, calls, start,
        adjudicator=adjudicator, rag=r2_rag,
    )


# ---------------------------------------------------------------------------
# The VALIDATED registry (plan section 2's "Initial profile registry" +
# "Registry updates from the validated record"). Every entry's config below
# was cross-read against benchmark/lever_experiments.py's corresponding
# solve_all_* function -- see tests/test_orchestration_profiles.py's
# structural + equivalence tests for the verification.
# ---------------------------------------------------------------------------


def _standard_panel() -> list[SeatSpec]:
    return [SeatSpec(model=MECHANICAL_MODEL, thinking=False, temperature=t, lens_index=i) for i, t in enumerate(_STANDARD_TEMPS)]


def _thinking_seat_panel() -> list[SeatSpec]:
    # solve_all_thinking_seat: seats 1-2 exactly as shipped, seat 3 thinking=True.
    return [
        SeatSpec(model=MECHANICAL_MODEL, thinking=False, temperature=0.3, lens_index=0),
        SeatSpec(model=MECHANICAL_MODEL, thinking=False, temperature=0.6, lens_index=1),
        SeatSpec(model=MECHANICAL_MODEL, thinking=True, temperature=0.9, lens_index=2),
    ]


def _flagship_thinking_panel() -> list[SeatSpec]:
    # solve_all_flagship_panel / solve_all_chem_flagship's chemistry branch.
    return [SeatSpec(model=ORCHESTRATOR_MODEL, thinking=True, temperature=t, lens_index=i) for i, t in enumerate(SOLVER_TEMPERATURES)]


REGISTRY: dict[str, OrchestrationProfile] = {}

REGISTRY["standard-tribunal"] = OrchestrationProfile(
    name="standard-tribunal",
    panel=_standard_panel(),
    acceptance_policy=AcceptancePolicy(kind="unanimity"),
    tribunal=TribunalSpec(),
    retrieval=RetrievalSpec(mode="none"),
    budget_label="cheap-tribunal",
    description=(
        "The shipped engine (quorumqa.engine.orchestrator.run_question / lever_experiments' default "
        "else-branch): 3x MECHANICAL_MODEL solver seats, thinking off, plain unanimity acceptance, "
        "shipped skeptic/verifier/judge on split. Frozen submission config, 78.9% on GPQA."
    ),
)

REGISTRY["thinking_gate"] = OrchestrationProfile(
    name="thinking_gate",
    panel=_thinking_seat_panel(),
    acceptance_policy=AcceptancePolicy(kind="unanimity+gate"),
    tribunal=TribunalSpec(),
    retrieval=RetrievalSpec(mode="none"),
    budget_label="cheap-tribunal+gate",
    description="solve_all_thinking_seat panel (seat 3 thinking=True) + universal second_opinion_gate doubt-check. Validated 3 seeds.",
)

REGISTRY["stem-max"] = OrchestrationProfile(
    name="stem-max",
    panel=_thinking_seat_panel(),
    subject_overrides={"Organic Chemistry": _flagship_thinking_panel()},
    acceptance_policy=AcceptancePolicy(kind="unanimity+gate"),
    tribunal=TribunalSpec(),
    retrieval=RetrievalSpec(mode="none"),
    budget_label="mixed: cheap-tribunal+gate everywhere, ~3x-flagship-thinking on Organic Chemistry",
    description=(
        "= chem_thinking_gate. Organic Chemistry routes to the 3x-flagship-thinking panel "
        "(solve_all_chem_flagship's chemistry branch); every other subject uses thinking_gate's panel. "
        "The universal gate applies to both branches. Validated 3 seeds, 90.9% mean."
    ),
)

REGISTRY["flagship_panel"] = OrchestrationProfile(
    name="flagship_panel",
    panel=_flagship_thinking_panel(),
    acceptance_policy=AcceptancePolicy(kind="unanimity"),
    tribunal=TribunalSpec(),
    retrieval=RetrievalSpec(mode="none"),
    budget_label="expensive: 3x-flagship-thinking panel + tribunal (~3x standard-tribunal cost)",
    description=(
        "solve_all_flagship_panel: all 3 seats on ORCHESTRATOR_MODEL, thinking=True. NOT gated -- "
        "flagship_panel is not in run_question_lever's gate-lever list. Validated 3 seeds, "
        "+4.1 mean vs flagship-solo on SuperGPQA-hard."
    ),
)

REGISTRY["rag_presolve"] = OrchestrationProfile(
    name="rag_presolve",
    panel=_standard_panel(),
    acceptance_policy=AcceptancePolicy(kind="unanimity"),
    tribunal=TribunalSpec(),
    retrieval=RetrievalSpec(mode="pre_solve", k=DEFAULT_RAG_K, corpus_domains=("stem",)),
    budget_label="cheap-tribunal + 1 retrieval call",
    description=(
        "solve_all_rag_presolve: standard-tribunal's panel, fed one shared R1 pre-solve evidence block "
        "per question from the pre-embedded STEM-Wikipedia index. Covers STEM only -- moves nothing on "
        "law (LEXam G3 probe). Validated 3 seeds, +6.5 mean vs cheap, floor cut every seed."
    ),
)

REGISTRY["rag_thinking_gate"] = OrchestrationProfile(
    name="rag_thinking_gate",
    panel=_thinking_seat_panel(),
    acceptance_policy=AcceptancePolicy(kind="unanimity+gate"),
    tribunal=TribunalSpec(),
    retrieval=RetrievalSpec(mode="pre_solve", k=DEFAULT_RAG_K, corpus_domains=("stem",)),
    budget_label="cheap-tribunal+gate + 1 retrieval call",
    description=(
        "solve_all_rag_thinking_gate: the composition test -- rag_presolve's R1 evidence block feeds "
        "thinking_gate's panel shape (all 3 seats, including the thinking seat). No R2. Pilot seed 271."
    ),
)

REGISTRY["single-call"] = OrchestrationProfile(
    name="single-call",
    panel=[],
    acceptance_policy=AcceptancePolicy(kind="never_escalate"),
    tribunal=TribunalSpec(skeptic_enabled=False, verifier_enabled=False, judge_model=None),
    retrieval=RetrievalSpec(mode="none"),
    budget_label="cheapest: one flagship call, no panel, no tribunal",
    description=(
        "quorumqa.baseline.solve_single_agent: one ORCHESTRATOR_MODEL call, thinking=True, zero-shot. "
        "LEXam (-14pts) / MMLU-Pro (-12pts) findings: deliberation subtracts value at ceiling -- routes "
        "easy/saturated queries or cost-constrained callers here."
    ),
)
