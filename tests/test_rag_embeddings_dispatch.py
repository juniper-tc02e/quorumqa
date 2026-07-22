"""Offline test for quorumqa.rag.embeddings.get_query_embedder -- pure
dispatch logic only, does NOT load either sentence-transformers model (no
network, no torch model download), matching this project's offline-test
discipline for the rag package.
"""

from __future__ import annotations

import pytest

from quorumqa.rag import embeddings


def test_get_query_embedder_none_resolves_to_default_bge_small():
    assert embeddings.get_query_embedder(None) is embeddings.embed_query


def test_get_query_embedder_explicit_default_model_name():
    assert embeddings.get_query_embedder(embeddings.MODEL_NAME) is embeddings.embed_query


def test_get_query_embedder_mxbai_model_name():
    assert embeddings.get_query_embedder(embeddings.MXBAI_MODEL_NAME) is embeddings.embed_query_mxbai


def test_get_query_embedder_unknown_model_raises():
    with pytest.raises(ValueError):
        embeddings.get_query_embedder("some/other-model-v9")
