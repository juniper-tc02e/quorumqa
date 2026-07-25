# SimpleQA / factuality harness -- build notes (F8, offline)

No paid API calls were made building this. Everything below is either a
live, free, non-model check (HF Hub dataset load, a direct CSV fetch, a raw
GitHub fetch of the published grader source) or a claim about code, not a
measured result. **Nothing in this document is a run finding.** docs/
capability-roadmap.md section 3.12 is authoritative on the thesis and the
pre-registered bar/kill criteria this build exists to make runnable (FA-0/
FA-1/FA-2); this file only covers what F8 (the build item) actually produced.

## What loaded

**Dataset:** `basicv8vc/SimpleQA`, HuggingFace Hub, `test` split (the only
split -- SimpleQA ships eval-only, no train/dev). **4326 rows.** Columns:
`problem` (question), `answer` (free-text gold answer), `metadata` (a
Python-literal dict string: `topic`, `answer_type`, `urls`).

**License:** MIT (HF dataset-card `license: mit`; matches OpenAI's own
`simple-evals` repository license for the SimpleQA release, "SimpleQA:
Measuring short-form factuality in large language models",
https://cdn.openai.com/papers/simpleqa.pdf).

**Cross-checked live against the official source, 2026-07-25:** fetched
`https://openaipublic.blob.core.windows.net/simple-evals/simple_qa_test_set.csv`
directly (2,012,910 bytes, decodes cleanly as UTF-8) and diffed against the
HF Hub load -- same 4326 rows, same three columns, same values for every row
spot-checked. The loader (`benchmark/load_simpleqa.py`) uses the HF Hub
mirror by default (`datasets.load_dataset`, the same mechanism every sibling
loader in this repo uses), not a bundled CSV copy.

**Encoding fix, verified live:** the roadmap flags "some distributions of
this file have double-encoded UTF-8" (e.g. `JÃ³hanna SigurÃ°ardÃ³ttir` where
`Jóhanna Sigurðardóttir` belongs). Checked directly against row 8 (the exact
example the roadmap cites) in BOTH sources above: **0/4326 rows in either
source exhibited the mojibake pattern** -- row 8's answer is already the
correctly-decoded `Jóhanna Sigurðardóttir` (confirmed at the codepoint
level, not just by string equality). All 4326 `metadata` values parsed
cleanly via `ast.literal_eval` (0 failures); 0 empty questions/answers.

The detect-and-fix step (`_fix_mojibake` in `load_simpleqa.py`) is
implemented anyway and runs on every load, defensively: it pattern-matches
the specific UTF-8-as-cp1252 mojibake lead-in bytes, attempts a
`cp1252`-encode / `utf-8`-decode round-trip, and only accepts the result if
it both succeeds AND actually removes the pattern (fails closed on every
axis -- see the function's docstring). On this load it is a no-op (0/4326
rows touched, logged as such). The roadmap's own phrasing ("some
distributions") means a clean check today is not a guarantee for every
mirror or a future dataset revision; the fixer stays in place so a future
regression shows up as a logged warning with a count, not a silent grading
failure on every accented gold answer.

`urls` (inside `metadata`) is read for nothing and dropped at load time --
see the module docstring's firewall note. It is the list of source URLs
SimpleQA's authors used to WRITE each gold answer; indexing it would let
retrieval trivially look up the answer instead of testing this engine's
actual retrieve/verify/abstain behavior against an independent corpus.

## Files built

- `benchmark/load_simpleqa.py` -- loader, `SimpleQAItem` dataclass
  (question_id, question, gold_answer, topic, answer_type), seeded shuffle,
  the mojibake fixer.
