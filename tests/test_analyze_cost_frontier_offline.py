"""Offline tests for benchmark/analyze_cost_frontier.py.

The frontier is the artifact most likely to be quoted out of context, so the
properties tested here are the ones that keep it honest: it must pair on
identical items, it must refuse a seed that lacks the reference arm, and a
RETIRED point estimate must never be allowed to sit on it or to dominate
anything.
"""

from __future__ import annotations

import json

import pytest

import benchmark.analyze_cost_frontier as cf
from benchmark.analyze_cost_frontier import REFERENCE, _record, analyze


def _row(wrapper: str, qid: str, correct: bool, tokens: int) -> dict:
    return {
        wrapper: {
            "item": {"question_id": qid},
            "correct": correct,
            "calls": [{"input_tokens": tokens, "output_tokens": 0}],
        }
    }


def _write(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _install(tmp_path, monkeypatch, arms_spec):
    monkeypatch.setattr(cf, "RESULTS", tmp_path)
    monkeypatch.setitem(cf.ARMS, "testds", arms_spec)


# ---------------------------------------------------------------------------
# Row-wrapper tolerance -- this repo writes three different shapes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("wrapper", ["engine", "baseline", "result"])
def test_record_tolerates_every_wrapper_this_repo_writes(wrapper):
    rec = _record(_row(wrapper, "q1", True, 100))
    assert rec is not None and rec["correct"] is True


def test_record_returns_none_on_an_unknown_shape():
    assert _record({"something_else": {"correct": True}}) is None


# ---------------------------------------------------------------------------
# Pairing on identical items -- the whole point of the script
# ---------------------------------------------------------------------------


def test_arms_are_compared_only_on_shared_items(tmp_path, monkeypatch):
    """Arm X ran 100 items, the reference only 80. The comparison must use 80,
    not flatter X with 20 items the reference never saw."""
    _install(tmp_path, monkeypatch, {
        REFERENCE: ("ref_seed{s}.jsonl", (1,)),
        "arm_x": ("x_seed{s}.jsonl", (1,)),
    })
    _write(tmp_path / "ref_seed1.jsonl", [_row("baseline", f"q{i}", True, 1000) for i in range(80)])
    _write(tmp_path / "x_seed1.jsonl", [_row("engine", f"q{i}", True, 5000) for i in range(100)])

    r = analyze("testds")
    assert r["seeds_used"][0]["n_shared"] == 80
    assert r["points"]["arm_x"]["n"] == 80
    assert r["points"][REFERENCE]["n"] == 80


def test_a_seed_without_the_reference_arm_is_skipped_not_pooled(tmp_path, monkeypatch):
    """Silently pooling such a seed would reintroduce the cross-seed error this
    script exists to prevent."""
    _install(tmp_path, monkeypatch, {
        REFERENCE: ("ref_seed{s}.jsonl", (1, 2)),
        "arm_x": ("x_seed{s}.jsonl", (1, 2)),
    })
    _write(tmp_path / "ref_seed1.jsonl", [_row("baseline", f"q{i}", True, 1000) for i in range(10)])
    _write(tmp_path / "x_seed1.jsonl", [_row("engine", f"q{i}", True, 5000) for i in range(10)])
    # seed 2 has arm_x only.
    _write(tmp_path / "x_seed2.jsonl", [_row("engine", f"z{i}", True, 5000) for i in range(10)])

    r = analyze("testds")
    assert [s["seed"] for s in r["seeds_used"]] == [1]
    assert r["seeds_missing"][0]["seed"] == 2
    assert r["points"]["arm_x"]["n"] == 10  # seed 2 contributed nothing


# ---------------------------------------------------------------------------
# Paired statistics
# ---------------------------------------------------------------------------


def test_beats_reference_requires_both_a_positive_net_and_significance(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, {
        REFERENCE: ("ref_seed{s}.jsonl", (1,)),
        "arm_x": ("x_seed{s}.jsonl", (1,)),
    })
    # 6 items arm_x wins, 0 the reference wins -> net +6, p=0.015625.
    ref, x = [], []
    for i in range(20):
        ref_ok = i >= 6
        ref.append(_row("baseline", f"q{i}", ref_ok, 1000))
        x.append(_row("engine", f"q{i}", True, 5000))
    _write(tmp_path / "ref_seed1.jsonl", ref)
    _write(tmp_path / "x_seed1.jsonl", x)

    e = analyze("testds")["points"]["arm_x"]
    assert (e["b"], e["c"], e["net"]) == (6, 0, 6)
    assert e["p_one_sided"] == pytest.approx(0.015625)
    assert e["beats_reference"] is True


def test_a_positive_but_insignificant_net_does_not_beat_the_reference(tmp_path, monkeypatch):
    """The TB-1 shape: net +1 at p=0.50 is not a win and must not be reported
    as one."""
    _install(tmp_path, monkeypatch, {
        REFERENCE: ("ref_seed{s}.jsonl", (1,)),
        "arm_x": ("x_seed{s}.jsonl", (1,)),
    })
    ref, x = [], []
    for i in range(20):
        # 4 discordant each way plus one extra for arm_x -> net +1.
        ref.append(_row("baseline", f"q{i}", i >= 5, 1000))
        x.append(_row("engine", f"q{i}", not (5 <= i < 9), 5000))
    _write(tmp_path / "ref_seed1.jsonl", ref)
    _write(tmp_path / "x_seed1.jsonl", x)

    e = analyze("testds")["points"]["arm_x"]
    assert e["net"] > 0
    assert e["p_one_sided"] > 0.05
    assert e["beats_reference"] is False


# ---------------------------------------------------------------------------
# Retired point estimates
# ---------------------------------------------------------------------------


def test_a_retired_config_can_never_sit_on_the_frontier(tmp_path, monkeypatch):
    """qwen3.8_solo's retracted 93.6% was found ON a published frontier. Even
    if a retired arm scores best on both axes, it must be flagged retired and
    excluded from the frontier."""
    monkeypatch.setitem(cf.RETIRED_POINT_ESTIMATES, "arm_retired", "retired for testing")
    _install(tmp_path, monkeypatch, {
        REFERENCE: ("ref_seed{s}.jsonl", (1,)),
        "arm_retired": ("ret_seed{s}.jsonl", (1,)),
    })
    _write(tmp_path / "ref_seed1.jsonl", [_row("baseline", f"q{i}", i < 15, 5000) for i in range(20)])
    # Retired arm: better accuracy AND cheaper -- would dominate on both axes.
    _write(tmp_path / "ret_seed1.jsonl", [_row("engine", f"q{i}", True, 1000) for i in range(20)])

    r = analyze("testds")
    assert r["retired_excluded"] == ["arm_retired"]
    assert r["points"]["arm_retired"]["retired"] is True
    assert r["points"]["arm_retired"]["on_frontier"] is False


def test_a_retired_config_cannot_dominate_a_live_one(tmp_path, monkeypatch):
    """The stronger property: a retired point must not knock a legitimate
    configuration off the frontier either."""
    monkeypatch.setitem(cf.RETIRED_POINT_ESTIMATES, "arm_retired", "retired for testing")
    _install(tmp_path, monkeypatch, {
        REFERENCE: ("ref_seed{s}.jsonl", (1,)),
        "arm_retired": ("ret_seed{s}.jsonl", (1,)),
    })
    _write(tmp_path / "ref_seed1.jsonl", [_row("baseline", f"q{i}", i < 15, 5000) for i in range(20)])
    _write(tmp_path / "ret_seed1.jsonl", [_row("engine", f"q{i}", True, 1000) for i in range(20)])

    r = analyze("testds")
    assert r["points"][REFERENCE]["dominated_by"] == []
    assert r["points"][REFERENCE]["on_frontier"] is True


def test_the_real_qwen38_solo_is_declared_retired():
    from benchmark.figure_data import RETIRED_POINT_ESTIMATES

    assert "qwen3.8_solo" in RETIRED_POINT_ESTIMATES


# ---------------------------------------------------------------------------
# Efficiency arithmetic
# ---------------------------------------------------------------------------


def test_accuracy_per_1k_tokens_is_computed_correctly(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, {
        REFERENCE: ("ref_seed{s}.jsonl", (1,)),
        "arm_x": ("x_seed{s}.jsonl", (1,)),
    })
    _write(tmp_path / "ref_seed1.jsonl", [_row("baseline", f"q{i}", True, 2000) for i in range(10)])
    _write(tmp_path / "x_seed1.jsonl", [_row("engine", f"q{i}", True, 10000) for i in range(10)])

    p = analyze("testds")["points"]
    assert p[REFERENCE]["accuracy_per_1k_tokens"] == pytest.approx(0.5)   # 1.0 / 2k
    assert p["arm_x"]["accuracy_per_1k_tokens"] == pytest.approx(0.1)     # 1.0 / 10k
    # Equal accuracy, 5x the cost -> dominated.
    assert p["arm_x"]["on_frontier"] is False
    assert REFERENCE in p["arm_x"]["dominated_by"]
