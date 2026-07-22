"""Reciprocal Rank Fusion (RRF) -- combines multiple ranked result lists
(here: FTS5 BM25 top-N and dense-cosine top-N) into one fused ranking
without needing the two scoring scales to be comparable.

score(doc) = sum over rankings r that contain doc of  1 / (k_rrf + rank_r(doc))

rank_r is 1-based position in ranking r. Standard choice k_rrf=60 (from the
original RRF paper, Cormack et al. 2009) is kept as the default.
"""

from __future__ import annotations

from typing import Hashable, Sequence, TypeVar

T = TypeVar("T", bound=Hashable)

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[T]],
    k: int = DEFAULT_RRF_K,
) -> list[tuple[T, float]]:
    """`rankings` is a list of ranked-id lists (best match first), e.g.
    [fts_ids_best_first, dense_ids_best_first]. A doc missing from one
    ranking simply doesn't get that ranking's term -- it isn't penalized
    beyond "gets fewer terms summed".

    Returns [(doc_id, fused_score), ...] sorted by fused_score descending.
    Ties broken by first-seen order across `rankings` (stable).
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")

    scores: dict[T, float] = {}
    first_seen: dict[T, int] = {}
    order = 0
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            if doc_id not in first_seen:
                first_seen[doc_id] = order
                order += 1

    return sorted(scores.items(), key=lambda pair: (-pair[1], first_seen[pair[0]]))
