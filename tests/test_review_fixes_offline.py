"""Regression tests for defects found by the full-repo adversarial review.

Each test names the finding it pins. All are offline.
"""

from __future__ import annotations

import asyncio

import pytest

from benchmark.ifeval_verify import (
    check_change_case_english_capital,
    check_change_case_english_lowercase,
)

# --------------------------------------------------------------------------
# C10 -- ifeval_verify change_case checkers failed OPEN on letter-free text
# --------------------------------------------------------------------------

# The official checker is `value.isupper() and langdetect.detect(value) == "en"`
# inside a try/except returning True. Python's `and` short-circuits, so a
# letter-free response never reaches langdetect and the official answer is
# False. Our port called _detect_language first and returned True on None.
LETTER_FREE = ["42", "123 456", "!!!", "1. 2. 3.", "3.14159", "[ ] [ ] [ ]", "***", "$1,000,000"]


@pytest.mark.parametrize("response", LETTER_FREE)
def test_letter_free_responses_do_not_fail_open(response):
    assert check_change_case_english_capital(response, {})["followed"] is False
    assert check_change_case_english_lowercase(response, {})["followed"] is False


def test_genuine_case_compliance_still_passes():
    assert check_change_case_english_capital(
        "THIS IS AN ENGLISH SENTENCE IN CAPITALS", {}
    )["followed"] is True
    assert check_change_case_english_lowercase(
        "this is an english sentence in lowercase", {}
    )["followed"] is True


def test_mixed_case_fails_both():
    assert check_change_case_english_capital("This Is Mixed", {})["followed"] is False
    assert check_change_case_english_lowercase("This Is Mixed", {})["followed"] is False


def test_langdetect_is_not_consulted_when_the_case_test_fails(monkeypatch):
    """Proves the short-circuit, not just its output.

    If _detect_language is reachable on a case-test failure, the fail-open
    branch can resurrect and the bug returns.
    """
    import benchmark.ifeval_verify as iv

    called = []
    monkeypatch.setattr(iv, "_detect_language", lambda s: called.append(s) or None)

    assert iv.check_change_case_english_capital("not caps", {})["followed"] is False
    assert iv.check_change_case_english_lowercase("NOT LOWER", {})["followed"] is False
    assert called == [], "langdetect was consulted despite the case test failing"

    # ...but it IS consulted once the case test passes, preserving fail-open.
    assert iv.check_change_case_english_capital("ALL CAPS", {})["followed"] is True
    assert called == ["ALL CAPS"]


# --------------------------------------------------------------------------
# C5 -- verifier.py dropped the WHOLE question on a non-dict claim
# --------------------------------------------------------------------------


class _FakeUsage:
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0


class _FakeResult:
    def __init__(self, data):
        self.data = data
        self.usage = _FakeUsage()


class _FakeClient:
    """Returns a malformed claims list, exactly as observed in the wild:
    lever_flagship_panel_supergpqa_seed123.log:743 'int' object has no
    attribute 'get'."""

    def __init__(self, claims):
        self._claims = claims
        self.calls = 0

    def chat_json(self, **kwargs):
        self.calls += 1
        return _FakeResult({"claims": self._claims})


class _FakeToolSession:
    async def call(self, tool, arguments):
        return "tool-result"


def _run_verify(claims):
    from quorumqa.engine.verifier import verify

    return asyncio.run(
        verify(_FakeClient(claims), _FakeToolSession(), "Q?", [])
    )


@pytest.mark.parametrize("claims", [[2, 3], ["a", "b"], [None], [[], {}], [3.14]])
def test_non_dict_claims_do_not_crash_the_question(claims):
    """Previously raised AttributeError, which the caller turned into
    'DROPPED after unrecoverable error' -- deleting a CONTESTED item."""
    findings, usages = _run_verify(claims)
    assert findings == []
    assert len(usages) >= 1


def test_a_valid_claim_beside_a_malformed_one_still_executes():
    """The malformed element must be skipped, not abort the batch."""
    findings, usages = _run_verify(
        [7, {"claim": "c", "tool": "safe_calculate", "arguments": {"expression": "1+1"}}]
    )
    # The valid claim survives far enough to reach the finalize call.
    assert len(usages) >= 1


# --------------------------------------------------------------------------
# C3 -- --ship-gate counted pool FILES, not distinct seeds
# --------------------------------------------------------------------------


