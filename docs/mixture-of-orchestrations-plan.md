# Mixture of Orchestrations: making QuorumQA excel in general use

Written 2026-07-22. Design plan, not implementation. Every design choice
below cites the measured finding that motivates it — this architecture is
not speculative shape-drawing; it is the generalization our own data has
been pointing at for two days.

## 1. The core claim, and the evidence it stands on

QuorumQA today is ONE orchestration: a fixed panel, fixed escalation
trigger, fixed tribunal, applied identically to every question. The
project's own results show that a single fixed orchestration cannot excel
in general use, because the right orchestration is a function of the
question:

- **Routing by domain beats any flat configuration.**
  `chem_thinking_gate` — flagship panel for Organic Chemistry, thinking
  seat everywhere else — is validated at 90.9% mean (three fresh seeds,
  0.2pt spread), ~+5 points over the flagship-on-everything baseline and
  above BOTH of its flat parents. Routing is not an optimization; it is
  where the accuracy came from.
- **The same subject can need a different MODEL, not more effort.**
  `smart_gate` (more thinking time on chemistry, same model) made
  chemistry WORSE (72.2% vs 77.8% baseline); a different model fixed it
  (90%+). An orchestration mixture must be able to switch model tier per
  domain, not just reasoning depth.
- **More capability per seat can subtract value.** `thinking_all`
  underperformed a single thinking seat at both seeds tested, because
  homogenizing the panel removes the disagreement that triggers useful
  escalation. Orchestration parameters interact; profiles must be
  validated as wholes, never composed by assuming monotonic improvements.
- **Sometimes the right orchestration is NONE.** On LEXam (-14pts) and
  MMLU-Pro (-12pts), deliberation lost to a single flagship call: the
  flagship was near ceiling, so the panel's one uncatchable failure mode
  (confident unanimous-wrong) dominated. A general-use system must be
  able to route easy/saturated queries to a single call — the
  "no-orchestration" profile is a first-class member of the mixture.
- **The verifier's tools are domain equipment.** On LEXam, 7/9
  escalations produced zero verifier findings — constant-lookup and
  calculator simply don't apply to statute reasoning. Tribunal tooling
  must be per-domain (statute lookup for law, symbolic math for math,
  test-execution for code), or escalation silently degrades to
  Skeptic+Judge.
- **Agentic domains are a different orchestration shape entirely.**
  Terminal-Bench work showed the QA pipeline doesn't transfer; the
  right cyber/terminal orchestration is a hardened tool-loop agent
  (37.5% baseline at 86% grading coverage) with verifier-filtered
  best-of-N as the deliberation analog — because these domains carry
  their own objective verifier, adjudication-by-argument is the wrong
  spend there.

**Mixture of Orchestrations (MoO):** a router classifies each incoming
query and dispatches it to one of a registry of orchestration profiles;
profiles are declarative configs over a shared engine; a memory layer
(§5) makes both the router and the profiles improve from accumulated
experience.

## 2. The orchestration-profile abstraction

Everything the ablation harness varies by hand today becomes one
declarative object. A profile specifies:

- **Panel**: number of seats; per-seat (model, thinking on/off,
  temperature, reasoning lens). Existing points in this space: shipped
  engine, thinking_gate, chem_flagship panel, five-solver (negative),
  thinking_all (negative), flagship_panel.
- **Acceptance policy**: what ends the question at the panel stage —
  unanimity, unanimity+doubt-gate (gate model/prompt configurable), or
  none (always escalate / never escalate).
- **Tribunal roster**: skeptic on/off + model; verifier on/off + model +
  TOOLSET (the per-domain equipment rack: `safe_calculate` +
  `lookup_constant` today; statute-lookup, unit-checker, SymPy, code
  runners as domain packs); judge model (validated finding: judge quality
  above qwen3.7-max was NOT the binding constraint on GPQA — qwen38_judge
  moved nothing — so profiles should not default to the most expensive
  judge).
- **Mode**: `deliberation` (single-turn QA) or `agent` (tool-loop, with
  turn budget, per-command timeout policy, best-of-N width and the task's
  own verifier as filter).
