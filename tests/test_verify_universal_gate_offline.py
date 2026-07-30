"""Pins universal_gate's live seed-1001 result against its committed file.

The claim: escalating every unanimous GPQA panel (instead of the shipped
`if unanimous: return`) nets +9 items (78.9% -> 88.9%), one-sided exact McNemar
p=0.00195 -- clears the repo bar (net>=+5 at one seed, p<0.05) on its own.

Also pins the mechanism (every unanimous panel escalated, no split panel
double-escalated) and the honest report that the pre-registered prediction
(conversion BELOW the 47.6% pooled estimate) did not hold -- this run converted
at 75.0%, above it.
"""

from __future__ import annotations

import pytest

from benchmark.verify_universal_gate import verify


@pytest.fixture(scope="module")
def r():
    return verify()


def test_seed_1001_present(r):
    assert 1001 in r["per_seed"]


def test_mechanism_is_clean(r):
    """Every unanimous panel escalated; no split panel was double-counted."""
    s = r["per_seed"][1001]
    assert s["n"] == 90
    assert s["unanimous_count"] == 48
    assert s["unanimous_escalated"] == 48
    assert s["non_unanimous_escalated"] == 42
    assert s["mechanism_clean"] is True


def test_recovery_and_breakage(r):
    s = r["per_seed"][1001]
    assert s["unanimous_wrong"] == 12
    assert s["recovered"] == 9
    assert s["recovery_rate"] == pytest.approx(0.75, abs=1e-9)
    assert s["unanimous_right"] == 36
    assert s["broken"] == 0
    assert s["breakage_rate"] == pytest.approx(0.0, abs=1e-9)


def test_paired_accuracy_and_significance(r):
    s = r["per_seed"][1001]
    assert s["shipped_correct"] == 71
    assert s["gated_correct"] == 80
    assert s["b"] == 9
    assert s["c"] == 0
    assert s["net"] == 9
    assert s["p_one_sided"] == pytest.approx(0.00195, abs=1e-4)
    assert s["p_one_sided"] < 0.05


def test_clears_the_single_seed_bar(r):
    """net>=+5 at one seed with p<0.05 -- the repo's own bar, satisfied here
    without needing the pooled 2-of-3-seed branch."""
    s = r["per_seed"][1001]
    assert s["net"] >= 5
    assert s["p_one_sided"] < 0.05


def test_conversion_exceeded_the_pre_registered_prediction(r):
    """Honesty guard: the pre-registered prediction was that a wider gate
    would convert BELOW the 47.6% pooled estimate (selection bias in existing
    doubt-gates). It did not -- this seed converted at 75.0%, above it. A
    future edit must not quietly flip this back to 'as predicted'."""
    from benchmark.verify_universal_gate import PRIOR_POOLED_RECOVERY_PCT

    s = r["per_seed"][1001]
    recovery_pct = 100 * s["recovery_rate"]
    assert recovery_pct > PRIOR_POOLED_RECOVERY_PCT
