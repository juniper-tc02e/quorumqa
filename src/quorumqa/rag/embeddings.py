"""Dense embedding model for the G0 retrieval stack.

Model choice: **BAAI/bge-small-en-v1.5** (Apache-2.0, 384-dim, ~130MB).
Appendix A of docs/recursive-rag-plan.md names Qwen3-Reranker-4B (with
BGE-reranker-v2-m3 as fallback) as the eventual reranker -- deliberately
NOT used here. Rationale: a 4B reranker is a cross-encoder that scores
every (query, candidate) pair with a full forward pass, which is fine for
a paid-API or GPU deployment but is the wrong tradeoff for G0's stated
constraint (CPU-only, no paid model calls, this needs to run inside a
per-question Verifier tool call with acceptable latency). bge-small is a
bi-encoder: embeddings are computed once per passage at INDEX time, so
query time is a single small forward pass + vectorized cosine, not
N cross-encoder passes. The reranker is deferred to G1+ per the plan --
noted here so the deferral has one canonical explanation.

The SentenceTransformer import is deliberately NOT at module load time --
it pulls in torch, which is slow to import and unnecessary for anything
that doesn't actually embed text (chunking/FTS5/RRF tests, the MCP
server's missing-DB fast path). It's loaded lazily on first call to
embed_texts() and cached for the process lifetime.
"""

from __future__ import annotations

import numpy as np

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


def embed_texts(texts: list[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
    """Encodes `texts` to float32 embeddings, shape (len(texts), EMBEDDING_DIM).

    L2-normalizes by default so dot product == cosine similarity at query
    time (cheaper than re-normalizing on every query).
    """
    if not texts:
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
    )
    return vectors.astype(np.float32)


def embed_query(query: str) -> np.ndarray:
    """Convenience wrapper for a single query string -- bge-small-en-v1.5
    doesn't require a distinct query prefix (unlike e.g. e5 models), so
    this is just embed_texts([query])[0]."""
    return embed_texts([query])[0]