- **Budget**: max cost/latency class, so the router can respect caller
  constraints ("fast and cheap" legitimately selects a different profile
  than "maximum accuracy").

The existing `lever_experiments.py` dispatch-by-name IS the primitive
version of this registry. M0 (§7) is the refactor that makes profiles
data instead of code branches.

### Initial profile registry (v1, all evidence-based)

| Profile | When routed | Basis |
|---|---|---|
| `single-call` | easy/saturated queries, or caller wants cheap | LEXam/MMLU-Pro findings: deliberation subtracts value at ceiling |
| `standard-tribunal` | default hard-question profile | frozen submission config, 78.9% on GPQA |
| `thinking-gate` | hard questions, no diagnosed domain weakness | validated 3 seeds |
| `stem-max` (= chem_thinking_gate generalized) | hard STEM where the cheap tier has a diagnosed blind spot | validated 3 seeds, 90.9% mean |
| `law` | legal/regulatory reasoning | LEXam diagnosis; BLOCKED on statute-lookup verifier tool (build item) |
| `terminal-agent` | shell/code/ops tasks | hardened baseline 37.5%; best-of-N is its Phase 2 |
| `math-verified` | competition/calculation math | verifier already computes; add SymPy tool; untested — pilot required |

Every new profile passes the loop's validation bar (three fresh seeds /
samples, matched baseline, drop-bias checks, honest negatives recorded)
before the router may select it in product mode.

### Registry updates from the validated record (2026-07-23)

| Profile | Status | Evidence |
|---|---|---|
| `stem-max` (chem_thinking_gate) | **VALIDATED** | 90.9% mean, 3 seeds, +4.4 matched |
| `flagship_panel` (hard-STEM tier-swap) | **VALIDATED** | +4.1 mean vs flagship-solo, 3 seeds, SuperGPQA-hard |
| `rag_presolve` (cheap + pre-solve retrieval) | **VALIDATED** | +6.5 mean vs cheap, 3 seeds, floor cut every seed; GPQA tripwire clean |
| `qwen38_panel` (max-tier homogeneous panel) | **NEGATIVE** | 0% escalation = expensive self-consistency; trails flagship_panel |
| `rag_recursive` (R2 tribunal retrieval) | **NEGATIVE (no-gain)** | −1.2 vs R1; structurally can't reach the unanimous-wrong floor |
| qwen38 judge swap | **NULL** | judge quality not the binding constraint |

**Two new router inputs the original design missed, both measured:**
1. **Corpus coverage** (from the LEXam G3 probe): RAG profiles are only
   selectable where the indexed corpus actually covers the domain — the
   same machinery that gains +6.5 on STEM moves nothing on Swiss law
   because the shelf has no statutes. The registry must record, per RAG
   profile, which domains its corpus snapshot covers.
2. **Budget-tiered floor fixes**: `rag_presolve` (+6.5 mean, cheap) and
   `flagship_panel` (+4.1 mean lift but higher absolute ceiling,
   ~3× cost) fix the same diagnosed floor from different directions —
   the router chooses by caller budget, not by which is "better."

**Design principle now triple-confirmed** (thinking_all, qwen38_panel,
qwen38_judge, R2): capability added downstream of the panel, or
homogeneously across it, does not pay. The gains all come from upstream
knowledge (retrieval, tier routing) or calibrated diversity (one thinking
seat). New profile proposals should be screened against this before
spending pilot budget.

## 3. The router

Three versions, shipped in order, each falling back to the previous:

- **R0 (heuristic)**: caller-supplied domain tag or trivial keyword rules
  → profile. This is what the benchmark harness already does implicitly
  (item.subject). Zero risk, zero generality.
- **R1 (classifier call)**: one `qwen3.6-flash` JSON call per query:
  `{domain, difficulty_estimate, checkability, agentic}` → registry
  lookup via explicit rules. Cost ~$0.0002/query — two orders of
  magnitude below one deliberation. Failure mode to measure: router
  misclassification sending hard questions to `single-call`; mitigated
  by biasing uncertain classifications toward stronger profiles
  (asymmetric loss: over-orchestrating wastes cents, under-orchestrating
  costs correctness).
