"""Deterministic constraint verifier for IFEval (`google/IFEval`).

WHY THIS EXISTS: docs/capability-roadmap.md section 3.11 names IFEval as the
strongest STRUCTURAL case in the portfolio -- constraint compliance is
decidable by a Python predicate, so detection coverage is 100% by
construction, unlike every other axis where our nulls trace back to
coverage failures (a judge that never sees the wrong answers cannot fix
them). FATAL 2 in that section is that the grader did not exist in this
repo. This module is that grader: a clean-room port of the check_following
logic in the official `instruction_following_eval` package
(google-research/google-research, Apache-2.0), covering all 25 instruction
types that actually appear in the 541-row dataset (verified by enumerating
`instruction_id_list` live against the cached HF dataset -- see
benchmark/results/ifeval_scorer_validation.md for the full count table).

PORT METHODOLOGY, stated plainly: this is not a reimplementation from a
spec, it is a line-by-line port of the official checker algorithms (regexes,
split logic, off-by-one quirks and all) fetched directly from
https://github.com/google-research/google-research/tree/master/instruction_following_eval
during the build of this module. Where the official code has a surprising
edge case (e.g. `EndChecker` strips a leading/trailing `"` before matching;
`ParagraphFirstWordCheck` indexes into the un-filtered paragraph list even
though it separately counts non-empty paragraphs), we replicate it exactly
rather than "fixing" it, because our job is to grade the way the official
scorer grades, not the way we might have designed it. Two dependencies the
official package pulls in (`nltk` for sentence/word tokenization, and
`langdetect` for the language-family checkers) are real, unavoidable
runtime deps of faithful IFEval grading -- both are pure-Python / bundled
corpora once their one-time data files are cached locally, so they impose
no network or paid-API cost at test time. `absl-py` and `immutabledict`,
which the official package also imports, are NOT dependencies of this
module -- they were only used transiently (outside this repo, in a
scratchpad) to run the actual reference implementation for validation; see
benchmark/results/ifeval_scorer_validation.md.

STRICT vs LOOSE: `verify_all` implements IFEval's strict prompt-level metric
(every instruction in the prompt must be followed, checked against the raw
response). `verify_all_loose` implements the official "loose" upper bound:
it retries each instruction against 8 response transforms (the original,
markdown-asterisks-stripped, first-line-dropped, last-line-dropped, both,
and the four combinations) and counts an instruction as followed if ANY
transform satisfies it -- ported verbatim from
`evaluation_lib.test_instruction_following_loose`.

ANTI-GAMING CONTROL (roadmap MAJOR 3): the predicate vocabulary used by
`extract_constraints_from_prompt` is drawn from IFEval's own instruction
families, so a future repair loop optimizing against this extractor would
really be optimizing against a reimplementation of the grader -- the
"held-out verifier is not independent of the optimization target" problem.
HELD_OUT_INSTRUCTION_TYPES below is the fix: ~1/3 of the 25 instruction
types, chosen and frozen before any run (see the validation doc for the
selection rationale and the frozen list), that `extract_constraints_from_prompt`
must never emit and that no repair loop may target. `verify_all` and
`verify_all_loose` still grade held-out instruction types normally (they
are real, gradeable constraints) -- only the EXTRACTOR is blind to them.
`instruction_id_list` (the dataset's own metadata) is reserved strictly for
post-hoc auditing of the extractor's recall; the extractor itself never
reads it.

Usage:
  from benchmark.ifeval_verify import verify_all, verify_all_loose, \\
      extract_constraints_from_prompt, HELD_OUT_INSTRUCTION_TYPES

  result = verify_all(response_text, item.instruction_id_list, item.kwargs)
  # {"strict_followed": bool, "per_instruction": [{"instruction_id":...,
  #   "followed": bool, "detail": "..."}, ...]}

  loose = verify_all_loose(response_text, item.instruction_id_list, item.kwargs)
  # {"loose_followed": bool, "per_instruction": [...]}

  constraints = extract_constraints_from_prompt(item.prompt)
  # [{"type": "length_constraints:number_words",
  #   "kwargs": {"relation": "at least", "num_words": 300},
  #   "matched_text": "300+ word"}, ...]
"""

from __future__ import annotations

import collections
import json
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# nltk (sentence/word tokenization) and langdetect (language-family
# checkers) are real runtime deps of faithful IFEval grading -- see the
# module docstring. Both are pure-Python once their data files are cached
# (nltk's `punkt`/`punkt_tab` tokenizer models; langdetect ships its
# n-gram profiles inside the package, no separate download).
import nltk
import langdetect

# Deterministic language detection. The official package does not set this,
# but langdetect's underlying algorithm is a naive-Bayes classifier over a
# random subset of n-gram features and is documented upstream as
# nondeterministic run-to-run unless seeded. We seed it so this module's
# checkers -- which this file's own docstring promises are "deterministic,
# no network, no model calls" -- actually are deterministic in practice, at
# the cost of a (harmless, well-known) departure from the unseeded official
# behavior on genuinely ambiguous inputs. Recorded as a known divergence in
# benchmark/results/ifeval_scorer_validation.md.
langdetect.DetectorFactory.seed = 0


# ---------------------------------------------------------------------------
# instructions_util.py port (tokenization helpers only -- WORD_LIST and
# split_into_sentences are dead code upstream for the 25 registered
# instruction types: KeySentenceChecker, the only caller of
# split_into_sentences, is commented out of the official registry, and
# WORD_LIST only feeds prompt *generation* (random keyword choice), never
# response *grading*. Neither is ported.)
# ---------------------------------------------------------------------------

_COMPARISON_RELATION = ("less than", "at least")

