# The general orchestration contract (Program 1 design)

**Status: DESIGN. Nothing here is implemented.** No schema is changed, no code is
written, no profile is added. This document defines the contract that a
general-purpose Mixture of Orchestrations would have to satisfy, and the two
proof families that must validate it before any implementation begins.

Written 2026-07-30. Approved direction: *contract first*, then prove it against
one hard-verification family (coding or math) and one soft-evaluation family
(research or writing), so the abstraction cannot be accidentally shaped around
multiple-choice QA.

---

## 0. The finding this contract is built around

On 2026-07-30 `flagship_panel`'s compute-matched control was run for the first
time (`benchmark/verify_compute_matched_control.py`). Each leg measured
directly:

| Comparison | net | p | n |
|---|---|---|---|
| 3× flagship majority vs 1× flagship | **+9** | **0.0245** | 251 |
| `flagship_panel` vs 3× majority | **+2** | **0.344** | 237 |

**The repo's only validated accuracy win is a compute effect, not a
deliberation effect.** Sampling the flagship three times and voting reproduces
the bulk of it; the skeptic/verifier/judge apparatus adds a residual
indistinguishable from zero.

Two consequences shape everything below:

1. **More opinions from the same model is not a quality mechanism.** It is a
   compute mechanism, and self-consistency already captures it more cheaply than
   a tribunal does. A contract that makes "add another seat" the easiest
   modifier to reach for will keep re-deriving this null.
2. **Verification and execution are the only levers left that manufacture new
   information.** A passing unit test, a symbolic identity, a retrieved primary
   source, a failing assertion — these are facts the model did not have before.
   A fourth opinion is not. The contract must therefore be organized around
   *evidence acquisition*, with deliberation as one narrow instrument inside it.

Corroborating internal evidence: 61.6% of wrong panel rows are unanimous
(structurally invisible to any disagreement trigger); a stronger judge got 9/9
overturns correct for zero net gain (coverage, not judge quality, was binding);
the oracle over the current registry caps at 96.4% against flat-best's 92.8%, so
*perfect selection* over today's profiles is worth at most +3.6pt.

---

## 1. What the contract must express that today's schema cannot

`OrchestrationProfile` is `panel: list[SeatSpec]` → `acceptance_policy` →
`tribunal`, plus optional `retrieval`. Every field answers *who votes and who
adjudicates*. Three things it cannot represent, each required by a real task
family:

| Required | Example | Why the current schema can't |
|---|---|---|
| **Sequence with data dependency** | inspect repo → plan → edit → run tests | No notion of ordered steps or of one step consuming another's output |
| **Bounded iteration on a signal** | repair until tests pass, max 3 rounds | `tribunal` fires at most once; there is no loop construct |
| **Conditional branching on evidence** | if no primary source found, abstain rather than answer | `acceptance_policy` branches on *vote agreement* only |

This is why the substrate cannot be extended into the general system: adding
fields for these would not be extending the schema, it would be replacing it.
The substrate is retained instead as **one template family** (`deliberation`)
among several, unchanged and still measured.

---

## 2. The contract, stated as five obligations

Any orchestration — QA tribunal, coding loop, research pipeline — must satisfy
all five to be admissible. This is the actual contract.

### Obligation 1: declare a typed task envelope
A normalized request carrying: the request text, conversation context,
attachments, a **distribution** over candidate task families (never a hard
label — the current router's `item.subject` falls through to `unknown` on any
unseen string, and MedQA has no subject column at all), requested output
format, freshness requirement, stakes tier, mode, cost ceiling, latency ceiling,
privacy constraints, and available tools/providers.

### Obligation 2: declare a verification contract *before* execution
Every orchestration must state, in advance, what would count as evidence that
its output is correct, at what grade:

| Grade | Instrument | Example |
|---|---|---|
| **H — hard** | executable / symbolic | unit tests, compiler, `sympy_check`, schema validation |
| **E — evidence** | primary-source grounding | citation entailment, freshness check |
| **X — cross-solution** | independent derivations | method-diverse solvers, blinded critique |
| **R — rubric** | structured criteria | instruction adherence, completeness |
| **S — soft** | model judgement | last resort, no verifier available |
| **N — none** | human-required | high-stakes or unresolved conflict |

