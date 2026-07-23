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

## What the unparsed answers actually are

- **Genuinely out of scope (correctly fail closed):** complex numbers
  (`6-5i`, `1+2i`), intervals (`(3,4]`), equations (`y = 2x + 3`,
  `5x-7y+11z+4=0`), `\text{}`-annotated answers (`\frac{270}7\text{ degrees}`).
- **Cheap future refinement (NOT in level 5, so irrelevant to the pilot):**
  the brace-less LaTeX fraction short-form (`\frac43`, `\frac 59`, `\frac9{19}`)
  — latex2sympy2 needs `\frac{a}{b}`. Expanding `\frac AB` → `\frac{A}{B}` in
  `_normalize` would push all-levels coverage above 95%. Deferred: every one
  of these is in levels 1–4; level-5 coverage is already 96%.

## Bottom line for the pilot

On the level-5 target the grader gives full-equivalence grading on 96% of
questions and exact-match credit on the rest, with ~0 false-positive risk and
a conservative (undercount) failure mode. Good enough to trust a
deliberation-vs-baseline delta, as long as both arms are graded identically
(they are — same `grade()` call).