# ISO 639-1 -> English name, restricted to the languages IFEval's own
# ResponseLanguageChecker recognizes (ported from instructions_util.LANGUAGE_CODES).
LANGUAGE_CODES: dict[str, str] = {
    "en": "English", "es": "Spanish", "pt": "Portuguese", "ar": "Arabic",
    "hi": "Hindi", "fr": "French", "ru": "Russian", "de": "German",
    "ja": "Japanese", "it": "Italian", "bn": "Bengali", "uk": "Ukrainian",
    "th": "Thai", "ur": "Urdu", "ta": "Tamil", "te": "Telugu",
    "bg": "Bulgarian", "ko": "Korean", "pl": "Polish", "he": "Hebrew",
    "fa": "Persian", "vi": "Vietnamese", "ne": "Nepali", "sw": "Swahili",
    "kn": "Kannada", "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi",
    "ml": "Malayalam", "fi": "Finnish",
}
_LANGUAGE_NAME_TO_CODE = {name.lower(): code for code, name in LANGUAGE_CODES.items()}


def _count_words(text: str) -> int:
    """Ported from instructions_util.count_words -- regex tokenizer, no
    punkt data needed (this one does NOT require nltk's downloaded models)."""
    tokenizer = nltk.tokenize.RegexpTokenizer(r"\w+")
    return len(tokenizer.tokenize(text))


def _count_sentences(text: str) -> int:
    """Ported from instructions_util.count_sentences -- uses nltk's punkt
    sentence tokenizer, which requires the `punkt`/`punkt_tab` nltk_data
    package to be present locally (downloaded once at build time; see
    benchmark/results/ifeval_scorer_validation.md)."""
    tokenizer = nltk.data.load("nltk:tokenizers/punkt/english.pickle")
    return len(tokenizer.tokenize(text))


def _word_tokenize(text: str) -> list[str]:
    """Ported from CapitalWordFrequencyChecker's direct use of
    nltk.word_tokenize (also requires punkt data)."""
    return nltk.tokenize.word_tokenize(text)


def _detect_language(text: str) -> str | None:
    """Wraps langdetect.detect, replicating the official checkers'
    fail-open behavior: if the detector cannot classify the text (raises
    LangDetectException, e.g. on empty or symbol-only input), the official
    code logs an error and counts the instruction as FOLLOWED. We surface
    that by returning None here and having each caller treat None as
    'followed' -- same fail-open semantics, ported faithfully rather than
    tightened, because the point of this module is to grade the way the
    official grader grades."""
    try:
        return langdetect.detect(text)
    except langdetect.LangDetectException as e:
        log.debug("langdetect could not classify response (%s); treating as followed", e)
        return None


# ---------------------------------------------------------------------------
# Per-instruction checkers. Each is `(response: str, kwargs: dict) ->
# {"followed": bool, "detail": str}`. `kwargs` is the dataset's raw
# per-row kwargs dict for this instruction: a superset schema shared across
# all 25 instruction types (HF's Sequence(dict) column forces a uniform
# key set), with irrelevant fields as None. Every checker below pulls only
# the fields it needs via .get() and ignores the rest -- unlike the
# official package's `build_description(**kwargs)` call, which fails with
# TypeError on the padded dict (verified live; see the validation doc),
# our functions are tolerant of the padding by construction.
# ---------------------------------------------------------------------------


def _cmp(actual: int, relation: str | None, threshold: int) -> bool:
    """Shared 'less than' / 'at least' comparison used by four checkers."""
    relation = relation or _COMPARISON_RELATION[1]  # default: "at least"
    if relation == _COMPARISON_RELATION[0]:
        return actual < threshold
    return actual >= threshold


def check_keywords_existence(response: str, kwargs: dict) -> dict:
    keywords = kwargs.get("keywords") or []
    missing = [kw for kw in keywords if not re.search(kw, response, flags=re.IGNORECASE)]
    return {
        "followed": len(missing) == 0,
        "detail": "all keywords present" if not missing else f"missing keywords: {missing}",
    }


def check_keywords_frequency(response: str, kwargs: dict) -> dict:
    keyword = kwargs.get("keyword") or ""
    frequency = kwargs.get("frequency")
    relation = kwargs.get("relation")
    actual = len(re.findall(keyword, response, flags=re.IGNORECASE))
    ok = _cmp(actual, relation, frequency)
    return {
        "followed": ok,
        "detail": f"'{keyword}' occurs {actual}x, need {relation or 'at least'} {frequency}",
    }


def check_keywords_forbidden_words(response: str, kwargs: dict) -> dict:
    forbidden = kwargs.get("forbidden_words") or []
    hit = [w for w in forbidden if re.search(r"\b" + w + r"\b", response, flags=re.IGNORECASE)]
    return {
        "followed": len(hit) == 0,
        "detail": "no forbidden words used" if not hit else f"forbidden words present: {hit}",
    }


def check_keywords_letter_frequency(response: str, kwargs: dict) -> dict:
    letter = (kwargs.get("letter") or "").lower()
    frequency = kwargs.get("let_frequency")
    relation = kwargs.get("let_relation")
    counts = collections.Counter(response.lower())
    actual = counts[letter]
    ok = _cmp(actual, relation, frequency)
    return {
        "followed": ok,
        "detail": f"letter '{letter}' occurs {actual}x, need {relation or 'at least'} {frequency}",
    }


def check_language_response_language(response: str, kwargs: dict) -> dict:
    language = kwargs.get("language")
    detected = _detect_language(response)
    if detected is None:
        return {"followed": True, "detail": "langdetect could not classify (fail-open, per official grader)"}
    return {
        "followed": detected == language,
        "detail": f"detected language '{detected}', need '{language}'",
    }


def check_length_number_sentences(response: str, kwargs: dict) -> dict:
    threshold = kwargs.get("num_sentences")
    relation = kwargs.get("relation")
    actual = _count_sentences(response)
    ok = _cmp(actual, relation, threshold)
    return {
        "followed": ok,
        "detail": f"{actual} sentences, need {relation or 'at least'} {threshold}",
    }


