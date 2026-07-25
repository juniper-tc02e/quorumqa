"""S3 (docs/experiment-spec-book.md section 2, S3): escalation-policy
trigger families as a function of N, replayed FREE against an already-
harvested diversified_panel/cycled_panel vote vector -- no API calls, no
cost. This module is pure -- every function takes a plain list of per-seat
LETTERS (e.g. ["A", "A", "B"]) and/or a threshold and returns a bool or a
float. It knows nothing about JSONL rows, GPQAItem, or QuestionResult; the
caller (benchmark/analyze_panel_scaling.py) is responsible for extracting
vote vectors from a harvest file (via nested-prefix subsampling for each N)
and for pairing each vote vector with its gold letter.

Four trigger families, each escalates (returns True) when the panel's vote
looks UNRELIABLE enough to be worth a tribunal call:

  (a) unanimity        -- the shipped rule: escalate iff not all seats agree.
                           Degenerates toward "always escalate" as N grows,
                           since the chance of N independent seats all
                           landing on the same letter shrinks with N even at
                           a fixed per-seat error rate -- see
                           test_escalation_policies.py's degeneracy test.
  (b) top_cluster_share -- escalate iff the plurality's SHARE of the vote
                           (top_count / N) is below theta. Swept at
                           theta in {0.55, 0.6, 0.7, 0.8, 0.9, 1.0} (theta=1.0
                           reduces to unanimity).
  (c) plurality_margin  -- escalate iff the gap between the top cluster and
                           the runner-up is below m. Swept both as an
                           ABSOLUTE seat count (m in {1,2,3,4}) and
                           NORMALIZED by N (m/N in {0.1,0.2,0.3}).
  (d) normalized_vote_entropy -- escalate iff the Shannon entropy of the
                           vote distribution, normalized by log(k) where k
                           is the number of possible answer letters (4,
                           "ABCD"), exceeds tau. Swept at
                           tau in {0.2, 0.4, 0.6, 0.8}.

For every (policy, threshold) pair the caller can compute, over a set of
items each contributing one vote vector + gold letter at a given N:
  - escalation_rate  -- fraction of items the policy escalates.
  - recall           -- of the items where the PLURALITY vote is wrong
                         (Counter.most_common(1) tie-break, matching
                         benchmark.lever_experiments._plurality exactly),
                         what fraction does the policy actually escalate?
                         A policy that never escalates has recall 0; one
                         that always escalates has recall 1 (and
                         escalation_rate 1) -- the useful middle ground
                         trades a low escalation_rate for a high recall.
See evaluate_policy_over_items / sweep_all_policies below.
"""

from __future__ import annotations

import math
from collections import Counter

# ---------------------------------------------------------------------------
# Threshold grids -- pre-registered, docs/experiment-spec-book.md section 2,
# S3's "threshold sweep". Swept exhaustively, never tuned on live data (this
# whole module is offline/free by construction).
# ---------------------------------------------------------------------------

TOP_CLUSTER_SHARE_GRID = [0.55, 0.6, 0.7, 0.8, 0.9, 1.0]
PLURALITY_MARGIN_ABS_GRID = [1, 2, 3, 4]
PLURALITY_MARGIN_NORM_GRID = [0.1, 0.2, 0.3]
NORMALIZED_ENTROPY_TAU_GRID = [0.2, 0.4, 0.6, 0.8]

POLICY_UNANIMITY = "unanimity"
POLICY_TOP_CLUSTER_SHARE = "top_cluster_share"
POLICY_PLURALITY_MARGIN_ABS = "plurality_margin_abs"
POLICY_PLURALITY_MARGIN_NORM = "plurality_margin_norm"
POLICY_NORMALIZED_VOTE_ENTROPY = "normalized_vote_entropy"

ALL_POLICIES = (
    POLICY_UNANIMITY, POLICY_TOP_CLUSTER_SHARE, POLICY_PLURALITY_MARGIN_ABS,
    POLICY_PLURALITY_MARGIN_NORM, POLICY_NORMALIZED_VOTE_ENTROPY,
)


# ---------------------------------------------------------------------------
# Vote-vector statistics -- shared arithmetic underneath every trigger.
# ---------------------------------------------------------------------------


def vote_counts(votes: list[str]) -> Counter:
    return Counter(votes)


def plurality_letter(votes: list[str]) -> tuple[str, bool]:
    """Mirrors benchmark.lever_experiments._plurality's tie-break exactly
    (Counter.most_common(1)[0] -- the first-inserted letter wins ties,
    since Counter is dict-backed and most_common sorts by count only,
    stable on insertion order for equal counts in CPython). Returns
    (top_letter, unanimous)."""
    if not votes:
        raise ValueError("plurality_letter: votes must be non-empty")
    counts = vote_counts(votes)
    top_letter, top_count = counts.most_common(1)[0]
    return top_letter, top_count == len(votes)


def top_cluster_share(votes: list[str]) -> float:
    """top_count / N -- the plurality's share of the vote. 1.0 iff
    unanimous."""
    if not votes:
        return 0.0
    counts = vote_counts(votes)
    top_count = counts.most_common(1)[0][1]
    return top_count / len(votes)


def plurality_margin(votes: list[str], normalized: bool = False) -> float:
    """top_count - runner_up_count (the runner-up is 0 if every seat agreed
    -- a single cluster has no second entry). `normalized=True` divides by
    N."""
    if not votes:
        return 0.0
    counts = vote_counts(votes)
    ordered = counts.most_common()
    top_count = ordered[0][1]
    runner_up_count = ordered[1][1] if len(ordered) > 1 else 0
    margin = top_count - runner_up_count
    return margin / len(votes) if normalized else float(margin)