- **R2 (calibrated)**: R1's features + the calibration memory (§5.1) as
  a prior: per-(domain, profile) measured accuracy and cost decide the
  dispatch by expected-utility, not fixed rules. This is where MoO
  starts genuinely learning from its own history.

**Ceiling analysis discipline:** every router evaluation reports three
numbers — flat-best (best single profile on the blend), routed (actual),
oracle (per-question best profile in hindsight). Routed value = distance
from flat-best toward oracle. If oracle-minus-flat is small on a
workload, MoO is not worth its complexity THERE, and we say so.

## 4. Thinking-mode axis, settled empirically

The mixture explicitly encodes what the ablations established rather than
leaving reasoning depth to intuition:

- Default: exactly ONE thinking seat (diversity > uniform capability;
  thinking_all is a validated negative).
- Full-thinking panels only where a domain blind spot is diagnosed AND
  tier-swap validated (stem-max pattern).
- Thinking off entirely for `single-call` easy routes and for cheap
  fast-voter roles (the engine's founding economic premise).
- Judge always thinking; gate never thinking (it's a cheap doubt
  detector, validated as such).

## 5. Memory architecture (orchestration layer — works against hosted APIs)

Three memories, one firewall.

### 5.1 Calibration memory (adopt first — highest value, lowest risk)
A store of per-(profile, domain, difficulty) outcome statistics from
every run the system executes: accuracy, escalation rate, overturn-
correct rate, false-escalation rate, drop rate, cost tokens. This is
literally what `lever_findings.md` has been accumulating by hand — the
loop's scoreboard, productized. Feeds: R2 routing priors, profile
regression alarms (a profile drifting below its validation band flags
re-validation), and honest public reporting (the site's escalation-
integrity numbers come from here).
Implementation: SQLite + a writer in the shared result path. No
framework needed.

### 5.2 Episodic deliberation memory ("case law")
Every deliberation transcript is already persisted (OSS bucket). Add an
embedding index; at query time retrieve k similar past cases. Two
consumers, in adoption order:
1. **Router feature**: similarity to past cases whose outcomes are known
   sharpens difficulty/domain estimates (cheap, no contamination risk in
   product mode).
2. **Judge precedent (experimental)**: the tribunal's judge sees "in a
   similar past case, the panel's unanimous answer was overturned
   because X" — fits the tribunal identity (case law), but MUST be
   validated for whether it helps or anchors the judge wrongly. Pilot
   with the same 3-seed bar before product adoption.

### 5.3 Agent skill/trajectory memory (terminal-agent profile only)
Store successful task trajectories; retrieve strategy sketches for
similar tasks (Voyager-style skill library, current OSS state per
research appendix). Bounded scope: strategy hints, never verbatim
command replay.

### The benchmark firewall (non-negotiable)
**Product mode: memory ON. Benchmark mode: memory OFF, always.** A
benchmark number produced with episodic memory of prior runs on the same
benchmark is contaminated, full stop. The runner sets a single flag;
every reported number states its mode. This discipline is what keeps our
published claims auditable, and it goes in the code as an assertion, not
a convention.

## 6. Attention and context efficiency — the honest boundary

We call hosted Qwen models. There is no access to attention internals on
that path. What the user asked for splits cleanly into what we can do
now versus what self-hosting would unlock, and the plan refuses to blur
that line.

### 6.1 Applicable NOW (hosted API)
- **Prompt-cache engineering.** The Token Plan Anthropic-compatible
  endpoint already returns `cache_creation_input_tokens` /
  `cache_read_input_tokens` (observed in our own smoke tests). Panel
  calls share a large static prefix (system prompt + lens preamble +
  choice formatting rules). Restructure every role prompt as
  [static shared prefix][per-question suffix] so 3-6 calls per question
  hit the cache instead of re-prefilling. Expected effect: input-token
  cost and latency reduction across every profile; measured, not
  assumed, via the usage fields we already log. Same restructuring for
  the agent's per-turn prompts (system + task statement stable across
  15 turns).
