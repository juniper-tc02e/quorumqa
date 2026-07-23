"""Offline tests for the open-answer math equivalence grader.

Covers the answer shapes MATH-500 actually uses and, critically, the
fail-closed contract: an answer the grader cannot parse must return False,
never True, so a lenient parse can never inflate measured accuracy.
"""

import pytest

from benchmark.math_grade import grade, _normalize, _as_seq, _as_multiset


# (gold, pred, expected) -- equivalences a good grader must accept
EQUIVALENT = [
    (r"\frac{1}{2}", r"0.5"),
    (r"\frac{1}{2}", r"\dfrac{1}{2}"),
    (r"\frac{3}{4}", r"0.75"),
    (r"18+2\pi", r"2\pi + 18"),
    (r"2\sqrt{5}", r"\sqrt{20}"),
    (r"12\pi", r"12 \pi"),
    (r"x^2+2x+1", r"(x+1)^2"),
    (r"7", r"7.0"),
    (r"145^\circ", r"145"),
    (r"\boxed{\frac{1}{2}}", r"\frac{1}{2}"),
    (r"(6,31,-1)", r"(6, 31, -1)"),
    (r"1,-2", r"-2,1"),            # multi-valued, order-insensitive
    (r"\frac{-3}{4}", r"-\frac{3}{4}"),
    (r"50\%", r"50"),
    # --- real MATH-500 L5 shapes that the first grader version got WRONG
    #     (found via the open-answer pilot; these are regression guards) ---
    (r"(3,4]", r"(3, 4]"),                                        # interval, whitespace
    (r"\left(\frac{3}{5},\frac{8}{3}\right]", r"\left(\frac{3}{5}, \frac{8}{3}\right]"),
    (r"1 \pm \sqrt{19}", r"1 + \sqrt{19}, 1 - \sqrt{19}"),        # pm vs enumerated
    (r"\{1\pm\sqrt{5},-2\}", r"\{-2, 1 - \sqrt{5}, 1 + \sqrt{5}\}"),  # set, pm, reorder
    (r"3 \pm 2\sqrt{2}", r"3 - 2\sqrt{2}, 3 + 2\sqrt{2}"),        # pm, 2 values, reorder
]

# (gold, pred) -- genuinely different answers the grader must reject
NON_EQUIVALENT = [
    (r"\frac{1}{2}", r"\frac{1}{3}"),
    (r"7", r"8"),
    (r"2\sqrt{5}", r"\sqrt{21}"),
    (r"(6,31,-1)", r"(6,31,1)"),
    (r"1,-2", r"1,2"),
    (r"x^2+2x+1", r"x^2+2x+2"),
    (r"12\pi", r"11\pi"),
    # brackets are significant: interval != interval with different endpoints
    (r"(3,4]", r"[3,4]"),                       # bracket-type mismatch
    (r"(3,4]", r"(3,4)"),                       # bracket-type mismatch
    (r"(1,2)", r"(2,1)"),                       # ordered tuple, order matters
    # a 2-value pm answer must NOT equal a 4-value enumeration
    (r"3 \pm 2\sqrt{2}", r"3 + 2\sqrt{2}, 3 - 2\sqrt{2}, -3 + 2\sqrt{2}, -3 - 2\sqrt{2}"),
]


@pytest.mark.parametrize("gold,pred", EQUIVALENT)
def test_accepts_equivalent(gold, pred):
    assert grade(gold, pred) is True, f"{gold!r} should equal {pred!r}"


@pytest.mark.parametrize("gold,pred", NON_EQUIVALENT)
def test_rejects_non_equivalent(gold, pred):
    assert grade(gold, pred) is False, f"{gold!r} should NOT equal {pred!r}"


def test_symmetry():
    # Equivalence must not depend on argument order.
    for gold, pred in EQUIVALENT:
        assert grade(gold, pred) == grade(pred, gold), f"asymmetric on {gold!r}/{pred!r}"


def test_fails_closed_on_garbage():
    # Unparseable / empty inputs must return False, never True.
    assert grade("", "") is False
    assert grade(None, "5") is False
    assert grade("5", None) is False
    assert grade(r"\frac{1}{2}", "not a number") is False
    assert grade("\\begin{pmatrix}1&2\\end{pmatrix}", "banana") is False


def test_identical_strings_short_circuit():
    assert grade("42", "42") is True
    assert grade(r"\frac{7}{9}", r"\frac{7}{9}") is True


def test_normalize_strips_decorations():
    assert _normalize(r"\boxed{42}") == "42"
    assert _normalize(r"$x = 5$") == "5"
    assert _normalize(r"145^\circ") == "145"
    assert _normalize(r"\$32,\!348") in ("32348", "32,348".replace(",", ""))


def test_as_seq_and_as_multiset():
    # bracketed ordered sequence (tuple / interval)
    assert _as_seq("(6,31,-1)") == ("(", ")", ["6", "31", "-1"])
    assert _as_seq("(3,4]") == ("(", "]", ["3", "4"])
    assert _as_seq("5") is None            # scalar
    assert _as_seq(r"\{1,2\}") is None     # set, not a bracketed seq
    # order-insensitive set / multi-valued
    assert _as_multiset("1,-2") == ["1", "-2"]
    assert _as_multiset(r"\{-2, 3\}") == ["-2", "3"]
    assert _as_multiset("(3,4]") is None   # bracketed seq is not a set
    assert _as_multiset("5") is None       # scalar
    # \pm expands to two values
    assert sorted(_as_multiset(r"1 \pm \sqrt{19}")) == sorted([r"1 + \sqrt{19}", r"1 - \sqrt{19}"])
