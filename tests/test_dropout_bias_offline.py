"""Offline tests for the qwen3.8-solo survivorship-bias analysis.

The Fisher exact implementation is hand-rolled to avoid adding scipy to the
runtime dependency set. It is validated against scipy where scipy is available
(dev-only), and pinned by hand-computed fixtures where it is not -- the same
belt-and-braces pattern used for ifeval_verify against Google's reference.

Regression guard: the first implementation computed the bottom-right cell as
`d - (x - a)` instead of `(c + d) - z`. Those are mirror images, so one tail of
the null distribution was silently truncated and the p-value came back at
exactly half its true value on asymmetric tables. The observed table for our
headline claim happened to be unaffected, which is precisely why this needs a
test rather than a spot check.
"""

from __future__ import annotations

import random

import pytest

from benchmark.analyze_dropout_bias import analyze, fisher_exact_two_sided

# Hand-checked / scipy-derived reference values. The two marked TRUNCATION are
# the tables the original buggy implementation halved.
REFERENCE = [
    ((6, 3, 67, 2), 0.00975241),   # the headline table: slow vs fast survivors
    ((1, 9, 11, 3), 0.00275946),   # TRUNCATION: bug returned 0.00137973
    ((0, 5, 4, 1), 0.04761905),    # TRUNCATION: bug returned 0.02380952
    ((3, 1, 1, 3), 0.48571429),
    ((10, 0, 0, 10), 0.00001083),
    ((2, 2, 2, 2), 1.00000000),
    ((5, 0, 1, 4), 0.04761905),
]


@pytest.mark.parametrize("table,expected", REFERENCE)
def test_fisher_matches_reference(table, expected):
    assert fisher_exact_two_sided(*table) == pytest.approx(expected, abs=1e-8)


def test_fisher_is_symmetric_under_transpose():
    """p must not depend on which margin is called 'rows'."""
    random.seed(11)
    for _ in range(200):
        a, b, c, d = (random.randint(0, 12) for _ in range(4))
        if not (a + b and c + d and a + c and b + d):
            continue
        assert fisher_exact_two_sided(a, b, c, d) == pytest.approx(
            fisher_exact_two_sided(a, c, b, d), abs=1e-12
        )


def test_fisher_never_exceeds_one():
    random.seed(12)
    for _ in range(200):
        a, b, c, d = (random.randint(0, 12) for _ in range(4))
        if not (a + b and c + d and a + c and b + d):
            continue
        p = fisher_exact_two_sided(a, b, c, d)
        assert 0.0 < p <= 1.0 + 1e-12


def test_fisher_matches_scipy_if_available():
    scipy_stats = pytest.importorskip("scipy.stats")
    random.seed(13)
    for _ in range(300):
        a, b, c, d = (random.randint(0, 14) for _ in range(4))
        if not (a + b and c + d and a + c and b + d):
            continue
        expected = scipy_stats.fisher_exact([[a, b], [c, d]])[1]
        assert fisher_exact_two_sided(a, b, c, d) == pytest.approx(
            expected, abs=1e-9
        ), f"table {(a, b, c, d)}"


def test_analysis_reproduces_committed_numbers():
    """Pins the finding itself against the committed result file."""
    r = analyze()
    assert r["survivors"] == 78
    assert r["dropped"] == 12
    assert r["correct"] == 73
    assert r["survivor_rate"] == pytest.approx(93.59, abs=0.01)
    # The bias signal.
    assert (r["slow_n"], r["fast_n"]) == (9, 69)
    assert r["slow_rate"] == pytest.approx(66.67, abs=0.01)
    assert r["fast_rate"] == pytest.approx(97.10, abs=0.01)
    assert r["fisher_p"] == pytest.approx(0.00975, abs=1e-5)
    assert r["fisher_p"] < 0.05
    # Hard imputation bounds, and the flip threshold for the society claim.
    assert r["bar_all_wrong"] == pytest.approx(81.1, abs=0.05)
    assert r["bar_all_right"] == pytest.approx(94.4, abs=0.05)
    assert r["flip_threshold"] == pytest.approx(73.4, abs=0.05)
    # The load-bearing inequality: the slowest survivors fall below the
    # threshold at which the bar drops under our society's 90.9%.
    assert r["slow_rate"] < r["flip_threshold"]


def test_society_lies_inside_the_hard_bounds():
    """The claim 'society is 2.7pt under the bar' is not identifiable."""
    r = analyze()
    assert r["bar_all_wrong"] < 90.9 < r["bar_all_right"]
