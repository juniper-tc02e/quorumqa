from typing import Optional

from pydantic import BaseModel, Field


class GPQAItem(BaseModel):
    question_id: str
    question: str
    choices: list[str]  # exactly 4, order already shuffled by the loader
    correct_letter: str  # "A" | "B" | "C" | "D"
    subject: Optional[str] = None


class SolverAnswer(BaseModel):
    letter: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    lens: Optional[str] = None


class SkepticRebuttal(BaseModel):
    target_letter: str
    disputed_step: str
    argument: str


class VerifierFinding(BaseModel):
    claim: str
    tool_used: str
    tool_query: str
    tool_result: str
    supports_claim: bool


class JudgeVerdict(BaseModel):
    final_letter: str
    decisive_reasoning: str
    dissent: Optional[str] = None
    overturned_plurality: bool
    confidence: str  # "high" | "medium" | "low"


class CallUsage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    role: str  # "solver" | "skeptic" | "verifier" | "judge" | "baseline"


class QuestionResult(BaseModel):
    item: GPQAItem
    solver_answers: list[SolverAnswer]
    plurality_letter: str
    escalated: bool
    skeptic_rebuttal: Optional[SkepticRebuttal] = None
    verifier_findings: list[VerifierFinding] = Field(default_factory=list)
    verdict: Optional[JudgeVerdict] = None
    final_letter: str
    correct: bool
    false_escalation: bool = False  # escalated but judge just re-confirmed the plurality
    calls: list[CallUsage] = Field(default_factory=list)
    latency_s: float = 0.0
    # rag_recursive (R2, docs/recursive-rag-plan.md section 2) only: the
    # disputed-step query actually sent to the index, and the titles it
    # retrieved. None/empty for every other lever, and for rag_recursive
    # questions that never escalated (R1-only, no R2 retrieval fired).
    rag_r2_query: Optional[str] = None
    rag_r2_titles: list[str] = Field(default_factory=list)
    # rag_gated_presolve only: whether the top fused RRF score cleared the
    # gate's --rag-score-threshold (True = evidence was injected into every
    # solver seat, same as rag_presolve; False = every seat ran on the
    # plain question, no evidence). rag_gate_top_score is the score itself
    # (None if nothing was retrieved at all). Both None for every other
    # lever -- see benchmark.lever_experiments.solve_all_rag_gated_presolve.
    rag_gate_applied: Optional[bool] = None
    rag_gate_top_score: Optional[float] = None

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return sum(c.input_tokens + c.output_tokens for c in self.calls)


class BaselineResult(BaseModel):
    item: GPQAItem
    answer_letter: str
    correct: bool
    calls: list[CallUsage] = Field(default_factory=list)
    latency_s: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)
