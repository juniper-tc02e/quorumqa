"""Offline tests for benchmark/escalation_policies.py (docs/experiment-spec-
book.md section 2, S3) -- pure functions over vote vectors, no API calls, no
cost. Covers:

  (a) each trigger family's math on constructed vote vectors, including the
      prompt's own worked example (15 seats, 8/4/3 split -> margin=4,
      top_share=8/15, entropy computed against a hand-derived value).
  (b) unanimity degenerates at large N: the escalation rate under a fixed
      per-seat error probability rises sharply as N grows, because the
      chance that ALL N seats land on the identical letter shrinks with N.
  (c) policy_grid() enumerates the full pre-registered sweep (18 combos:
      1 unanimity + 6 top_cluster_share + 4 margin_abs + 3 margin_norm + 4
      entropy).
  (d) evaluate_policy_over_items: escalation_rate + recall of
      plurality-wrong items, including the zero-wrong-items recall=None
      edge case.
  (e) a light integration check against benchmark/analyze_panel_scaling.py's
      escalation_sweep_at_n, proving the two modules compose the way
      analyze_panel_scaling.py relies on.
"""

import math
import random

import pytest

import benchmark.escalation_policies as ep


# ---------------------------------------------------------------------------
# (a) per-family math, including the prompt's 15-seat 8/4/3 worked example
# ---------------------------------------------------------------------------


def _votes_8_4_3():
    # 8 "A", 4 "B", 3 "C" -- sums to 15.
    return ["A"] * 8 + ["B"] * 4 + ["C"] * 3


def test_top_cluster_share_worked_example():
    assert ep.top_cluster_share(_votes_8_4_3()) == pytest.approx(8 / 15)


def test_plurality_margin_absolute_worked_example():
    assert ep.plurality_margin(_votes_8_4_3(), normalized=False) == 4.0


def test_plurality_margin_normalized_worked_example():
    assert ep.plurality_margin(_votes_8_4_3(), normalized=True) == pytest.approx(4 / 15)


def test_normalized_vote_entropy_worked_example():
    votes = _votes_8_4_3()
    n = 15
    probs = [8 / n, 4 / n, 3 / n]
    h = -sum(p * math.log(p) for p in probs)
    expected = h / math.log(4)
    assert ep.normalized_vote_entropy(votes, alphabet="ABCD") == pytest.approx(expected)
    assert 0.0 < expected < 1.0


def test_unanimous_votes_have_zero_entropy_and_full_share_and_full_margin():
    votes = ["A"] * 7
    assert ep.top_cluster_share(votes) == 1.0
    assert ep.plurality_margin(votes) == 7.0
    assert ep.normalized_vote_entropy(votes) == pytest.approx(0.0)
    assert ep.trigger_unanimity(votes) is False


def test_maximally_split_votes_across_all_four_letters_approach_full_entropy():
    votes = ["A", "B", "C", "D"] * 4  # 16 seats, perfectly even across k=4
    assert ep.normalized_vote_entropy(votes, alphabet="ABCD") == pytest.approx(1.0, abs=1e-9)


def test_plurality_margin_zero_runner_up_when_only_one_cluster_present():
    # A single unanimous cluster has no "runner-up" -- margin degenerates to
    # top_count - 0, i.e. the full seat count.
    votes = ["D"] * 5
    assert ep.plurality_margin(votes) == 5.0


def test_plurality_letter_matches_documented_tie_break():
    # Counter.most_common(1) breaks ties by first-inserted letter among the
    # max-count group -- same convention as benchmark.lever_experiments._plurality.
    votes = ["A", "B", "C"]  # 3-way tie, "A" appears first
    letter, unanimous = ep.plurality_letter(votes)
    assert letter == "A"
    assert unanimous is False


# ---------------------------------------------------------------------------
# trigger predicates: escalate iff the condition holds
# ---------------------------------------------------------------------------


def test_trigger_unanimity_true_iff_not_all_agree():
    assert ep.trigger_unanimity(["A", "A", "A"]) is False
    assert ep.trigger_unanimity(["A", "A", "B"]) is True
    assert ep.trigger_unanimity([]) is False  # degenerate, never crashes


@pytest.mark.parametrize("theta,expected", [
    (0.5, False),   # 8/15 ~= 0.533 >= 0.5 -> NOT escalated
    (0.55, True),   # 8/15 ~= 0.533 < 0.55 -> escalated
    (1.0, True),    # not unanimous -> below 1.0
])
def test_trigger_top_cluster_share(theta, expected):
    assert ep.trigger_top_cluster_share(_votes_8_4_3(), theta) is expected


@pytest.mark.parametrize("m,expected", [
    (3, False),  # margin=4, not < 3
    (4, False),  # margin=4, not < 4
    (5, True),   # margin=4 < 5
])
def test_trigger_plurality_margin_absolute(m, expected):
    assert ep.trigger_plurality_margin(_votes_8_4_3(), m, normalized=False) is expected