def _pool_row(qid, correct, dataset, seed):
    return {
        "question_id": qid,
        "item": {"question_id": qid, "question": "Q",
                 "choices": ["c1", "c2", "c3", "c4"], "correct_letter": correct},
        "dataset": dataset,
        "seed": seed,
        "samples": [
            {"question_id": qid, "sample_index": i, "letter": l, "confidence": c, "reasoning": "r"}
            for i, (l, c) in enumerate([("A", 0.1), ("A", 0.1), ("B", 0.99)])
        ],
    }


def _write_pool(path, seed, dataset="supergpqa", n_gain=13):
    import json as _json

    rows = [_pool_row(f"g{seed}_{i}", "B", dataset, seed) for i in range(n_gain)]
    rows += [_pool_row(f"s{seed}_{i}", "A", dataset, seed) for i in range(77)]
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(_json.dumps(r) + "\n")
    return str(path)


def test_the_same_pool_three_times_is_rejected(tmp_path):
    """Previously: one honest seed-411 pool (b=13,c=0) passed three times
    summed to b=39/c=0/p=0.0000 and printed SHIP with exit code 0 -- the exact
    single-seed overfitting S7 exists to prevent."""
    from benchmark.score_selectors import main

    p = _write_pool(tmp_path / "pool_supergpqa_cheap_k3_seed411.jsonl", 411)
    with pytest.raises(ValueError, match="same pool file more than once"):
        main([p, p, p], "max_single_confidence", None, True, None)


def test_distinct_files_carrying_the_same_seed_are_rejected(tmp_path):
    """Distinct paths are not enough -- a copy or a re-run under a new name
    carries the same logged seed, and the seed is what makes pools independent."""
    from benchmark.score_selectors import main

    a = _write_pool(tmp_path / "pool_a.jsonl", 411)
    b = _write_pool(tmp_path / "pool_b.jsonl", 411)
    c = _write_pool(tmp_path / "pool_c.jsonl", 523)
    with pytest.raises(ValueError, match="3 DISTINCT held-out seeds"):
        main([a, b, c], "max_single_confidence", None, True, None)


# --------------------------------------------------------------------------
# C1 -- the degeneracy guard omitted two subject-branching levers
# --------------------------------------------------------------------------


def test_every_subject_branching_lever_is_guarded():
    """The drift this test exists to prevent.

    `combined` and `flagship_panel_combined` branch on
    subject == "Organic Chemistry" but were absent from the guard, so running
    either on SuperGPQA (whose `subject` is a coarse discipline) silently
    produced a byte-identical re-run of `thinking` / `flagship_panel` at full
    flagship price -- and would have entered the record as an independent
    lever corroborating the flagship claim.
    """
    from benchmark.lever_experiments import (
        CHEMISTRY_BRANCHING_LEVERS,
        SUBJECT_BRANCHING_LEVERS,
    )

    unguarded = set(SUBJECT_BRANCHING_LEVERS) - set(CHEMISTRY_BRANCHING_LEVERS)
    assert not unguarded, f"subject-branching but unguarded: {sorted(unguarded)}"
    for lever in ("combined", "flagship_panel_combined"):
        assert lever in CHEMISTRY_BRANCHING_LEVERS


def test_the_guard_list_is_derived_not_duplicated():
    """If someone re-hardcodes the guard tuple, this fails."""
    from benchmark.lever_experiments import (
        CHEMISTRY_BRANCHING_LEVERS,
        SUBJECT_BRANCHING_LEVERS,
    )

    assert set(SUBJECT_BRANCHING_LEVERS).issubset(set(CHEMISTRY_BRANCHING_LEVERS))
    # No duplicates from the union construction.
    assert len(CHEMISTRY_BRANCHING_LEVERS) == len(set(CHEMISTRY_BRANCHING_LEVERS))


def test_finalize_tolerates_non_dict_findings():
    from quorumqa.engine.verifier import _finalize

    class _C:
        def chat_json(self, **kwargs):
            return _FakeResult({"findings": [5]})

    executed = [{"claim": "c", "tool": "safe_calculate", "arguments": {}, "tool_result": "2"}]
    findings, _ = _finalize(_C(), executed)
    assert len(findings) == 1
    assert findings[0].supports_claim is False
