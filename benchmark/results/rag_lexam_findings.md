# G3: LEXam retry with recursive retrieval

The test of whether R2's disputed-step retrieval revives LEXam's dead
verifier (original diagnosis: 7/9 escalations produced ZERO verifier
findings; engine lost −14 to the flagship). Seed 42, n=90, rag_recursive
vs cheap-panel control, same STEM-Wikipedia corpus (RAG-ON,
Laz4rz@e51169b).

## Result: corpus-coverage limitation, not mechanism failure

| LEXam, 90 common items | Accuracy |
|---|---|
| cheap-panel control | 74.4% |
| rag_recursive (R1+R2) | 76.7% |

**+2.2 — noise-level at n=90. And the mechanism check failed: only 2/30
escalations produced verifier findings** — the verifier is still
essentially dead on legal reasoning.

The retrieved titles explain why, unambiguously: "Robot tax",
"Predicate transformer semantics", "Proofreading (biology)", plus a few
US case-law articles ("Selman v. Cobb County", "Industrial Union Dept v.
American Petroleum Institute"). LEXam is **Swiss** law; the corpus is
**STEM Wikipedia**. The retrieval machinery fired correctly on the
Skeptic's disputed steps — but the shelf contains no Swiss statutes, so
it returned the closest STEM/US-legal neighbors, which ground nothing.

This was the pre-registered alternative outcome (stated before the run):
"if retrieval doesn't help because the corpus lacks legal content, that's
a corpus-coverage finding, not a mechanism failure." That is exactly what
the data shows. Unanimous-wrong unchanged (14→15); nothing degraded.

## What this establishes

1. **Retrieval quality is corpus-bound, mechanism-neutral.** The same
   R1+R2 machinery that gained +4.7/+6.9 on hard STEM (where the corpus
   HAS the knowledge) moves nothing on law (where it doesn't). Corpus
   coverage is a first-class routing input: the MoO router should gate
   RAG not just on "is the gap knowledge-shaped" but "does our corpus
   cover this domain."
2. **The law profile's blocker is unchanged and now precisely specified:**
   a Swiss/legal statute corpus (not more retrieval engineering). Until
   one is indexed, LEXam routes to `single-call` per the standing
   gap-lens table.
3. Control re-measured at 74.4% (original pilot: 72%) — consistent.

## Caveats
- n=90, 1 seed, same-seed as the original diagnosis (fine: this is a
  mechanism probe, not a validation claim).
- The 2 escalations WITH findings both involved calculation-flavored
  sub-questions — consistent with the science-tools-only diagnosis.
