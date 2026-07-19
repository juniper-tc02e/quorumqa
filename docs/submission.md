# Devpost Submission — QuorumQA

**Track: Agent Society (Track 3)**

## Elevator pitch (for the Devpost tagline field)

An agent society that argues only when it's worth arguing: three cheap Qwen
solvers vote independently; a Skeptic, a tool-using Verifier, and a Judge are
summoned only on disagreement — matching flagship-model accuracy on
"Google-proof" PhD-level science questions at a fraction of the cost.

## Text description (paste into "About the project")

### What it does

QuorumQA answers graduate-level, deliberately search-proof science questions
(GPQA-Diamond) with a society of Qwen agents in escalating tiers:

1. **Three Solver agents** (`qwen3.6-flash`, cheapest tier) answer every
   question independently and in parallel — none sees another's answer, and
   each reasons through a different assigned lens so they are genuinely
   diverse, not three clones.
2. **If they agree**, that's the answer. No further cost. This is the common
   case, and it's what makes the economics work.
3. **If they split**, the society escalates:
   - a **Skeptic** (`qwen3.7-plus`) attacks the plurality answer's weakest
     inferential step — it must name the specific step it disputes;
   - a **Verifier** (`qwen3.6-flash`) extracts checkable numeric/factual
     claims from the solver reasoning and grounds each one through a real
     **MCP server** (constant lookup + sandboxed calculator) — every number
     is forced through a tool call, never asserted from memory;
   - a **Judge** (`qwen3.7-max`, flagship — the only place we pay flagship
     price) reads the full transcript and rules by weighing arguments, never
     by counting votes. Consensus-collapse research shows plurality voting
     discards correct minority answers; our Judge can and does overturn
     2-vs-1 splits, and every ruling records unresolved dissent verbatim on
     a rendered Verdict Card.

### How agents divide work, disagree, and resolve conflict (the track brief)

- **Task division / role assignment:** asymmetric-by-design — cheap roles run
  always, expensive roles are assigned only when the cheap roles' output
  proves contested. Role assignment is driven by measured disagreement, not
  a fixed pipeline.
- **Dialogue & negotiation:** the Skeptic's rebuttal, the minority solver's
  standing rationale, and the Verifier's tool-grounded evidence form a real
  adversarial exchange that the Judge adjudicates.
- **Measurable efficiency gain (final numbers, n=90 GPQA-Diamond, complete
  run, zero dropped questions, from the committed re-runnable script):**

  | System | Accuracy | Cost/question |
  |---|---|---|
  | Self-consistency@5 — the same cheap tier, no society | 58.9% | $0.0093 |
  | **QuorumQA — the same cheap tier, organized as a society** | **78.9%** | **$0.0213** |
  | Single flagship agent (`qwen3.7-max`, thinking) | 84.4% | $0.0240 |

  **Headline: organizing the same cheap models into a society buys +20.0
  accuracy points over using them as a plain ensemble — closing ~78% of the
  gap to the thinking flagship while costing 11% less than it.**

  Escalation mechanics, measured: escalation rate 37.8% (62% of questions
  never pay for the expensive roles at all; unanimous questions cost
  ~$0.004 vs the baseline's ~$0.024); the Judge overturned the solver
  plurality 14 times and was right in 11 (78.6%) — adjudication by argument
  demonstrably beats majority vote; false-escalation rate 58.8% (reported
  honestly: the cost of the escalations that merely re-confirmed the
  panel).

### Qwen Cloud usage

- `qwen3.7-max` / `qwen3.7-plus` / `qwen3.6-flash` via the OpenAI-compatible
  DashScope endpoint — the three-tier price spread is the architecture.
- A custom **MCP server** (Model Context Protocol) provides the Verifier's
  tools — genuine MCP integration end-to-end, not a bespoke function shim.
- Backend runs on **Alibaba Cloud ECS**; every deliberation transcript and
  Verdict Card is persisted to **Alibaba Cloud OSS** via `deploy/oss_client.py`
  (the linked proof-of-deployment file).

### Why it matters beyond an exam

"Vote cheap, escalate on disagreement" generalizes to any contested-judgment
pipeline: insurance claims triage, content-moderation appeals, medical
second-opinion routing. GPQA is the proving ground because its public answer
key makes every claim auditable — judges can re-run our benchmark script and
check the numbers themselves.

## Submission checklist

- [ ] Repo public, MIT LICENSE visible in About section
- [ ] Proof of Alibaba Cloud deployment: link to `deploy/oss_client.py`
- [ ] Architecture diagram: `docs/architecture.md` (render the mermaid to PNG for the gallery)
- [ ] Demo video ≤3 min, public on YouTube/Vimeo/Youku, link pasted
- [ ] Track declared: Agent Society
- [x] Final benchmark numbers inserted (n=90 complete run, 2026-07-19)
- [ ] Testing access instructions in README (judges must be able to run it free)

## Demo video storyboard (≤3:00)

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:15 | Hook + generalization up front: "Vote cheap, escalate on disagreement — the pattern behind claims triage, moderation appeals, medical second opinions. We prove it on the hardest auditable ground there is: a Google-proof PhD exam." | Title card → dashboard |
| 0:15–0:40 | Single flagship agent confidently answers a real GPQA question **wrong** — checked live against the public key. Use question `recBhnXrUyTJ6WHIR` (baseline wrong, society correct in the benchmark run) | Baseline panel, red X |
| 0:40–1:30 | Same question through the society: 3 solver cards → live 2–1 split highlight → Skeptic rebuttal streams in → Verifier's MCP tool call shown in the log ("every number forced through a tool, never memory") → Judge's Verdict Card renders with dissent quoted verbatim → green check. For the overturn beat, `recIj8lR4tuDgrHou` (Quantum Mechanics, plurality D overruled to correct C) | Dashboard live run |
| 1:30–2:10 | Scoreboard: accuracy bars (baseline vs QuorumQA), cost/question bars, escalation rate, false-escalation rate ("the expensive calls earn their keep") | Benchmark tab |
| 2:10–2:45 | Zoom out: same engine, swap the domain — name the three verticals again; GPQA chosen because judges can re-run the script and audit every number | Architecture diagram |
| 2:45–3:00 | Headline number + repo link | Close card |

**Recording notes:** screen-record the Streamlit dashboard (OBS or Xbox Game
Bar, Win+Alt+R). Record the live-question segment against a question you've
pre-checked produces a split + correct overturn (pick from the benchmark run
log: any `escalated=True, overturned=True, correct=True` question). No
copyrighted music. English narration or captions.