- `benchmark/factuality_engine.py` -- the engine (two arms:
  `solve_single_factual` baseline, `solve_panel_factual` panel), the
  citation-check gate (`verify_claim_against_evidence`), and grading
  (`grade_simpleqa`, `exact_match_normalized`, `compute_simpleqa_metrics`).
  **Build honesty, per the roadmap:** this is a SECOND engine path, not an
  extension of the shipped GPQA engine -- `schemas.py`'s `QuestionResult`/
  `JudgeVerdict` hard-require `final_letter: str` with no abstain sentinel,
  and every shipped prompt formats choices with `zip("ABCD", ...)`. Neither
  applies to free text, so this module returns plain dict rows (mirrors
  `benchmark/math_open_engine.py`'s existing precedent -- also a fork off
  the 4-choice engine, also open-answer, also dict-row rather than
  pydantic-schema output). `schemas.py` itself was NOT touched.
- `tests/test_factuality_offline.py` -- 38 offline tests, fake clients only.

Retrieval reuses `benchmark/lever_experiments.py`'s existing RAG plumbing
directly (`RagPresolveConfig`, `retrieve_rag_evidence`, `build_evidence_
block`, `build_rag_presolve_config`, `resolve_rag_db_path` -- imported, not
reimplemented) against the same pre-embedded STEM/US-law-Wikipedia index
every `rag_*` lever already opens (`benchmark/data/rag_index_preembedded.
sqlite3`, confirmed present on disk at build time). One deliberate contract
DIFFERENCE from `rag_presolve`/`rag_recursive`: those fail loudly at startup
if the index is missing, because retrieval IS the entire point of those
levers. The factuality panel's contract is the opposite, per the build spec
-- `try_open_factuality_rag` and `solve_panel_factual`'s own retrieval call
both catch every exception broadly, log a warning, and proceed with
`evidence_block=""` / `retrieval=[]` / `supported=None`. Tested directly
(missing index, and an index that opens fine but whose `.search()` itself
raises mid-call).

## The three-way metric definitions

SimpleQA's own scorer (`openai/simple-evals`, `simpleqa_eval.py`,
`SimpleQAEval.__call__` -- fetched and read directly, not from memory)
grades every item into exactly one of three labels via `grade_simpleqa`,
then aggregates:

| Metric | Formula | What it measures |
|---|---|---|
| `correct_rate` | `#CORRECT / N` | Accuracy over ALL items (their "is_correct") -- an abstained/wrong item counts as 0 here. |
| `attempt_rate` | `(#CORRECT + #INCORRECT) / N` | 1 − abstention rate. `not_attempted_rate = #NOT_ATTEMPTED / N` is the abstention rate directly. |
| `accuracy_given_attempted` | `#CORRECT / (#CORRECT + #INCORRECT)`, defined as 0 if nothing was attempted | Accuracy restricted to the items the system actually answered -- what a bare exact-match accuracy number would look like if abstentions were simply excluded rather than counted against the system. |
| **`f1`** | harmonic mean of `correct_rate` and `accuracy_given_attempted`, `2ab/(a+b)`, 0 if both are 0 | **The headline number.** Rewards a HIGH attempt rate on items the system gets right and a LOW attempt rate on items it doesn't -- calibrated abstention raises the second term without adding knowledge, but abstaining on everything drives BOTH terms toward 0 (not toward a free win), because `accuracy_given_attempted` is undefined-as-0 with nothing attempted. |

Implemented as `compute_simpleqa_metrics(grades: list[str]) -> dict` in
`factuality_engine.py`, formulas matched exactly against the reference
implementation (line-by-line, not paraphrased) and unit-tested against it,
including the total-abstention edge case (scores 0, not a division error)
and the roadmap's own pre-stated hard ceiling: **F1 ≤ 2k/(1+k)** where k is
the fraction of facts the base model actually knows (verified in the tests:
a perfectly-calibrated abstainer -- correct or silent, never wrong -- hits
this ceiling exactly).

## The grader caveat -- read this before reporting any F1 number

**`grade_simpleqa` is the metric. `exact_match_normalized` is a floor, not
the metric. They will disagree, and the disagreement direction is known in
advance.**

