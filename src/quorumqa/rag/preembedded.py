"""Loader for pre-embedded HF Wikipedia datasets -- ingests passage text
plus ALREADY-COMPUTED embedding vectors directly into the RagIndex SQLite
store, without recomputing embeddings locally. See docs/rag-corpus-notes.md
for the full corpus choice, license, and provenance writeup.

PROBLEM THIS SOLVES (docs/recursive-rag-plan.md phase G0.5): the
from-scratch build (benchmark/build_rag_index.py) streams raw Wikipedia
and embeds every kept chunk with bge-small on CPU at ~1.6 kept-articles/s
-- a 200k-article corpus is a many-hour build, impractical for this
project's timeline. HF `Laz4rz/wikipedia_stem_small_rag_embeddings` ships
STEM-filtered Wikipedia passages ALREADY embedded (explicit CC-BY-SA-3.0
license), so ingesting it is bounded by download bandwidth, not CPU
embedding throughput.

CRITICAL CONSTRAINT: this corpus's embedding model
(mixedbread-ai/mxbai-embed-large-v1, 1024-dim, Apache-2.0, locally
runnable) is NOT this project's default query encoder (bge-small-en-v1.5,
384-dim, still used by the from-scratch build path). An index built by
this loader is tagged with its embedding_model in build_progress
(see quorumqa.rag.store's migration) so mcp_server.search_corpus can pick
the matching query encoder (quorumqa.rag.embeddings.get_query_embedder)
instead of defaulting to bge-small and silently searching in the wrong
vector space. store.RagIndex.dense_search's existing dimension guard is
the last-resort trip wire if that wiring is ever bypassed.

FIREWALL (docs/recursive-rag-plan.md section 4): this corpus is Wikipedia
STEM articles sourced (per the dataset's own card) from HF
`millawell/wikipedia_field_of_science` -- a general encyclopedia corpus,
independent of and unrelated to any benchmark question set. Nothing
benchmark-derived is introduced by this loader.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from quorumqa.rag.subset import is_stem_article

SOURCE_DATASET_ID = "Laz4rz/wikipedia_stem_small_rag_embeddings"
SOURCE_EMBEDDING_MODEL = "mixedbread-ai/mxbai-embed-large-v1"
SOURCE_EMBEDDING_DIM = 1024
SOURCE_LICENSE = "cc-by-sa-3.0"

# The dataset's own README flags this category as off-topic ("unfortunately
# there is also Business&Economics... I thought it may contain some useful
# data as well, even by accident"). Excluded here to keep the corpus
# honestly STEM per docs/recursive-rag-plan.md section 1's target (hard
# STEM breadth). This is a coarse first filter -- `is_stem_article` below
# is a second, independent check over title+text using this project's own
# STEM keyword rule (quorumqa.rag.subset), not just trusting the source's
# self-reported category label.
EXCLUDED_CATEGORIES = frozenset({"Business&Economics"})


class DimensionMismatchError(ValueError):
    """Raised when a source row's embedding vector length doesn't match
    SOURCE_EMBEDDING_DIM. This is a hard stop, not a skip-and-continue:
    writing a wrong-dim vector into the embeddings table would corrupt
    store._load_dense_matrix for the WHOLE index (it stacks every row's
    vector into one fixed-width numpy matrix), not just this one row."""


@dataclass(frozen=True)
class MappedPassage:
    article_id: str
    title: str
    chunk_index: int
    text: str
    word_count: int
    source_url: str | None
    vector: np.ndarray  # float32, L2-normalized, SOURCE_EMBEDDING_DIM-dim


def _raw_vector(row: dict):
    # The upstream HF dataset names the column "embeddings" (plural); some
    # mirrors/exports of similar datasets use the singular "embedding" --
    # accept either so this loader isn't brittle to that cosmetic drift.
    if "embeddings" in row and row["embeddings"] is not None:
        return row["embeddings"]
    return row.get("embedding")


def is_stem_row(row: dict) -> bool:
    """The article-level accept/reject decision: excluded category, or
    fails this project's own STEM keyword rule (quorumqa.rag.subset,
    reused unchanged from the from-scratch builder) over this row's
    title+text.

    Callers MUST evaluate this only on the FIRST row of an article (see
    map_row's docstring) and reuse the same decision for that article's
    remaining chunks -- evaluating it per-chunk would apply subset.py's
    title-or-lead-paragraph rule to arbitrary MID-article continuation
    text, which very often lacks the recurring keyword a lead paragraph
    has, and would silently drop valid continuation chunks of a clearly-
    STEM article. That would also be inconsistent with
    benchmark/build_rag_index.py, which gates by is_stem_article ONCE per
    article and keeps every chunk of an accepted article.
    """
    category = (row.get("category") or "").strip()
    if category in EXCLUDED_CATEGORIES:
        return False
    title = (row.get("title") or "").strip()
    text = row.get("text") or ""
    return is_stem_article(title, text)


def map_row(
    row: dict,
    *,
    article_kept: bool,
    prior_url: str | None = None,
    prior_chunk_index: int = -1,
    row_index: int = 0,
) -> MappedPassage | None:
    """Maps one raw HF dataset row (a dict with title/text/category/url/
    embeddings keys, as yielded by `datasets.load_dataset(...,
    streaming=True)`) to a MappedPassage, or None if the row is filtered
    out (its article was rejected, or this row has no usable text/
    embedding).

    `article_kept` is the caller-supplied accept/reject decision for the
    ARTICLE this row belongs to (see `is_stem_row`) -- computed once per
    article, not re-derived per row, so every kept article contributes ALL
    its chunks, not just chunks that individually repeat a STEM keyword.

    `prior_url`/`prior_chunk_index` let the caller thread per-article chunk
    numbering across a contiguous stream: consecutive rows sharing the same
    source `url` are consecutive chunks of the same Wikipedia article (this
    dataset's chunker emits them that way), so chunk_index increments and
    article_id is reused; a different (or first) url starts a new article
    at chunk_index 0.

    Raises DimensionMismatchError if a row that would otherwise be written
    (article kept, text present) has an embedding vector whose length
    isn't exactly SOURCE_EMBEDDING_DIM -- see that class's docstring for
    why this is a hard stop rather than a skipped row. A row with no
    embedding at all (key missing/None) is treated as an unusable row and
    skipped (returns None), same as missing text.
    """
    if not article_kept:
        return None

    title = (row.get("title") or "").strip()
    text = row.get("text") or ""
    if not text.strip():
        return None

    raw_vector = _raw_vector(row)
    if raw_vector is None:
        return None
    vector = np.asarray(raw_vector, dtype=np.float32)
    if vector.shape != (SOURCE_EMBEDDING_DIM,):
        raise DimensionMismatchError(
            f"row embedding has shape {vector.shape}, expected ({SOURCE_EMBEDDING_DIM},) "
            f"for {SOURCE_EMBEDDING_MODEL} -- refusing to write a mixed-dimension index"
        )
    # Source vectors are NOT unit-normalized (observed norm ~16 on live
    # rows) -- normalize here so the on-disk convention matches
    # quorumqa.rag.embeddings.embed_texts's stored vectors (unit norm,
    # dot product == cosine at query time). Cosine similarity is scale-
    # invariant per-vector, so this is lossless relative to the original
    # (unnormalized) embedding space.
    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector = vector / norm

    url = row.get("url")
    if url is not None and prior_url is not None and url == prior_url:
        article_id = url
        chunk_index = prior_chunk_index + 1
    else:
        article_id = url if url else f"untitled:{title}:{row_index}"
        chunk_index = 0

    return MappedPassage(
        article_id=article_id,
        title=title,
        chunk_index=chunk_index,
        text=text,
        word_count=len(text.split()),
        source_url=url,
        vector=vector,
    )


def group_into_articles(passages: list[MappedPassage]) -> list[tuple[str, str, list[MappedPassage]]]:
    """Groups an in-order list of MappedPassage by contiguous article_id
    runs, returning [(article_id, title, [passages...]), ...] in the same
    per-article ordering as store.add_article expects (chunks in
    chunk_index order). Passages are assumed already in stream order (as
    produced by repeated map_row calls threading prior_url/prior_chunk_index),
    so a run of consecutive same-article_id passages is exactly one
    article's chunks -- this does not re-sort or merge non-contiguous runs.
    """
    groups: list[tuple[str, str, list[MappedPassage]]] = []
    for passage in passages:
        if groups and groups[-1][0] == passage.article_id:
            groups[-1][2].append(passage)
        else:
            groups.append((passage.article_id, passage.title, [passage]))
    return groups