**Rule with teeth: an orchestration may not use a lower grade when a higher one
is available for the task.** No LLM judge where a test suite exists. This single
rule is what would have prevented today's result from being mistaken for a
deliberation win — a tribunal is grade X at best, and X on same-family seats is
where the 61.6% unanimous-wrong ceiling lives.

### Obligation 3: declare a budget and a stopping rule
Total token/tool cost, sequential critical path (distinct from total cost —
parallelism buys latency, not tokens), max repair rounds, and at least one
terminating condition from: hard verifier passes · all material claims
evidence-supported · candidates converged with no surviving high-severity
objection · repairs stopped improving · expected marginal gain below next
action's cost · budget/latency exhausted · abstain.

**No orchestration is admissible without a stopping rule.** "Agents converse
until done" is not a stopping rule.

### Obligation 4: emit a structured trace, not prose
Per step: what ran, inputs consumed, evidence produced, verification grade
achieved, cost, latency, and the decision taken next with its reason. This is
what makes calibration learnable and claims auditable. **Never raw hidden
chain-of-thought** — structured claims, tool results, and concise role
rationales only.

### Obligation 5: declare an output contract
Answer/artifact · supporting rationale · sources where applicable ·
**verification summary naming the grade actually achieved** · unresolved
uncertainty · material dissent · cost and latency · mode · orchestration
summary.

---

## 3. Workflow representation: typed DAG with a bounded repair operator

Assessed three options.

- **Unrestricted agent conversation** — rejected. Unbounded cost, no stopping
  rule, destroys calibration. Violates Obligations 3 and 4 by construction.
- **Pure DAG** — insufficient alone. Cannot express "repair until tests pass",
  which is the central shape of coding work.
- **Typed DAG + a `repeat_until` operator with a declared max and a declared
  signal** — recommended. Acyclic except for explicitly bounded repair loops,
  each of which must name the verifier whose result it polls and a hard
  iteration cap. This keeps every workflow statically analysable for worst-case
  cost while still expressing iteration.

**Node primitives** (closed set; adding one is a contract change requiring
re-validation): `classify` · `decompose` · `propose` · `retrieve` · `research` ·
`execute` · `calculate` · `critique` · `cross_examine` · `verify` · `rank` ·
`synthesize` · `repair` · `abstain` · `request_human_review`.

**Bounded modifiers** the controller may apply to a validated template:
add retrieval · add one independent solver · promote one role's model tier ·
add a deterministic checker · add an evidence auditor · add a critic/editor
pass · change the synthesizer · adjust search depth · abstain.

Closed sets on both are deliberate: they are what keep the calibration table
learnable, which is the asset the current substrate actually earned.

---

## 4. Task-family → orchestration → verification matrix

| Family | Workflow shape | Primary grade | Deliberation's role |
|---|---|---|---|
| **Coding / SWE** | inspect → plan → execute → test → `repeat_until(tests pass, max 3)` | **H** | Independent reviewer only for architecture/security, *after* tests pass |
| **Mathematics** | method-diverse derive → symbolic/numeric check → equivalence-normalize → counterexample search | **H** | Proof-critic for non-computational steps only |
| **Research** | decompose → parallel search tracks → retrieve primary → extract atomic claims → triangulate → citation/freshness audit → synthesize | **E** | Adversarial evidence review, not opinion debate |
| **General factual** | answer direct if stable+low-risk → retrieve if fresh/uncertain → verify only outcome-changing claims | **E** or none | Escalate only on surviving contradiction |
| **Science (QA)** | *today's substrate*: panel → acceptance → tribunal | **X** | The whole template — and now known to be a compute effect |
| **Writing / editing** | infer audience → outline → draft → rubric critics → editor synthesis → instruction-adherence check | **R** | Rubric criticism; **majority voting is invalid here** |
| **Data analysis** | data contract → quality validation → reproducible computation → cross-check → separate findings from interpretation | **H** | Verify narrative matches computed results |
| **Planning / decisions** | clarify objectives → alternatives → scenario model → risk/financial/contrarian reviews → synthesize | **R** | Genuine — no false consensus; reversible vs irreversible flagged |
| **High-stakes med/legal/fin** | authoritative-source retrieval → prominent limitations → info-not-advice → **abstain or human review** | **E** + **N** | Agreement is never presented as proof |

