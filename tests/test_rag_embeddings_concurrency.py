"""Regression test for a live-reproduced concurrency bug: calling
quorumqa.rag.embeddings' cached SentenceTransformer .encode() from more
than one thread at once raised "RuntimeError: mat1 and mat2 must have the
same dtype, but got Half and Float" inside the model's forward pass (seen
running the rag_presolve lever at concurrency=2 -- one of two simultaneous
embed_query_mxbai() calls crashed, dropping that question). Fixed with a
module-level threading.Lock serializing every encode() call. This test uses
a fake model (no real sentence-transformers/torch load) to assert the lock
actually prevents overlapping encode() calls -- it does not reproduce the
dtype error itself (that requires the real model), only the serialization
contract that fixes it.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest
import sentence_transformers as st_module

from quorumqa.rag import embeddings


@pytest.fixture(autouse=True)
def _reset_model_singletons():
    """The double-checked-locking tests below deliberately poke
    embeddings._model / _mxbai_model to force a construction race -- reset
    both to their real pre-test state afterward so a fake model object
    never leaks into a later test (e.g. test_rag_mcp_tool.py's real-index
    test, which needs the REAL cached SentenceTransformer)."""
    saved_model, saved_mxbai = embeddings._model, embeddings._mxbai_model
    yield
    embeddings._model, embeddings._mxbai_model = saved_model, saved_mxbai


class _FakeModel:
    """Records how many threads are simultaneously inside .encode() --
    max_concurrent()==1 proves calls never overlap."""

    def __init__(self, dim: int, sleep_s: float = 0.03):
        self._dim = dim
        self._sleep_s = sleep_s
        self._active = 0
        self._max_active = 0
        self._lock = threading.Lock()  # protects the bookkeeping counters only

    def max_concurrent(self) -> int:
        return self._max_active

    def encode(self, texts_or_query, **kwargs):
        with self._lock:
            self._active += 1
            self._max_active = max(self._max_active, self._active)
        time.sleep(self._sleep_s)
        with self._lock:
            self._active -= 1
        n = len(texts_or_query) if isinstance(texts_or_query, list) else 1
        return np.zeros((n, self._dim), dtype=np.float32) if isinstance(texts_or_query, list) else np.zeros(self._dim, dtype=np.float32)


def test_embed_texts_never_overlaps_across_threads(monkeypatch):
    fake = _FakeModel(dim=embeddings.EMBEDDING_DIM)
    monkeypatch.setattr(embeddings, "_get_model", lambda: fake)

    threads = [threading.Thread(target=embeddings.embed_texts, args=(["hello"],)) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert fake.max_concurrent() == 1


def test_embed_query_mxbai_never_overlaps_across_threads(monkeypatch):
    fake = _FakeModel(dim=embeddings.MXBAI_EMBEDDING_DIM)
    monkeypatch.setattr(embeddings, "_get_mxbai_model", lambda: fake)

    threads = [threading.Thread(target=embeddings.embed_query_mxbai, args=("query text",)) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert fake.max_concurrent() == 1


def test_bge_and_mxbai_encode_share_one_global_lock(monkeypatch):
    # Both embedders must serialize against EACH OTHER too (they share
    # process-wide GIL-adjacent CPU resources) -- not just against
    # themselves. Verified by having a slow bge call block a concurrently
    # started mxbai call.
    combined_active = {"n": 0, "max": 0}
    lock = threading.Lock()

    class SlowModel:
        def __init__(self, dim, sleep_s):
            self._dim = dim
            self._sleep_s = sleep_s

        def encode(self, texts_or_query, **kwargs):
            with lock:
                combined_active["n"] += 1
                combined_active["max"] = max(combined_active["max"], combined_active["n"])
            time.sleep(self._sleep_s)
            with lock:
                combined_active["n"] -= 1
            n = len(texts_or_query) if isinstance(texts_or_query, list) else 1
            return np.zeros((n, self._dim), dtype=np.float32) if isinstance(texts_or_query, list) else np.zeros(self._dim, dtype=np.float32)

    monkeypatch.setattr(embeddings, "_get_model", lambda: SlowModel(embeddings.EMBEDDING_DIM, 0.05))
    monkeypatch.setattr(embeddings, "_get_mxbai_model", lambda: SlowModel(embeddings.MXBAI_EMBEDDING_DIM, 0.05))

    t1 = threading.Thread(target=embeddings.embed_texts, args=(["hello"],))
    t2 = threading.Thread(target=embeddings.embed_query_mxbai, args=("query text",))
    t1.start()
    time.sleep(0.01)  # ensure t1 is inside encode() before t2 starts
    t2.start()
    t1.join()
    t2.join()

    assert combined_active["max"] == 1


# ---------------------------------------------------------------------------
# Double-checked-locking regression: the SECOND bug found (2026-07-22, live,
# at concurrency=4) -- the lazy-singleton check-then-act pattern in
# _get_model/_get_mxbai_model raced independently of the encode()-lock
# above. Multiple threads all seeing the cached-model global as None at
# once each started constructing their OWN SentenceTransformer instance
# concurrently, corrupting the underlying torch weight materialization
# (the same "Half vs Float" crash as the encode() bug, but from
# construction, not from a serialized encode() call).
# ---------------------------------------------------------------------------


class _FakeSentenceTransformer:
    """Records how many instances get constructed, and how long each
    construction takes (to widen the race window) -- a fake stand-in for
    the real (heavy, slow-to-download) SentenceTransformer class."""

    construction_count = 0
    _count_lock = threading.Lock()

    def __init__(self, model_name, device="cpu", sleep_s: float = 0.05):
        with _FakeSentenceTransformer._count_lock:
            _FakeSentenceTransformer.construction_count += 1
        time.sleep(sleep_s)
        self.model_name = model_name


def test_get_model_constructs_exactly_once_under_concurrent_first_access(monkeypatch):
    embeddings._model = None
    _FakeSentenceTransformer.construction_count = 0
    monkeypatch.setattr(st_module, "SentenceTransformer", _FakeSentenceTransformer)

    results = []
    results_lock = threading.Lock()

    def worker():
        m = embeddings._get_model()
        with results_lock:
            results.append(m)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert _FakeSentenceTransformer.construction_count == 1
    assert len({id(r) for r in results}) == 1  # every thread got back the SAME instance


def test_get_mxbai_model_constructs_exactly_once_under_concurrent_first_access(monkeypatch):
    embeddings._mxbai_model = None
    _FakeSentenceTransformer.construction_count = 0
    monkeypatch.setattr(st_module, "SentenceTransformer", _FakeSentenceTransformer)

    results = []
    results_lock = threading.Lock()

    def worker():
        m = embeddings._get_mxbai_model()
        with results_lock:
            results.append(m)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert _FakeSentenceTransformer.construction_count == 1
    assert len({id(r) for r in results}) == 1
