"""Offline tests for benchmark/build_rag_index_preembedded.py's `build()`
orchestration -- fake in-memory rows via the `rows=` test hook, no network,
no real HF dataset or embedding model. Covers the cross-category-duplicate
guard (a real bug found while building the corpus: the source dataset
repeats the SAME Wikipedia article, non-contiguously, under more than one
field-of-science category -- see docs/rag-corpus-notes.md) and basic
resumability.
"""

from __future__ import annotations

import numpy as np
import pytest

from benchmark.build_rag_index_preembedded import build
from quorumqa.rag import store
from quorumqa.rag.preembedded import SOURCE_EMBEDDING_DIM


def _row(url, title, text, category="Natural_sciences", seed=1.0):
    rng = np.random.default_rng(abs(hash((url, text))) % (2**32))
    vector = (rng.standard_normal(SOURCE_EMBEDDING_DIM) + seed).tolist()
    return {"url": url, "title": title, "text": text, "category": category, "embeddings": vector}


def test_build_writes_kept_stem_passages(tmp_path):
    db_path = tmp_path / "index.sqlite3"
    rows = [
        _row("A", "Photon", "Photon\n\nA photon is a quantum of electromagnetic radiation."),
        _row("B", "Business Cycle", "A business cycle is an economic fluctuation.", category="Business&Economics"),
        _row("C", "Electron", "Electron\n\nAn electron is a subatomic particle."),
    ]
    result = build(db_path, max_passages=100, checkpoint_scanned=1, rows=rows)

    assert result["complete"] is True
    assert result["passages_written"] == 2  # Photon + Electron; Business Cycle excluded

    conn = store.open_for_read(db_path)
    titles = {r["title"] for r in conn.execute("SELECT title FROM passages")}
    assert titles == {"Photon", "Electron"}


def test_build_deduplicates_cross_category_repeat_article(tmp_path):
    # The same article (url="A") appears twice, non-contiguously, under
    # two different categories -- exactly the pattern observed in the real
    # source dataset (e.g. CRISPR present 3x). Only the FIRST occurrence's
    # chunks should be written.
    db_path = tmp_path / "index.sqlite3"
    rows = [
        _row("A", "CRISPR", "CRISPR\n\nCRISPR is a gene editing technology.", category="Natural_sciences"),
        _row("B", "Electron", "Electron\n\nAn electron is a subatomic particle.", category="Natural_sciences"),
        _row("A", "CRISPR", "CRISPR\n\nCRISPR is a gene editing technology.", category="Computer_science"),
    ]
    result = build(db_path, max_passages=100, checkpoint_scanned=1, rows=rows)

    assert result["passages_written"] == 2  # one CRISPR passage + one Electron passage, not two CRISPR

    conn = store.open_for_read(db_path)
    crispr_rows = conn.execute("SELECT COUNT(*) c FROM passages WHERE title = 'CRISPR'").fetchone()
    assert crispr_rows["c"] == 1


def test_build_dedup_guard_seeded_from_existing_db_rows(tmp_path):
    # seen_article_ids must be reseeded from whatever's ALREADY in the DB
    # at build() startup (see build()'s comment) -- not just accumulated
    # in memory within one call -- so a build() call against a DB that
    # already has article "A" (written some other way, e.g. by an earlier
    # resumed run) still refuses to add a second "A" group.
    from quorumqa.rag.chunking import Chunk
    from quorumqa.rag.preembedded import SOURCE_DATASET_ID
    from benchmark.build_rag_index_preembedded import DATASET_REVISION

    db_path = tmp_path / "index.sqlite3"
    conn = store.open_for_build(db_path)
    pre_existing_snapshot = f"{SOURCE_DATASET_ID}@{DATASET_REVISION}"
    vec = np.ones(SOURCE_EMBEDDING_DIM, dtype=np.float32) / np.sqrt(SOURCE_EMBEDDING_DIM)
    store.add_article(
        conn, "A", "CRISPR",
        [Chunk(chunk_index=0, title="CRISPR", text="CRISPR\n\nCRISPR is a gene editing technology.", word_count=6)],
        np.stack([vec]), "A", pre_existing_snapshot,
    )
    conn.commit()
    store.set_progress(conn, snapshot_id=pre_existing_snapshot)  # rows_scanned stays 0 -- nothing consumed via build() yet
    conn.close()

    rows = [
        _row("A", "CRISPR", "CRISPR\n\nCRISPR is a gene editing technology."),  # duplicate of the pre-existing row
        _row("B", "Electron", "Electron\n\nAn electron is a subatomic particle."),
    ]
    result = build(db_path, max_passages=100, checkpoint_scanned=1, rows=rows)

    conn = store.open_for_read(db_path)
    assert conn.execute("SELECT COUNT(*) c FROM passages WHERE title = 'CRISPR'").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM passages WHERE title = 'Electron'").fetchone()["c"] == 1
    assert result["passages_written"] == 1  # only Electron newly written this call


def test_build_refuses_to_mix_snapshots(tmp_path):
    db_path = tmp_path / "index.sqlite3"
    conn = store.open_for_build(db_path)
    store.set_progress(conn, snapshot_id="some-other-dataset:v1")
    conn.close()

    with pytest.raises(RuntimeError, match="refusing to mix"):
        build(db_path, max_passages=10, rows=[])
