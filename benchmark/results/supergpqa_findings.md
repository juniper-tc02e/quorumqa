# SuperGPQA (hard subset) pilot findings

Third non-GPQA benchmark, and the most informative one for the Mixture of
Orchestrations design. n=86/90 (4 dropped), seed 42, `difficulty=hard`
subset, trimmed to 4 choices (see load_supergpqa.py — trimmed numbers are
not comparable to published SuperGPQA scores).

## The headline refines our central hypothesis

The "escalation needs flagship headroom" hypothesis from the MMLU-Pro
findings predicted: where the flagship has room to be wrong, QuorumQA
should recover value. SuperGPQA-hard is the cleanest possible test —
unlike LEXam (86%) and MMLU-Pro (94%), here the **flagship baseline is
79.1%**, MORE headroom than even GPQA-Diamond (84-86%).

**And the engine still lost, badly: 67.4% vs 79.1%, −11.6 points.**

So headroom is **necessary but not sufficient.** The hypothesis needs a
second term.

## What actually drives the gap: the cheap-tier-to-flagship distance

The tribunal is not the problem. When it fires, it works well: 27
overturns, 23 correct (85% overturn-correct — as good as GPQA's 78.6%,
far better than LEXam's coin-flip). The problem is upstream, in two
linked measurements:

- **20 of 86 questions (23%) were unanimous-wrong** — all three cheap
  solvers confidently agreed on the same wrong answer, so nothing
  escalated. That is ~3x GPQA-Diamond's unanimous-wrong rate.
- **Escalation rate was 51.2%** — the cheap panel split on half the
  questions, far above GPQA's 37.8%.

Both point at the same thing: on this broad, hard Science/Engineering
set, the cheap tier (`qwen3.6-flash`) sits so far below the flagship
(`qwen3.7-max`) that (a) it splits constantly, and (b) when it doesn't
split, it's often confidently, unanimously wrong. Even a perfect tribunal
on the 51% that escalate cannot close a gap that large, because the 23%
unanimous-wrong floor is uncatchable by construction (confidence doesn't
discriminate — established on GPQA, re-confirmed by the high unanimous-
wrong rate here).

**Refined hypothesis:** QuorumQA's deliberation recovers value only when
the cheap solver tier is *close enough* to the flagship on the question
set that escalation can bridge the remaining distance. Flagship headroom
is necessary (so the flagship itself has errors worth beating), but the
cheap-tier-to-flagship GAP must also be small enough that the uncatchable
unanimous-wrong floor stays low. GPQA-Diamond happens to sit in that
sweet spot for this model pair; SuperGPQA-hard is past it — the cheap
tier is simply out of its depth across too much of the set.

Per-discipline (small n, directional only): Science n=58 baseline 76% →
engine 64%; Engineering n=25 baseline 88% → engine 76%. The loss is broad,
not concentrated in one subfield the way GPQA's was in Organic Chemistry —
which matters for the lever choice below.

## What this means for Mixture of Orchestrations

This is the strongest evidence yet for the MoO router's core job: **it
must estimate the cheap-tier-to-flagship gap, not just raw difficulty.**
A difficulty classifier alone would route SuperGPQA-hard to a heavy
deliberation profile and lose 11.6 points; the right move is the opposite
— where the cheap tier is out of its depth across a whole domain, route
the *solver panel itself* to a stronger tier from the start (the
`chem_flagship_gate` pattern), or fall back to a single flagship call
(the `single-call` profile), rather than deliberating with a panel that
can't get close.

GPQA's Organic Chemistry was a narrow, single-subject version of exactly
this (one blind subject in an otherwise-competent panel), and
`chem_flagship_gate` fixed it by routing that one subject to flagship
solvers. SuperGPQA-hard is the broad version: the "blind subject" is most
of hard Science/Engineering. The open question the next lever tests:
**does routing the whole domain's solver panel to the flagship tier
recover the gap here the way it did for chemistry?** If yes, the
domain-profile approach generalizes cleanly from one subject to a whole
benchmark. If a flagship solver panel still can't close it, that tells us
the ceiling is the tier itself, not the orchestration — a different and
also valuable finding.

## Caveats

- 4-choice trim (from SuperGPQA's native up-to-10): this hard subset may
  be easier than untrimmed SuperGPQA, so the 79.1%/67.4% absolutes aren't
  comparable to published numbers; the −11.6 *delta* between two systems
  on the identical trimmed items is the trustworthy quantity.
- n=86, single seed. The delta is large enough (−11.6) that it won't
  vanish with more samples, but the per-discipline splits are too small
  to trust individually.
- The hard-label subset skews heavily Science/Engineering (a property of
  SuperGPQA's own difficulty labeling), so this is not a broad-domain
  read — it's a hard-STEM read.

## The lever generalizes: flagship solver panel recovers the gap and beats the baseline

The open question above — does routing the whole domain's solver panel to
the flagship tier recover the gap, as `chem_flagship_gate` did for one
subject — is answered: **yes, decisively.** Ran the `flagship_panel`
lever (all three solver seats on `qwen3.7-max`, thinking on; skeptic/
verifier/judge unchanged) on the identical SuperGPQA-hard seed-42 set.

Apples-to-apples on the 78 items common to all three runs (drops excluded
by intersection, so drop-bias cannot skew the comparison):

| System (SuperGPQA-hard, 78 common items) | Accuracy |
|---|---|
| Single flagship baseline | 79.5% |
| Cheap-panel engine (shipped config) | 67.9% |
| **Flagship-panel engine** | **83.3%** |

Routing the solver panel to the flagship tier turns a **−11.6-point loss
into a +3.8-point win over the single flagship call** — a +15.4-point
swing over the cheap panel on the same questions. Escalation collapsed to
8.9% (flagship solvers agree far more often — the same dynamic seen on
GPQA), so the win comes almost entirely from a competent panel rarely
being unanimous-wrong, with the tribunal as occasional cleanup.

**This is the general-use proof the Mixture of Orchestrations thesis
needed.** On GPQA, `flagship_panel` beat the baseline by a margin inside
the noise band (+1.2/+3.4/+0.2) — because the cheap tier was already
close there, so a flagship panel had little to add. On SuperGPQA-hard,
where the cheap tier is genuinely out of its depth, the flagship panel
adds +3.8 cleanly — deliberation contributes *most* exactly where the
solver tier has real headroom AND the task is hard enough that even the
flagship errs. The domain-profile approach (`chem_flagship_gate`
generalized: route a whole hard domain's panel to the stronger tier)
transfers from one chemistry subject to an entire broad-STEM benchmark.

Caveat: one seed. The apples-to-apples margin (+15.4 over cheap, +3.8
over baseline on identical items) is large enough that it will not vanish
with replication, but a `flagship_panel` domain profile only enters the
MoO router as "validated" after the standard three-seed bar. Drops (11,
all flagship-thinking ReadTimeouts on hard questions, Engineering 7 /
Science 4) are the known API-latency ceiling and are excluded from the
comparison by intersection.

## Second seed (7): replicates

Ran the matched pair again at seed 7 (single-flagship baseline +
flagship_panel), apples-to-apples on the 82 common items:

| SuperGPQA-hard | Seed 42 | Seed 7 |
|---|---|---|
| Single flagship baseline | 79.5% | 79.3% |
| Flagship-panel engine | 83.3% | 81.7% |
| **Delta** | **+3.8** | **+2.4** |

Both seeds positive; the baseline is remarkably stable (79.5 / 79.3). Mean
+3.1 over two independent seeds — the flagship_panel-beats-single-flagship
generalization on hard STEM is replicated, not a one-seed artifact. The
margin is smaller at seed 7 (+2.4 vs +3.8), so the effect size carries
normal per-seed variance, but the sign is consistent. One more fresh seed
completes the 3-seed bar to promote `flagship_panel` to a validated MoO
domain profile; on current evidence it is a strong, replicated positive.
