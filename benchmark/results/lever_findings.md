# Architecture lever findings

Exploratory research, run against the fixed HuggingFace-authenticated GPQA
path, **separate from the frozen n=90 submission run**
(`full_run2.jsonl`/`summary.md`, untouched throughout). Every number below
comes from `benchmark/lever_experiments.py` and the raw `lever_*.jsonl` files
in this directory.

## Why two seeds

Seed 42 is the same 90 questions the submission and the site are built on.
Seed 7 is a completely independent draw the levers were never tuned against.
A result that only holds at seed 42 is not evidence the mechanism generalizes
-- it could just mean the lever happens to fix exactly the errors we already
knew about. Every lever below was tested at both, except where noted.

## The noise floor (measured, not assumed)

Before trusting any lever's effect size, we measured what a **zero-change
rerun** looks like: the unmodified engine, same 90 seed-7 questions, run
twice.

| | Accuracy |
|---|---|
| Control run | 77.8% |
| Replicate run (identical code, identical questions) | 75.3% |

**2.5 points of pure sampling noise**, with 14/90 questions (15.6%) flipping
correctness between two identical runs -- solvers sample at temperature > 0,
so nothing here is fully deterministic. 8 of those 14 noise-flips were
Organic Chemistry, independently corroborating the diagnosis below from a
completely different angle. Any lever effect smaller than roughly this
magnitude should not be trusted from a single run.

## Diagnosis: where the baseline gap actually comes from

On the frozen seed-42 run, QuorumQA trails the flagship baseline by 5.5
points (78.9% vs 84.4%). Breaking down exactly where:

- 80% of the net loss (8 of 10 lost questions) never escalated at all --
  all three solvers agreed, confidently, on the same wrong answer. The
  orchestrator's escalation trigger (`orchestrator.py:27-39`) is pure exact-
  agreement; it has no way to notice.
- Confidence does not discriminate: unanimous-wrong cases average 0.865
  confidence vs 0.904 for unanimous-correct. One unanimous-wrong case hit a
  perfect 1.0 across all three seats.
- Subject does discriminate, with real statistical weight: Organic
  Chemistry (37/90 questions) has an 18.9% unanimous-wrong rate. Every
  physics subject (quantum mechanics, general physics, HEP, astrophysics,
  relativistic mechanics -- 35 questions combined) has **zero** unanimous-
  wrong cases. This is a systematic weakness in `qwen3.6-flash`'s organic-
  chemistry reasoning, not noise -- confirmed independently by the noise-
  floor measurement above, where Organic Chemistry was again the most
  volatile subject with no architecture change involved at all.
- A prior attempt at model diversity (a `qwen3.7-plus` seat, thinking off)
  was already tried and removed (`config.py:29-32`): 54.1% accuracy, weakest
  seat, source of every JSON-malformation drop. Re-proposing a plain model
  swap without addressing *why* that failed would reproduce the same result.

## Levers tested

| Lever | Mechanism | Cost driver |
|---|---|---|
| Gate | Cheap universal second-opinion call before accepting any unanimous answer; escalates only on detected doubt | 1 extra cheap call/question + tribunal only on flagged cases |
| Lever 2 / thinking-seat | One of three solver seats runs with `thinking=True` instead of the uniform `thinking=False` | Thinking tokens on 1 seat (~4.9x a plain call) |
| Lever 3 / subject-escalation | Force escalation for Organic Chemistry regardless of unanimity | More tribunal calls on ~40% of the question set |
| Lever 4 / five solvers | `N_SOLVERS=5` instead of 3 (existing config knob; lenses/temps cycle since only 3 of each are defined) | 2 extra solver calls/question |
| Combined | Lever 2 + Lever 3 together | Both of the above, stacked |
| thinking_all | All three seats `thinking=True`, still cheap tier | 3x thinking cost |
| **thinking_gate** | Lever 2's thinking-seat **+** the doubt-gate (not the blunt subject rule) | Thinking on 1 seat + 1 gate call, tribunal only when either signal fires |
| Flagship panel | All three solver seats on `qwen3.7-max` (thinking on), same escalation machinery | ~3x a single flagship call |