def check_length_number_paragraphs(response: str, kwargs: dict) -> dict:
    """Ported from ParagraphChecker.check_following, including the
    leading/trailing-empty-paragraph tolerance and mid-string-empty-fails
    quirk of the original."""
    num_paragraphs = kwargs.get("num_paragraphs")
    paragraphs = re.split(r"\s?\*\*\*\s?", response)
    count = len(paragraphs)
    for index, paragraph in enumerate(paragraphs):
        if not paragraph.strip():
            if index == 0 or index == len(paragraphs) - 1:
                count -= 1
            else:
                return {"followed": False, "detail": "empty paragraph found mid-response (between *** dividers)"}
    return {
        "followed": count == num_paragraphs,
        "detail": f"{count} paragraphs (split on ***), need exactly {num_paragraphs}",
    }


def check_length_number_words(response: str, kwargs: dict) -> dict:
    threshold = kwargs.get("num_words")
    relation = kwargs.get("relation")
    actual = _count_words(response)
    ok = _cmp(actual, relation, threshold)
    return {
        "followed": ok,
        "detail": f"{actual} words, need {relation or 'at least'} {threshold}",
    }


def check_length_nth_paragraph_first_word(response: str, kwargs: dict) -> dict:
    """Ported from ParagraphFirstWordCheck.check_following verbatim,
    including the quirk that `nth_paragraph` indexes into the un-filtered
    `\\n\\n`-split list even though `num_paragraphs` is compared against
    the count with empty paragraphs excluded."""
    num_paragraphs = kwargs.get("num_paragraphs")
    nth_paragraph = kwargs.get("nth_paragraph")
    first_word = (kwargs.get("first_word") or "").lower()

    paragraphs = re.split(r"\n\n", response)
    count = len(paragraphs)
    for paragraph in paragraphs:
        if not paragraph.strip():
            count -= 1

    if nth_paragraph is None or nth_paragraph > len(paragraphs) or nth_paragraph <= 0:
        return {"followed": False, "detail": f"nth_paragraph={nth_paragraph} out of range for {len(paragraphs)} paragraphs"}
    if nth_paragraph > count:
        return {"followed": False, "detail": f"only {count} non-empty paragraphs, need paragraph {nth_paragraph}"}

    paragraph = paragraphs[nth_paragraph - 1].strip()
    if not paragraph:
        return {"followed": False, "detail": f"paragraph {nth_paragraph} is empty"}

    punctuation = {".", ",", "?", "!", "'", '"'}
    word = paragraph.split()[0].strip().lstrip("'").lstrip('"')
    actual_first_word = ""
    for letter in word:
        if letter in punctuation:
            break
        actual_first_word += letter.lower()

    ok = count == num_paragraphs and actual_first_word == first_word
    return {
        "followed": ok,
        "detail": f"{count} paragraphs (need {num_paragraphs}); paragraph {nth_paragraph} starts with '{actual_first_word}' (need '{first_word}')",
    }


def check_detectable_content_number_placeholders(response: str, kwargs: dict) -> dict:
    threshold = kwargs.get("num_placeholders")
    placeholders = re.findall(r"\[.*?\]", response)
    actual = len(placeholders)
    return {
        "followed": actual >= threshold,
        "detail": f"{actual} [placeholders] found, need at least {threshold}",
    }


def check_detectable_content_postscript(response: str, kwargs: dict) -> dict:
    marker = kwargs.get("postscript_marker")
    value = response.lower()
    if marker == "P.P.S":
        pattern = r"\s*p\.\s?p\.\s?s.*$"
    elif marker == "P.S.":
        pattern = r"\s*p\.\s?s\..*$"
    else:
        pattern = r"\s*" + re.escape((marker or "").lower()) + r".*$"
    found = re.findall(pattern, value, flags=re.MULTILINE)
    return {
        "followed": bool(found),
        "detail": f"postscript marker '{marker}' {'found' if found else 'not found'}",
    }


def check_detectable_format_number_bullet_lists(response: str, kwargs: dict) -> dict:
    threshold = kwargs.get("num_bullets")
    bullets_star = re.findall(r"^\s*\*[^\*].*$", response, flags=re.MULTILINE)
    bullets_dash = re.findall(r"^\s*-.*$", response, flags=re.MULTILINE)
    actual = len(bullets_star) + len(bullets_dash)
    return {
        "followed": actual == threshold,
        "detail": f"{actual} bullet points found, need exactly {threshold}",
    }


_CONSTRAINED_RESPONSE_OPTIONS = ("My answer is yes.", "My answer is no.", "My answer is maybe.")


def check_detectable_format_constrained_response(response: str, kwargs: dict) -> dict:
    value = response.strip()
    hit = any(opt in value for opt in _CONSTRAINED_RESPONSE_OPTIONS)
    return {
        "followed": hit,
        "detail": f"one of {_CONSTRAINED_RESPONSE_OPTIONS} {'found' if hit else 'not found'} in response",
    }


def check_detectable_format_number_highlighted_sections(response: str, kwargs: dict) -> dict:
    threshold = kwargs.get("num_highlights")
    num_highlights = 0
    highlights = re.findall(r"\*[^\n\*]*\*", response)
    double_highlights = re.findall(r"\*\*[^\n\*]*\*\*", response)
    for h in highlights:
        if h.strip("*").strip():
            num_highlights += 1
    for h in double_highlights:
        if h.removeprefix("**").removesuffix("**").strip():
            num_highlights += 1
    return {
        "followed": num_highlights >= threshold,
        "detail": f"{num_highlights} highlighted sections found, need at least {threshold}",
    }


def check_detectable_format_multiple_sections(response: str, kwargs: dict) -> dict:
    spliter = kwargs.get("section_spliter") or "Section"
    threshold = kwargs.get("num_sections")
    pattern = r"\s?" + re.escape(spliter) + r"\s?\d+\s?"
    sections = re.split(pattern, response)
    count = len(sections) - 1
    return {
        "followed": count >= threshold,
        "detail": f"{count} '{spliter} N' sections found, need at least {threshold}",
    }


