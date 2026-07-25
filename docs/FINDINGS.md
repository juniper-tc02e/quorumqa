# QuorumQA — research findings index

QuorumQA is a multi-agent deliberation engine built on the Qwen family: three
cheap `qwen3.6-flash` solvers vote on a question; a 2+ majority is accepted
immediately; a split escalates to a tribunal (Skeptic → tool-using Verifier →
`qwen3.7-max` Judge). This document indexes everything we measured.

**Everything here is reproducible from committed result files.** Where a result
is one-seed or small-n, the n is stated. Where two of our own documents
disagree, the disagreement is catalogued and adjudicated rather than smoothed
over (see [negative-results.md §4](negative-results.md)).

---

## 1. The one law that organizes every result

> **Deliberation pays if and only if (a) solver errors decorrelate into visible
> disagreement, and (b) the escalation mechanism actually fires on it.**
> The **cheap-to-flagship gap** (the unanimous-wrong rate) is what predicts
> whether those conditions *can* be met — **not** benchmark difficulty, not
> baseline height, and not the subject label.

The evidence that makes the subject label useless: medicine and hard science are
both "knowledge-and-reasoning multiple choice," and they sit at opposite ends of
the table below.

**But the gap is NECESSARY, not SUFFICIENT — and our own data says so.** Figure
[F05](figures/f05_unanimous_wrong_vs_lever_delta.png) plots the gap against the
best lever delta, and two of five points land in a quadrant labelled *"large
gap, lever still lost"*: LEXam has a 22% unanimous-wrong rate and still loses
**−6.0**, and MMLU-Pro has 14% and loses **−2.0**. A large gap only pays when the
missing ingredient is *decorrelation*. Where it is missing **knowledge or corpus**
(LEXam's Swiss law against a STEM/US-law index) the gap is real, the escalation
fires, and the answer is still wrong. Earlier summaries in this repo stated the
gap as the predictor outright; that was too strong, and F05 is what caught it.

| Surface | Flagship single call | Cheap-tier unanimous-wrong | Best lever outcome |
|---|---|---|---|
| SuperGPQA-hard | ~79.5% | 23% | **+4.1 mean** (3 seeds) |
| Organic-chemistry slice | ~86.5% matched | large | **+4.4** (+7.9 on chem itself) |
| GPQA-Diamond | 84.4% | ~11% | **+1.1 mean** (marginal, inside noise) |
| MedQA | 94% | **4%** | ties (+2 = one item of 50) |
| MMLU-Pro STEM (4-way) | 96.7% | **1.7%** | **+0.0**, escalation 3.3% |
| MATH-500 L5 open-answer | 96.6% | 0% escalation *at both tiers* | inert |
| LEXam (law) | 86.0% | — | **−14** |

![The law, and where it breaks](figures/f05_unanimous_wrong_vs_lever_delta.png)

*The law and its counterexamples in one frame. SuperGPQA-hard (23% gap, +4.1) is
the confirming point; LEXam (22% gap, −6.0) and MMLU-Pro (14% gap, −2.0) sit in
the quadrant marked "large gap, lever still lost." Five points, not seven —
GPQA-Diamond is omitted because its only published unanimous-wrong figure is a
pooled quantity that would change this axis. No fit line: five heterogeneous
points at different n do not earn a regression.*

A corollary we did not expect and had to accept: on **6 of 9 benchmarks a bare
single flagship call Pareto-dominates every lever we ever built** — more tokens
for equal or worse accuracy. Levers clear the frontier on exactly two surfaces
plus the chemistry slice.

![Accuracy vs tokens](figures/f04_accuracy_vs_tokens_frontier.png)

*Six panels on a red "FLAGSHIP DOMINATES" ground, two on green. Pooled-marginal
data — read the shape, not the gaps.*

---

## 2. Validated wins (3-seed bar, vs a `qwen3.7-max` single call)

![Build progress in gap space](figures/f01_build_progress_gap_space.png)

*The wins below, in delta space against a single flagship call. Absolute
accuracies are not comparable across these benchmarks (SuperGPQA-hard and
MMLU-Pro-STEM are 4-choice trims), which is why there is no accuracy leaderboard
anywhere in this repo.*

| Benchmark | Config | Models & roles | Result |
|---|---|---|---|
| **SuperGPQA-hard** | `flagship_panel` | 3 solvers = `qwen3.7-max` (thinking); Skeptic/Verifier = `qwen3.6-flash`; Judge = `qwen3.7-max` | **+4.1 mean** (+3.8 / +2.4 / +6.2) |
| **Chemistry** | `chem_thinking_gate` | organic-chem → 3× `qwen3.7-max`; else 3× `qwen3.6-flash` (seat 3 thinking) + doubt-gate; Judge = `qwen3.7-max` | **90.9% mean**, +4.4 matched |
| **GPQA-Diamond** | `thinking_gate` | 3× `qwen3.6-flash` (seat 3 thinking) + doubt-gate; Judge = `qwen3.7-max` | 86.7 / tie / +1.1 — matches-or-beats, marginal |
| **Retrieval** | `rag_presolve` | cheap panel + top-k STEM passages pre-solve | +4.7 / +6.9 / +8.0 / **−5.6** (mean **+3.5**, "validated-with-variance") |
| **Retrieval, gated** | `rag_thinking_gate` | as above + reasoning gate | +0.0 / +4.6 / +4.5 — **never negative** |
| **Coding agent** | `QuorumQAAgent` hardening | single `qwen3.7-max` agent, Harbor sandbox | graded coverage **36% → 86%** |

Honest framing: the wins on SuperGPQA-hard and chemistry are
**orchestration-beats-flagship** — those configs *use* flagship solvers, so the
claim is "deliberation on top of the best model beats one call of it," at
higher cost. `thinking_gate` on GPQA is the closest to a genuine
cheap-beats-flagship result, with the flagship appearing only as the escalation
judge.

**The frozen submission number is 78.9%** — *below* the flagship's 84.4%, at
~11% lower cost. That was always a cost claim, never an accuracy claim.

---

## 3. Negative results — the largest artifact here

**[negative-results.md](negative-results.md)** — 22 measured nulls, each with
its **mechanism**, plus 6 methodological negatives (errors we caught in our own
work) and 4 adjudicated contradictions between our own documents.

Why this is the scarcest thing in the repo: a
[verified research pass](frontier-oss-model-research.md) established that **no
frontier lab publishes on multi-agent ensembling, mixture-of-agents,
LLM-as-judge, or self-preference bias.** Labs publish on *building* single
models, not *orchestrating* panels of them. These nulls have no published prior
to compete with, and each is a run someone else does not have to waste.

Selected mechanisms:
- **The homogeneity trap.** Making solvers stronger or more numerous *kills* the
  disagreement the tribunal needs. Three `qwen3.8-max-preview` solvers →
  **0% escalation**, ties the baseline, trails the cheaper flagship panel.
- **Coverage, not judge quality, is the bottleneck.** A stronger judge got
  **9/9 overturns correct and produced zero net gain** — it never sees the
  failures, because they never escalate.
- **Saturation actively harms.** On saturated surfaces deliberation *subtracts*
  (−4.0 / −6.1 / −12).
- **A signal that wasn't.** Answer-instability looks like a +24.4pp wrongness
  signal, but under a permutation null it lands on the null mean (p=0.48) — a
  pure arithmetic artifact.
- **The ceiling.** **61.6% of wrong panel rows are unanimous.** A
  disagreement-triggered escalation cannot see them *by construction*.

---

## 4. Research

| Document | What it establishes |
|---|---|
| [reasoning_arc_synthesis.md](../benchmark/results/reasoning_arc_synthesis.md) | The full "when does deliberation help" arc |
| [frontier-oss-model-research.md](frontier-oss-model-research.md) | Verified, cited digest of Kimi K2 / DeepSeek V3-R1-V3.2, with confidence tags. Includes the publication gap above, and that **"Kimi K3" is unconfirmed** |
| [same-provider-scaling-research.md](same-provider-scaling-research.md) | How far one provider's models can scale: 28-technique map, a do-not-spend list, and the honest ceiling |
| [capability-roadmap.md](capability-roadmap.md) | All 12 capability axes reframed by *structural advantage* rather than subject; which are winnable, which are not |
| [experiment-spec-book.md](experiment-spec-book.md) | 38 pre-registered, runnable experiment specs |

---

## 5. Methodology

![Every lever against the noise floor](figures/f02_lever_deltas_by_benchmark.png)

*Why most of these results are not claims. The shaded band is the ±2.5pp measured
noise floor (an n=90 control replicate flipped 14/90 items). The dashed lines sit
at ±5 **percentage points**, drawn as a visual proxy for the +5-**item**
net-discordant bar — the two coincide only at n=100, and every benchmark here has
n<100, so the drawn line is **more permissive than the real bar** (on an n=50
benchmark, 5pp is 2.5 items). Marker fill is computed from the true item count,
not from this line. A lollipop inside the band is indistinguishable from
re-running the same config; a lollipop past the dashed line is **not** thereby
significant.*

Standards adopted the hard way, after each was violated once:

- **Bars are net-discordant counts with an exact McNemar test.** A "+3 items per
  90" bar is *unreachable* — one-sided exact McNemar gives p=0.125 at +3 and
  p=0.0625 at +4, so **+5 is the minimum that clears p<0.05 — and only with
  zero losses** (b=5, c=0). That qualifier is load-bearing and was missing from
  this summary until 2026-07-26: a net of +5 built from 10 gains and 5 losses
  gives **p=0.151**, nowhere near significant, and at 10 discordant pairs the
  net required is **+8**. Net magnitude is therefore a *necessary screen, never
  sufficient*; the portfolio bar in
  [capability-roadmap.md](capability-roadmap.md) has always required
  `net ≥ +5` **and** `McNemar p < 0.05` as separate conjuncts, and that is the
  binding rule. Seven levers had been pre-registered against a bar their own
  analysis plan rejects.
- **Kill dominates bar**, pre-registered, never decided after seeing data.
- **Paired same-item designs only.** A run with dropped items is re-run, never
  analysed — one pilot was invalidated by 32/60 drops whose survivors then
  showed a meaningless 100%/100%.
- **Cost is measured in tokens, not price-list dollars.** The measured meter
  refutes the "cheap tier is 4× cheaper" assumption: **2,009 vs 3,096 tok** per
  seat (~35% cheaper), and on AIME the *cheap* call costs **4.6× more** than the
  flagship because `max_tokens` is not enforced and the small model rambles.
- **Contamination firewall.** Benchmark answer keys are never retrieved; a
  deliberate tripwire (retrieval scoring **−4.7** on a benchmark whose answers
  the corpus must not contain) is what proves the corpus is clean.

---

## 6. Tooling built along the way

| Tool | Why it exists |
|---|---|
| [`math_grade.py`](../benchmark/math_grade.py) | LaTeX/sympy answer-equivalence (`0.5` == `\frac12`, intervals, sets, `±`). **0 false positives in 4,000 pairs**, fails closed. Built because HuggingFace's `math_verify` is unusable on Windows |
| [`ifeval_verify.py`](../benchmark/ifeval_verify.py) | 25-checker IFEval scorer, validated against Google's official reference (50/50, 126/126, 77.22% vs 77.0–77.2%). **Found a bug in the official grader** — it is nondeterministic on its own fixture |
| [`quorumqa/letters.py`](../src/quorumqa/letters.py) | Frees the engine from hardcoded A–D to any A–J, with byte-identity at 4 choices proven by a frozen call-fingerprint fixture |
| [`escalation_policies.py`](../benchmark/escalation_policies.py) | Four escalation-trigger families, because "not unanimous" degenerates as panel size grows |
| [`rag/`](../src/quorumqa/rag/) | Hybrid BM25 + dense retrieval with RRF fusion |

---

## 7. Reproducing any number

```bash
pip install -r requirements.txt
python -m pytest tests/ -q          # offline suite, no API calls
```

Result files live in `benchmark/results/` (`*_findings.md` for write-ups,
`*.jsonl` for raw per-item outcomes). Offline analyses re-run with no API access
and print their own reproduce command, e.g.:

```bash
python benchmark/audit_selectors.py
python benchmark/analyze_family_floor.py
python benchmark/council_union_gate.py
```