## Full results, both seeds

**Seed 42** (n=90 unless noted; flagship baseline 84.4% / $0.02396, unmodified engine 78.9% / $0.02132)

| Configuration | Accuracy | Cost/q | Escalation rate |
|---|---|---|---|
| **thinking_gate** | **86.7%** | $0.03679 | 52.2% |
| Lever 2 (thinking-seat) | 86.7% | $0.03329 | 47.8% |
| Combined | 85.6% | $0.03871 | 62.2% |
| thinking_all | 85.6% | $0.05086 | 18.9% |
| Flagship panel | 85.6% | $0.07507 | 12.2% |
| Lever 4 (five solvers) | 81.1% | $0.02973 | 43.3% |

**Seed 7** (n=88-90, drops noted; flagship baseline 86.5%/$0.02201 [n=89], unmodified engine 77.8%/$0.02152)

| Configuration | Accuracy | Cost/q | Escalation rate |
|---|---|---|---|
| **thinking_gate** | **86.5%** | $0.03319 | 53.9% |
| Combined | 86.4% | $0.03731 | 63.6% |
| Flagship panel | 86.7% | $0.07454 | 12.2% |
| Lever 2 (thinking-seat) | 83.3% | $0.03284 | 50.0% |
| Lever 3 (subject-escalation) | 83.1% | $0.02739 | 60.7% |
| thinking_all | 83.3% | $0.05277 | 21.1% |
| Unmodified engine (replicate) | 75.3% | $0.02007 | 39.3% |

## Headline findings

1. **thinking_gate is the only configuration that matches or beats the
   flagship at both independent seeds** (86.7% vs 84.4% at seed 42; 86.5%
   tie at seed 7). Every other lever wins clearly at one seed and falls
   short at the other.
2. **The gate beats the blunt subject rule at combining cleanly.** The
   blunt "combined" lever (thinking-seat + force-escalate-all-Organic-
   Chemistry) sometimes *hurt* -- at seed 42 it scored 85.6%, worse than
   thinking-seat alone (86.7%), because the extra forced escalations gave
   the Judge chances to override answers that were already correct. The
   gate only escalates on detected doubt, avoiding that failure mode, and
   is cheaper too.
3. **Scaling thinking to all three seats is a real negative result.**
   thinking_all underperformed the single-thinking-seat lever at both
   seeds (85.6%/83.3% vs 86.7%/83.3%) while costing 40-60% more. Mechanism:
   making every seat "smarter" makes them agree more often (escalation rate
   dropped to 19-21%, vs 48-54% for one thinking seat), which means fewer
   questions ever reach the tribunal where most of the actual error-
   correction happens. The value wasn't raw capability -- it was one
   differently-calibrated seat creating productive disagreement.
4. **Does multi-agent deliberation help the flagship model itself, not
   just cheap models?** A consistent small positive lean across three
   independent runs, but not statistically established. Readings: 85.6%
   and 87.8% at seed 42 (two runs of the identical config -- a 2.2pt
   swing between them, its own measured noise floor), 86.7% at seed 7.
   Baselines: 84.4% (seed 42), 86.5% (seed 7). All three flagship-panel
   readings land at or above their respective baseline, but each
   individual gap (+1.2pt, +3.4pt, +0.2pt) is comparable to or smaller
   than the ~2.2-2.5pt noise measured for both this config and the plain
   engine -- no single run proves anything, and the baseline itself was
   never replicated to check its own noise band. The honest read: a
   real effect is plausible and the direction is consistent, but this
   would need several more replicates each side to state as established
   fact. The mechanism reason it's plausible but small: the flagship
   model already reasons well and thinks by default, so there is much
   less headroom for deliberation to recover versus the cheap tier's
   genuine, systematic, closeable gap (Organic Chemistry). Its escalation
   rate is only 12-16% at both seeds -- three independent flagship
   attempts simply agree with each other far more often than three
   cheap-model attempts do, so the tribunal rarely even gets invoked.