- **Judge context ordering.** The judge reads the longest context in the
  system (full transcript). Lost-in-the-middle effects are real and
  documented (research appendix pins current best practice); reorder the
  tribunal record so the load-bearing pieces (dissenting rationale,
  verifier findings) sit at the edges, and measure on a replay set —
  judge-input reordering is free to A/B against saved transcripts
  without new solver spend (the gate-replay pattern already built).
- **Transcript compression for the judge.** Solver reasoning is
  capped at 3 sentences by prompt, but agent trajectories and long
  tribunal records aren't; evaluate a compression pass (LLMLingua-family
  or successor per research appendix) ONLY if judge-context length is
  shown to correlate with overturn errors on replay data.

### 6.2 Gated on self-hosting open-weight Qwen (explicit decision, not
drift)
- Prefix KV-cache sharing across panel calls (vLLM/SGLang state per
  research appendix) — the inference-level twin of §6.1, worth real
  money at panel fan-out.
- Long-trajectory attention management (StreamingLLM-class or current
  successor) for the agent profile.
- Speculative decoding for the cheap tier.
**Gate condition:** self-hosting is justified only when monthly hosted
spend or quota ceilings measurably constrain the roadmap (the Token Plan
5h/7d sliding windows already serialized our experiments twice in one
night — that pressure is real data for this decision). A one-page
cost/benefit with measured numbers precedes any GPU commitment.

## 7. Phasing

- **M0 — Profile registry refactor.** Levers become declarative profiles;
  one engine path consumes them; benchmark-mode flag + memory firewall
  assertion land here. (Code motion, no new claims. TDD throughout.)
- **M1 — Router R1 + `single-call` + blended-workload eval.** Build the
  mixed benchmark blend (GPQA hard + SuperGPQA hard + MMLU-Pro slice +
  LEXam slice + a saturated-easy slice); report flat-best / routed /
  oracle. MoO earns its existence here or stops.
- **M2 — Calibration memory + R2.** SQLite store, writer, router priors;
  re-run M1 eval; regression alarms live.
- **M3 — Prompt-cache restructuring + judge context ordering.** Measured
  via existing usage logging and gate-replay A/Bs.
- **M4 — Episodic memory (router feature first, judge precedent as
  experiment) + law-profile verifier tool + math-profile pilot.**
- **M5 (conditional) — self-hosting cost/benefit decision doc; only then
  inference-level work.**

Each phase ends with its numbers in `lever_findings.md`-style docs and
the loop's validation bar applied to any accuracy claim.

## 8. Risks, stated plainly

- **Router misclassification** silently downgrades hard questions; the
  asymmetric-loss bias (§3) plus calibration alarms are the mitigations,
  and the oracle-gap metric makes the damage visible rather than
  hidden.
- **Profile proliferation** without validation discipline would turn the
  registry into folklore; the 3-seed bar is the gate, and profiles the
  data stops supporting get demoted to documented-negative status (the
  registry keeps its negatives, like the harness does today).
- **Memory-induced contamination** of public claims — handled by the
  firewall assertion; any number published from product mode says so.
- **Complexity vs. the frozen submission**: none of this touches the
  submitted engine or numbers until after judging (Aug 11); MoO work
  lives beside it, same as every lever has.

## Appendix A — verified open-source landscape (adversarially verified 2026-07-22)

Every item below was verified against a live primary source with a
3-vote adversarial pass. Maintenance facts are as of 2026-07-22 in a
fast-moving space — re-check before adoption.

### Bucket 1 — usable NOW against the hosted Qwen API

**ADOPT-NOW (three moves, all evidence-backed, none require a framework):**

