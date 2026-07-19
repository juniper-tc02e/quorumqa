import os

from dotenv import load_dotenv

load_dotenv()

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")

# Confirmed directly from the Qwen Cloud console's own "Pay-As-You-Go Base
# URL" panel (home.qwencloud.com/api-keys) -- this is the correct endpoint
# for sk-ws- workspace keys too. An earlier attempt to route sk-ws- keys
# through a workspace-specific "*.maas.aliyuncs.com" URL (based on a
# third-party search result, not official docs) was wrong -- reverted.
DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

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
SKEPTIC_MODEL = WORKER_MODEL
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