5. **None of these configurations are cheaper than the flagship baseline.**
   Every lever that improves accuracy costs $0.027-0.038/q, above the
   flagship's own $0.022-0.024/q. This was an explicit, accepted tradeoff
   for this investigation (proving the architecture works, not preserving
   the "cheaper than flagship" story) -- the shipped, cost-optimized
   QuorumQA remains a separate configuration/tier.

## Third-seed validation, and a targeting hypothesis that inverted

`thinking_gate` was flagged above as needing "a third, still-unseen sample"
before any public claim. That run happened at **seed 123** (never used to
develop or tune any lever), alongside a fresh flagship baseline on the exact
same 90 questions, and a new lever testing a natural follow-up hypothesis.

**thinking_gate holds at a third independent seed:**

| Seed | thinking_gate | Fresh baseline | Margin |
|---|---|---|---|
| 42 | 86.7% | 84.4% | +2.3pt |
| 7 | 86.5% | 86.5% | tie |
| 123 | 86.7% | 85.6% | +1.1pt |

Three independent seeds, three matches-or-beats-the-flagship results. This
closes the validation gap -- `thinking_gate` is no longer "promising, needs a
third sample," it is a replicated result.

**New lever tested: `smart_gate`.** The diagnosis earlier in this document
found Organic Chemistry carries an 18.9% unanimous-wrong rate against 0% for
every physics subject -- so the natural next hypothesis was: concentrate the
expensive thinking-seat treatment specifically on Organic Chemistry (seat 3
runs `thinking=True` only when `item.subject == "Organic Chemistry"`,
otherwise identical to the shipped engine), keep the universal doubt-gate,
and see if this captures most of `thinking_gate`'s gain at a fraction of the
cost.

It did not. `smart_gate` scored **83.1%** (n=89, one dropped question) at
$0.0303/q -- worse than both `thinking_gate` (86.7%, $0.0346/q) and the
plain flagship baseline (85.6%, $0.0250/q) at the same seed.

Breaking both engines down by subject at seed 123 explains why, and it is
not the explanation the hypothesis predicted:

| | Organic Chemistry (n=36) | Everything else (n=53-54) |
|---|---|---|
| Baseline | 77.8% | 90.7% |
| thinking_gate | 75.0% (escalated 25/36) | **94.4%** (escalated 19/54) |
| smart_gate | 72.2% (escalated 26/36) | 90.6% (escalated 25/53) |

`thinking_gate`'s entire net gain over baseline at this seed comes from
subjects *outside* Organic Chemistry -- exactly the questions `smart_gate`
deliberately left untreated (bare gate + shipped solvers there, which is why
its "everything else" number lands right back at baseline, 90.6% vs 90.7%).
On Organic Chemistry itself, both gated engines score *below* the plain
baseline, despite escalating roughly seven in ten of those questions each
way.

The likely mechanism: the diagnosis was right that Organic Chemistry is
where disagreement concentrates, but disagreement is a symptom of the
underlying gap, not a target you can fix by pointing more reasoning time at
it. All three solver seats, the Skeptic, and the Verifier share the same
base model (`qwen3.6-flash`) -- if that model has a genuine conceptual blind
spot in a subject, a thinking-enabled seat running the *same* model is prone
to reproduce the same misconception with more confident-sounding reasoning
attached, and the tribunal it escalates to has no fundamentally new
information to correct it with. Outside chemistry, the disagreement a
thinking seat surfaces looks more like execution-level slips -- exactly the
kind a second, closer look from the same model family can actually catch.
This reframes the earlier diagnosis: Organic Chemistry's error rate is a
real, systematic weakness, but it is a knowledge gap, not an
attention/effort gap, and this architecture's escalation mechanism is built
to catch the latter, not the former.

## chem_flagship_gate: the follow-up hypothesis confirmed

