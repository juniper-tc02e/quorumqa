import os

from dotenv import load_dotenv

# override=True: .env must always win over a same-named OS environment
# variable. Without this, a credential already set at the OS level (e.g. a
# persistent Windows User env var from an earlier setup) silently shadows
# every .env edit -- rotating a key in .env then has no effect, with no
# error, because load_dotenv() by default never overwrites an existing
# os.environ entry. Found live 2026-07-21: a stale User-level
# DASHSCOPE_API_KEY (the very first key ever used in this project) was
# silently overriding two rounds of key rotation in .env all session.
load_dotenv(override=True)

# Pay-as-you-go credentials -- kept for reference/rollback, no longer the
# default QwenClient transport as of the Token Plan migration (2026-07-21).
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")

# Confirmed directly from the Qwen Cloud console's own "Pay-As-You-Go Base
# URL" panel (home.qwencloud.com/api-keys) -- this is the correct endpoint
# for sk-ws- workspace keys too. An earlier attempt to route sk-ws- keys
# through a workspace-specific "*.maas.aliyuncs.com" URL (based on a
# third-party search result, not official docs) was wrong -- reverted.
DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

# Token Plan credentials -- the DEFAULT QwenClient transport now. A
# completely separate product/key from pay-as-you-go: this key 401s on
# DASHSCOPE_BASE_URL above, and the pay-as-you-go key 401s on this endpoint.
# Uses the Anthropic Messages API shape (x-api-key auth, {"content": [...]}
# response blocks, top-level "system" field), not OpenAI chat.completions --
# QwenClient's transport is written against this shape. Billed via Credits
# against a 5-hour/7-day sliding quota, not per-token USD -- see the cost_usd
# note on CallUsage calls made through this client.
TOKEN_PLAN_API_KEY = os.environ.get("QUORUMQA_TOKEN_PLAN_API_KEY", "")
TOKEN_PLAN_BASE_URL = os.environ.get(
    "QUORUMQA_TOKEN_PLAN_BASE_URL",
    "https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic",
)

# Qwen Cloud model tiers.
ORCHESTRATOR_MODEL = os.environ.get("QUORUMQA_ORCHESTRATOR_MODEL", "qwen3.7-max")
WORKER_MODEL = os.environ.get("QUORUMQA_WORKER_MODEL", "qwen3.7-plus")
MECHANICAL_MODEL = os.environ.get("QUORUMQA_MECHANICAL_MODEL", "qwen3.6-flash")

# Role -> tier. This mapping is what makes the "cheap-by-default,
# escalate-on-conflict" cost story actually true rather than aspirational:
# Solvers run 3x in parallel on EVERY question, so they must sit on the
# cheapest tier for the unanimous (non-escalated) case to ever beat a single
# flagship-tier baseline call on cost. Skeptic/Verifier only run when
# solvers split. Judge (most expensive) only runs on that same subset.
SOLVER_MODEL = MECHANICAL_MODEL
# All-flash solver panel. We TRIED the Heter-MAD mixed panel (flash/flash/
# plus) first; the measured 74-question run showed the no-thinking plus seat
# was both the weakest solver (54.1% vs flash's 66-72%) and the source of
# every JSON-malformation drop. Panel diversity now comes from distinct
# lenses + per-seat temperature (below) instead of model family.
SOLVER_MODELS = [MECHANICAL_MODEL, MECHANICAL_MODEL, MECHANICAL_MODEL]
SOLVER_TEMPERATURES = [0.3, 0.6, 0.9]
SKEPTIC_MODEL = MECHANICAL_MODEL  # same measured reliability rationale
VERIFIER_MODEL = MECHANICAL_MODEL
JUDGE_MODEL = ORCHESTRATOR_MODEL
BASELINE_MODEL = ORCHESTRATOR_MODEL  # the required single-agent baseline

N_SOLVERS = int(os.environ.get("QUORUMQA_N_SOLVERS", "3"))
MAX_REBUTTAL_ROUNDS = 1  # hard cap (Graft 2) so escalation cost is bounded

# Distinct instruction framings per solver seat so independent proposals are
# not identical clones of the same prompt (heterogeneity rule).
SOLVER_LENSES = [
    "Answer by reasoning from first principles, step by step.",
    "Answer by first eliminating choices you're confident are wrong, then picking among what remains.",
    "Answer by recalling the single most relevant fact, law, or formula, then checking each choice against it.",
]

# Panel-scaling coprime factorial (docs/experiment-spec-book.md section 2.2):
# five PROCEDURE prompts, deliberately a period-5 list against
# SOLVER_TEMPERATURES' period-3 list, so a seat index cycled through both
# (procedure = SOLVER_PROCEDURES[i % 5], temperature = SOLVER_TEMPERATURES
# [i % 3]) lands on a unique (procedure, temperature) cell for every i in
# 0..14 -- gcd(5, 3) == 1. This is the fix for the N=5 confound: with only 3
# lenses and 3 temperatures both cycling on period 3, seat 4 was a
# byte-identical config to seat 1. Entries 1-3 reuse the exact semantics of
# benchmark/lever_experiments.py's METHOD_PROMPTS (solve-forward
# analytically, verify-by-candidate/eliminate, estimate-first/order-of-
# magnitude); entries 4-5 are new. Additive only -- SOLVER_LENSES,
# SOLVER_TEMPERATURES, and N_SOLVERS above are unchanged, so every existing
# lever's behavior stays byte-identical.
SOLVER_PROCEDURES = [
    "Method: solve forward analytically, step by step. Derive the answer "
    "from first principles or known formulas in a clear logical sequence, "
    "then match your result to the closest choice.",
    "Method: verify by candidate. Evaluate EACH answer choice against the "
    "question's stated constraints in turn, eliminating any that fail, and "
    "select the one that survives (or fits best).",
    "Method: estimate first. Start from an order-of-magnitude estimate or "
    "a limiting-case/sanity check, then refine that estimate with exact "
    "reasoning to pick the closest choice.",
    "Method: dimensional analysis. Identify the units and scales involved "
    "first, then check each answer choice for dimensional and order-of-"
    "magnitude consistency, ruling out any choice whose units or scale "
    "cannot be right before picking among what remains.",
    "Method: analogy to a canonical problem. Recall the single most similar "
    "well-known textbook problem or pattern, solve that pattern first, then "
    "adapt the result to this question's specific numbers and wording.",
]

# USD per 1M tokens, midpoint of Qwen Cloud's published tiered ranges as of
# 2026-07. Re-check against https://docs.qwencloud.com pricing before
# reporting benchmark $ figures publicly -- tiered pricing changes with
# volume/context length.
PRICING_USD_PER_MTOK = {
    "qwen3.7-max": {"input": 2.50, "output": 7.50},
    "qwen3.7-plus": {"input": 0.80, "output": 3.20},
    "qwen3.6-flash": {"input": 0.60, "output": 2.75},
}

HF_TOKEN = os.environ.get("HF_TOKEN") or None
