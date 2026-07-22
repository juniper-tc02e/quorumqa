from quorumqa.tools import mcp_server


def test_search_corpus_missing_db_is_clean_error(tmp_path, monkeypatch):
    missing_db = tmp_path / "no_such_index.sqlite3"
    monkeypatch.setenv("QUORUMQA_RAG_DB", str(missing_db))

    result = mcp_server.search_corpus("quantum mechanics", k=5)

    assert result["ok"] is False
    assert "error" in result
    assert str(missing_db) in result["error"]
    assert "build_rag_index.py" in result["error"]


def test_search_corpus_missing_db_never_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("QUORUMQA_RAG_DB", str(tmp_path / "also_missing.sqlite3"))
    # The whole point of the no-op contract: this must not raise, no
    # matter the query content.
    result = mcp_server.search_corpus("", k=5)
    assert result["ok"] is False


def test_search_corpus_default_db_path_is_under_repo_benchmark_data():
    path = mcp_server._rag_db_path()
    assert path.name == "rag_index.sqlite3"
    assert path.parent.name == "data"
    assert path.parent.parent.name == "benchmark"


def test_search_corpus_against_real_built_index(tmp_path, monkeypatch):
    from quorumqa.rag import store
    from quorumqa.rag.chunking import Chunk
    from quorumqa.rag.embeddings import embed_texts

    db_path = tmp_path / "rag_index.sqlite3"
    conn = store.open_for_build(db_path)
    chunk = Chunk(chunk_index=0, title="Photon", text="Photon\n\nA photon is a quantum of light.", word_count=8)
    # Real embeddings (dim must match what search_corpus's query embedding
    # produces) -- this exercises the actual end-to-end tool path, not a
    # stub.
    vec = embed_texts([chunk.text])
    store.add_article(conn, "1", "Photon", [chunk], vec, "https://example.org/Photon", "test-snapshot:v1")
    conn.commit()
    conn.close()

    monkeypatch.setenv("QUORUMQA_RAG_DB", str(db_path))
    result = mcp_server.search_corpus("photon", k=3)

    assert result["ok"] is True
    assert result["dense"] is True
    assert result["results"]
    assert result["results"][0]["title"] == "Photon"