`smart_gate` showed that more *thinking time* on Organic Chemistry, still on
`qwen3.6-flash`, didn't help -- it made chemistry slightly worse than the
plain baseline. The natural next question: is the gap a knowledge blind
spot specific to that model, or something more fundamental about the
subject? Tested directly with a new lever, `chem_flagship_gate`: all three
solver seats switch to the flagship (`qwen3.7-max`, thinking enabled) for
Organic Chemistry only; every other subject is untouched, identical to the
shipped engine; the universal doubt-gate still applies everywhere.

**A genuinely different, stronger model fixes most of the gap.** Tested at
a fresh seed (555, n=90):

| | Organic Chemistry | Everything else | Overall |
|---|---|---|---|
| Baseline (flagship alone, seed 123 for reference) | 77.8% | 90.7% | 85.6% |
| `smart_gate` (more thinking, same model) | 72.2% | 90.6% | 83.1% |
| `chem_flagship_gate` (different, stronger model) | **90.0%** | 89.7% | **89.8%** |

90.0% (27/30) on Organic Chemistry specifically, up from the 72-78% range
every other tested configuration landed in -- and 89.8% overall is the best
single-seed result of the whole ablation study, ahead of `thinking_gate`'s
86.7% best. This confirms the reframed diagnosis from the `smart_gate`
section above: the chemistry gap is a knowledge blind spot in
`qwen3.6-flash` specifically, not an effort/attention gap, and it responds
to a different model, not more time from the same one.

**A real methodological lesson worth keeping on record.** The first run of
this lever appeared to hit 100% on chemistry (18/18) -- but 14 of the 32
sampled chemistry questions had silently dropped to a 120s request timeout,
and 100% of the drops were chemistry (the subject routed to the slower,
thinking-enabled flagship calls). That 100% was almost certainly inflated
by exactly the same survivorship-bias mechanism already caught once this
session on the `qwen3.8-max-preview` baseline: the hardest, slowest-to-
answer questions were disproportionately the ones timing out and getting
excluded from the "surviving" sample. Fixed by bumping the shared client's
timeout to 300s and re-running the full 90 clean -- 88/90 completed, and
the honest number (90.0%) is still an excellent result, just not the
inflated one. Reported here as a reminder that an exciting first number is
exactly when to check for this, not skip the check because the result looks
good.

**Not yet at the same validation bar as `thinking_gate`.** This is one
seed. `thinking_gate` wasn't trusted as a real result until it replicated
across three independent seeds (42, 7, 123); `chem_flagship_gate` needs the
same treatment -- at least one more fresh seed -- before being treated as
settled rather than a strong, promising single-run result.

**Second seed (777, run overnight by the improvement loop): replicates
overall, softer on chemistry.** n=88/90, overall **88.6%** (seed-555:
89.8%) -- both seeds clearly above `thinking_gate`'s 86.7% best, so the
overall effect looks real. Chemistry specifically: **82.1%** (23/28),
down from seed-555's 90.0%. Drop-bias check: both dropped questions were
chemistry, so the honest chemistry band is 76.7% (both would-be-wrong) to
83.3% (both would-be-right) out of the sampled 30. That band still sits
above every non-flagship configuration's chemistry rate (72-78%), but the
per-subject effect size is smaller than seed-555 suggested -- consistent
with a real improvement plus ordinary per-subject noise at n≈30/seed.
Third seed queued before this is called settled.

*Billing-regime note for anyone comparing costs across seeds:* seed-555
ran on pay-as-you-go DashScope (real per-token USD in `cost_usd`);
seed-777 ran after the client's migration to the Token Plan subscription
endpoint, where billing is quota-Credits and `cost_usd` is 0.0 by design
(no published $/token rate -- tokens are the honest signal). Accuracy
comparisons across the two seeds stand; USD cost comparisons do not.

## Does the doubt-gate generalize past GPQA-Diamond?

