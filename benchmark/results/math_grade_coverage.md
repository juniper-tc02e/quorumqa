# math_grade.py — coverage & safety characterization on MATH-500

Measured against all 500 real MATH-500 answers (and the level-5 subset that
the hard-math deliberation pilot will target). Purpose: know the grader's
blind spots BEFORE interpreting any pilot number.

## Parse coverage (answer parses to a sympy object)

| Slice | Parsed | Coverage |
|---|---|---|
| All 500 | 477/500 | **95%** |
| Level 5 (pilot target) | 129/134 | **96%** |

## Safety (the property that matters most)

- **Cross false-positive: 1/3000** random distinct-answer pairs graded equal —
  and that one is `30^\circ` vs `30`, which is *correct* (degree-mark
  normalization by design). Effectively **zero** genuine false-positives, so
  the grader cannot inflate accuracy by calling different answers equal.
- **Fails closed on unparsed golds:** for every one of the 23 (all-levels) /
  5 (level-5) answers the grader can't parse to sympy, an EXACT string match
  from the model is *still* graded correct (23/23, 5/5 via the string
  short-circuit). The only thing lost on an unparsed gold is equivalence
  *tolerance* (a differently-notated correct answer may be missed). That is a
  conservative **undercount**, never an overcount — the honest direction.

## UPGRADE (2026-07-24): intervals / \pm / sets now handled

The first grader version fell back to fail-closed on intervals, `\pm`
multi-valued answers, and sets — and the open-answer pilot revealed those are
NOT rare at level 5: **4 of the 6 apparent flagship "errors" were grader
false-negatives** on exactly these shapes (e.g. `(3, 4]` vs gold `(3,4]`;
`1 + \sqrt{19}, 1 - \sqrt{19}` vs `1 \pm \sqrt{19}`; `\{-2, 1-\sqrt5, 1+\sqrt5\}`
vs `\{1\pm\sqrt5,-2\}`). Left unfixed, the grader undercounted the flagship's
MATH-500-L5 accuracy by ~7 points (89.8% → 96.6% corrected) and manufactured
illusory "headroom".

`grade()` now models three answer structures explicitly:
- **Bracketed ordered sequences** (tuples/intervals): brackets AND order are
  significant — `(3,4]` ≠ `[3,4]` ≠ `(3,4)`, `(a,b)` ≠ `(b,a)`.
- **Order-insensitive sets / multi-valued answers** (`\{...\}`, bare
  comma-lists, and `\pm`/`\mp` expansions), compared as multisets via `grade`.
- **Scalars**: symbolic then numeric equivalence (unchanged).

Re-validated after the upgrade: **0/4000** cross false-positives on real
distinct answers (no over-matching introduced), level-5 gradeable coverage
96% → **97%**. 35 grader tests (was 26), full suite 378.

## Still out of scope (correctly fail closed)

Complex numbers (`6-5i`, `1+2i`), equations (`y = 2x + 3`, `5x-7y+11z+4=0`),
and `\text{}`-annotated answers. Also the brace-less `\frac43` short-form
(levels 1–4 only, not L5). All fail CLOSED — undercount, never overcount.

## Bottom line for the pilot

On the level-5 target the grader now gives full-equivalence grading on 97% of
questions (including intervals/sets/±) and exact-match credit on the rest,
with **0** false-positive risk and a conservative (undercount) failure mode.
The pilot delta is trustworthy — both arms are graded by the identical
`grade()` call, and the corrected absolute numbers are backed by re-grading
the stored answers.
