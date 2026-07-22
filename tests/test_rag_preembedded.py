"""Offline tests for quorumqa.rag.preembedded (the G0.5 pre-embedded-corpus
loader) -- fake HF rows only, no network access and no real embedding
model load, per docs/rag-corpus-notes.md's "no paid/heavy calls in tests"
discipline.
"""

from __future__ import annotations

import numpy as np
import pytest

from quorumqa.rag import store
from quorumqa.rag.preembedded import (
    SOURCE_EMBEDDING_DIM,
    DimensionMismatchError,
    group_into_articles,
    is_stem_row,
    map_row,
)


def _fake_row(
    title="Photon",
    text="Photon\n\nA photon is a quantum of electromagnetic radiation.",
    category="Natural_sciences",
    url="https://en.wikipedia.org/wiki?curid=1",
    dim=SOURCE_EMBEDDING_DIM,
    seed=0.01,
):
    rng = np.random.default_rng(42)
    vector = (rng.standard_normal(dim) * (1 + seed) + seed).tolist() if dim else []
    return {"title": title, "text": text, "category": category, "url": url, "embeddings": vector}


# ---------------------------------------------------------------------------
# is_stem_row
# ---------------------------------------------------------------------------


def test_is_stem_row_true_for_stem_title():
    row = _fake_row(title="Photon", text="A photon is a quantum of light.", category="Natural_sciences")
    assert is_stem_row(row) is True


def test_is_stem_row_false_for_excluded_category():
    row = _fake_row(title="Photon", text="A photon is a quantum of light.", category="Business&Economics")
    assert is_stem_row(row) is False


def test_is_stem_row_false_for_non_stem_content():
    row = _fake_row(title="List of pop songs", text="A list of popular songs from the 1990s.", category="Natural_sciences")
    assert is_stem_row(row) is False


# ---------------------------------------------------------------------------
# map_row
# ---------------------------------------------------------------------------


def test_map_row_returns_none_when_article_not_kept():
    row = _fake_row()
    assert map_row(row, article_kept=False) is None


def test_map_row_returns_none_for_empty_text():
    row = _fake_row(text="   ")
    assert map_row(row, article_kept=True) is None


def test_map_row_returns_none_for_missing_embedding():
    row = _fake_row()
    del row["embeddings"]
    assert map_row(row, article_kept=True) is None


def test_map_row_raises_dimension_mismatch_error_on_wrong_length_vector():
    row = _fake_row(dim=384)  # bge-small's dim, not mxbai's 1024
    with pytest.raises(DimensionMismatchError):
        map_row(row, article_kept=True)


def test_map_row_dimension_guard_does_not_fire_when_article_rejected():
    # A wrong-dim vector on a row we're not going to write anyway must not
    # abort the whole build -- only rows that would actually be persisted
    # are checked (see map_row's docstring).
    row = _fake_row(dim=384)
    assert map_row(row, article_kept=False) is None


def test_map_row_normalizes_vector_to_unit_norm():
    row = _fake_row()
    row["embeddings"] = (np.ones(SOURCE_EMBEDDING_DIM) * 3.0).tolist()  # norm = 3*sqrt(dim), not 1
    mapped = map_row(row, article_kept=True)
    assert mapped is not None
    assert np.linalg.norm(mapped.vector) == pytest.approx(1.0, abs=1e-5)


def test_map_row_zero_vector_is_not_divided_by_zero():
    row = _fake_row()
    row["embeddings"] = [0.0] * SOURCE_EMBEDDING_DIM
    mapped = map_row(row, article_kept=True)
    assert mapped is not None
    assert np.linalg.norm(mapped.vector) == pytest.approx(0.0, abs=1e-9)


def test_map_row_accepts_singular_embedding_column_name():
    row = _fake_row()
    row["embedding"] = row.pop("embeddings")
    mapped = map_row(row, article_kept=True)
    assert mapped is not None


def test_map_row_chunk_index_increments_for_same_url_run():
    row1 = _fake_row(url="https://en.wikipedia.org/wiki?curid=7")
    m1 = map_row(row1, article_kept=True, prior_url=None, prior_chunk_index=-1)
    assert m1.chunk_index == 0
    assert m1.article_id == "https://en.wikipedia.org/wiki?curid=7"

    row2 = _fake_row(url="https://en.wikipedia.org/wiki?curid=7", text="Photon\n\nMore about photons.")
    m2 = map_row(row2, article_kept=True, prior_url=row1["url"], prior_chunk_index=m1.chunk_index)
    assert m2.chunk_index == 1
    assert m2.article_id == m1.article_id


def test_map_row_chunk_index_resets_on_new_url():
    row1 = _fake_row(url="https://en.wikipedia.org/wiki?curid=7")
    m1 = map_row(row1, article_kept=True, prior_url=None, prior_chunk_index=-1)

    row2 = _fake_row(url="https://en.wikipedia.org/wiki?curid=8", title="Electron")
    # Simulating the build script's own url-change reset (prior_chunk_index
    # would be reset to -1 by the caller before this call, per
    # build_rag_index_preembedded.py).
    m2 = map_row(row2, article_kept=True, prior_url=row2["url"], prior_chunk_index=-1)
    assert m2.chunk_index == 0
    assert m2.article_id == "https://en.wikipedia.org/wiki?curid=8"


def test_map_row_missing_url_falls_back_to_synthetic_article_id():
    row = _fake_row(url=None)
    mapped = map_row(row, article_kept=True, row_index=5)
    assert mapped is not None
    assert "untitled:" in mapped.article_id


# ---------------------------------------------------------------------------
# group_into_articles
# ---------------------------------------------------------------------------


