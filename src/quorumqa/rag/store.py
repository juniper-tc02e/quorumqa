"""SQLite-backed passage store + hybrid (FTS5 BM25 + dense cosine) search
for the G0 retrieval stack.

Schema:
  passages    -- one row per chunk: article_id, title, chunk_index, text
                 (title-prefixed, see chunking.py), word_count, source_url,
                 snapshot_id (provenance -- firewall section 4).
  passages_fts -- FTS5 external-content index over passages(title, text),
                 kept in sync via triggers.
  embeddings  -- one row per passage: float16 vector BLOB + dim. float16
                 (not float32) specifically to halve on-disk/in-memory
                 footprint at this corpus scale, per the G0 spec.
  build_progress -- single-row table the build script reads/writes to
                 resume a streamed build (see benchmark/build_rag_index.py).

Dense search is brute-force cosine over the whole embedding matrix,
vectorized with numpy (no ANN index) -- the spec's explicit call for G0
scale (a few hundred thousand passages fits comfortably in memory as
float32; see RagIndex._ensure_dense_cache).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import numpy as np

from quorumqa.rag.chunking import Chunk
from quorumqa.rag.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion

_SCHEMA = """
CREATE TABLE IF NOT EXISTS passages (
    id INTEGER PRIMARY KEY,
    article_id TEXT NOT NULL,
    title TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    source_url TEXT,
    snapshot_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_passages_article ON passages(article_id);

CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(
    title, text, content='passages', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS passages_ai AFTER INSERT ON passages BEGIN
    INSERT INTO passages_fts(rowid, title, text) VALUES (new.id, new.title, new.text);
END;

CREATE TRIGGER IF NOT EXISTS passages_ad AFTER DELETE ON passages BEGIN
    INSERT INTO passages_fts(passages_fts, rowid, title, text) VALUES('delete', old.id, old.title, old.text);
END;

CREATE TRIGGER IF NOT EXISTS passages_au AFTER UPDATE ON passages BEGIN
    INSERT INTO passages_fts(passages_fts, rowid, title, text) VALUES('delete', old.id, old.title, old.text);
    INSERT INTO passages_fts(rowid, title, text) VALUES (new.id, new.title, new.text);
END;

CREATE TABLE IF NOT EXISTS embeddings (
    passage_id INTEGER PRIMARY KEY REFERENCES passages(id),
    vector BLOB NOT NULL,
    dim INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS build_progress (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    articles_scanned INTEGER NOT NULL DEFAULT 0,
    articles_kept INTEGER NOT NULL DEFAULT 0,
    passages_written INTEGER NOT NULL DEFAULT 0,
    snapshot_id TEXT,
    dataset_config TEXT,
    updated_at TEXT
);
"""


class IndexNotFoundError(FileNotFoundError):
    """Raised when a caller asks to open a RAG index DB that hasn't been
    built yet -- the MCP tool catches this specifically to return a clean
    no-op error instead of crashing the engine."""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.execute("INSERT OR IGNORE INTO build_progress (id) VALUES (1)")
    conn.commit()


def open_for_build(db_path: str | Path) -> sqlite3.Connection:
    """Opens (creating the file/schema if needed) for writing. WAL +
    synchronous=NORMAL trade a small durability window for materially
    faster bulk-insert throughput during the build -- acceptable since a
    crash mid-build is recovered by re-running the resumable build script,
    not by transaction replay."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    ensure_schema(conn)
    return conn


def open_for_read(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        raise IndexNotFoundError(f"RAG index DB not found at {path}")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_progress(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT * FROM build_progress WHERE id = 1").fetchone()
    return dict(row) if row else {}


def set_progress(conn: sqlite3.Connection, **fields) -> None:
    if not fields:
        return
    fields = dict(fields, updated_at=_now_iso())
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE build_progress SET {cols} WHERE id = 1", tuple(fields.values()))
    conn.commit()


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def add_article(
    conn: sqlite3.Connection,
    article_id: str,
    title: str,
    chunks: list[Chunk],
    vectors: np.ndarray | None,
    source_url: str | None,
    snapshot_id: str,
) -> list[int]:
    """Inserts every chunk of one article as a passage row (FTS synced via
    trigger) plus its embedding row if `vectors` is given (one row per
    chunk, same order). Returns the new passage ids. Does not commit --
    caller batches commits across articles for build throughput."""
    if vectors is not None and len(vectors) != len(chunks):
        raise ValueError(f"{len(vectors)} vectors for {len(chunks)} chunks")

    ids: list[int] = []
    cur = conn.cursor()
    for i, chunk in enumerate(chunks):
        cur.execute(
            "INSERT INTO passages (article_id, title, chunk_index, text, word_count, source_url, snapshot_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (article_id, title, chunk.chunk_index, chunk.text, chunk.word_count, source_url, snapshot_id),
        )
        pid = cur.lastrowid
        ids.append(pid)
        if vectors is not None:
            vec16 = np.asarray(vectors[i], dtype=np.float16)
            cur.execute(
                "INSERT INTO embeddings (passage_id, vector, dim) VALUES (?, ?, ?)",
                (pid, vec16.tobytes(), vec16.shape[0]),
            )
    return ids


def count_passages(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0]


def count_articles(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(DISTINCT article_id) FROM passages").fetchone()[0]


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _fts_match_query(raw_query: str) -> str:
    """Builds a safe FTS5 MATCH expression from free text. Free text can
    contain characters FTS5's query syntax treats specially (quotes,
    parens, `-`, `:`, `*`...) -- rather than trying to escape every case,
    tokenize to plain words and OR them together as quoted phrases (a
    quoted single word can't trigger FTS5 operator parsing)."""
    tokens = _TOKEN_RE.findall(raw_query)
    if not tokens:
        return ""
    quoted = [f'"{tok}"' for tok in tokens]
    return " OR ".join(quoted)


def _load_dense_matrix(conn: sqlite3.Connection) -> tuple[np.ndarray, np.ndarray]:
    rows = conn.execute("SELECT passage_id, vector, dim FROM embeddings ORDER BY passage_id").fetchall()
    if not rows:
        return np.zeros(0, dtype=np.int64), np.zeros((0, 0), dtype=np.float32)
    dim = rows[0]["dim"]
    ids = np.empty(len(rows), dtype=np.int64)
    matrix = np.empty((len(rows), dim), dtype=np.float32)
    for i, row in enumerate(rows):
        ids[i] = row["passage_id"]
        matrix[i] = np.frombuffer(row["vector"], dtype=np.float16).astype(np.float32)
    return ids, matrix


class RagIndex:
    """One open connection to a built index DB, with an in-memory dense
    embedding matrix cache. The cache is rebuilt only when the embeddings
    row count changes (cheap COUNT(*) check every call) -- avoids
    re-loading a multi-hundred-MB matrix on every search_corpus call
    within a long-lived MCP server process."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._dense_ids: np.ndarray | None = None
        self._dense_matrix: np.ndarray | None = None
        self._dense_count_at_cache = -1

    @classmethod
    def open(cls, db_path: str | Path) -> "RagIndex":
        return cls(open_for_read(db_path))

    def close(self) -> None:
        self.conn.close()

    def _ensure_dense_cache(self) -> None:
        count = self.conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        if self._dense_matrix is not None and count == self._dense_count_at_cache:
            return
        self._dense_ids, self._dense_matrix = _load_dense_matrix(self.conn)
        self._dense_count_at_cache = count

    def fts_search(self, query: str, limit: int = 50) -> list[tuple[int, float]]:
        match_query = _fts_match_query(query)
        if not match_query:
            return []
        rows = self.conn.execute(
            "SELECT rowid AS passage_id, bm25(passages_fts) AS score "
            "FROM passages_fts WHERE passages_fts MATCH ? ORDER BY score LIMIT ?",
            (match_query, limit),
        ).fetchall()
        # bm25() in SQLite FTS5 is a "cost": lower (more negative) = better
        # match, and the query above already ORDERs by it ascending, so
        # this is best-match-first exactly as reciprocal_rank_fusion wants.
        return [(row["passage_id"], row["score"]) for row in rows]

    def dense_search(self, query_vector: np.ndarray, limit: int = 50) -> list[tuple[int, float]]:
        self._ensure_dense_cache()
        if self._dense_matrix is None or self._dense_matrix.shape[0] == 0:
            return []
        qv = np.asarray(query_vector, dtype=np.float32)
        if qv.shape[0] != self._dense_matrix.shape[1]:
            raise ValueError(
                f"query embedding dim {qv.shape[0]} != index embedding dim {self._dense_matrix.shape[1]} "
                "(index was likely built with a different embedding model)"
            )
        norm = np.linalg.norm(qv)
        if norm > 0:
            qv = qv / norm
        sims = self._dense_matrix @ qv
        top = min(limit, sims.shape[0])
        if top <= 0:
            return []
        part = np.argpartition(-sims, top - 1)[:top]
        ordered = part[np.argsort(-sims[part])]
        return [(int(self._dense_ids[i]), float(sims[i])) for i in ordered]

    def fetch_passages(self, passage_ids: list[int]) -> dict[int, sqlite3.Row]:
        if not passage_ids:
            return {}
        placeholders = ",".join("?" for _ in passage_ids)
        rows = self.conn.execute(
            f"SELECT id, article_id, title, text, source_url, snapshot_id FROM passages WHERE id IN ({placeholders})",
            passage_ids,
        ).fetchall()
        return {row["id"]: row for row in rows}

    def search(
        self,
        query: str,
        query_vector: np.ndarray | None,
        k: int = 5,
        fts_k: int = 50,
        dense_k: int = 50,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> list[dict]:
        """Fuses FTS5 top-`fts_k` and dense top-`dense_k` via RRF, returns
        the fused top-`k` with title/text/score/provenance. If
        `query_vector` is None, falls back to FTS5-only (e.g. embeddings
        unavailable)."""
        fts_ranked = [pid for pid, _ in self.fts_search(query, fts_k)]
        dense_ranked = [pid for pid, _ in self.dense_search(query_vector, dense_k)] if query_vector is not None else []

        rankings = [r for r in (fts_ranked, dense_ranked) if r]
        fused = reciprocal_rank_fusion(rankings, k=rrf_k)[:k] if rankings else []

        rows = self.fetch_passages([pid for pid, _ in fused])
        results = []
        for pid, score in fused:
            row = rows.get(pid)
            if row is None:
                continue
            results.append(
                {
                    "passage_id": pid,
                    "article_id": row["article_id"],
                    "title": row["title"],
                    "text": row["text"],
                    "score": score,
                    "source_url": row["source_url"],
                    "snapshot_id": row["snapshot_id"],
                }
            )
        return results