def normalized_vote_entropy(votes: list[str], alphabet: str = "ABCD") -> float:
    """Shannon entropy (natural log) of the observed letter frequencies,
    normalized by log(k) where k = len(alphabet) (4 for the standard A-D
    answer set) so the result is bounded to [0, 1] regardless of N: 0.0 for
    a unanimous vote, approaching 1.0 as votes spread evenly across all k
    possible letters. Zero-count letters contribute 0 to the sum (standard
    Shannon convention, 0*log(0) := 0) -- only letters that actually appear
    in `votes` are summed over."""
    n = len(votes)
    if n == 0:
        return 0.0
    k = len(alphabet)
    if k <= 1:
        return 0.0
    counts = vote_counts(votes)
    h = -sum((c / n) * math.log(c / n) for c in counts.values() if c > 0)
    return h / math.log(k)


# ---------------------------------------------------------------------------
# Trigger predicates -- one per family, each a pure function of
# (votes, threshold) -> bool. "Escalate" is always the True case.
# ---------------------------------------------------------------------------


def trigger_unanimity(votes: list[str]) -> bool:
    """The shipped rule: escalate iff NOT every seat agrees."""
    if not votes:
        return False
    return len(set(votes)) > 1


def trigger_top_cluster_share(votes: list[str], theta: float) -> bool:
    """Escalate iff the plurality's vote share is below theta."""
    return top_cluster_share(votes) < theta


def trigger_plurality_margin(votes: list[str], m: float, normalized: bool = False) -> bool:
    """Escalate iff the margin (top - runner-up, absolute or /N) is below
    m."""
    return plurality_margin(votes, normalized=normalized) < m


def trigger_normalized_vote_entropy(votes: list[str], tau: float, alphabet: str = "ABCD") -> bool:
    """Escalate iff the normalized vote entropy exceeds tau."""
    return normalized_vote_entropy(votes, alphabet=alphabet) > tau


def evaluate_trigger(policy: str, threshold, votes: list[str]) -> bool:
    """Dispatches to the right trigger_* function by policy name. threshold
    is ignored for POLICY_UNANIMITY (pass None)."""
    if policy == POLICY_UNANIMITY:
        return trigger_unanimity(votes)
    if policy == POLICY_TOP_CLUSTER_SHARE:
        return trigger_top_cluster_share(votes, threshold)
    if policy == POLICY_PLURALITY_MARGIN_ABS:
        return trigger_plurality_margin(votes, threshold, normalized=False)
    if policy == POLICY_PLURALITY_MARGIN_NORM:
        return trigger_plurality_margin(votes, threshold, normalized=True)
    if policy == POLICY_NORMALIZED_VOTE_ENTROPY:
        return trigger_normalized_vote_entropy(votes, threshold)
    raise ValueError(f"unknown escalation policy {policy!r}")


def policy_grid():
    """Yields (policy_name, threshold) for every pre-registered sweep point,
    including the shipped unanimity policy (threshold=None). 1 + 6 + 4 + 3
    + 4 = 18 (policy, threshold) combinations total."""
    yield (POLICY_UNANIMITY, None)
    for theta in TOP_CLUSTER_SHARE_GRID:
        yield (POLICY_TOP_CLUSTER_SHARE, theta)
    for m in PLURALITY_MARGIN_ABS_GRID:
        yield (POLICY_PLURALITY_MARGIN_ABS, m)
    for m in PLURALITY_MARGIN_NORM_GRID:
        yield (POLICY_PLURALITY_MARGIN_NORM, m)
    for tau in NORMALIZED_ENTROPY_TAU_GRID:
        yield (POLICY_NORMALIZED_VOTE_ENTROPY, tau)


# ---------------------------------------------------------------------------
# Aggregate evaluation -- escalation rate + recall of plurality-wrong items,
# for one (policy, threshold) over a set of (votes, gold_letter) items.
# ---------------------------------------------------------------------------


def evaluate_policy_over_items(policy: str, threshold, items: list[tuple[list[str], str]]) -> dict:
    """items: list of (votes, gold_letter) -- ALREADY at whatever N the
    caller wants evaluated (the caller does the prefix subsampling; this
    function has no notion of N). Returns:
      escalation_rate -- fraction of items the policy escalates (None if
        items is empty).
      recall          -- of items where the plurality is WRONG, the
        fraction the policy escalates (None if there are no wrong items --
        recall is undefined with a zero denominator, never silently 0).
      n_items, n_wrong -- denominators, so a None recall's cause is legible.
    """
    n_items = len(items)
    if n_items == 0:
        return {"escalation_rate": None, "recall": None, "n_items": 0, "n_wrong": 0}
    n_escalated = 0
    n_wrong = 0
    n_wrong_caught = 0
    for votes, gold in items:
        top_letter, _unanimous = plurality_letter(votes)
        wrong = top_letter != gold
        triggered = evaluate_trigger(policy, threshold, votes)
        if triggered:
            n_escalated += 1
        if wrong:
            n_wrong += 1
            if triggered:
                n_wrong_caught += 1
    return {
        "escalation_rate": n_escalated / n_items,
        "recall": (n_wrong_caught / n_wrong) if n_wrong > 0 else None,
        "n_items": n_items,
        "n_wrong": n_wrong,
    }


def sweep_all_policies(items: list[tuple[list[str], str]]) -> list[dict]:
    """Runs every (policy, threshold) in policy_grid() over the same
    `items`, returning a flat list of rows: {policy, threshold,
    escalation_rate, recall, n_items, n_wrong}."""
    rows = []
    for policy, threshold in policy_grid():
        stats = evaluate_policy_over_items(policy, threshold, items)
        rows.append({"policy": policy, "threshold": threshold, **stats})
    return rows
