# HLE feasibility check (verdict: not building a loader)

Re-verification of the earlier adversarial pass that refuted "HLE is
structurally compatible with QuorumQA" and "has a single unambiguous
verifiable correct answer" (0 votes for, 3 against; reasoning not
preserved). This pass re-derives the refutation from primary evidence --
live HuggingFace API checks, HLE's own eval-harness source, and an
independent third-party implementation -- rather than trusting memory of
the earlier verdict. **The refutation holds, and holds more strongly than
the two grounds it was originally reduced to.**

## Dataset identity (live-verified)

- HF dataset ID: `cais/hle` (`https://huggingface.co/api/datasets/cais/hle`,
  unauthenticated, 200 OK). Not renamed/mis-cited.
- `private: false`, `gated: "auto"`. 1 config (`default`), 1 split (`test`),
  **2,500 examples** (live, from the dataset card's `dataset_info`). Note:
  the arXiv paper's abstract says "2,700 questions" -- that's the
  pre-publication count; 2,500 is the current live count after CAIS pruned
  disputed/broken items post-publication. Use 2,500, not the paper number.
- Schema (live, from the public card metadata -- this part is visible
  without gate approval): `id, question, image, image_preview, answer,
  answer_type, author_name, rationale, rationale_image, raw_subject,
  category, canary`. **There is no `choices`/`options` column.** Confirmed
  independently in two pieces of real source code that consume this exact
  dataset (see below) -- neither reads any such field.

## Gating: this repo's HF_TOKEN does not have access

The task brief noted "if gated, datasets-server may still show schema" --
checked, and that assumption doesn't hold here. Four independent live
checks, all with the repo's real `HF_TOKEN` (account `junipertc02e`,
confirmed valid and `canReadGatedRepos: true` via `/api/whoami-v2`):

1. `datasets-server.huggingface.co/info` (and `/rows`, `/splits`, `/size`,
   `/is-valid`) all return `404` -- gated datasets that the querying
   credential hasn't been granted for read back as "does not exist."
2. Direct parquet resolve
   (`huggingface.co/datasets/cais/hle/resolve/main/data/test-*.parquet`)
   returns `403`, `X-Error-Code: GatedRepo`, `X-Error-Message: Access to
   dataset cais/hle is restricted and you are not in the authorized list.`
3. `datasets.load_dataset("cais/hle", split="test")` (project venv, same
   token) raises `DatasetNotFoundError: ... gated dataset ... Visit the
   dataset page ... to ask for access.`
4. Fetching the dataset's own HF page shows no row preview and states
   "You need to agree to share your contact information to access this
   dataset."

So the repo's token is not the blocker on HF's side generally (`auto`
gating usually means fast/automatic approval) -- it's that nobody has
clicked through HF's access-request agreement for this specific dataset
under this account yet. That's a "log in and accept a form" action, which
falls under this agent's explicit-permission-required bucket (accepting
agreements, submitting forms) -- not something to do autonomously mid-task.
**No row-level data was read for this check.** Everything below is from
public metadata plus primary source code that itself operates on this
dataset, not from inspecting actual rows.

## Quantifying (a) multimodal fraction and (b) exact-match fraction