- **`grade_simpleqa`** runs the OFFICIAL SimpleQA grader prompt
  (`GRADER_TEMPLATE`, reproduced VERBATIM in `factuality_engine.py`,
  fetched directly from `https://raw.githubusercontent.com/openai/
  simple-evals/main/simpleqa_eval.py` on 2026-07-25, MIT license) as a
  single plain-text model call, mapped to CORRECT/INCORRECT/NOT_ATTEMPTED
  exactly as the reference implementation does (including its own
  default-to-NOT_ATTEMPTED fallback on an unparseable response). **This is
  a MODEL grader and therefore FALLIBLE** -- unlike `benchmark/math_grade.
  py`'s `grade()`, a deterministic CAS-equivalence check with no judgment
  call involved, `grade_simpleqa`'s verdict depends on which model is asked
  and is not guaranteed to reproduce across seeds or runs. SimpleQA's own
  paper uses GPT-4 as the reference grader; this repo has no access to that
  model and defaults to `ORCHESTRATOR_MODEL` (qwen3.7-max) instead. **Any
  reported F1 number must disclose the grader-model substitution alongside
  it** -- it is not established that qwen3.7-max grades this rubric the way
  GPT-4 does, in either direction (stricter or more lenient), and nothing in
  this build measures that gap.
- **`exact_match_normalized`** is deterministic and zero-cost: normalized-
  string equality after the SAME conservative normalizer clustering uses
  (casefold, strip punctuation, strip English articles, collapse
  whitespace -- see `normalize_answer`'s docstring). It **under-counts**
  relative to the official grader on paraphrases the official rubric
  explicitly accepts as CORRECT (its own worked examples: "Malia Obama and
  Sasha Obama" vs "sasha and malia obama" would pass this loader's
  normalizer too, but "Michelle Obama" vs "Michelle", "San Francisco,
  California" vs "San Francisco", or "1.73 m" vs "1.75" -- all CORRECT
  under the official rubric's stated leniency rules -- would NOT match this
  string check). It never OVER-counts: a normalized-string match is always
  a genuine string match. Use it only as a free sanity check on the panel's
  mechanics (clustering, escalation, abstention wiring) during offline
  development, never as the reported accuracy number.

Both graders are wired identically into the engine's output rows
(`correct` is computed via `exact_match_normalized` inside `solve_single_
factual`/`solve_panel_factual` for a zero-cost sanity signal at generation
time; `grade_simpleqa` is a separate, explicit re-grading pass a caller runs
over the same rows -- `question`/`gold_answer`/`final_answer` are exactly
what it needs, no re-generation required). **No runner script re-grades a
result file with `grade_simpleqa` yet** -- see "What remains unbuilt."

## The retrieval-gate precondition (read before any headline claim)

This repo's RAG index is STEM + US-law Wikipedia (`benchmark/build_rag_
index_preembedded.py`; confirmed by the corpus's own build provenance, not
re-verified by this build item). **SimpleQA asks broad general trivia** --
sports, TV shows, music, politics, geography, history, video games, "other"
(10 topics measured live in the loader: Science and technology 858,
Politics 709, Art 550, Other 475, Geography 424, Music 341, Sports 368, TV
shows 293, History 173, Video games 135 -- only a minority of that mix is
STEM-adjacent). This is **structurally the same corpus-mismatch failure
mode LEXam already measured and killed as an accuracy axis** (2/30
retrievals on-topic, RAG +2.2 noise, engine −14 -- docs/capability-
roadmap.md's "what we will deliberately NOT chase" table) -- a
general-knowledge Wikipedia index would fit SimpleQA's topic mix far better
than this repo's STEM/law-skewed one, and nothing in this build measures
whether retrieval on this specific index actually helps, is neutral, or
actively misleads the panel (rag_presolve's own seed-271 finding: bad
top-k passages can manufacture confident false consensus).

**Consequence, stated as the roadmap requires:** a retrieval-relevance gate
(blinded on-topic/off-topic check on the top retrieved passage per item,
per the same discipline the frozen relevance rubric committed for W6's
`rag_r3_targeted` already establishes as this repo's house pattern) **must
run and clear BEFORE any headline SimpleQA claim that uses `rag=`
retrieval**. The answer-only arm (`rag=None`) has no such precondition --
FA-0's own two arms (single flagship, no abstain / abstain-permitted) don't
touch retrieval at all, and are runnable without this gate. This build does
not implement or run that gate; it only names the precondition so it cannot
be skipped implicitly.

## What remains unbuilt (deliberately, per this build item's scope)

- **The actual k-probe** (fraction of SimpleQA facts qwen3.7-max's
  parametric knowledge covers, gating the ≥38% frontier-topping claim per
  the roadmap) -- requires live paid calls, out of scope for this offline
  build.
- **A runner/CLI script** to execute FA-0 (2-arm k-probe + comparator
  baseline), FA-1 (3-solver panel + official grader, 3 seeds), or FA-2
  (verified-gate rider on unanimous answers) end-to-end and write result
  files -- `lever_experiments.py` was explicitly out of scope for this
  build item (owned by another worker) and no other runner exists yet.
  `solve_single_factual`/`solve_panel_factual` are ready to be called by
  one; none of the required plumbing (dataset loading, calling the engine
  per item, calling `grade_simpleqa` per row, aggregating with
  `compute_simpleqa_metrics`, writing a `.jsonl`/summary) is wired together
  into a script.
- **The retrieval-relevance gate itself** (see above) -- named as a
  precondition, not implemented here.
- **A free-text judge system-prompt/behavior validation** -- `judge_
  factual`'s prompt is new (not adapted from a shipped, previously-measured
  prompt the way `math_open_engine.judge_math` reuses the shipped panel's
  general shape); it has offline JSON-contract tests but no live signal on
  whether qwen3.7-max actually follows "abstain if you don't trust any
  candidate" well in practice.
- **FA-2's flaw-finder pass** (a second flagship interrogation of UNANIMOUS
  answers specifically, demoting flagged ones to escalation/abstention) --
  not built; `solve_panel_factual`'s only verification step is the
  post-hoc citation check against retrieved evidence, which fires
  regardless of whether the panel was unanimous or escalated, not FA-2's
  narrower unanimous-only design.
- **Any live measurement of `grade_simpleqa` vs. GPT-4 grading agreement**
  -- the substitution caveat above is stated, not quantified.

## Test coverage (offline, `tests/test_factuality_offline.py`)

38 tests, fake clients only (`JsonCallResult(data=..., usage=...)` for
`chat_json`, `(text, CallUsage)` for `chat`), no network. Covers: free-text
clustering (variant-form agreement vs genuine disagreement, both as a direct
`normalize_answer` property and end-to-end via the panel's `n_clusters`/
`cluster_margin`); the abstain path (unsupported -> `abstained=True`, never
scored correct even when the pre-abstain candidate matched gold exactly);
the supported path; plurality-wins-outright vs. no-margin-escalates
dispatch, including the judge abstaining directly; `exact_match_normalized`
positives/negatives/documented paraphrase blind spot; `grade_simpleqa`'s
three labels plus its unparseable-response fallback plus prompt-content
assertions; `compute_simpleqa_metrics` arithmetic including the
total-abstention edge case and the F1-ceiling formula; missing-index and
mid-call-retrieval-failure fallback (no crash, logged, `supported=None`,
never coerced to a forced abstain from missing evidence alone); retrieval
log entries carrying title/score only, never passage text; and the mojibake
fixer's detect/repair/no-op-when-clean behavior.

**`.venv/Scripts/python.exe -m pytest tests/ -q` -> 572 passed** (full
suite, this build's 38 included, at the time this build item finished; run
concurrently with other workers' in-flight test additions per the task
brief -- 0 failures anywhere in the suite at that snapshot).