def test_trigger_plurality_margin_normalized():
    # margin/N = 4/15 ~= 0.267
    assert ep.trigger_plurality_margin(_votes_8_4_3(), 0.2, normalized=True) is False
    assert ep.trigger_plurality_margin(_votes_8_4_3(), 0.3, normalized=True) is True


def test_trigger_normalized_vote_entropy():
    entropy = ep.normalized_vote_entropy(_votes_8_4_3())
    assert ep.trigger_normalized_vote_entropy(_votes_8_4_3(), entropy - 0.01) is True
    assert ep.trigger_normalized_vote_entropy(_votes_8_4_3(), entropy + 0.01) is False


def test_evaluate_trigger_dispatches_by_policy_name():
    votes = _votes_8_4_3()
    assert ep.evaluate_trigger(ep.POLICY_UNANIMITY, None, votes) == ep.trigger_unanimity(votes)
    assert ep.evaluate_trigger(ep.POLICY_TOP_CLUSTER_SHARE, 0.6, votes) == ep.trigger_top_cluster_share(votes, 0.6)
    assert ep.evaluate_trigger(ep.POLICY_PLURALITY_MARGIN_ABS, 2, votes) == ep.trigger_plurality_margin(votes, 2, normalized=False)
    assert ep.evaluate_trigger(ep.POLICY_PLURALITY_MARGIN_NORM, 0.2, votes) == ep.trigger_plurality_margin(votes, 0.2, normalized=True)
    assert ep.evaluate_trigger(ep.POLICY_NORMALIZED_VOTE_ENTROPY, 0.5, votes) == ep.trigger_normalized_vote_entropy(votes, 0.5)
    with pytest.raises(ValueError):
        ep.evaluate_trigger("not-a-real-policy", None, votes)


# ---------------------------------------------------------------------------
# (b) unanimity degenerates at large N
# ---------------------------------------------------------------------------


def test_unanimity_escalation_rate_rises_with_n_at_fixed_per_seat_error_rate():
    rng = random.Random(1234)
    per_seat_correct_prob = 0.85  # each seat independently right 85% of the time

    def escalation_rate_at_n(n, n_items=400):
        escalated = 0
        for _ in range(n_items):
            votes = ["X" if rng.random() < per_seat_correct_prob else "Y" for _ in range(n)]
            if ep.trigger_unanimity(votes):
                escalated += 1
        return escalated / n_items

    rate_at_3 = escalation_rate_at_n(3)
    rate_at_15 = escalation_rate_at_n(15)
    # At N=3, P(all agree) = p^3 + (1-p)^3 is still fairly high; at N=15 the
    # chance all 15 independent seats land on the same letter is much lower,
    # so the unanimity trigger fires far more often -- "degenerates toward
    # always escalate" as N grows.
    assert rate_at_15 > rate_at_3
    assert rate_at_15 > 0.9  # near-certain escalation at N=15


def test_unanimity_exact_probability_matches_binomial_closed_form():
    # P(unanimous at N | per-seat correct prob p, binary outcome) =
    # p^N + (1-p)^N exactly -- verify the trigger's empirical rate converges
    # to this closed form, and that it shrinks as N grows from 3 to 15.
    p = 0.8
    exact_unanimous_n3 = p ** 3 + (1 - p) ** 3
    exact_unanimous_n15 = p ** 15 + (1 - p) ** 15
    assert exact_unanimous_n15 < exact_unanimous_n3

    rng = random.Random(99)
    n_items = 6000

    def empirical_unanimous_rate(n):
        agree = 0
        for _ in range(n_items):
            votes = ["X" if rng.random() < p else "Y" for _ in range(n)]
            if not ep.trigger_unanimity(votes):
                agree += 1
        return agree / n_items

    assert empirical_unanimous_rate(3) == pytest.approx(exact_unanimous_n3, abs=0.03)
    assert empirical_unanimous_rate(15) == pytest.approx(exact_unanimous_n15, abs=0.03)


# ---------------------------------------------------------------------------
# (c) policy_grid enumerates the full pre-registered sweep
# ---------------------------------------------------------------------------


def test_policy_grid_has_eighteen_combinations():
    grid = list(ep.policy_grid())
    assert len(grid) == 1 + 6 + 4 + 3 + 4 == 18
    policies_seen = {name for name, _ in grid}
    assert policies_seen == set(ep.ALL_POLICIES)