Could not compute these by counting rows directly (blocked, see above).
Cross-checked instead against two sources that should agree if either is
right: the arXiv paper (`arxiv.org/abs/2501.14249`, fetched live) and
Scale AI's official HLE leaderboard (`labs.scale.com/leaderboard/
humanitys_last_exam`, the benchmark's own administrator, fetched live).
Both independently state the same numbers:

- **~24% multiple-choice / ~76% exact-match** (of 2,500 -> ~600 MC /
  ~1,900 exact-match).
- **~13-14% multimodal (image) / ~86-87% text-only** (~325-350 image
  questions / ~2,150-2,175 text-only).

These are **marginal** percentages, not the joint figure the decision
rule actually needs (text-only **AND** multiple-choice). That
intersection is not published anywhere found, and can't be computed
without row access. If the two properties were independent, 24% x 86% ~=
21% of 2,500 ~= ~515 questions -- comfortably over the ~300 threshold --
but the task brief explicitly said not to estimate, and independence
isn't a safe assumption here (e.g. "identify this diagram" style
exact-match questions plausibly correlate with the image flag in ways
that shift the joint count either direction). **This joint count is
unmeasured, not merely unfavorable** -- worth being precise about which
of those two states this is.

## The structural finding that matters more than the joint count

Even setting the count question aside, two things confirmed from real
source code (not requiring gated access, since these are public repos
whose authors already have access and had to write real field-handling
code) make a loader unsound to build blind:

1. **No native choices column, at all.** CAIS's own eval script
   (`github.com/centerforaisafety/hle/hle_eval/run_model_predictions.py`)
   sends the model only `question['question']` (text) and
   `question['image']` (`""` if not multimodal -- this is the confirmed,
   correct text-only filter predicate: `image == ""`). The independent UK
   AISI implementation (`inspect_evals/hle/hle.py`) confirms the same
   thing from the other side: its `record_to_sample` reads
   `id/question/image/answer/answer_type/author_name/rationale/
   raw_subject/category` and nothing else -- no choices field exists to
   read. Multiple-choice options, when present, are embedded as free text
   *inside* the `question` string, not a structured list like
   GPQA/LEXam/MMLU-Pro all have. Extracting them into `GPQAItem.choices:
   list[str]` would require a regex parser over free text whose
   reliability is exactly the kind of thing load_lexam.py's own stated
   discipline says to verify against real rows before writing the loader
   -- and that verification is the thing currently blocked. Public
   descriptions of HLE's MC format also describe "five or more answer
   choices," i.e. not fixed at 4 like every dataset this engine currently
   ingests (would need MMLU-Pro's trim-to-4 treatment too, on top of the
   parsing problem).
2. **Official grading is LLM-judge semantic equivalence, not letter
   matching, for every question type including multipleChoice.**
   `hle_eval/run_judge_results.py`'s `JUDGE_PROMPT` asks a judge model
   whether a free-text response is equivalent to `question['answer']` --
   there is no separate branch for MC vs exact-match, and no letter-only
   compare anywhere in either eval script. The independent implementation
   confirms `answer_type` only takes two exact values, `"exactMatch"` and
   `"multipleChoice"` (`VALID_ANSWER_TYPES` in inspect_evals/hle/hle.py),
   but both are scored the same way: `scorer=llm_grader()`. QuorumQA's
   entire engine (solver.py, skeptic.py, judge.py, and
   `quorumqa.schemas.GPQAItem.correct_letter` /
   `JudgeVerdict.final_letter`) is hardcoded around eliciting and
   comparing a single A-D letter. Even a perfectly-parsed HLE MC subset
   would need its own grading path, since "correct" in HLE is defined as
   "an LLM judge accepted the semantic match," not "the letter matched."

## Verdict

**Not building `benchmark/load_hle.py` in this pass.** Not because the
text-only-MC subset is confirmed too small -- its size is genuinely
unmeasured, not measured-and-small -- but because two separate,
independently-sourced blockers each individually stop a responsible build
right now:

- The row-level data needed to verify the real joint count and validate a
  choice-extraction regex is behind a gate this agent isn't authorized to
  click through (accepting HF's access agreement requires the user's own
  action).
- Even with access, HLE's schema (no choices column, LLM-judge grading for
  every question type) is a structurally different shape than every
  dataset this engine currently ingests -- closer to a second engine mode
  than a fourth loader.

This reinforces, rather than merely repeats, the earlier 0-3 refutation:
the original two grounds (multimodal fraction, exact-match fraction) are
real and confirmed live, but the stronger and more decisive grounds turn
out to be the missing choices column and the judge-based grading model --
both true regardless of what the exact joint count turns out to be.

## To reopen this

1. Jun Kai (or whoever owns the `junipertc02e` HF account) visits
   `https://huggingface.co/datasets/cais/hle`, logs in, and clicks through
   the access request (`auto`-gated, historically fast/automatic).
2. Re-run this check's live queries against `/rows` to get the real joint
   count (`image == "" AND answer_type == "multipleChoice"`) and inspect
   ~20 real `multipleChoice` rows' `question` text to see whether the
   embedded choices follow one consistent, regex-parseable format.
3. Only if both come back favorable (subset >= ~300, format is reliably
   parseable), write `load_hle.py` following `load_lexam.py`'s discipline
   -- and additionally decide whether to build a semantic-match grading
   path or accept that letter-only grading changes what "correct" means
   relative to HLE's own published scores (on top of the trim-to-4
   caveat this repo already discloses for MMLU-Pro).
