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

**Read the comparator column first.** An audit on 2026-07-26 found two rows in
this table measured against a *cheap-panel* control while the heading promised a
flagship one. The table is now split by comparator, and each row states the test
behind it rather than only its delta.

**(a) Against a single `qwen3.7-max` call — the flagship comparator**

| Benchmark | Config | Models & roles | Result |
|---|---|---|---|
| **SuperGPQA-hard** | `flagship_panel` | 3 solvers = `qwen3.7-max` (thinking); Skeptic/Verifier = `qwen3.6-flash`; Judge = `qwen3.7-max` | **+4.1 mean** (+3.8 / +2.4 / +6.2); pooled b=11 c=1 **net +10, p=0.0032**, n=241, at ~3.0× tokens. **⚠ Clears the bar against a 1× call, but FAILS its compute-matched control (2026-07-30):** 3× flagship majority alone gets **+9 (p=0.025)**; the tribunal's own contribution is **+2 (p=0.34, n.s.)**. This is a **compute effect, not a deliberation effect** — see §2.1 below |
| **Chemistry** | `chem_thinking_gate` | organic-chem → 3× `qwen3.7-max`; else 3× `qwen3.6-flash` (seat 3 thinking) + doubt-gate; Judge = `qwen3.7-max` | **90.9% mean** (3 seeds). **Updated 2026-07-29** — the two missing matched baselines landed: pooled b=16 c=4 **net +12, p=0.0059 — clears the bar**. Per-seed: 217 net +9 (p=0.0020, big win), 314 net +4 (p=0.145, noise), **471 net −1 (slightly negative)** — a real pooled effect built from one strong seed, one null, one mild loss, not three confirmations of the same number |
| **GPQA-Diamond** | `thinking_gate` | 3× `qwen3.6-flash` (seat 3 thinking) + doubt-gate; Judge = `qwen3.7-max` | 86.7 / tie / +1.1 — matches-or-beats, marginal, inside noise |
| **GPQA-Diamond** | `universal_gate` | shipped cheap panel, unconditional escalation on unanimity (no doubt-check) | **UPDATED 2026-08-01 — now 3 seeds (1001/2311/3407): pooled net +25, c=0, n=269, p=2.98×10⁻⁸** (conservatively **+21, p=4.8×10⁻⁷** counting each item once, since 3 seeds of 90 over a ~198-question set cover only 170 unique items). Every seed clears the single-seed bar independently (+9 / +11 / +5). Recovers 25/38 unanimous-wrong (65.8%), breaks **0/118** unanimous-right. **Survives its compute-matched control**, run up front at the same seed: `diversified_panel --n-solvers 9 --no-tribunal` scores 65.2% vs 89.9% (paired net +22, p=0.00001), and within that arm N=3→N=9 nets exactly 0. **Read what it is:** the lever escalates everything, so judge calls/item = **1.00** and *nothing returns without a flagship call*. A claim about **when to escalate** (all items vs only splits), **NOT** "cheap seats beat a stronger model". ⚠ **TB-1 (2026-08-02) supplies the missing denominator and it is a NULL:** against a single `qwen3.7-max` call on the same items, `universal_gate` scores 238/265 vs 237/265 — **net +1, p=0.50** — at **4.7× the tokens**. The +25 above is real but is measured against a comparator 9 points below the flagship; the scaffolding's entire gain is climbing back to where one flagship call already was. See `benchmark/results/tb1_flagship_comparison_result.md` |

**(b) Against the cheap-panel control (3× `qwen3.6-flash`, no retrieval)** —
*not* a flagship comparison:

| Benchmark | Config | Result vs cheap-panel control | Against a flagship call |
|---|---|---|---|
| **Retrieval** | `rag_presolve` | +4.7 / +6.9 / +8.0 / **−5.6** (mean **+3.5**) | **−7.0 / −2.4 / −4.7 — loses on every seed where the comparison exists** |
| **Retrieval, gated** | `rag_thinking_gate` | +0.0 / +4.6 / +4.5 — never negative vs control | **unmeasurable** — seeds 271/606/838 have no flagship baseline file |

**(c) Not an accuracy comparison at all**