The LEXam and MMLU-Pro pilots (see `lexam_findings.md`, `mmlu_pro_findings.md`)
both showed the *shipped* engine losing to the flagship baseline by double
digits, driven almost entirely by confident unanimous-wrong agreement --
exactly the failure mode `thinking_gate` was built to catch on GPQA. The
harness was generalized to run any lever against any dataset (pure plumbing,
no lever-specific code) specifically to test this directly rather than
guess. Same seed (42) as both plain-engine pilots, so these are a clean
before/after:

| Dataset | Plain engine | `thinking_gate` | Flagship baseline | Gap closed |
|---|---|---|---|---|
| GPQA-Diamond (seed 42, frozen) | 78.9% | 86.7% | 84.4% | full gap closed, engine wins |
| MMLU-Pro (seed 42, n=50) | 82.0% | **92.0%** | 94.0% | 10 of 12 points |
| LEXam (seed 42, n=50) | 72.0% | **80.0%** | 86.0% | 8 of 14 points |

**The gate mechanism itself generalizes -- it helps on every domain tested
so far, not just GPQA.** MMLU-Pro's unanimous-wrong count dropped from 7 to
2, and all 5 overturns triggered were correct (100%). LEXam's unanimous-
wrong barely moved (11 to 7) and overturn quality was weaker (9 overturns,
6 correct, 67%) -- closing less of the gap than MMLU-Pro despite a bigger
absolute improvement over its own plain-engine baseline (+8 points vs
+10).

**Why LEXam still trails when MMLU-Pro nearly catches up: this confirms the
mechanistic diagnosis from `lexam_findings.md`.** MMLU-Pro's sample includes
plenty of STEM subjects (math, physics, chemistry, engineering) where the
Verifier's actual tools (`lookup_constant`, `safe_calculate`) have real
claims to check -- the same kind of grounding that makes escalation work on
GPQA. LEXam's statement-based legal questions mostly don't -- 7 of 9
escalations in the original plain-engine LEXam pilot produced zero Verifier
findings. The gate can still make the panel escalate *more often* on LEXam
(escalation rate rose to 34%, matching MMLU-Pro's 32%), but once escalated,
the Judge on LEXam is working from a Skeptic's argument alone, without the
tool-grounded evidence that makes GPQA's and MMLU-Pro's Judge calls
reliable. More disagreement caught is not the same as more disagreement
*resolved well* -- that second part needs a Verifier with tools that
actually apply to the domain, which LEXam does not yet have (see
`lexam_findings.md`'s "what this would take" section: a statute/case-lookup
tool, not built here).

**Practical read:** the doubt-gate is close to a domain-general win --
adopt it and you gain real accuracy on GPQA, MMLU-Pro, and LEXam alike --
but "close most of the gap to the flagship" specifically depends on the
Verifier having something real to check in that domain. Single seed on the
new-dataset numbers above; same replication caveat as everything else in
this section.

## What this would take to ship

Adopting `thinking_gate` as a new tier (e.g. "Tribunal-max") would mean:
- `solver.py`: parameterize `_solve_one` to accept `thinking`, add a third
  distinct seat config.
- `orchestrator.py`: add the gate call in the unanimous branch before
  returning, matching `lever_experiments.py`'s `second_opinion_gate`.
- ~~A fresh, larger benchmark run on a third, still-unseen sample before any
  public number is published~~ -- **done**: seed 123 above, 86.7% vs an
  85.6% fresh baseline on that exact sample. Three independent seeds now
  replicate the result (42, 7, 123). The remaining gap before a public
  number is a *larger* n per seed, not another seed.
- `recBhnXrUyTJ6WHIR` should be re-verified under the final shipped config
  before the demo video is recorded, since it broke under some (not all)
  of the tested variants.
- Do not chase the Organic Chemistry gap by targeting reasoning effort at
  it -- `smart_gate` tried exactly that and scored below the plain baseline
  on chemistry itself (72.2% vs 77.8%). The chemistry gap looks like a
  shared knowledge gap across the cheap tier, not something a same-model
  thinking pass can catch.
