import numpy as np
import pytest

from quorumqa.rag import store
from quorumqa.rag.chunking import Chunk


def _mk_chunk(title: str, text: str, index: int = 0) -> Chunk:
    return Chunk(chunk_index=index, title=title, text=text, word_count=len(text.split()))


@pytest.fixture()
def built_db(tmp_path):
    """A small hand-built index: 3 articles, one chunk each, with
    deliberately-designed fake (non-ML) embeddings so dense_search results
    are predictable without loading sentence-transformers."""
    db_path = tmp_path / "rag_index.sqlite3"
    conn = store.open_for_build(db_path)

    articles = [
        ("1", "Photon", "Photon\n\nA photon is a quantum of electromagnetic radiation.", [1.0, 0.0, 0.0]),
        ("2", "Electron", "Electron\n\nAn electron is a subatomic particle with negative charge.", [0.9, 0.1, 0.0]),
        ("3", "Baking Bread", "Baking Bread\n\nBread is baked from flour, water, yeast, and salt.", [0.0, 0.0, 1.0]),
    ]
    for article_id, title, text, vec in articles:
        chunks = [_mk_chunk(title, text)]
        vectors = np.array([vec], dtype=np.float32)
        store.add_article(conn, article_id, title, chunks, vectors, f"https://example.org/{title}", "test-snapshot:v1")
    conn.commit()
    conn.close()
    return db_path


def test_fts_search_finds_keyword_match(built_db):
    index = store.RagIndex.open(built_db)
    results = index.fts_search("photon", limit=10)
    ids = [pid for pid, _ in results]
    assert len(ids) == 1
    row = index.fetch_passages(ids)[ids[0]]
    assert row["title"] == "Photon"


def test_fts_search_ranks_multi_term_match_first(built_db):
    index = store.RagIndex.open(built_db)
    # "electron" should match only the Electron passage; "particle" also
    # only appears there -- best match should be Electron, not Photon.
    results = index.fts_search("subatomic particle electron", limit=10)
    assert results, "expected at least one FTS hit"
    top_id = results[0][0]
    row = index.fetch_passages([top_id])[top_id]
    assert row["title"] == "Electron"


def test_fts_search_handles_special_characters_without_erroring(built_db):
    index = store.RagIndex.open(built_db)
    # FTS5 query-syntax special characters (quotes, parens, colon, dash)
    # must not raise -- see _fts_match_query.
    results = index.fts_search('photon (quantum) "test": -bread', limit=10)
    assert isinstance(results, list)


def test_fts_search_empty_query_returns_empty(built_db):
    index = store.RagIndex.open(built_db)
    assert index.fts_search("   ", limit=10) == []


def test_dense_search_finds_nearest_by_fake_embedding(built_db):
    index = store.RagIndex.open(built_db)
    query_vector = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    results = index.dense_search(query_vector, limit=10)

    assert results, "expected dense results"
    top_id, top_score = results[0]
    row = index.fetch_passages([top_id])[top_id]
    assert row["title"] == "Photon"
    # exact match on Photon's own vector -> cosine similarity == 1.0
    assert top_score == pytest.approx(1.0, abs=1e-4)

    ordered_titles = [index.fetch_passages([pid])[pid]["title"] for pid, _ in results]
    # Photon (identical) then Electron (close: [0.9,0.1,0]) then Baking Bread (orthogonal)
    assert ordered_titles == ["Photon", "Electron", "Baking Bread"]


def test_dense_search_empty_index_returns_empty(tmp_path):
    db_path = tmp_path / "empty.sqlite3"
    conn = store.open_for_build(db_path)
    conn.close()
    index = store.RagIndex.open(db_path)
    results = index.dense_search(np.array([1.0, 0.0, 0.0], dtype=np.float32), limit=5)
    assert results == []


def test_fused_search_returns_title_text_score_provenance(built_db):
    index = store.RagIndex.open(built_db)
    query_vector = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    results = index.search("photon quantum", query_vector, k=3)

    assert results, "expected fused results"
    top = results[0]
    assert top["title"] == "Photon"
    assert "photon" in top["text"].lower()
    assert isinstance(top["score"], float)
    assert top["source_url"] == "https://example.org/Photon"
    assert top["snapshot_id"] == "test-snapshot:v1"


def test_fused_search_respects_k(built_db):
    index = store.RagIndex.open(built_db)
    query_vector = np.array([0.5, 0.5, 0.5], dtype=np.float32)
    results = index.search("electromagnetic particle bread", query_vector, k=2)
    assert len(results) <= 2


def test_fused_search_falls_back_to_fts_only_without_query_vector(built_db):
    index = store.RagIndex.open(built_db)
    results = index.search("photon", None, k=3)
    assert results
    assert results[0]["title"] == "Photon"


def test_open_for_read_missing_db_raises_index_not_found(tmp_path):
    missing = tmp_path / "does_not_exist.sqlite3"
    with pytest.raises(store.IndexNotFoundError):
        store.open_for_read(missing)


def test_progress_roundtrip(tmp_path):
    db_path = tmp_path / "progress.sqlite3"
    conn = store.open_for_build(db_path)
    assert store.get_progress(conn)["articles_scanned"] == 0

    store.set_progress(conn, articles_scanned=100, articles_kept=10, passages_written=15)
    progress = store.get_progress(conn)
    assert progress["articles_scanned"] == 100
    assert progress["articles_kept"] == 10
    assert progress["passages_written"] == 15
    conn.close()


def test_count_helpers(built_db):
    conn = store.open_for_read(built_db)
    assert store.count_articles(conn) == 3
    assert store.count_passages(conn) == 3


def test_embedding_model_column_defaults_to_none(tmp_path):
    db_path = tmp_path / "embmodel.sqlite3"
    conn = store.open_for_build(db_path)
    assert store.get_progress(conn).get("embedding_model") is None
    conn.close()


def test_embedding_model_roundtrips_via_set_progress(tmp_path):
    db_path = tmp_path / "embmodel2.sqlite3"
    conn = store.open_for_build(db_path)
    store.set_progress(conn, embedding_model="mixedbread-ai/mxbai-embed-large-v1")
    assert store.get_progress(conn)["embedding_model"] == "mixedbread-ai/mxbai-embed-large-v1"
    conn.close()


def test_ensure_schema_migration_is_idempotent(tmp_path):
    # Calling open_for_build (which runs ensure_schema) twice against the
    # same DB must not raise on the second "ALTER TABLE ADD COLUMN" --
    # this is the guard that lets an old, pre-migration DB be reopened for
    # a resumed build without erroring.
    db_path = tmp_path / "migration.sqlite3"
    conn1 = store.open_for_build(db_path)
    conn1.close()
    conn2 = store.open_for_build(db_path)  # re-runs ensure_schema
    assert store.get_progress(conn2) is not None
    conn2.close()
