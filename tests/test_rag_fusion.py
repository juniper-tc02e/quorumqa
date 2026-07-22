import pytest

from quorumqa.rag.fusion import reciprocal_rank_fusion


def test_single_ranking_preserves_order():
    fused = reciprocal_rank_fusion([["a", "b", "c"]])
    assert [doc for doc, _ in fused] == ["a", "b", "c"]


def test_agreement_across_rankings_boosts_score():
    fts = ["a", "b", "c", "d"]
    dense = ["b", "a", "d", "c"]
    fused = reciprocal_rank_fusion([fts, dense])
    order = [doc for doc, _ in fused]

    # "a" (ranks 1,2) and "b" (ranks 2,1) both appear near the top in both
    # rankings, so they should fuse ahead of "c"/"d" which are consistently
    # lower in both.
    assert set(order[:2]) == {"a", "b"}
    assert set(order[2:]) == {"c", "d"}


def test_doc_only_in_one_ranking_still_included():
    fused = reciprocal_rank_fusion([["a", "b"], ["c"]])
    docs = {doc for doc, _ in fused}
    assert docs == {"a", "b", "c"}


def test_scores_are_sorted_descending():
    fused = reciprocal_rank_fusion([["x", "y", "z"], ["y", "z", "x"]])
    scores = [score for _, score in fused]
    assert scores == sorted(scores, reverse=True)


def test_empty_rankings_yield_empty_result():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_known_rrf_values_default_k():
    # k=60 default. doc "a" at rank 1 in both lists:
    # score = 1/(60+1) + 1/(60+1) = 2/61
    fused = dict(reciprocal_rank_fusion([["a"], ["a"]]))
    assert fused["a"] == pytest.approx(2 / 61)


def test_custom_k_changes_scores_but_not_relative_agreement_boost():
    fused_k10 = dict(reciprocal_rank_fusion([["a", "b"], ["b", "a"]], k=10))
    # both docs appear once at rank1 and once at rank2 across the two
    # rankings, so they tie.
    assert fused_k10["a"] == pytest.approx(fused_k10["b"])


def test_rejects_non_positive_k():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], k=0)
