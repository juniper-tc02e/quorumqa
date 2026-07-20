# Devpost Submission — QuorumQA

**Track: Agent Society (Track 3)**

## Elevator pitch (for the Devpost tagline field)

An agent society that argues only when it's worth arguing: three cheap Qwen
solvers vote independently, and a Skeptic, a tool-using Verifier and a flagship
Judge are summoned only on the 37.8% of questions where they disagree — closing
most of the gap to a flagship model on "Google-proof" PhD-level science
questions while costing 11% less than running that flagship on everything.

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
   - a **Skeptic** (`qwen3.6-flash`) attacks the plurality answer's weakest
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
  | **QuorumQA — cheap panel, flagship Judge only on a split** | **78.9%** | **$0.0213** |
  | Single flagship agent (`qwen3.7-max`, thinking) | 84.4% | $0.0240 |

  **Headline: +20.0 accuracy points over the identical cheap models run as a
  plain ensemble, closing ~78% of the gap to the thinking flagship while
  costing 11% less than it.** The Judge is that same `qwen3.7-max`, so the
  result comes from *routing* the expensive model to the 37.8% of questions
  that need it, not from doing without it. The flagship still wins outright on
  accuracy by 5.5 points, and we say so on the site.

  Escalation mechanics, measured: escalation rate 37.8% (62% of questions
  never pay for the expensive roles at all; unanimous questions cost
  ~$0.004 vs the baseline's ~$0.024); the Judge overturned the solver
  plurality 14 times and was right in 11 (78.6%) — adjudication by argument
  demonstrably beats majority vote; false-escalation rate 58.8% (reported
  honestly: the cost of the escalations that merely re-confirmed the
  panel).

### Qwen Cloud usage

- `qwen3.6-flash` and `qwen3.7-max` via the OpenAI-compatible DashScope
  endpoint. Every cheap role (3 solvers, Skeptic, Verifier) runs on flash; only
  the Judge runs on max, and only on the 37.8% of questions that split. The
  Judge is the *same* model as the single-agent baseline, so the saving comes
  from routing it rather than from avoiding it. That price spread is the
  architecture.
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

**Business model:** open-core. The adjudication engine (this repo,
MIT-licensed) stays free and drives adoption; verticals with real appeal and
audit exposure pay for vertical lens libraries, an escalation-integrity
dashboard, and self-hosted/compliance-ready packaging — priced per-decision
or as a platform license, not inference margin. The moat isn't the
orchestration algorithm (a well-resourced lab will always out-engineer
that) — it's the audit-artifact format and each customer's own accumulated
calibration data becoming what reviewers and regulators come to trust.

**Roadmap, stated honestly:** the engine and the n=90 benchmark above are
real and independently reproducible. A pilot customer, a validated price
point, and vertical-specific lens libraries are not — that's next-quarter
work, not a claim made here.

## Submission checklist

- [x] Repo public, MIT LICENSE visible in About section (github.com/juniper-tc02e/quorumqa)
- [x] Live public site: **https://magiachiral.com** — replays real recorded deliberations from the n=90 run (the hero is a scroll-scrubbed film of a genuine 2-1 split that the Judge overturns), publishes the full scoreboard including the numbers that do not flatter us, and exposes a filterable gallery of 33 cases with every transcript, MCP tool call and ruling. Runs on Cloudflare Workers + D1; source in the same account as this repo
- [x] Proof of Alibaba Cloud deployment: `deploy/oss_client.py`, live-verified on ECS instance `magiachiral-prod` (`i-t4n5ukaobmzp3ckby557`, Singapore) — Qwen Cloud API call and OSS transcript upload both smoke-tested successfully from the instance, 2026-07-20
- [x] Architecture diagram: `docs/architecture.md` (render the mermaid to PNG for the gallery)
- [ ] Demo video ≤3 min, public on YouTube/Vimeo/Youku, link pasted (shot list + narration ready in `docs/demo-script.md`)
- [ ] Track declared: Agent Society
- [x] Final benchmark numbers inserted (n=90 complete run, 2026-07-19)
- [x] Testing access instructions in README (judges must be able to run it free)

## Demo video

The shot list, the word-for-word narration and the claims-to-avoid list live in
[`docs/demo-script.md`](demo-script.md). It uses two distinct cases on purpose:
`recIj8lR4tuDgrHou` shows majority voting failing and adjudication fixing it
(the flagship also got that one right, so it is not a win over the flagship),
and `recBhnXrUyTJ6WHIR` is one of the five where the cheap society beat the
flagship outright.