1. **Prompt-cache engineering, designed around the real contract.** Cache
   prefixes build in strict order tools → system → messages; any change
   at a level invalidates that level and everything downstream, so
   tool-definition churn nukes the whole cache. Put the breakpoint on the
   last block identical across requests. **The load-bearing finding for
   our 3-solver fan-out:** a cache entry only becomes available after the
   first response *begins* — simultaneously-fired parallel calls sharing
   a prefix all miss and all pay cache-write price (1.25×–2×). Fix: fire
   a cheap warm-up call (or stagger the first solver) before the rest of
   the panel. Verified against Anthropic's official docs AND replicated
   on Alibaba's own Model Studio context-cache docs — but with regime
   differences we must not paper over: **Alibaba documents 125% write /
   10% read multipliers and 5-min-only TTL; the 1-hour TTL and automatic
   top-level breakpoints are Anthropic-only and unverified on our Token
   Plan endpoint.** Measure via the `cache_creation_input_tokens` /
   `cache_read_input_tokens` fields we already log.
   (platform.claude.com/docs/.../prompt-caching; alibabacloud.com Model Studio context-cache)

2. **Judge-stage position-bias mitigation (randomize/swap answer order).**
   LLM-judge position bias is systematic, not noise — peer-reviewed
   (IJCNLP-AACL 2025, 15 judges, >150k evaluation instances), and
   **strongest precisely in close-call disagreements**, which is
   QuorumQA's exact escalation trigger. Mitigation: randomize or
   swap-and-average answer order at the judge. Cheap to A/B on our saved
   transcripts via the existing gate-replay path (no new solver spend).
   (arxiv.org/abs/2406.07791)

3. **Episodic case-memory as a PATTERN to borrow, not a framework to
   adopt.** The pattern is validated (DS-Agent, Memento's Case Bank,
   MemRL's two-phase semantic-then-utility retrieval) but the leading
   implementations are research artifacts (Memento: MIT, arXiv 2508.16153;
   MemRL: MIT, arXiv 2601.03192, commits through Jul 2026). Build our own
   §5.2 case-law store on SQLite+embeddings using their retrieval shape,
   don't take a dependency. (github.com/Memento-Teams/Memento; github.com/MemTensor/MemRL)

**EVALUATE (one credible framework, still probably overkill):**
- **Mem0** (Apache-2.0, actively maintained — release 2026-07-13, 61k
  stars). Code-verified to genuinely fuse semantic + BM25 + entity-graph
  retrieval in the OSS SDK (not just marketing). Two honest deflators:
  time-aware ranking is platform-only (absent from OSS `scoring.py`), and
  its headline benchmark numbers are the proprietary platform, not the
  OSS SDK. Earns its complexity only if we specifically want BM25+entity
  fusion out of the box; SQLite+embeddings covers most of our value.
  (github.com/mem0ai/mem0)

**SKIP (real, active, wrong-fit):**
- **Graphiti/Zep** (Apache-2.0, active bi-temporal knowledge graph):
  solves evolving-user-state, which QuorumQA doesn't have. Zep's
  self-hosted Community Edition was deprecated April 2025.
- **LangMem** (MIT, pre-1.0): LangGraph-coupled, functionally stalled
  since Oct 2025.

**UNVERIFIED from the original candidate list (treat as unknown, not
safe):** A-MEM, MemoRAG, cognee (status not confirmed either way); the
LLMLingua context-compression family's current state; and
lost-in-the-middle mitigations beyond the judge position-bias finding.
§6.1's compression idea therefore stays gated on a fresh verification
pass before adoption.

### Bucket 2 — self-hosting inference-level (UNRESEARCHED, do not assume fine)

**Nothing in this bucket survived verification.** Zero confirmed claims
on vLLM automatic prefix caching, SGLang RadixAttention, LMCache,
StreamingLLM/attention sinks, sparse/linear attention adoption, or
speculative decoding for Qwen-family models. This is a coverage gap, not
a green light. §6.2's self-hosting work must open with its own verified
research pass; the plan explicitly does NOT endorse any specific
inference-stack technique yet, and the self-hosting decision doc (M5)
owns that research.

### Net effect on the plan
The three adopt-now moves map exactly onto M3 (prompt-cache
restructuring + judge ordering) and §5.2 (case-law store, now confirmed
as build-our-own not adopt-a-framework). No plan phase depended on a
framework we can't stand behind, and the one place the plan hand-waved
("compression tools that work") is now correctly marked unverified.
