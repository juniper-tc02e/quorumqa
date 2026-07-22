"""Builds the G0 STEM-subset Wikipedia RAG index (docs/recursive-rag-plan.md
section 6, phase G0).

PROVENANCE (firewall section 4): streams HF `wikimedia/wikipedia`, config
`20231101.en` (the 2023-11-01 dump snapshot), split=train -- a general
encyclopedia corpus, unrelated to and independent of any benchmark question
set. SUBSET RULE: keep an article iff quorumqa.rag.subset.is_stem_article
matches its title or lead text against a STEM keyword allowlist (physics,
chemistry, biology/medicine, engineering, mathematics); see subset.py's
docstring for the full rationale. Each kept article is chunked into
300-500 word title-prefixed passages (quorumqa.rag.chunking), embedded
with BAAI/bge-small-en-v1.5 (quorumqa.rag.embeddings), and written to a
SQLite index (quorumqa.rag.store) with an FTS5 BM25 index and float16
dense vectors.

RESUMABLE: `articles_scanned` (a count of stream rows consumed, kept or
not) is checkpointed into the DB's build_progress row after every batch
commit -- both on a normal batch boundary and every `--checkpoint-scanned`
rows scanned (so a hard kill mid-scan loses at most that many rows of
rework, not the whole run). Re-running with the same --db-path resumes by
skipping that many rows of the deterministic, unshuffled HF stream before
resuming work; a `finally` block guarantees the last batch and progress
row are flushed even on Ctrl+C or an unhandled exception.

Usage:
  python benchmark/build_rag_index.py --max-articles 2000 --db-path benchmark/data/rag_index_smoke.sqlite3
  python benchmark/build_rag_index.py --max-articles 200000 --db-path benchmark/data/rag_index.sqlite3
  # re-run the same command to resume an interrupted build
"""

from __future__ import annotations

import argparse
import itertools
import logging
import sys
import time
from pathlib import Path

from datasets import load_dataset

from quorumqa.rag import store
from quorumqa.rag.chunking import chunk_text
from quorumqa.rag.embeddings import embed_texts
from quorumqa.rag.subset import is_stem_article

log = logging.getLogger("build_rag_index")

DATASET_ID = "wikimedia/wikipedia"
DATASET_CONFIG = "20231101.en"
SNAPSHOT_ID = f"{DATASET_ID}:{DATASET_CONFIG}"

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "rag_index.sqlite3"


def build(
    db_path: Path,
    max_articles: int | None,
    batch_articles: int = 25,
    log_every: int = 500,
    checkpoint_scanned: int = 2000,
    embed_batch_size: int = 32,
) -> dict:
    conn = store.open_for_build(db_path)
    progress = store.get_progress(conn)
    articles_scanned = progress.get("articles_scanned") or 0
    articles_kept = progress.get("articles_kept") or 0
    passages_written = progress.get("passages_written") or 0
    prior_snapshot = progress.get("snapshot_id")

    if prior_snapshot and prior_snapshot != SNAPSHOT_ID:
        raise RuntimeError(
            f"DB at {db_path} was built from snapshot {prior_snapshot!r}; "
            f"refusing to mix in {SNAPSHOT_ID!r}. Use a fresh --db-path."
        )

    log.info(
        "Resuming build at %s: articles_scanned=%d articles_kept=%d passages_written=%d",
        db_path, articles_scanned, articles_kept, passages_written,
    )

    ds = load_dataset(DATASET_ID, DATASET_CONFIG, split="train", streaming=True)
    stream = iter(ds)
    if articles_scanned:
        stream = itertools.islice(stream, articles_scanned, None)

    batch_ids: list[str] = []
    batch_titles: list[str] = []
    batch_chunks: list[list] = []
    batch_urls: list[str | None] = []
    scanned_since_checkpoint = 0
    last_logged_kept = articles_kept
    start = time.time()
    stream_exhausted = False

    def flush_batch() -> None:
        nonlocal passages_written
        if not batch_chunks:
            return
        flat_texts = [c.text for chunks in batch_chunks for c in chunks]
        vectors = embed_texts(flat_texts, batch_size=embed_batch_size)
        offset = 0
        for article_id, title, chunks, url in zip(batch_ids, batch_titles, batch_chunks, batch_urls):
            n = len(chunks)
            vecs = vectors[offset : offset + n]
            offset += n
            store.add_article(conn, article_id, title, chunks, vecs, url, SNAPSHOT_ID)
            passages_written += n
        conn.commit()
        batch_ids.clear()
        batch_titles.clear()
        batch_chunks.clear()
        batch_urls.clear()

    def checkpoint() -> None:
        store.set_progress(
            conn,
            articles_scanned=articles_scanned,
            articles_kept=articles_kept,
            passages_written=passages_written,
            snapshot_id=SNAPSHOT_ID,
            dataset_config=DATASET_CONFIG,
        )

    try:
        for row in stream:
            articles_scanned += 1
            scanned_since_checkpoint += 1
            title = row.get("title") or ""
            text = row.get("text") or ""
            if is_stem_article(title, text):
                chunks = chunk_text(title, text)
                if chunks:
                    batch_ids.append(str(row.get("id")))
                    batch_titles.append(title)
                    batch_chunks.append(chunks)
                    batch_urls.append(row.get("url"))
                    articles_kept += 1

            need_flush = len(batch_ids) >= batch_articles or scanned_since_checkpoint >= checkpoint_scanned
            if need_flush:
                flush_batch()
                checkpoint()
                scanned_since_checkpoint = 0

            if articles_kept - last_logged_kept >= log_every:
                elapsed = time.time() - start
                rate = articles_scanned / elapsed if elapsed else 0.0
                log.info(
                    "scanned=%d kept=%d passages=%d elapsed=%.0fs (%.1f scanned/s)",
                    articles_scanned, articles_kept, passages_written, elapsed, rate,
                )
                last_logged_kept = articles_kept

            if max_articles is not None and articles_kept >= max_articles:
                break
        else:
            stream_exhausted = True
    finally:
        flush_batch()
        checkpoint()
        conn.close()

    complete = stream_exhausted or (max_articles is not None and articles_kept >= max_articles)
    return {
        "articles_scanned": articles_scanned,
        "articles_kept": articles_kept,
        "passages_written": passages_written,
        "complete": complete,
        "elapsed_s": time.time() - start,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-articles", type=int, default=200_000, help="Stop once this many STEM articles are kept (default 200000). Use a small value for a smoke test.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help=f"SQLite index path (default {DEFAULT_DB_PATH})")
    parser.add_argument("--batch-size", type=int, default=25, help="Kept articles per embed/commit batch (default 25)")
    parser.add_argument("--log-every", type=int, default=500, help="Log progress every N kept articles (default 500)")
    parser.add_argument("--checkpoint-scanned", type=int, default=2000, help="Force a checkpoint every N scanned rows even without a full kept-batch (default 2000)")
    parser.add_argument("--embed-batch-size", type=int, default=32, help="sentence-transformers encode() batch size (default 32)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if not args.verbose else logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    result = build(
        db_path=args.db_path,
        max_articles=args.max_articles,
        batch_articles=args.batch_size,
        log_every=args.log_every,
        checkpoint_scanned=args.checkpoint_scanned,
        embed_batch_size=args.embed_batch_size,
    )
    log.info("Build result: %s", result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