**The design test the brief demanded:** these are not the same graph. Coding
terminates on an executable signal; writing has no such signal and terminates on
rubric satisfaction; high-stakes may terminate in refusal. If a future revision
collapses them, it has failed.

---

## 5. Mode contracts

| | Fast | Balanced (default) | Max |
|---|---|---|---|
| Objective | useful answer, minimal latency | frontier-parity at lower expected cost | materially better than one frontier call |
| Grades allowed | up to E | up to H, selective | all, incl. N |
| Max repair rounds | 0 | 1 | 3 |
| Escalation | only on cheap hard-failure signal | on evidence | planned |
| **Success criterion** | quality floor per family, latency envelope | **parity band vs flagship-single at materially lower cost on realistic traffic** | **beats a COMPUTE-MATCHED baseline, not a 1× call** |

Max's criterion is written that way *because of* §0. Beating a 1× call at 3×
tokens is measuring spend. Today's result is the proof.

Provisional targets — **hypotheses requiring measurement, not claims**: Fast
≤1.2× cheap-single cost / p95 ≤6s; Balanced ≤0.6× flagship-single / p95 ≤20s;
Max ≤4× flagship-single hard-capped / p95 ≤120s.

---

## 6. What is reused, and what is retired

**Reused as-is:** the profile registry pattern · the calibration table and
`cheapest_within_margin` selection · the benchmark memory firewall
(`set_benchmark_mode` / `assert_benchmark_mode_no_memory`) · every committed
result and the whole negative-results ledger · the paired-McNemar discipline and
its bar.

**Reframed:** today's seven profiles become the `deliberation` family — valid,
measured, and no longer privileged. The router becomes one input to a controller
rather than the decision-maker.

**Retired:** `item.subject` as a routing feature (benchmark metadata, absent on
real requests); the assumption that the tribunal is the quality mechanism (§0);
`mode: "agent"` as a data-only placeholder — it either gets a real executor
under this contract or it comes out of the schema.

---

## 7. Validation gates before implementation

1. **G1 — contract sufficiency.** Express coding and research as typed DAGs on
   paper. Gate: neither is expressible as `panel → acceptance → tribunal`, and
   both satisfy all five obligations. *No code.*
2. **G2 — worst-case cost analysability.** Given a template plus modifiers,
   compute worst-case tokens and critical path statically. Gate: no workflow
   admits unbounded cost.
3. **G3 — smallest credible proof.** Implement the runtime for exactly two
   families, one grade-H and one grade-R/E. Gate: the grade rule (Obligation 2)
   demonstrably fires — i.e. an LLM judge is *refused* where a test exists.
4. **G4 — no regression.** The `deliberation` family reproduces today's
   committed numbers bit-for-bit through the new runtime.

**G4 is the honesty gate.** If the new layer cannot reproduce the old results
exactly, the comparison across this repo's entire history breaks.

---

## 8. Risks

- **Contract shaped by QA anyway.** Mitigated by G1's two-family requirement.
- **Modifier explosion** — closed set, and each addition re-validates.
- **Calibration starvation:** more templates × modifiers means thinner cells.
  Today's table already has n=4–5 cells. Priors must be hierarchical, and cells
  below a minimum n must fall back to the family default.
- **The grade rule gets bypassed under deadline pressure.** It is the one rule
  whose violation reproduces today's null. It should fail closed.
- **Latency accounting forgotten.** Parallelism reduces wall-clock, never cost;
  they must be separately budgeted or Max mode silently becomes unusable.

---

## 9. Open decisions

1. Which grade-H family proves the contract first — **coding** (richest
   verification, needs Docker, currently down) or **math** (`math_grade.py`
   already validated at 0/4000 false positives, no infrastructure needed)?
   *Recommendation: math, because the verifier is already trusted and it
   isolates the contract from environment flakiness.*
2. Does `mode: "agent"` get an executor under this contract, or come out of the
   schema until it does? *Recommendation: remove it; a data-only mode that
   raises `NotImplementedError` is a claim the code cannot honour.*
3. Provider-agnostic interfaces now, or Qwen-first with the seam designed in?
   *Recommendation: the seam, not the abstraction — no second provider is
   provisioned, and cross-vendor is parked.*