def test_policy_grid_thresholds_match_documented_values():
    grid = dict()
    for name, threshold in ep.policy_grid():
        grid.setdefault(name, []).append(threshold)
    assert grid[ep.POLICY_UNANIMITY] == [None]
    assert grid[ep.POLICY_TOP_CLUSTER_SHARE] == [0.55, 0.6, 0.7, 0.8, 0.9, 1.0]
    assert grid[ep.POLICY_PLURALITY_MARGIN_ABS] == [1, 2, 3, 4]
    assert grid[ep.POLICY_PLURALITY_MARGIN_NORM] == [0.1, 0.2, 0.3]
    assert grid[ep.POLICY_NORMALIZED_VOTE_ENTROPY] == [0.2, 0.4, 0.6, 0.8]


# ---------------------------------------------------------------------------
# (d) evaluate_policy_over_items: escalation rate + recall
# ---------------------------------------------------------------------------


def test_evaluate_policy_over_items_escalation_rate_and_recall():
    # 4 items: 2 unanimous-correct (never escalated by unanimity, and
    # correct so they can't be "wrong"), 1 unanimous-WRONG (never escalated
    # by unanimity despite being wrong -- unanimity structurally misses it),
    # 1 split-WRONG (escalated by unanimity, and it IS wrong).
    items = [
        (["A", "A", "A"], "A"),   # unanimous, correct
        (["B", "B", "B"], "B"),   # unanimous, correct
        (["C", "C", "C"], "D"),   # unanimous, WRONG -- unanimity can't catch this
        (["A", "A", "B"], "B"),   # split, plurality "A" is WRONG -- unanimity catches it
    ]
    stats = ep.evaluate_policy_over_items(ep.POLICY_UNANIMITY, None, items)
    assert stats["n_items"] == 4
    assert stats["n_wrong"] == 2  # the unanimous-wrong item + the split-wrong item
    assert stats["escalation_rate"] == pytest.approx(1 / 4)  # only the split item triggers
    assert stats["recall"] == pytest.approx(1 / 2)  # catches only 1 of the 2 wrong items


def test_evaluate_policy_over_items_recall_is_none_when_no_wrong_items():
    items = [(["A", "A", "A"], "A"), (["B", "B", "B"], "B")]
    stats = ep.evaluate_policy_over_items(ep.POLICY_UNANIMITY, None, items)
    assert stats["n_wrong"] == 0
    assert stats["recall"] is None
    assert stats["escalation_rate"] == 0.0


def test_evaluate_policy_over_items_empty_items():
    stats = ep.evaluate_policy_over_items(ep.POLICY_UNANIMITY, None, [])
    assert stats == {"escalation_rate": None, "recall": None, "n_items": 0, "n_wrong": 0}


def test_looser_top_cluster_share_threshold_never_has_lower_recall_than_a_tighter_one():
    # theta=1.0 (unanimity-equivalent) escalates a SUBSET of what a lower
    # theta escalates (a lower top_share bar is easier to trip) -- so
    # recall should be monotonically non-decreasing as theta rises.
    rng = random.Random(7)
    items = []
    for _ in range(200):
        n = 9
        gold = "A"
        top_count = rng.randint(3, 9)
        votes = ["A"] * top_count + ["B"] * (n - top_count)
        rng.shuffle(votes)
        items.append((votes, gold))

    recalls = []
    for theta in ep.TOP_CLUSTER_SHARE_GRID:
        stats = ep.evaluate_policy_over_items(ep.POLICY_TOP_CLUSTER_SHARE, theta, items)
        recalls.append(stats["recall"] or 0.0)
    assert recalls == sorted(recalls)


def test_sweep_all_policies_returns_one_row_per_grid_combination():
    items = [(_votes_8_4_3(), "A"), (["B"] * 15, "B")]
    rows = ep.sweep_all_policies(items)
    assert len(rows) == 18
    for row in rows:
        assert set(row.keys()) == {"policy", "threshold", "escalation_rate", "recall", "n_items", "n_wrong"}


# ---------------------------------------------------------------------------
# (e) integration with benchmark/analyze_panel_scaling.py
# ---------------------------------------------------------------------------


def test_analyze_panel_scaling_escalation_sweep_composes_with_escalation_policies():
    import benchmark.analyze_panel_scaling as aps

    rows = [
        {
            "engine": {"item": {"question_id": f"q{i}", "correct_letter": "B"}},
            "seat_answers": [
                {"seat_index": j, "letter": ("A" if j < 2 else "B"), "confidence": 0.7,
                 "procedure_or_lens": "solve_forward", "temperature": 0.3, "permutation": None}
                for j in range(3)
            ],
        }
        for i in range(5)
    ]
    table = aps.escalation_sweep_at_n(rows, 3)
    assert len(table) == 18
    unanimity_row = next(r for r in table if r["policy"] == ep.POLICY_UNANIMITY)
    # every item is a 2-1 split ("A","A","B") -> plurality "A" is wrong
    # (gold "B") and non-unanimous -> unanimity escalates every item.
    assert unanimity_row["escalation_rate"] == 1.0
    assert unanimity_row["recall"] == 1.0
    assert unanimity_row["n"] == 3
