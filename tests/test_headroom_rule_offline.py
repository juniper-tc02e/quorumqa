"""Offline tests for benchmark/analyze_headroom_rule.py.

The analysis exists to retire one word. README.md said the unanimous-wrong rate
"predicts" whether orchestration pays; it bounds it and does not predict it, and
the difference decides whether a reader can use the number to plan work.

These tests use synthetic frames wherever the property is about the ANALYSIS
rather than about our data, so they prove the logic is right rather than
re-asserting the result we happened to get. The two that read the real CSV are
marked as such.
"""

from __future__ import annotations

import pandas as pd
import pytest

from benchmark.analyze_headroom_rule import PREDICTIVE_P_MAX, SOURCE, analyze


def _frame(rows):
    """rows: (benchmark, rate, delta, verdict, seeds)"""
    return pd.DataFrame(rows, columns=[
        "benchmark", "unanimous_wrong_rate_pct", "best_lever_delta_pp",
        "best_lever_verdict", "best_lever_seeds",
    ])


def _write(tmp_path, rows):
    p = tmp_path / "f05.csv"
    _frame(rows).to_csv(p, index=False)
    return p


# ---------------------------------------------------------------------------
# The bound and the prediction are separate verdicts
# ---------------------------------------------------------------------------


def test_a_perfect_predictor_is_reported_as_predictive(tmp_path):
    """Guard against a verdict that says NOT SUPPORTED no matter what. If the
    relationship were real, this analysis must be able to say so."""
    rows = [(f"b{i}", r, r / 2, "validated", 3)
            for i, r in enumerate([2, 6, 10, 14, 18, 22, 26])]
    a = analyze(_write(tmp_path, rows))
    assert a["pearson"]["p"] < PREDICTIVE_P_MAX
    assert a["verdict"]["prediction"] == "SUPPORTED"
    assert a["verdict"]["bound"] == "SUPPORTED"


def test_noise_is_reported_as_not_predictive(tmp_path):
    rows = [("a", 22.0, -6.0, "screen", 1), ("b", 23.0, 4.1, "validated", 3),
            ("c", 14.0, -2.0, "screen", 1), ("d", 4.0, 2.0, "inert", 1),
            ("e", 1.7, 0.0, "inert", 1)]
    a = analyze(_write(tmp_path, rows))
    assert a["verdict"]["prediction"] == "NOT SUPPORTED"


def test_the_bound_can_be_violated_and_is_then_reported(tmp_path):
    """The bound is an arithmetic necessity given how the rate is defined, so a
    violation means the INPUTS are wrong -- a mis-scoped rate, or a delta
    measured against a different comparator. It must surface, not pass quietly.
    """
    rows = [("a", 5.0, 12.0, "screen", 1), ("b", 10.0, 1.0, "screen", 1),
            ("c", 20.0, 2.0, "screen", 1)]
    a = analyze(_write(tmp_path, rows))
    assert a["bound_holds_on_all"] is False
    assert a["verdict"]["bound"] == "VIOLATED"


def test_a_predictive_correlation_does_not_excuse_a_violated_bound(tmp_path):
    """The two verdicts are independent; a strong correlation must not paper
    over inputs that are arithmetically impossible."""
    rows = [(f"b{i}", r, r * 3, "validated", 3) for i, r in enumerate([2, 6, 10, 14, 18])]
    a = analyze(_write(tmp_path, rows))
    assert a["verdict"]["prediction"] == "SUPPORTED"
    assert a["verdict"]["bound"] == "VIOLATED"


# ---------------------------------------------------------------------------
# Sign disagreement -- the specific thing that makes our data uninformative
# ---------------------------------------------------------------------------


def test_sign_disagreement_between_the_two_correlations_is_flagged(tmp_path):
    """Pearson and Spearman disagreeing on direction is the clearest possible
    signal that neither is measuring anything. It gets its own field so the
    write-up cannot quote whichever one it prefers."""
    rows = [("a", 22.0, -6.0, "screen", 1), ("b", 23.0, 4.1, "validated", 3),
            ("c", 14.0, -2.0, "screen", 1), ("d", 4.0, 2.0, "inert", 1),
            ("e", 1.7, 0.0, "inert", 1)]
    a = analyze(_write(tmp_path, rows))
    assert a["correlation_signs_agree"] is False
    assert (a["pearson"]["r"] > 0) != (a["spearman"]["rho"] > 0)


def test_near_identical_headroom_pairs_are_surfaced(tmp_path):
    rows = [("lex", 22.0, -6.0, "screen", 1), ("sg", 23.0, 4.1, "validated", 3),
            ("low", 4.0, 2.0, "inert", 1)]
    a = analyze(_write(tmp_path, rows))
    names = {e["benchmark"] for e in a["near_identical_headroom"]}
    assert names == {"lex", "sg"}, "only the >=20% headroom rows belong here"
    deltas = [e["delta_pp"] for e in a["near_identical_headroom"]]
    assert min(deltas) < 0 < max(deltas), "the point is that they disagree in sign"


def test_negative_conversion_is_preserved_not_absolute_valued(tmp_path):
    """A lever that moved accuracy the WRONG way converted a negative share of
    the headroom. Reporting |x| here would turn a loss into a win."""
    rows = [("a", 20.0, -10.0, "screen", 1), ("b", 20.0, 10.0, "screen", 1)]
    a = analyze(_write(tmp_path, rows))
    assert a["headroom_converted_pct"]["min"] == -50.0
    assert a["headroom_converted_pct"]["max"] == 50.0


def test_constant_input_yields_valid_json_not_nan(tmp_path):
    """scipy returns NaN when a column is constant, and NaN is not valid JSON --
    the artifact would be unreadable by anything that consumes it. Found by the
    fixture above, which happens to hold the rate constant.
    """
    import json
    import math

    rows = [("a", 20.0, -10.0, "screen", 1), ("b", 20.0, 10.0, "screen", 1)]
    a = analyze(_write(tmp_path, rows))
    assert a["degenerate_input"] is True
    assert not math.isnan(a["pearson"]["r"])
    assert not math.isnan(a["spearman"]["rho"])
    assert a["verdict"]["prediction"] == "NOT SUPPORTED", (
        "constant input is the ABSENCE of a relationship, not evidence of one"
    )
    json.loads(json.dumps(a))  # would raise on NaN


def test_real_data_is_not_degenerate():
    if not SOURCE.exists():
        pytest.skip("F05 CSV not committed")
    assert analyze()["degenerate_input"] is False


# ---------------------------------------------------------------------------
# Against the real committed data
# ---------------------------------------------------------------------------


def test_our_actual_data_does_not_support_the_prediction_claim():
    if not SOURCE.exists():
        pytest.skip("F05 CSV not committed")
    a = analyze()
    assert a["verdict"]["bound"] == "SUPPORTED"
    assert a["verdict"]["prediction"] == "NOT SUPPORTED"
    assert a["correlation_signs_agree"] is False
    assert a["n_validated_3seed"] == 1, (
        "only SuperGPQA-hard is validated at 3 seeds; if that changes, revisit "
        "whether a rule can now be fitted"
    )


def test_the_readme_no_longer_says_the_rate_predicts():
    readme = (SOURCE.parent.parent.parent / "README.md").read_text(encoding="utf-8")
    assert "unanimous-wrong rate) **bounds**" in readme
    assert "rate) predicts whether" not in readme, (
        "README reverted to claiming the rate predicts the outcome; r=-0.216 "
        "(p=0.73) and rho=+0.100 (p=0.87) do not support it"
    )
