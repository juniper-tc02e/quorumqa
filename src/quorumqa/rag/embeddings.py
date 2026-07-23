"""Dense embedding model(s) for the G0/G0.5 retrieval stack.

Default model: **BAAI/bge-small-en-v1.5** (Apache-2.0, 384-dim, ~130MB).
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

Second model: **mixedbread-ai/mxbai-embed-large-v1** (Apache-2.0, 1024-dim,
~640MB) -- NOT the default, only used for the G0.5 pre-embedded STEM-
Wikipedia corpus (docs/rag-corpus-notes.md), because that corpus (HF
`Laz4rz/wikipedia_stem_small_rag_embeddings`) ships embeddings already
computed with this model. The whole point of ingesting a pre-embedded
corpus is to NOT recompute embeddings locally -- so query-time encoding
for THAT corpus must use the SAME model, not bge-small. bge-small stays
the default for the from-scratch build path and existing tests/callers
that don't pass a model name. See `get_query_embedder` for how a caller
(e.g. mcp_server.search_corpus) picks the right one per-index using the
model name recorded in that index's build_progress row.

The SentenceTransformer import is deliberately NOT at module load time --
it pulls in torch, which is slow to import and unnecessary for anything
that doesn't actually embed text (chunking/FTS5/RRF tests, the MCP
server's missing-DB fast path). It's loaded lazily on first call to
embed_texts() and cached for the process lifetime.
"""

from __future__ import annotations

import threading

import numpy as np

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

MXBAI_MODEL_NAME = "mixedbread-ai/mxbai-embed-large-v1"
MXBAI_EMBEDDING_DIM = 1024

_model = None
_mxbai_model = None

# A cached SentenceTransformer is one shared model object -- calling
# .encode() on it concurrently from multiple threads (e.g. rag_presolve
# retrieving for several questions in flight under asyncio.to_thread, or
# multiple concurrent Verifier search_corpus tool calls) is NOT safe: live-
# reproduced 2026-07-22 running the rag_presolve lever at concurrency=2 --
# one of two simultaneous embed_query_mxbai() calls raised "RuntimeError:
# mat1 and mat2 must have the same dtype, but got Half and Float" inside
# the model's forward pass, dropping that question outright. A single
# global lock serializes every encode() call project-wide -- correctness
# over throughput here: one query embedding is a sub-second CPU forward
# pass, dwarfed by the LLM API latency this project's calls are already
# bottlenecked on, so serializing it costs nothing that matters while
# eliminating a real drop-bias source that would otherwise correlate with
# concurrency setting, not question difficulty.
_encode_lock = threading.Lock()

# A SEPARATE bug from the encode()-concurrency one above, found immediately
# after fixing it: live-reproduced 2026-07-22 running rag_presolve at
# concurrency=4 -- the SAME dtype-mismatch crash recurred even with
# encode() calls serialized, because the lazy-singleton check below
# (`if _model is None: construct it`) is itself a classic check-then-act
# race. With 4 threads calling _get_mxbai_model() near-simultaneously on
# a fresh process (all seeing the module-level global as None before any
# of them finishes assigning it), MULTIPLE threads each start constructing
# their own SentenceTransformer instance concurrently -- racing on the
# underlying torch weight materialization from the same cached safetensors
# file, which is where the mixed-dtype corruption actually came from (the
# encode()-lock above only protects the STEADY STATE, once one model
# object is safely cached; it does nothing for the initial construction
# race). Fixed with the standard double-checked-locking idiom: only ONE
# thread ever constructs the model; every other thread blocks on the lock
# and then reads the already-set global instead of racing to build its own.
_model_lock = threading.Lock()
_mxbai_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # re-check: another thread may have built it while we waited for the lock
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


def _get_mxbai_model():
    global _mxbai_model
    if _mxbai_model is None:
        with _mxbai_model_lock:
            if _mxbai_model is None:  # re-check: another thread may have built it while we waited for the lock
                from sentence_transformers import SentenceTransformer

                _mxbai_model = SentenceTransformer(MXBAI_MODEL_NAME, device="cpu")
    return _mxbai_model


def embed_texts(texts: list[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
    """Encodes `texts` to float32 embeddings, shape (len(texts), EMBEDDING_DIM).

    L2-normalizes by default so dot product == cosine similarity at query
    time (cheaper than re-normalizing on every query).
    """
    if not texts:
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
    model = _get_model()
    with _encode_lock:
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


def embed_query_mxbai(query: str) -> np.ndarray:
    """Query-side embedding for the mxbai-embed-large-v1 corpus.

    Unlike bge-small, mxbai-embed-large-v1's model card specifies a
    required retrieval query prompt ("Represent this sentence for
    searching relevant passages: "), applied to QUERIES only, never to
    indexed passages -- `prompt_name="query"` invokes the prompt baked
    into the model's own config. Returns a float32, L2-normalized,
    MXBAI_EMBEDDING_DIM-dim vector.
    """
    model = _get_mxbai_model()
    with _encode_lock:
        vector = model.encode(
            query,
            prompt_name="query",
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
    return vector.astype(np.float32)


def get_query_embedder(model_name: str | None):
    """Returns the `str -> np.ndarray` query-embedding function matching
    `model_name` (as recorded in an index DB's build_progress.embedding_model).

    `None` or MODEL_NAME both resolve to the default bge-small embedder --
    `None` covers indexes built before embedding_model was tracked (all of
    which used bge-small, the only model that existed at the time). Raises
    ValueError for any other unrecognized name rather than silently
    embedding in the wrong space.
    """
    if model_name is None or model_name == MODEL_NAME:
        return embed_query
    if model_name == MXBAI_MODEL_NAME:
        return embed_query_mxbai
    raise ValueError(f"no query embedder registered for model {model_name!r}")