| Benchmark | Config | Result |
|---|---|---|
| **Coding agent** | `QuorumQAAgent` hardening | single `qwen3.7-max` agent, Harbor sandbox — graded coverage **36% → 86%** |

Honest framing: **exactly one row above clears the bar** — `flagship_panel` on
SuperGPQA-hard. It is **sampling-beats-one-sample**, not
cheap-beats-flagship: the config *uses* flagship solvers, and the
compute-matched control (below) shows three flagship samples beat one
(+9, p=0.025) while routing those samples through a tribunal instead of a
majority vote adds nothing measurable (+2, p=0.34). At **~3.0× the measured
tokens** (10,685 vs 3,589 tok/q, summed over every call at seed 7).

### The compute-matched control was run on 2026-07-30. The claim does not survive it.

[capability-roadmap.md](capability-roadmap.md) mandates that "every
whole-pipeline swap (panels, councils, replicated ensembles) must carry a
compute-matched control — the same base config sampled the same number of times,
aggregated by majority," because without it a gain is indistinguishable from
plain self-consistency. That control had never been run for `flagship_panel`. It
has now been: 3× `qwen3.7-max` single calls per item, text-majority, no tribunal,
on the same items and seeds (85/84/84 rows).

**Each leg measured directly — paired tests on different shared-item sets do not
subtract cleanly, so nothing here is inferred by arithmetic:**

| Comparison | net | p | n | verdict |
|---|---|---|---|---|
| 3× flagship majority **vs 1× flagship** | **+9** | **0.0245** | 251 | **clears p<0.05** |
| `flagship_panel` **vs 3× majority** (the tribunal's own contribution) | **+2** | **0.344** | 237 | **does not clear** |

**The self-consistency leg carries the claim; the tribunal leg does not.**
Sampling the flagship three times and taking a majority reproduces the bulk of
the +10 on its own. The skeptic/verifier/judge apparatus adds a residual of +2
that is statistically indistinguishable from zero. Self-MoA (ICML 2025) predicted
exactly this, and the roadmap predicted it too — which is why it required the
control.

**Corrected claim.** `flagship_panel`'s advantage over a single flagship call is
a **compute effect, not a deliberation effect**. It is honestly stated as: *three
samples of the flagship beat one sample of the flagship (+9, p=0.025); routing
those samples through a tribunal instead of a majority vote adds nothing
measurable (+2, p=0.34) at roughly the same cost.* The +4.1 / pooled +10 figures
against a 1× call remain arithmetically correct and are **not** withdrawn — but
they may no longer be presented as evidence that deliberation works.

Reproduce: `python -m benchmark.verify_compute_matched_control`

`thinking_gate` on GPQA remains the closest to a genuine cheap-beats-flagship
result, with the flagship appearing only as the escalation judge — but it is
marginal and inside the noise band.

**The frozen submission number is 78.9%** — *below* the flagship's 84.4%, at
~11% lower cost. That was always a cost claim, never an accuracy claim.

---

## 3. Negative results — the largest artifact here

**[negative-results.md](negative-results.md)** — 22 measured nulls, each with
its **mechanism**, plus 6 methodological negatives (errors we caught in our own
work) and 4 adjudicated contradictions between our own documents.

Why this is the most valuable thing in the repo — stated carefully, because an
earlier version of this paragraph overreached. A
[verified research pass](frontier-oss-model-research.md) found that no
frontier-lab technical report **in its corpus** covered multi-agent ensembling,
mixture-of-agents, LLM-as-judge, or self-preference bias; that corpus was about
*building* single models. **That is a fact about the corpus, not about the
field** — published prior work on all of those topics exists, and this repo
cites some of it (Self-MoA, arXiv 2502.00674, appears here and in eleven other
places). The earlier claim that "these nulls have no published prior" is
retracted; see [`prior-art-and-positioning.md`](prior-art-and-positioning.md).

What makes the ledger valuable is not priority but **consolidation and
traceability**: 22 nulls measured on one reproducible orchestration stack,
under one benchmark harness and one token-based cost model, each diagnosed to a
*mechanism* rather than reported as a bare number, with positive and negative
outcomes recorded together and every claim traced to a committed artifact. Each
is still a run someone else does not have to waste.

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
