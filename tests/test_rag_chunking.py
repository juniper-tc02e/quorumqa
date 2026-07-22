from quorumqa.rag.chunking import chunk_text


def test_empty_body_yields_no_chunks():
    assert chunk_text("Title", "") == []
    assert chunk_text("Title", "   \n  \n") == []


def test_short_body_is_one_chunk_with_title_prefix():
    chunks = chunk_text("Photon", "A photon is a quantum of light.", min_words=300, max_words=500)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("Photon\n\n")
    assert "photon is a quantum" in chunks[0].text
    assert chunks[0].chunk_index == 0


def test_long_body_splits_into_multiple_chunks_within_bounds():
    # One long paragraph of 1200 words -> should split into multiple
    # chunks, each within [min_words, max_words] except possibly the last.
    paragraph = " ".join(f"word{i}" for i in range(1200))
    chunks = chunk_text("Big Article", paragraph, min_words=300, max_words=500)

    assert len(chunks) >= 3
    for c in chunks[:-1]:
        assert 1 <= c.word_count <= 500
    assert chunks[-1].word_count >= 1
    # chunk_index is sequential starting at 0
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    # every chunk still carries the title prefix
    for c in chunks:
        assert c.text.startswith("Big Article\n\n")


def test_reconstructs_all_words_no_loss_no_duplication():
    words = [f"tok{i}" for i in range(950)]
    paragraph = " ".join(words)
    chunks = chunk_text("T", paragraph, min_words=300, max_words=500)

    reconstructed = []
    for c in chunks:
        body = c.text[len("T\n\n") :]
        reconstructed.extend(body.split())
    assert reconstructed == words


def test_paragraph_breaks_preferred_as_boundaries():
    para_a = " ".join(f"a{i}" for i in range(280))
    para_b = " ".join(f"b{i}" for i in range(280))
    body = para_a + "\n" + para_b
    chunks = chunk_text("T", body, min_words=300, max_words=500)

    # 280 + 280 = 560 > 500, so paragraphs should not be forced into one
    # chunk -- expect a boundary between them.
    assert len(chunks) == 2
    assert "a279" in chunks[0].text
    assert "b0" in chunks[1].text


def test_invalid_bounds_raise():
    import pytest

    with pytest.raises(ValueError):
        chunk_text("T", "some text", min_words=0, max_words=500)
    with pytest.raises(ValueError):
        chunk_text("T", "some text", min_words=500, max_words=100)