def test_group_into_articles_groups_contiguous_runs():
    row_a1 = _fake_row(url="A", title="Alpha")
    m_a1 = map_row(row_a1, article_kept=True)
    row_a2 = _fake_row(url="A", title="Alpha", text="Alpha\n\nMore.")
    m_a2 = map_row(row_a2, article_kept=True, prior_url="A", prior_chunk_index=m_a1.chunk_index)
    row_b1 = _fake_row(url="B", title="Beta")
    m_b1 = map_row(row_b1, article_kept=True, prior_url="A", prior_chunk_index=-1)

    groups = group_into_articles([m_a1, m_a2, m_b1])
    assert [g[0] for g in groups] == ["A", "B"]
    assert len(groups[0][2]) == 2
    assert len(groups[1][2]) == 1


def test_group_into_articles_does_not_merge_noncontiguous_runs():
    row_a1 = _fake_row(url="A", title="Alpha")
    m_a1 = map_row(row_a1, article_kept=True)
    row_b1 = _fake_row(url="B", title="Beta")
    m_b1 = map_row(row_b1, article_kept=True, prior_url="A", prior_chunk_index=-1)
    row_a2 = _fake_row(url="A", title="Alpha", text="Alpha\n\nMore, out of order.")
    m_a2 = map_row(row_a2, article_kept=True, prior_url="B", prior_chunk_index=-1)

    groups = group_into_articles([m_a1, m_b1, m_a2])
    # Non-contiguous "A" runs stay as TWO separate groups, not merged --
    # documented behavior, not a bug: this loader relies on the source
    # stream already being article-contiguous.
    assert [g[0] for g in groups] == ["A", "B", "A"]


# ---------------------------------------------------------------------------
# End-to-end: fake rows -> map_row -> store round-trip
# ---------------------------------------------------------------------------


def test_fake_rows_round_trip_through_store(tmp_path):
    rows = [
        _fake_row(url="A", title="Photon", text="Photon\n\nA photon is a quantum of light.", category="Natural_sciences"),
        _fake_row(url="A", title="Photon", text="Photon\n\nPhotons carry electromagnetic force.", category="Natural_sciences"),
        _fake_row(url="B", title="Business Cycle", text="A business cycle is an economic fluctuation.", category="Business&Economics"),
        _fake_row(url="C", title="Electron", text="Electron\n\nAn electron is a subatomic particle.", category="Natural_sciences"),
    ]

    db_path = tmp_path / "preembedded.sqlite3"
    conn = store.open_for_build(db_path)

    prior_url = None
    prior_chunk_index = -1
    mapped_passages = []
    for i, row in enumerate(rows):
        if row["url"] != prior_url:
            prior_chunk_index = -1
            article_kept = is_stem_row(row)
        mapped = map_row(row, article_kept=article_kept, prior_url=prior_url, prior_chunk_index=prior_chunk_index, row_index=i)
        prior_url = row["url"]
        if mapped is not None:
            prior_chunk_index = mapped.chunk_index
            mapped_passages.append(mapped)

    # Business&Economics article ("B") is excluded entirely; Photon (2
    # chunks) and Electron (1 chunk) survive.
    assert [p.title for p in mapped_passages] == ["Photon", "Photon", "Electron"]

    for article_id, title, group in group_into_articles(mapped_passages):
        from quorumqa.rag.chunking import Chunk

        chunks = [Chunk(chunk_index=p.chunk_index, title=p.title, text=p.text, word_count=p.word_count) for p in group]
        vectors = np.stack([p.vector for p in group])
        store.add_article(conn, article_id, title, chunks, vectors, group[0].source_url, "test-snapshot:preembedded")
    conn.commit()
    store.set_progress(conn, embedding_model="mixedbread-ai/mxbai-embed-large-v1", snapshot_id="test-snapshot:preembedded")
    conn.close()

    assert store.get_progress(store.open_for_read(db_path)).get("embedding_model") == "mixedbread-ai/mxbai-embed-large-v1"

    index = store.RagIndex.open(db_path)
    assert store.count_passages(index.conn) == 3
    assert store.count_articles(index.conn) == 2  # Photon (2 chunks), Electron (1 chunk)

    fts_results = index.fts_search("electromagnetic", limit=10)
    assert fts_results
    ids = [pid for pid, _ in fts_results]
    row = index.fetch_passages(ids)[ids[0]]
    assert row["title"] == "Photon"

    # No "Business Cycle" passage was ever written -- the excluded category
    # never reaches the store.
    all_titles = {r["title"] for r in index.fetch_passages(list(range(1, 10))).values()}
    assert "Business Cycle" not in all_titles


def test_store_dense_search_rejects_query_vector_of_wrong_dim(tmp_path):
    # Integration with store.py's own dimension guard: an index built from
    # SOURCE_EMBEDDING_DIM (1024) vectors must reject a bge-small-shaped
    # (384) query vector rather than silently returning nonsense --
    # exercises the "CRITICAL CONSTRAINT" from the loader's module
    # docstring end to end.
    from quorumqa.rag.chunking import Chunk

    row = _fake_row(url="A", title="Photon")
    mapped = map_row(row, article_kept=True)
    db_path = tmp_path / "dimcheck.sqlite3"
    conn = store.open_for_build(db_path)
    chunk = Chunk(chunk_index=0, title=mapped.title, text=mapped.text, word_count=mapped.word_count)
    store.add_article(conn, mapped.article_id, mapped.title, [chunk], np.stack([mapped.vector]), mapped.source_url, "test-snapshot:dimcheck")
    conn.commit()
    conn.close()

    index = store.RagIndex.open(db_path)
    wrong_dim_query = np.ones(384, dtype=np.float32)
    with pytest.raises(ValueError):
        index.dense_search(wrong_dim_query, limit=5)
