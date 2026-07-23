"""The M1 router (docs/mixture-of-orchestrations-plan.md section 3, section 7
"M1 -- Router R1 + `single-call` + blended-workload eval"), CORRECTED per
benchmark/results/moo_m1_corrected_findings.md.

route(item, budget="balanced") maps a GPQAItem to one of the M0 REGISTRY
profile names (src/quorumqa/engine/profiles.py). This is where the Mixture
of Orchestrations thesis is tested: every rule below is cited to a specific
measured finding, not intuition, per the plan's discipline ("every design
choice cites the measured finding that motivates it").

The correction (benchmark/results/moo_m1_corrected_findings.md): the FIRST
version of this router (moo_m1_findings.md) LOST to flat-best flagship_panel
on the M1 blended-workload eval (-2.7pts, costing more) because its hard-
STEM rules assumed "flagship_panel = expensive, avoid it, use the cheap-tier
escalation-heavy stacks instead" -- an assumption the eval itself disproved:
flagship_panel rarely escalates on hard STEM (~8% -> 3 solver calls) while
the "cheap" rag_thinking_gate/thinking_gate stacks escalate 60-80% of the
time into a full tribunal, making them BOTH less accurate AND pricier there.
The gpqa_hard_stem and supergpqa_hard_stem rules below now route to
flagship_panel (balanced/quality budget) instead, driven by a measured
calibration table (quorumqa.engine.calibration, benchmark/results/
moo_calibration_table.csv -- built offline from moo_m1_eval.jsonl's own
recorded outcomes, no new paid calls) rather than a tier assumption, via a
cost-aware tie-break (_cost_aware_hard_stem_pick / calibration.
cheapest_within_margin): among profiles within ~1pt measured accuracy for a
bucket, pick the cheapest by measured tokens. The medicine/saturated_easy/
gpqa_organic_chem/unknown rules were already correct on the same eval (they
tied flat-best accuracy at a fraction of the cost) and are unchanged.

Two implementations, both reachable through the same route() entry point:

- **R0/R1 heuristic** (default): item.subject + ROUTING_RULES, a fixed,
  ordered table. Deterministic, zero cost, zero latency -- this is what
  benchmark/run_moo_eval.py runs against, per the M1 task's explicit
  instruction to "keep the eval cheap and deterministic." See
  ROUTING_RULES below for the rules themselves and _domain_bucket() for
  the matching logic.
- **R1 classifier call** (opt-in via use_classifier=True): one
  MECHANICAL_MODEL (qwen3.6-flash) JSON call producing
  {domain, difficulty, checkability, is_agentic} per the plan's R1
  description (section 3), mapped through classify_bucket() to the same
  bucket vocabulary the heuristic uses, then through the same
  _profile_for_bucket() selection table. NOT exercised by the M1 eval
  (every blend bucket is already disambiguable from item.subject alone,
  so spending a classifier call per question would only add cost without
  changing routing decisions on this workload) -- wired and offline-
  tested so R2 (calibration-weighted dispatch, plan section 3) has a real
  classifier path to build on rather than inventing one later.

Why item.subject alone is not the same thing as a real domain classifier,
stated plainly (plan section 3's honesty requirement): item.subject is
whatever string each benchmark loader happens to record -- a fine-grained
GPQA subdomain, a coarse SuperGPQA discipline, MedQA's exam-step label
(not a medical specialty), an MMLU-Pro category, or None (GSM8K/MATH have
no subject column at all). ROUTING_RULES is grounded in the *actual*
string values each loader emits (spot-checked live against the cached HF
datasets, see the comment on each rule below), not guessed patterns. A
subject string this table has never seen falls to the "unknown" bucket,
which is deliberately biased toward a STRONGER default profile as budget
increases (plan section 3: "biasing uncertain classifications toward
stronger profiles... asymmetric loss: over-orchestrating wastes cents,
under-orchestrating costs correctness") rather than silently guessing
"saturated_easy" and routing to the cheapest, most failure-prone-on-a-
real-gap option.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING

from quorumqa.config import MECHANICAL_MODEL
from quorumqa.engine import calibration as _calibration
from quorumqa.engine import profiles as _profiles

if TYPE_CHECKING:
    from quorumqa.qwen_client import QwenClient
    from quorumqa.schemas import GPQAItem

BUDGETS = ("cheap", "balanced", "quality")

# MedQA's only per-row category (load_medqa.py: meta_info is the USMLE exam
# step, "step1" or "step2&3" -- NOT a clinical specialty; this dataset has
# no subject/specialty field at all). Exact strings confirmed against
# load_medqa.py's own docstring.
_MEDQA_SUBJECTS = ("step1", "step2&3")

# SuperGPQA's discipline field (13 top-level values); the difficulty="hard"
# filter this project uses (benchmark/load_supergpqa.py) is dominated by
# these two -- live-checked against the cached m-a-p/SuperGPQA dataset,
# hard subset: Science=4210, Engineering=2458 of ~6975 hard rows (~96%).
# This is the exact "cheap tier out of its depth across a whole domain"
# pattern diagnosed in supergpqa_findings.md (23% unanimous-wrong, engine
# -11.6 vs flagship baseline).
_SUPERGPQA_HARD_STEM_SUBJECTS = ("Science", "Engineering")

# GPQA-Diamond's own Subdomain/High-level-domain values that name physics or
# chemistry -- live-checked against the cached Idavidrein/gpqa gpqa_diamond
# split's real Subdomain distribution: 'Organic Chemistry', 'Chemistry
# (general)', 'Inorganic Chemistry' (chem); 'Physics (general)',
# 'High-energy particle physics', 'Astrophysics', 'Condensed Matter
# Physics' (physic). Matched by case-insensitive substring rather than an
# exact set because GPQA's Subdomain field is free-form (unlike SuperGPQA's
# fixed 13-way discipline enum above).
_GPQA_CHEM_PHYSIC_MARKERS = ("chem", "physic")

# MMLU-Pro's `category` field is a fixed, already-lowercase 14-way enum --
# live-checked against the cached TIGER-Lab/MMLU-Pro test split. Matched
# by exact (case-sensitive) membership, deliberately NOT via .lower(), so
# this never accidentally swallows a GPQA item whose subject fell back to
# the Title-Case High-level-domain field ("Physics"/"Chemistry"/"Biology")
# -- case-sensitive exact match means "Physics" != "physics", no collision.
# Restricted to the categories mmlu_pro_findings.md's per-category
# breakdown showed fully saturated (100% baseline=engine, n=50 pilot):
# math, economics, business, physics, biology, health, psychology,
# computer science, philosophy, history, other. Deliberately EXCLUDES
# engineering/chemistry/law -- the same pilot's own per-category table
# showed those three specifically losing ground (engineering 86%->43%,
# chemistry 100%->75%, law 67%->33%, all tiny n but the only categories
# that regressed at all), so they are not claimed as "saturated" here.
SATURATED_MMLU_PRO_CATEGORIES = frozenset({
    "math", "economics", "business", "physics", "biology", "health",
    "psychology", "computer science", "philosophy", "history", "other",
})


@dataclass(frozen=True)
class RoutingRule:
    """One row of the router's rules table -- see ROUTING_RULES below.
    `profile_by_budget` maps every value in BUDGETS to a REGISTRY profile
    name; a rule whose routing does not vary by budget repeats the same
    name for all three keys (documented as such at the call site)."""

    bucket: str
    match: str
    profile_by_budget: dict = field(default_factory=dict)
    finding: str = ""


@lru_cache(maxsize=1)
def _default_calibration_table() -> _calibration.CalibrationTable:
    """Lazily loads benchmark/results/moo_calibration_table.csv (built
    offline by benchmark/build_moo_calibration.py from the already-recorded
    moo_m1_eval.jsonl, no live API calls -- plan section 5.1's calibration
    memory, simplest static form) exactly once per process. Returns {} if
    the file is missing (e.g. a fresh clone before the table has been
    built) rather than raising -- the hard-STEM cost-aware picks below
    treat that identically to "no candidate has enough data", falling back
    to their hardcoded default rather than failing to route at all."""
    try:
        return _calibration.load_calibration_table(_calibration.DEFAULT_CALIBRATION_CSV)
    except FileNotFoundError:
        return {}


def _cost_aware_hard_stem_pick(router_bucket: str, candidates: tuple[str, ...], default: str) -> str:
    """The corrected router's cost-aware tie-break (moo_m1_corrected_
    findings.md item 2c): among `candidates`, defer to quorumqa.engine.
    calibration.cheapest_within_margin over the measured calibration table
    -- among profiles within ~1pt measured accuracy of each other for
    `router_bucket`, pick the cheapest by measured tokens. Falls back to
    `default` (the hardcoded, findings-cited pick) when the calibration
    table has no entry, or too thin a sample (n < cheapest_within_margin's
    min_n=10), for `router_bucket` -- e.g. gpqa_hard_stem's real n=4-5/
    profile is deliberately NOT trusted standalone (see that rule's finding
    text)."""
    picked = _calibration.cheapest_within_margin(_default_calibration_table(), bucket=router_bucket, candidates=candidates)
    return picked or default


def _profile_for_bucket(bucket: str, budget: str) -> str:
    if bucket == "gpqa_organic_chem":
        # stem-max IS chem_thinking_gate: validated 90.9% mean (3 seeds,
        # 0.2pt spread) on exactly this subject (docs/mixture-of-
        # orchestrations-plan.md section 1; benchmark/results/
        # supergpqa_findings.md's chem_flagship_gate lineage). Not budget-
        # gated: no cheaper validated fix for this diagnosed blind spot
        # exists (RAG must NOT be used here -- see gpqa_hard_stem below),
        # so "cheap" gets the same answer as "quality".
        return "stem-max"
    if bucket == "gpqa_hard_stem":
        # CORRECTED per moo_m1_corrected_findings.md (M1's honest-negative
        # diagnosis, moo_m1_findings.md): the OLD rule routed here to
        # stem-max, whose panel is BYTE-IDENTICAL to thinking_gate's for
        # every subject except "Organic Chemistry" (profiles.py: stem-max's
        # subject_overrides only has that one key) -- so it had no
        # different EFFECT from thinking_gate on this bucket, and
        # moo_m1_findings.md's per-bucket table measured that choice WORSE
        # AND costlier than flagship_panel on the coarser gpqa_hard
        # workload bucket (85%@14426 vs flagship_panel's 93%@12248) -- the
        # same "escalation-heavy stack is the expensive AND less accurate
        # one" pattern diagnosed on supergpqa_hard_stem below. "cheap"
        # takes the cheapest measured option (single-call, 86.2%@3739 tok
        # on the gpqa_hard workload bucket -- close behind flagship_panel
        # at a fraction of the cost); "balanced"/"quality" defer to the
        # cost-aware tie-break (moo_m1_corrected_findings.md item 2c),
        # falling back to flagship_panel since this router-bucket's own
        # calibration sample is thin (n=4-5/profile -- see
        # moo_calibration_table.csv -- too small to trust standalone; the
        # fallback leans on the coarser, more robust gpqa_hard-bucket
        # evidence instead).
        #
        # Deliberately NEVER rag_presolve/rag_thinking_gate (not in the
        # candidate list below): the R1 contamination tripwire (benchmark/
        # results/rag_r1_findings.md) measured retrieval on GPQA-Diamond at
        # -4.7 (search-proof by construction, injected passages are pure
        # noise/distraction) -- RAG profiles are gated OFF this bucket by
        # construction, not merely deprioritized. stem-max is also excluded
        # from the candidate list: it is redundant with thinking_gate here
        # by construction (see above) and thinking_gate itself already
        # loses to flagship_panel on the evidence this fix is based on.
        if budget == "cheap":
            return "single-call"
        return _cost_aware_hard_stem_pick(
            "gpqa_hard_stem", ("flagship_panel", "thinking_gate", "single-call"), default="flagship_panel"
        )
    if bucket == "supergpqa_hard_stem":
        # CORRECTED per moo_m1_corrected_findings.md: the OLD rule (rag_
        # thinking_gate at cheap/balanced, supergpqa_findings.md/rag_stack_
        # findings.md's validated-in-isolation picks) assumed "flagship_
        # panel = expensive, avoid on hard STEM." moo_m1_findings.md's
        # blended-workload eval proved that assumption false: flagship_
        # panel rarely escalates here (~8% -> 3 solver calls), while rag_
        # thinking_gate escalates 63% -> full tribunal -> nearly 2x the
        # tokens. Calibration table (n=26-30/profile, moo_calibration_
        # table.csv): flagship_panel 84.6%@9553tok vs rag_thinking_gate's
        # 73.3%@17719tok -- flagship_panel is BOTH more accurate AND
        # cheaper, not a quality-only upgrade. "cheap" takes single-call
        # (79.3%@4106tok -- within a few points of flagship_panel at under
        # half the tokens); "balanced"/"quality" resolve through the same
        # cost-aware tie-break as gpqa_hard_stem above (this bucket's
        # sample comfortably clears the tie-break's min_n=10 guard, so this
        # is a live calibration-driven pick, not a thin-data fallback).
        if budget == "cheap":
            return "single-call"
        return _cost_aware_hard_stem_pick(
            "supergpqa_hard_stem", ("flagship_panel", "rag_thinking_gate", "thinking_gate", "single-call"), default="flagship_panel"
        )
    if bucket == "medicine":
        # medqa_findings.md: 4% unanimous-wrong (vs SuperGPQA-hard's 23%)
        # -- the cheap tier is genuinely competent at medicine, so cheap
        # deliberation ties the flagship "at a fraction of the cost...
        # arguably QuorumQA's ideal economic case." "cheap" budget takes
        # that literally (single-call, cheapest possible, same accuracy).
        # "balanced"/"quality" keep the cheap 3-seat panel (standard-
        # tribunal) rather than upgrading further: the finding explicitly
        # says this is NOT a flagship_panel domain (no diagnosed gap to
        # buy back with extra spend), so a bigger budget should not be
        # spent here even when the caller has it to spend.
        return "single-call" if budget == "cheap" else "standard-tribunal"
    if bucket == "saturated_easy":
        # mmlu_pro_findings.md / the plan's founding LEXam+MMLU-Pro
        # evidence: deliberation SUBTRACTS value at ceiling (-12/-14) via
        # the one uncatchable failure mode (confident unanimous-wrong).
        # single-call is not just the cheapest option here, it is the most
        # ACCURATE one measured -- so this is the one bucket that ignores
        # budget entirely; a "quality" caller does not want deliberation
        # bought here, they want the single flagship call the finding
        # shows wins outright.
        return "single-call"
    # "unknown": no rule matched item.subject. Per the plan's asymmetric-
    # loss principle (section 3), bias toward a STRONGER default as budget
    # rises rather than guessing cheap: standard-tribunal (the frozen
    # submission's cheapest full panel) at "cheap", thinking_gate (the
    # registry's general "hard questions, no diagnosed domain weakness"
    # profile, validated 3 seeds) at "balanced", flagship_panel (max
    # accuracy, ~3x cost) at "quality".
    return {"cheap": "standard-tribunal", "balanced": "thinking_gate", "quality": "flagship_panel"}[budget]


ROUTING_RULES: tuple[RoutingRule, ...] = (
    RoutingRule(
        bucket="gpqa_organic_chem",
        match="item.subject == 'Organic Chemistry' (GPQA-Diamond)",
        profile_by_budget={b: _profile_for_bucket("gpqa_organic_chem", b) for b in BUDGETS},
        finding=(
            "stem-max/chem_thinking_gate validated 90.9% mean, 3 seeds, 0.2pt spread "
            "(docs/mixture-of-orchestrations-plan.md section 1; the chem_flagship_gate lineage)."
        ),
    ),
    RoutingRule(
        bucket="supergpqa_hard_stem",
        match="item.subject in {'Science', 'Engineering'} (SuperGPQA hard-subset disciplines)",
        profile_by_budget={b: _profile_for_bucket("supergpqa_hard_stem", b) for b in BUDGETS},
        finding=(
            "CORRECTED (benchmark/results/moo_m1_corrected_findings.md, diagnosed by "
            "moo_m1_findings.md's honest-negative R1 eval): the prior rag_thinking_gate pick assumed "
            "'flagship_panel = expensive, avoid on hard STEM' -- false. Calibration table (n=26-30/"
            "profile, moo_calibration_table.csv): flagship_panel 84.6%@9553tok vs rag_thinking_gate's "
            "73.3%@17719tok -- flagship_panel is BOTH more accurate AND cheaper (it rarely escalates "
            "here, ~8%, while rag_thinking_gate escalates 63% into a full tribunal). Resolved via the "
            "cost-aware tie-break (item 2c) over this calibration table, not a bare hardcoded string."
        ),
    ),
    RoutingRule(
        bucket="gpqa_hard_stem",
        match="item.subject contains 'chem' or 'physic' (case-insensitive; GPQA-Diamond Subdomain/High-level-domain)",
        profile_by_budget={b: _profile_for_bucket("gpqa_hard_stem", b) for b in BUDGETS},
        finding=(
            "CORRECTED (benchmark/results/moo_m1_corrected_findings.md): the prior stem-max pick was "
            "byte-identical to thinking_gate's panel here (stem-max only overrides Organic Chemistry) "
            "and moo_m1_findings.md's per-bucket table measured that WORSE and costlier than "
            "flagship_panel on the coarser gpqa_hard workload bucket (85%@14426 vs 93%@12248). This "
            "router-bucket's own calibration sample is thin (n=4-5/profile) -- the fix leans on the "
            "coarser evidence plus consistency with supergpqa_hard_stem's robust fix, flagged honestly "
            "as thin-evidence rather than an independently robust result. RAG excluded: rag_r1_"
            "findings.md's GPQA tripwire measured retrieval at -4.7 on GPQA-Diamond (search-proof by "
            "construction)."
        ),
    ),
    RoutingRule(
        bucket="medicine",
        match="item.subject in {'step1', 'step2&3'} (MedQA's only per-row field, the USMLE exam step)",
        profile_by_budget={b: _profile_for_bucket("medicine", b) for b in BUDGETS},
        finding=(
            "benchmark/results/medqa_findings.md: 4% unanimous-wrong (vs SuperGPQA-hard's 23%), engine "
            "ties flagship (+2, inside noise) -- 'a single-call-or-standard-tribunal domain, NOT a "
            "flagship_panel domain.'"
        ),
    ),
    RoutingRule(
        bucket="saturated_easy",
        match=f"item.subject in {sorted(SATURATED_MMLU_PRO_CATEGORIES)!r} (exact, case-sensitive; MMLU-Pro category)",
        profile_by_budget={b: _profile_for_bucket("saturated_easy", b) for b in BUDGETS},
        finding=(
            "benchmark/results/mmlu_pro_findings.md: flagship baseline 94%, engine -12 overall; "
            "per-category breakdown showed these categories 100% baseline=engine (unanimous-and-correct); "
            "excludes engineering/chemistry/law, the only categories that regressed in that pilot."
        ),
    ),
    RoutingRule(
        bucket="unknown",
        match="no rule above matched item.subject (including subject=None, e.g. GSM8K/MATH loaders)",
        profile_by_budget={b: _profile_for_bucket("unknown", b) for b in BUDGETS},
        finding=(
            "Plan section 3's asymmetric-loss principle: bias uncertain classifications toward stronger "
            "profiles as budget rises (standard-tribunal -> thinking_gate -> flagship_panel) rather than "
            "guessing a cheap route on an undiagnosed domain."
        ),
    ),
)


def _domain_bucket(subject: str | None) -> str:
    """Pure string-matching classification of item.subject into one of
    ROUTING_RULES' bucket names. See the module docstring and each rule's
    `finding` field for what grounds every branch below."""
    if subject is None:
        return "unknown"
    s = subject.strip()
    if not s:
        return "unknown"
    if s == "Organic Chemistry":
        return "gpqa_organic_chem"
    if s in _SUPERGPQA_HARD_STEM_SUBJECTS:
        return "supergpqa_hard_stem"
    if s in _MEDQA_SUBJECTS:
        return "medicine"
    if s in SATURATED_MMLU_PRO_CATEGORIES:
        return "saturated_easy"
    s_lower = s.lower()
    if any(marker in s_lower for marker in _GPQA_CHEM_PHYSIC_MARKERS):
        return "gpqa_hard_stem"
    return "unknown"


def _check_budget(budget: str) -> None:
    if budget not in BUDGETS:
        raise ValueError(f"budget must be one of {BUDGETS!r}, got {budget!r}")


def route(
    item: "GPQAItem",
    budget: str = "balanced",
    *,
    use_classifier: bool = False,
    client: "QwenClient | None" = None,
) -> str:
    """Map item to a profile name from src/quorumqa/engine/profiles.py's
    REGISTRY. Default path is the deterministic R0/R1 heuristic (item.
    subject + ROUTING_RULES) -- zero cost, zero latency, what benchmark/
    run_moo_eval.py runs against.

    Pass use_classifier=True (with a real `client`) to route via one R1
    classifier call instead (plan section 3): a MECHANICAL_MODEL JSON call
    producing {domain, difficulty, checkability, is_agentic}, mapped
    through classify_bucket() to the same bucket vocabulary the heuristic
    uses. Not used by the M1 eval -- see the module docstring for why.
    """
    _check_budget(budget)
    if use_classifier:
        if client is None:
            raise ValueError("use_classifier=True requires a client (a QwenClient) to make the classification call")
        classification = classify_via_llm(client, item)
        bucket = classify_bucket(classification)
    else:
        bucket = _domain_bucket(item.subject)
    profile_name = _profile_for_bucket(bucket, budget)
    if profile_name not in _profiles.REGISTRY:
        raise AssertionError(
            f"router bucket {bucket!r} resolved to profile {profile_name!r}, which is not in "
            "quorumqa.engine.profiles.REGISTRY -- this is a bug in router.py, not a valid routing decision"
        )
    return profile_name


# ---------------------------------------------------------------------------
# R1 classifier call (plan section 3), optional -- see route()'s
# use_classifier flag and the module docstring for why the M1 eval does not
# exercise this path.
# ---------------------------------------------------------------------------

_CLASSIFIER_SYSTEM = (
    "You are a routing classifier for a multi-agent QA system. Given a "
    "multiple-choice question, classify it along four axes. Respond with "
    "ONLY a JSON object: "
    '{"domain": "<one short label, e.g. organic_chemistry, physics, '
    'chemistry, medicine, law, math, general>", '
    '"difficulty": "<easy|medium|hard>", '
    '"checkability": "<search_proof|retrievable|computable>", '
    '"is_agentic": <true|false>}. '
    "checkability=search_proof means the question is designed to resist "
    "being answered by looking up facts (e.g. GPQA-style Google-proof "
    "science); retrievable means general encyclopedic knowledge would "
    "help; computable means it reduces to a calculation. is_agentic means "
    "the task requires running tools/commands in a loop rather than a "
    "single deliberative answer."
)


def classify_via_llm(client: "QwenClient", item: "GPQAItem") -> dict:
    """One MECHANICAL_MODEL (qwen3.6-flash) JSON call classifying `item`
    along the plan's R1 axes (section 3): {domain, difficulty,
    checkability, is_agentic}. Returns the parsed dict (the caller is
    responsible for tracking client.chat_json's returned CallUsage for
    cost accounting, same discipline as every other role in this engine --
    this function intentionally mirrors solver.py's chat_json call shape
    rather than inventing a new client-call convention)."""
    user = (
        f"Question: {item.question}\n"
        f"Choices: {', '.join(item.choices)}\n"
        f"Loader-provided subject tag (may be uninformative or absent): {item.subject!r}"
    )
    result = client.chat_json(
        model=MECHANICAL_MODEL,
        system=_CLASSIFIER_SYSTEM,
        user=user,
        role="router_classifier",
        temperature=0.0,
        thinking=False,
    )
    return result.data


def classify_bucket(classification: dict) -> str:
    """Maps an R1 classifier result (classify_via_llm's return value) to
    the same bucket vocabulary _domain_bucket() uses, so both routing
    paths share _profile_for_bucket()'s selection table. Deliberately
    conservative: only maps to a bucket the heuristic path also recognizes
    (no classifier-only buckets), keeping the two paths' final profile
    sets identical -- a classifier disagreement can change WHICH bucket a
    question lands in, never invent a new one."""
    domain = str(classification.get("domain", "")).strip().lower()
    checkability = str(classification.get("checkability", "")).strip().lower()
    difficulty = str(classification.get("difficulty", "")).strip().lower()

    if domain in ("organic_chemistry", "organic chemistry"):
        return "gpqa_organic_chem"
    if domain == "medicine":
        return "medicine"
    if difficulty == "easy":
        return "saturated_easy"
    if domain in ("chemistry", "physics") and checkability != "search_proof":
        # A classifier that read the question and judged it retrievable/
        # computable chemistry or physics, rather than deliberately
        # search-proof, matches the SuperGPQA-hard pattern (broad hard-STEM
        # where retrieval helps) more than the GPQA-Diamond pattern (where
        # it hurts) -- see supergpqa_hard_stem's finding vs gpqa_hard_stem's.
        return "supergpqa_hard_stem"
    if domain in ("chemistry", "physics", "engineering", "science"):
        return "gpqa_hard_stem"
    return "unknown"
