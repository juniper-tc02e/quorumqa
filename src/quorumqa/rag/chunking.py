"""Splits article text into title-prefixed passages of ~300-500 tokens.

Token counting here is a cheap whitespace-word proxy, not a real BPE
tokenizer -- pulling in a tokenizer just to size chunks would be a real
dependency for a rough sizing knob. English word count and BPE token count
for prose are close enough (empirically ~0.7-0.8 words per token, i.e. a
given word budget slightly UNDER-counts true tokens) that a 300-500 *word*
target chunk still lands in the right ballpark for a 300-500 *token* spec;
documented here so nobody mistakes `_WORDS_PER_CHUNK_MIN/MAX` for an exact
tokenizer count.
"""

from __future__ import annotations

from dataclasses import dataclass

_WORDS_PER_CHUNK_MIN = 300
_WORDS_PER_CHUNK_MAX = 500


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    title: str
    text: str
    """Full passage text INCLUDING the title prefix -- this is what gets
    embedded and FTS-indexed, so title terms are always retrievable."""
    word_count: int


def chunk_text(
    title: str,
    body: str,
    min_words: int = _WORDS_PER_CHUNK_MIN,
    max_words: int = _WORDS_PER_CHUNK_MAX,
) -> list[Chunk]:
    """Splits `body` into word-bounded chunks, each prefixed with `title`.

    Chunk boundaries fall on paragraph breaks where possible (keeps a
    passage from splitting mid-thought), falling back to a hard word-count
    cut for paragraphs longer than `max_words` on their own. The final
    chunk of an article is allowed to run short (min_words is a target, not
    a hard floor) rather than being dropped or merged with padding.

    Returns [] for empty/whitespace-only bodies.
    """
    if min_words <= 0 or max_words < min_words:
        raise ValueError(f"invalid chunk bounds: min_words={min_words}, max_words={max_words}")

    paragraphs = [p.split() for p in body.split("\n") if p.strip()]
    paragraphs = [words for words in paragraphs if words]
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        text = f"{title}\n\n{' '.join(current)}"
        chunks.append(Chunk(chunk_index=len(chunks), title=title, text=text, word_count=len(current)))

    for para_words in paragraphs:
        if len(para_words) > max_words:
            # Paragraph alone exceeds the chunk cap: flush whatever's
            # pending, then hard-slice this paragraph on its own.
            flush()
            current = []
            for i in range(0, len(para_words), max_words):
                current = para_words[i : i + max_words]
                flush()
                current = []
            continue

        if current and len(current) + len(para_words) > max_words:
            flush()
            current = []
        current.extend(para_words)
        if len(current) >= min_words:
            flush()
            current = []

    flush()
    return chunks
