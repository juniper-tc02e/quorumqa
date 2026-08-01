# KI-0R — tool-augmented self-verification carries zero signal: KILL

**Measured 2026-08-01.** `docs/spec-sci1-and-knowledge-injection.md` §3.1, fired
first in the knowledge-injection family because it gates 5.06M of downstream
spend. Cost: **0.39M tokens.** Killed: **5.06M.**

Independently re-derived from the raw JSON, not just read off the generated
report. Reproduce the report for free (no API calls) with `--from-json`.

---

## 1. The verdict

| dataset | pool | n | gate fires | rate | vs the 0.311 gate |
|---|---|---:|---:|---:|---|
| GPQA | unanimous-**wrong** | 34 | 1 | **2.9%** | FAILS (Wilson CI [0.5%, 14.9%]) |
| GPQA | unanimous-**right** | 34 | 5 | 14.7% | — |
| SuperGPQA-hard | unanimous-**wrong** | 151 | 24 | **15.9%** | FAILS (Wilson CI [10.9%, 22.6%]) |
| SuperGPQA-hard | unanimous-**right** | 151 | 24 | 15.9% | — |

Both entire confidence intervals lie below the gate. **This is not a power
problem** — more seeds would not rescue it.

## 2. The finding that actually matters, which the gate threshold does not capture

A gate can have any firing rate and still be worthless if it fires at the *same*
rate on right and wrong answers. That is precisely what happened.

**SuperGPQA-hard: Fisher exact two-sided p = 1.0000.** The gate fired on 24 of
151 unanimous-wrong items and 24 of 151 unanimous-right items. Not
approximately equal — **exactly** equal. The two pools are disjoint by
construction (verified: zero question_id overlap), so these are 48 genuinely
different items, not a double-counting artifact.

**GPQA: the gate is anti-correlated.** It fired on 1 wrong item and 5 right
ones — **5× more often on answers that were already correct** (p=0.1974, not
significant at this n, but pointing the wrong way).

`verified_gate_cas` does not detect wrongness. It detects *something*, at a
15.9% rate, that is statistically independent of whether the answer is right.

## 3. Why — the mechanism, pre-registered before the data existed

From this script's own module docstring, written before the run:

> CAS_EXTRACT_SYSTEM asks the model to write "LHS = RHS with the chosen
> answer's numeric value already substituted in" — **from its own transcript.**
> A model reconstructing its own wrong chain writes a **self-consistent**
> equation, sympy_check returns "pass", and nothing escalates.

The data confirms this exactly. The arithmetic verdict is genuinely new
information — `sympy_check` runs real offline sympy, no model involved — but
**the premise is a re-read.** The model chooses which equation to write, and it
writes one consistent with the answer it already committed to. Verifying a
self-authored premise verifies nothing.

There is a second, compounding reason. Three seats at T=0.3/0.6/0.9 agreeing
*unanimously* actively selects **against** stochastic arithmetic slips — the one
error class a CAS can catch — and **for** correlated conceptual and setup error,
which it cannot. Unanimity filters out precisely the failures CAS could see.

## 4. What this kills

Per §3.1's pre-registered kill clause (`product < 0.311 on SuperGPQA-hard`):

- **KI-1 Arm A (`verified_gate_cas`), 2.30M — dead.** Not "under-powered";
  the signal is absent, and on GPQA it points backwards.
- **KI-2 (`verified_discriminator`), 2.76M — dead.** It depends on the same
  model-written-relation parseability, and was already independently rejected
  in review for citing an N=15 oracle figure to motivate an N=3 run.
- **The mechanical-verification branch of knowledge injection is closed for
  MC-science**, at least in the "ask the model to write its own check" shape.

**5.06M killed for 0.39M spent — a 13:1 return on the cheapest thing in the
queue.** This is the whole argument for firing a diagnostic replay before a
live arm.

## 5. What this does NOT kill

- **The MCP tools themselves.** `sympy_check` is correct and deterministic; the
  failure is in who writes its input, not in the checker. A tool fed a check
  derived *independently of the answer under test* is untouched by this result.
- **`universal_gate`.** It escalates every unanimous panel unconditionally,
  needing no trigger at all — and by set inclusion it dominates any
  `verified_gate_cas` configuration before a single run. That is the arm the
  review funded, and it is unaffected.
- **Knowledge injection as a class.** What died is *self-authored* verification.
  An external observation the model did not produce — retrieval against a
  corpus, an independently-derived check, a genuinely different information
  channel — remains untested by this result.

## 6. A latent crash found on the way

This replay was the first time `sympy_check` had ever met live data, because
`verified_gate_cas` had never been fired. It crashed:

```
TypeError: unsupported operand type(s) for -: 'function' and 'Integer'
```

`sympy.sympify` resolves `beta`, `gamma`, `zeta`, `Q`, `N`, `S`, `O` to
non-expression objects (FunctionClass, AssumptionKeys, SingletonRegistry,
type). `_relation_to_difference` then evaluated `lhs - rhs` on a function and
raised — breaking `sympy_check`'s documented "never raises, fails safe to
unparseable" contract. **A live `verified_gate_cas` run would have crashed on
the first physics item using β, γ, Q, N or S as a variable.** Fixed at the root
(commit `56234c8`), 16 regression tests. Recorded here because it is an
argument for replaying a never-fired lever offline before paying for it.

## 7. Honest limits

- **GPQA's n=34 is small.** Its 2.9% point estimate has a wide interval and its
  anti-correlation is not significant (p=0.1974). The SuperGPQA result (n=151,
  p=1.0000) is the load-bearing one; GPQA is consistent with it and adds no
  contrary evidence.
- **One extractor prompt.** This tests `CAS_EXTRACT_SYSTEM` as written. A
  materially different extraction strategy — one that derives the check from
  the *question* rather than the *answer's own reasoning* — is a different
  experiment, and is the only revival path worth considering.
- **Unanimous items only.** This says nothing about CAS on split panels, which
  already escalate anyway and so have no gate to trigger.
- **The false-positive rate is a cost, not an accuracy harm.** Escalating a
  correct item usually leaves it correct (measured breakage 0.8%). The
  indictment is that the gate provides no *targeting* value, so it is strictly
  dominated by escalating everything.