def check_detectable_format_json_format(response: str, kwargs: dict) -> dict:
    value = (
        response.strip()
        .removeprefix("```json")
        .removeprefix("```Json")
        .removeprefix("```JSON")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    try:
        json.loads(value)
    except ValueError:
        return {"followed": False, "detail": "response is not valid JSON after stripping ``` fences"}
    return {"followed": True, "detail": "response parses as valid JSON"}


def check_detectable_format_title(response: str, kwargs: dict) -> dict:
    titles = re.findall(r"<<[^\n]+>>", response)
    hit = any(t.lstrip("<").rstrip(">").strip() for t in titles)
    return {
        "followed": hit,
        "detail": "non-empty <<title>> found" if hit else "no non-empty <<title>> found",
    }


def check_combination_two_responses(response: str, kwargs: dict) -> dict:
    valid = []
    parts = response.split("******")
    for index, part in enumerate(parts):
        if not part.strip():
            if index != 0 and index != len(parts) - 1:
                return {"followed": False, "detail": "empty response segment between ****** separators"}
        else:
            valid.append(part)
    ok = len(valid) == 2 and valid[0].strip() != valid[1].strip()
    return {
        "followed": ok,
        "detail": f"{len(valid)} non-empty responses found (need 2, distinct)",
    }


def check_combination_repeat_prompt(response: str, kwargs: dict) -> dict:
    prompt_to_repeat = kwargs.get("prompt_to_repeat") or ""
    ok = response.strip().lower().startswith(prompt_to_repeat.strip().lower())
    return {
        "followed": ok,
        "detail": "response opens by repeating the prompt" if ok else "response does not start with the repeated prompt",
    }


def check_startend_end_checker(response: str, kwargs: dict) -> dict:
    end_phrase = (kwargs.get("end_phrase") or "").strip().lower()
    value = response.strip().strip('"').lower()
    ok = value.endswith(end_phrase)
    return {
        "followed": ok,
        "detail": f"response {'ends' if ok else 'does not end'} with required phrase",
    }


def check_change_case_capital_word_frequency(response: str, kwargs: dict) -> dict:
    threshold = kwargs.get("capital_frequency")
    relation = kwargs.get("capital_relation")
    words = _word_tokenize(response)
    actual = len([w for w in words if w.isupper()])
    ok = _cmp(actual, relation, threshold)
    return {
        "followed": ok,
        "detail": f"{actual} ALL-CAPS words, need {relation or 'at least'} {threshold}",
    }


def check_change_case_english_capital(response: str, kwargs: dict) -> dict:
    detected = _detect_language(response)
    if detected is None:
        return {"followed": True, "detail": "langdetect could not classify (fail-open, per official grader)"}
    ok = response.isupper() and detected == "en"
    return {"followed": ok, "detail": f"isupper={response.isupper()}, detected_lang={detected}"}


def check_change_case_english_lowercase(response: str, kwargs: dict) -> dict:
    detected = _detect_language(response)
    if detected is None:
        return {"followed": True, "detail": "langdetect could not classify (fail-open, per official grader)"}
    ok = response.islower() and detected == "en"
    return {"followed": ok, "detail": f"islower={response.islower()}, detected_lang={detected}"}


def check_punctuation_no_comma(response: str, kwargs: dict) -> dict:
    ok = not re.search(r",", response)
    return {"followed": ok, "detail": "no commas found" if ok else "response contains a comma"}


def check_startend_quotation(response: str, kwargs: dict) -> dict:
    value = response.strip()
    ok = len(value) > 1 and value[0] == '"' and value[-1] == '"'
    return {"followed": ok, "detail": "wrapped in double quotes" if ok else "not wrapped in double quotes"}


CHECKERS: dict[str, Any] = {
    "keywords:existence": check_keywords_existence,
    "keywords:frequency": check_keywords_frequency,
    "keywords:forbidden_words": check_keywords_forbidden_words,
    "keywords:letter_frequency": check_keywords_letter_frequency,
    "language:response_language": check_language_response_language,
    "length_constraints:number_sentences": check_length_number_sentences,
    "length_constraints:number_paragraphs": check_length_number_paragraphs,
    "length_constraints:number_words": check_length_number_words,
    "length_constraints:nth_paragraph_first_word": check_length_nth_paragraph_first_word,
    "detectable_content:number_placeholders": check_detectable_content_number_placeholders,
    "detectable_content:postscript": check_detectable_content_postscript,
    "detectable_format:number_bullet_lists": check_detectable_format_number_bullet_lists,
    "detectable_format:constrained_response": check_detectable_format_constrained_response,
    "detectable_format:number_highlighted_sections": check_detectable_format_number_highlighted_sections,
    "detectable_format:multiple_sections": check_detectable_format_multiple_sections,
    "detectable_format:json_format": check_detectable_format_json_format,
    "detectable_format:title": check_detectable_format_title,
    "combination:two_responses": check_combination_two_responses,
    "combination:repeat_prompt": check_combination_repeat_prompt,
    "startend:end_checker": check_startend_end_checker,
    "change_case:capital_word_frequency": check_change_case_capital_word_frequency,
    "change_case:english_capital": check_change_case_english_capital,
    "change_case:english_lowercase": check_change_case_english_lowercase,
    "punctuation:no_comma": check_punctuation_no_comma,
    "startend:quotation": check_startend_quotation,
}

# All 25 instruction families that appear in the 541-row google/IFEval
# dataset (verified live by enumerating instruction_id_list -- see
# benchmark/results/ifeval_scorer_validation.md). CHECKERS must cover
# exactly this set; asserted at import time so a future dataset refresh
# that adds an unrecognized instruction id fails loudly instead of
# silently under-grading.
KNOWN_INSTRUCTION_TYPES = frozenset(CHECKERS.keys())
assert len(KNOWN_INSTRUCTION_TYPES) == 25, f"expected 25 instruction types, got {len(KNOWN_INSTRUCTION_TYPES)}"


def _check_one(instruction_id: str, response: str, kwargs: dict) -> dict:
    checker = CHECKERS.get(instruction_id)
    if checker is None:
        raise KeyError(
            f"no checker registered for instruction_id={instruction_id!r} -- "
            f"known types: {sorted(KNOWN_INSTRUCTION_TYPES)}"
        )
    result = checker(response, kwargs)
    return {"instruction_id": instruction_id, "followed": result["followed"], "detail": result["detail"]}


def verify_all(response: str, instruction_id_list: list[str], kwargs_list: list[dict]) -> dict:
    """IFEval's STRICT prompt-level metric: every instruction must be
    followed by the raw response for the prompt to count as followed.
    Ported from evaluation_lib.test_instruction_following_strict, including
    the `response.strip()` empty-response guard (an empty response fails
    every instruction, matching the official scorer)."""
    per_instruction = []
    for instruction_id, kwargs in zip(instruction_id_list, kwargs_list):
        result = _check_one(instruction_id, response, kwargs)
        if not response.strip():
            result = {**result, "followed": False, "detail": "response is empty"}
        per_instruction.append(result)
    return {
        "strict_followed": all(r["followed"] for r in per_instruction),
        "per_instruction": per_instruction,
    }


def _loose_transforms(response: str) -> list[str]:
    """Ported verbatim from evaluation_lib.test_instruction_following_loose:
    8 candidate transforms of the response (original / asterisks-stripped
    x original / first-line-dropped / last-line-dropped / both-dropped)."""
    lines = response.split("\n")
    remove_first = "\n".join(lines[1:]).strip()
    remove_last = "\n".join(lines[:-1]).strip()
    remove_both = "\n".join(lines[1:-1]).strip()
    return [
        response,
        response.replace("*", ""),
        remove_first,
        remove_last,
        remove_both,
        remove_first.replace("*", ""),
        remove_last.replace("*", ""),
        remove_both.replace("*", ""),
    ]


def verify_all_loose(response: str, instruction_id_list: list[str], kwargs_list: list[dict]) -> dict:
    """IFEval's LOOSE prompt-level metric: an instruction counts as followed
    if ANY of the 8 response transforms satisfies its checker. This is an
    upper bound used to separate genuine non-compliance from formatting
    tolerance (e.g. the model added a leading 'Sure, here you go:' line, or
    used markdown bold where the checker only looks for single asterisks)."""
    candidates = _loose_transforms(response)
    per_instruction = []
    for instruction_id, kwargs in zip(instruction_id_list, kwargs_list):
        followed = False
        detail = "no transform satisfied the checker"
        for candidate in candidates:
            if not candidate.strip():
                continue
            result = _check_one(instruction_id, candidate, kwargs)
            if result["followed"]:
                followed = True
                detail = result["detail"]
                break
        per_instruction.append({"instruction_id": instruction_id, "followed": followed, "detail": detail})
    return {
        "loose_followed": all(r["followed"] for r in per_instruction),
        "per_instruction": per_instruction,
    }


# ---------------------------------------------------------------------------
# Anti-gaming control: held-out instruction types.
#
# Rationale and the frozen list are the authoritative content of
# benchmark/results/ifeval_scorer_validation.md; this constant is the
# single source of truth the code and the doc must agree on (tests assert
# they match). Chosen BEFORE any run: ~1/3 (8/25 = 32%) of instruction
# types, stratified across families (never the sole member of a
# single-member family, so the in-domain set still has full-family
# coverage for `language:` and `punctuation:`), picked to leave a
# non-trivial "only held-out constraints" cohort in the real dataset
# (measured: 115/541 = 21.3% of prompts have every instruction_id in this
# set -- the future headline-metric cohort).
# ---------------------------------------------------------------------------
HELD_OUT_INSTRUCTION_TYPES = frozenset({
    "change_case:english_lowercase",
    "keywords:letter_frequency",
    "detectable_format:number_highlighted_sections",
    "detectable_format:multiple_sections",
    "length_constraints:nth_paragraph_first_word",
    "combination:repeat_prompt",
    "detectable_content:postscript",
    "startend:quotation",
})
assert HELD_OUT_INSTRUCTION_TYPES <= KNOWN_INSTRUCTION_TYPES
assert 0.30 <= len(HELD_OUT_INSTRUCTION_TYPES) / len(KNOWN_INSTRUCTION_TYPES) <= 0.36


# ---------------------------------------------------------------------------
# extract_constraints_from_prompt: heuristic, model-free, prompt-text-only
# extractor. Never reads instruction_id_list or kwargs -- that would be the
# label leakage the roadmap already warns is controlled for. Never emits a
# HELD_OUT_INSTRUCTION_TYPES type -- that is the vocabulary-leakage control
# this build adds. Recall against instruction_id_list is a POST-HOC AUDIT
# metric only (see benchmark/results/ifeval_scorer_validation.md); it must
# never be used to tune the extractor's own regexes in a way that then
# gets treated as validation of a live lever.
# ---------------------------------------------------------------------------

_RELATION_UNIT_PATTERNS = [
    (re.compile(r"\bat least\s+(\d+)\+?\s*", re.I), "at least"),
    (re.compile(r"\b(\d+)\+\s*", re.I), "at least"),
    (re.compile(r"\b(?:less than|fewer than)\s+(\d+)\s*", re.I), "less than"),
    (re.compile(r"\b(?:no more than|at most)\s+(\d+)\s*", re.I), "less than"),
    (re.compile(r"\bexactly\s+(\d+)\s*", re.I), "at least"),  # nearest supported relation
]


def _find_relation_count(prompt: str, unit_regex: str, exclude_context: str | None = None) -> tuple[str, int, str] | None:
    """Scans prompt for '<relation> <N> <unit>' style phrasing. Returns
    (relation, count, matched_text) for the first hit, else None.

    `exclude_context`, if given, is a regex checked against a small window
    around the match (both sides): if it hits, this candidate is skipped.
    Used to keep "N words in all CAPITAL letters" (a
    change_case:capital_word_frequency constraint on how many words are
    capitalized) from being misread as a plain
    length_constraints:number_words constraint -- a real collision found
    during the recall spot-check (see benchmark/results/ifeval_scorer_validation.md)."""
    unit_pat = re.compile(unit_regex, re.I)
    exclude_pat = re.compile(exclude_context, re.I) if exclude_context else None
    for m in unit_pat.finditer(prompt):
        if exclude_pat is not None:
            wide_start = max(0, m.start() - 25)
            wide_end = min(len(prompt), m.end() + 25)
            if exclude_pat.search(prompt[wide_start:wide_end]):
                continue
        window_start = max(0, m.start() - 30)
        window = prompt[window_start:m.end()]
        for rel_pat, relation in _RELATION_UNIT_PATTERNS:
            rel_match = rel_pat.search(window)
            if rel_match:
                return relation, int(rel_match.group(1)), window[rel_match.start():].strip()
    return None


def _extract_no_comma(prompt: str) -> dict | None:
    m = re.search(
        r"(?:do not|don't|not allowed to|refrain from|without)\s+(?:use|using)\s+(?:any\s+)?commas?"
        r"|no\s+commas?\s+(?:allowed|are allowed)"
        r"|not\s+(?:use|contain)\s+(?:any\s+)?commas?",
        prompt, re.I,
    )
    if not m:
        return None
    return {"type": "punctuation:no_comma", "kwargs": {}, "matched_text": m.group(0)}


def _extract_number_words(prompt: str) -> dict | None:
    # Exclude "N words in/with all CAPITAL letters" / "N words in all caps"
    # -- that is change_case:capital_word_frequency's territory (how many
    # words are capitalized), not a total-response-length constraint.
    hit = _find_relation_count(
        prompt, r"\d+\+?\s*words?\b",
        exclude_context=r"capital|\ball[- ]?caps?\b",
    )
    if not hit:
        return None
    relation, count, matched = hit
    return {"type": "length_constraints:number_words", "kwargs": {"relation": relation, "num_words": count}, "matched_text": matched}


def _extract_number_placeholders(prompt: str) -> dict | None:
    hit = _find_relation_count(prompt, r"\d+\s*placeholders?\b")
    if not hit:
        return None
    _relation, count, matched = hit
    return {
        "type": "detectable_content:number_placeholders",
        "kwargs": {"num_placeholders": count},
        "matched_text": matched,
    }


def _extract_number_sentences(prompt: str) -> dict | None:
    hit = _find_relation_count(prompt, r"\d+\s*sentences?\b")
    if not hit:
        return None
    relation, count, matched = hit
    return {"type": "length_constraints:number_sentences", "kwargs": {"relation": relation, "num_sentences": count}, "matched_text": matched}


def _extract_number_paragraphs(prompt: str) -> dict | None:
    # ParagraphChecker (length_constraints:number_paragraphs) always splits
    # the RESPONSE on a literal "***" divider -- that is the discriminating
    # signal vs detectable_format:multiple_sections, whose SectionChecker
    # instead looks for a "Section N" / "SECTION N" marker word. Because
    # "***" is the reliable tell, we can safely accept "paragraphs",
    # "sections" or "parts" as the counted noun in the prompt's own
    # phrasing (real prompts use all three loosely) without risking
    # collision with multiple_sections-style prompts, which don't mention
    # "***" at all.
    if "***" not in prompt and "divider" not in prompt.lower():
        return None
    m = re.search(r"(\d+)\s*(?:paragraphs?|sections?|parts?)\b", prompt, re.I)
    if not m:
        return None
    return {
        "type": "length_constraints:number_paragraphs",
        "kwargs": {"num_paragraphs": int(m.group(1))},
        "matched_text": m.group(0),
    }


def _extract_bullet_lists(prompt: str) -> dict | None:
    m = re.search(r"(\d+)\s*bullet\s*points?\b", prompt, re.I)
    if not m:
        return None
    return {
        "type": "detectable_format:number_bullet_lists",
        "kwargs": {"num_bullets": int(m.group(1))},
        "matched_text": m.group(0),
    }


def _extract_constrained_response(prompt: str) -> dict | None:
    if re.search(r"my answer is yes", prompt, re.I) and re.search(r"my answer is no", prompt, re.I):
        return {"type": "detectable_format:constrained_response", "kwargs": {}, "matched_text": "My answer is yes/no/maybe"}
    return None


def _extract_json_format(prompt: str) -> dict | None:
    m = re.search(r"\bjson\s*(?:format|block|object)\b|\bin\s+json\b", prompt, re.I)
    if not m:
        return None
    return {"type": "detectable_format:json_format", "kwargs": {}, "matched_text": m.group(0)}


def _extract_title(prompt: str) -> dict | None:
    m = re.search(r"title[^.]{0,40}angular brackets|<<[^>]+>>|wrapped in double angular brackets", prompt, re.I)
    if not m:
        return None
    return {"type": "detectable_format:title", "kwargs": {}, "matched_text": m.group(0)}


def _extract_two_responses(prompt: str) -> dict | None:
    # "two different responses" catches the canonical phrasing; the
    # 6-asterisk separator ("******" or "6 asterisk symbols") is a
    # distinctive signal on its own and catches variants that describe
    # what's being separated ("two jokes", "the two itineraries") rather
    # than literally saying "responses" -- a real miss found during the
    # recall spot-check (see benchmark/results/ifeval_scorer_validation.md).
    m = re.search(
        r"two different responses|exactly two.{0,20}responses|\*{6,}|6\s*asterisks?",
        prompt, re.I,
    )
    if not m:
        return None
    return {"type": "combination:two_responses", "kwargs": {}, "matched_text": m.group(0)}


def _extract_end_checker(prompt: str) -> dict | None:
    # "exact phrase" is the strongest, most phrasing-invariant signal
    # (covers "finish/end ... with this/the exact phrase", "... the exact
    # phrase of", etc.); the two literal cue phrases below catch prompts
    # that omit the words "exact phrase" entirely (e.g. "The very last
    # sentence of your response should be ...").
    m = re.search(
        r"(?:exact phrase|last sentence of your response should be|"
        r"finish your response with|end your (?:entire )?response with|must end with)"
        r"[^\"']{0,25}[\"']([^\"']+)[\"']",
        prompt, re.I,
    )
    if not m:
        return None
    return {
        "type": "startend:end_checker",
        "kwargs": {"end_phrase": m.group(1)},
        "matched_text": m.group(0),
    }


# Any phrasing of "words {in,with} all {capital letters,caps}" or "all-caps
# words" signals a per-word capitalization constraint (capital_word_frequency
# territory), regardless of word order -- both orders appear in real
# prompts ("words with all capital letters" vs "words in all caps").
_CAPITAL_WORD_PHRASING = re.compile(
    r"words?\s+(?:in|with)\s+all[- ]?(?:capital letters|caps?)\b|all[- ]?caps?\s+words",
    re.I,
)


def _extract_capital_word_frequency(prompt: str) -> dict | None:
    if not _CAPITAL_WORD_PHRASING.search(prompt):
        return None
    hit = _find_relation_count(prompt, r"\d+\s*times?\b") or _find_relation_count(prompt, r"\d+\s*words?\b")
    if not hit:
        return None
    relation, count, matched = hit
    return {
        "type": "change_case:capital_word_frequency",
        "kwargs": {"capital_relation": relation, "capital_frequency": count},
        "matched_text": matched,
    }


def _extract_english_capital(prompt: str) -> dict | None:
    if _CAPITAL_WORD_PHRASING.search(prompt):
        return None  # that's capital_word_frequency's territory, not this one
    m = re.search(r"all capital letters|in all caps\b|entirely in capital", prompt, re.I)
    if not m:
        return None
    return {"type": "change_case:english_capital", "kwargs": {}, "matched_text": m.group(0)}


def _extract_response_language(prompt: str) -> dict | None:
    # "the X language" is the canonical IFEval template phrasing; many
    # real prompts drop the trailing word "language" entirely ("respond
    # ... only in Korean.") or insert an adverb ("in entirely Swahili").
    # Precision is protected two ways: the captured capitalized word must
    # be in the closed LANGUAGE_CODES name list, AND -- because
    # change_case:english_capital / english_lowercase render as "Your
    # entire response should be in English, and in all capital/lowercase
    # letters" (their OWN official boilerplate, not a separate language
    # instruction) -- an "English" match is only accepted when it carries
    # the explicit word "language" or a "no other language" qualifier
    # nearby; that collision is real (confirmed on live dataset rows
    # during the recall spot-check, see the validation doc) and specific
    # to English, since the change_case checkers never mention any other
    # language name.
    for m in re.finditer(
        r"\b(?:in|using)\s+(?:only\s+)?(?:entirely\s+)?(?:the\s+)?([A-Z][a-z]+)\b(?:\s+language)?",
        prompt,
    ):
        name = m.group(1)
        code = _LANGUAGE_NAME_TO_CODE.get(name.lower())
        if code is None:
            continue
        if name.lower() == "english":
            window = prompt[m.start():m.end() + 25]
            if not re.search(r"language|no other language", window, re.I):
                continue
        return {"type": "language:response_language", "kwargs": {"language": code}, "matched_text": m.group(0)}
    return None


# Forward cue: "<cue phrase> ... '<word>' [and/or/, '<word>' ...]" -- the
# word(s) come AFTER the negation cue.
_FORBIDDEN_FORWARD_CUE = re.compile(
    r"(?:without using|must not use|should not use|do not use|not use|"
    r"do not say|does not say|do not mention|avoid using|avoid the word|"
    r"don't include|do not include|not include|forbidden)\s+"
    r"(?:the\s+)?(?:words?|keywords?)?",
    re.I,
)
# Reversed cue: "'<word>' ... should not appear/be used" -- the word comes
# BEFORE the cue (e.g. 'The word "rock" should not appear in your response.').
_FORBIDDEN_REVERSE_CUE = re.compile(r"should not (?:appear|be used|be included)", re.I)


def _quoted_words_in(span: str) -> list[str]:
    """Pulls out short quoted tokens (single words, not full phrases) from
    a text span -- used for both keywords:existence and
    keywords:forbidden_words, which the dataset's prompts render as
    "keyword(s) 'a' and 'b'" style comma/and-separated quoted lists."""
    quoted = re.findall(r"[\"']([^\"']+)[\"']", span)
    return [w for w in quoted if w and " " not in w.strip() and len(w) < 30]


def _extract_keywords_forbidden(prompt: str) -> dict | None:
    m = _FORBIDDEN_FORWARD_CUE.search(prompt)
    if m:
        # look ahead up to the next sentence boundary (or ~120 chars) for
        # one or more quoted words
        window = prompt[m.end():m.end() + 120]
        stop = re.search(r"[.\n]", window)
        if stop:
            window = window[:stop.end()]
        words = _quoted_words_in(window)
        if words:
            return {
                "type": "keywords:forbidden_words",
                "kwargs": {"forbidden_words": words},
                "matched_text": m.group(0) + " " + ", ".join(words),
            }

    m2 = _FORBIDDEN_REVERSE_CUE.search(prompt)
    if m2:
        window = prompt[max(0, m2.start() - 60):m2.start()]
        words = _quoted_words_in(window)
        if words:
            return {
                "type": "keywords:forbidden_words",
                "kwargs": {"forbidden_words": words},
                "matched_text": ", ".join(words) + " " + m2.group(0),
            }
    return None


_WORD_NUMBER = {"once": 1, "twice": 2}


def _extract_keywords_frequency(prompt: str) -> dict | None:
    # Pattern A: "word 'X' at least N times" / "word X less than N times".
    m = re.search(
        r"word\s+[\"']?(\w+)[\"']?\s+(at least|less than|fewer than)\s+(\d+)\s+times?",
        prompt, re.I,
    )
    if m:
        word, relation_raw, count = m.group(1), m.group(2).lower(), int(m.group(3))
        relation = "less than" if relation_raw in ("less than", "fewer than") else "at least"
        return {
            "type": "keywords:frequency",
            "kwargs": {"keyword": word, "relation": relation, "frequency": count},
            "matched_text": m.group(0),
        }

    # Pattern B: "word X should appear N (or more) times" / "... N times".
    m = re.search(
        r"word\s+[\"']?(\w+)[\"']?\s+should appear\s+(\d+)\s*(or more\s+)?times?",
        prompt, re.I,
    )
    if m:
        word, count, or_more = m.group(1), int(m.group(2)), m.group(3)
        relation = "at least" if or_more else "at least"
        return {
            "type": "keywords:frequency",
            "kwargs": {"keyword": word, "relation": relation, "frequency": count},
            "matched_text": m.group(0),
        }

    # Pattern C: "include the word X at least once/twice".
    m = re.search(
        r"word\s+[\"']?(\w+)[\"']?\s+(at least|less than|fewer than)\s+(once|twice)\b",
        prompt, re.I,
    )
    if m:
        word, relation_raw, word_count = m.group(1), m.group(2).lower(), m.group(3).lower()
        relation = "less than" if relation_raw in ("less than", "fewer than") else "at least"
        return {
            "type": "keywords:frequency",
            "kwargs": {"keyword": word, "relation": relation, "frequency": _WORD_NUMBER[word_count]},
            "matched_text": m.group(0),
        }

    # Pattern D: "word X appears at least N time(s)" (verb before relation,
    # and tolerates the dataset's own "3 time" singular typos via `times?`).
    m = re.search(
        r"word\s+[\"']?(\w+)[\"']?\s+appears?\s+(at least|less than|fewer than)\s+(\d+)\s*times?",
        prompt, re.I,
    )
    if m:
        word, relation_raw, count = m.group(1), m.group(2).lower(), int(m.group(3))
        relation = "less than" if relation_raw in ("less than", "fewer than") else "at least"
        return {
            "type": "keywords:frequency",
            "kwargs": {"keyword": word, "relation": relation, "frequency": count},
            "matched_text": m.group(0),
        }

    # Pattern E: "Mention <name/word> only once" -- "only once" means
    # strictly fewer than 2 occurrences.
    m = re.search(r"[Mm]ention(?:ing)?\s+(?:the\s+(?:name|word)\s+)?[\"']?(\w+)[\"']?\s+only once\b", prompt)
    if m:
        return {
            "type": "keywords:frequency",
            "kwargs": {"keyword": m.group(1), "relation": "less than", "frequency": 2},
            "matched_text": m.group(0),
        }
    return None


def _extract_keywords_existence(prompt: str) -> dict | None:
    if not re.search(r"\bkeywords?\b", prompt, re.I):
        return None
    # Broad negation guard: any of these anywhere in the prompt means this
    # is forbidden-words territory, not existence -- even if
    # _extract_keywords_forbidden itself fails to parse out the specific
    # word(s) (a miss there should not become a wrong-type false positive
    # here; see benchmark/results/ifeval_scorer_validation.md).
    if re.search(
        r"without|forbidden|not use|must not|should not|do not use|"
        r"don't include|do not include|not include|avoid",
        prompt, re.I,
    ):
        return None
    words = _quoted_words_in(prompt)
    if not words:
        return None
    return {"type": "keywords:existence", "kwargs": {"keywords": words}, "matched_text": ", ".join(words)}


# Order matters: more specific extractors (that could otherwise be
# shadowed by a looser sibling, e.g. capital_word_frequency vs
# english_capital) run first.
_EXTRACTORS = [
    _extract_no_comma,
    _extract_number_paragraphs,
    _extract_number_words,
    _extract_number_placeholders,
    _extract_number_sentences,
    _extract_bullet_lists,
    _extract_constrained_response,
    _extract_json_format,
    _extract_title,
    _extract_two_responses,
    _extract_end_checker,
    _extract_capital_word_frequency,
    _extract_english_capital,
    _extract_response_language,
    _extract_keywords_forbidden,
    _extract_keywords_frequency,
    _extract_keywords_existence,
]


def extract_constraints_from_prompt(prompt_text: str) -> list[dict]:
    """Heuristic, model-free extractor: reads ONLY prompt_text (never
    instruction_id_list or kwargs) and proposes typed constraints from the
    17 in-domain instruction types (25 known minus the 8
    HELD_OUT_INSTRUCTION_TYPES). This is a v0 heuristic tuned against a
    sample of real google/IFEval prompts, not a guarantee of full recall --
    see benchmark/results/ifeval_scorer_validation.md for the measured
    spot-check numbers and known misses. This is what a future live lever
    would call to build a repair target; instruction_id_list is reserved
    for auditing this function after the fact, never for feeding it."""
    found = []
    for extractor in _EXTRACTORS:
        result = extractor(prompt_text)
        if result is not None:
            assert result["type"] not in HELD_OUT_INSTRUCTION_TYPES, (
                f"extractor {extractor.__name__} emitted a held-out type {result['type']!r} "
                "-- this must never happen, it is the anti-gaming control"
            )
            found.append(result)
    return found
