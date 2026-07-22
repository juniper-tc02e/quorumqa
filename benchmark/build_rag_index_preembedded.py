"""Builds a RAG index from a PRE-EMBEDDED HF Wikipedia dataset -- ingests
passage text + already-computed embedding vectors directly into the
RagIndex SQLite store, without recomputing embeddings locally (see
quorumqa.rag.preembedded's module docstring for why, and
docs/rag-corpus-notes.md for the full provenance writeup).

This is the throughput fix for the from-scratch build's CPU-embedding
bottleneck (benchmark/build_rag_index.py: ~1.6 kept-articles/s with
bge-small on CPU, ~29-100h for a 200k-article corpus). Here, embedding
compute is zero -- the build is bounded by HF download bandwidth for
streaming the source parquet shards, not by CPU.

CRITICAL: this corpus's embedding model
(mixedbread-ai/mxbai-embed-large-v1, 1024-dim) is NOT the project's
default bge-small-en-v1.5 (384-dim) -- writes the model name into
build_progress.embedding_model so mcp_server.search_corpus picks the
matching query encoder automatically (quorumqa.rag.embeddings.
get_query_embedder). Never point QUORUMQA_RAG_DB at an index built by
this script while assuming bge-small query encoding -- the dimension
guard in store.RagIndex.dense_search will raise, not silently degrade.

Usage:
  python benchmark/build_rag_index_preembedded.py --max-passages 2000 --db-path benchmark/data/rag_index_preembedded_smoke.sqlite3
  python benchmark/build_rag_index_preembedded.py --max-passages 150000 --db-path benchmark/data/rag_index_preembedded.sqlite3
  # re-run the same command to resume an interrupted build
"""

from __future__ import annotations

import argparse
import itertools
import logging
import sys
import time
from pathlib import Path

import numpy as np
from datasets import load_dataset

from quorumqa.rag import store
from quorumqa.rag.chunking import Chunk
from quorumqa.rag.preembedded import (
    SOURCE_DATASET_ID,
    SOURCE_EMBEDDING_MODEL,
    SOURCE_LICENSE,
    DimensionMismatchError,
    group_into_articles,
    is_stem_row,
    map_row,
)

log = logging.getLogger("build_rag_index_preembedded")

# Pinned revision (git-style commit sha on the HF dataset repo) so the
# corpus snapshot is reproducible even if the dataset's `main` branch
# changes later -- verified 2026-07-22 via
# https://huggingface.co/api/datasets/Laz4rz/wikipedia_stem_small_rag_embeddings
DATASET_REVISION = "e51169b853c6f03b256521d535a991826c8a4bbf"
SNAPSHOT_ID = f"{SOURCE_DATASET_ID}@{DATASET_REVISION}"

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "rag_index_preembedded.sqlite3"


def build(
    db_path: Path,
    max_passages: int | None,
    batch_articles: int = 200,
    log_every: int = 5000,
    checkpoint_scanned: int = 5000,
    rows: list[dict] | None = None,
) -> dict:
    """`rows`, if given, replaces the real HF stream with this in-memory
    list (test-only hook -- see tests/test_build_rag_index_preembedded.py).
    Real callers (main() below) always leave this None, which streams the
    live HF dataset exactly as before."""
    conn = store.open_for_build(db_path)
    progress = store.get_progress(conn)
    rows_scanned = progress.get("articles_scanned") or 0
    articles_kept = progress.get("articles_kept") or 0
    passages_written = progress.get("passages_written") or 0
    prior_snapshot = progress.get("snapshot_id")

    if prior_snapshot and prior_snapshot != SNAPSHOT_ID:
        raise RuntimeError(
            f"DB at {db_path} was built from snapshot {prior_snapshot!r}; "
            f"refusing to mix in {SNAPSHOT_ID!r}. Use a fresh --db-path."
        )

    # The source dataset has cross-category duplicates: the SAME Wikipedia
    # article (same url) reappears verbatim under more than one field-of-
    # science category bucket (observed e.g. the CRISPR article present
    # 3x, non-contiguously, in the raw stream -- presumably tagged under
    # multiple science-field categories upstream). Without this guard,
    # duplicate copies of the same article's chunks get written as
    # separate passages, wasting index space and -- worse -- letting the
    # SAME article occupy multiple slots in a fused top-k search result.
    # seen_article_ids is seeded from what's ALREADY in the DB (relevant
    # on a resumed build, where this set would otherwise start empty and
    # miss duplicates of articles written in an earlier run) and grown as
    # new articles are kept.
    seen_article_ids: set[str] = {
        row["article_id"] for row in conn.execute("SELECT DISTINCT article_id FROM passages")
    }

    log.info(
        "Resuming build at %s: rows_scanned=%d articles_kept=%d passages_written=%d seen_article_ids=%d",
        db_path, rows_scanned, articles_kept, passages_written, len(seen_article_ids),
    )

    if rows is not None:
        stream = iter(rows)
    else:
        ds = load_dataset(SOURCE_DATASET_ID, split="train", revision=DATASET_REVISION, streaming=True)
        stream = iter(ds)
    if rows_scanned:
        stream = itertools.islice(stream, rows_scanned, None)

    pending: list = []  # MappedPassage buffer, flushed on article boundary
    scanned_since_checkpoint = 0
    last_logged_kept = passages_written
    start = time.time()
    stream_exhausted = False
    prior_url: str | None = None
    prior_chunk_index = -1
    current_article_kept = False

    def flush(final: bool = False) -> None:
        """Writes complete article-groups from `pending` to the store. On a
        non-final flush, the LAST group is kept back (it may still be
        receiving chunks from the next rows in the stream); on a final
        flush every group is written. Returns nothing -- updates
        passages_written/articles_kept via the enclosing closure."""
        nonlocal passages_written, articles_kept
        if not pending:
            return
        groups = group_into_articles(pending)
        write_upto = len(groups) if final else max(0, len(groups) - 1)
        if write_upto == 0:
            return
        for article_id, title, group_passages in groups[:write_upto]:
            chunks = [
                Chunk(chunk_index=p.chunk_index, title=p.title, text=p.text, word_count=p.word_count)
                for p in group_passages
            ]
            vectors = np.stack([p.vector for p in group_passages])
            store.add_article(
                conn, article_id, title, chunks, vectors,
                group_passages[0].source_url, SNAPSHOT_ID,
            )
            passages_written += len(chunks)
            articles_kept += 1
        conn.commit()
        kept_groups = groups[write_upto:]
        pending.clear()
        for _, _, group_passages in kept_groups:
            pending.extend(group_passages)

    def checkpoint() -> None:
        store.set_progress(
            conn,
            articles_scanned=rows_scanned,
            articles_kept=articles_kept,
            passages_written=passages_written,
            snapshot_id=SNAPSHOT_ID,
            dataset_config=SOURCE_DATASET_ID,
            embedding_model=SOURCE_EMBEDDING_MODEL,
        )

    try:
        for row in stream:
            rows_scanned += 1
            scanned_since_checkpoint += 1

            row_url = row.get("url")
            if row_url != prior_url:
                # New article boundary (by source url) -- reset the running
                # chunk-index counter BEFORE calling map_row, so a filtered
                # first-chunk-of-a-new-article row can never leak a stale
                # chunk_index from the PREVIOUS article into this one (see
                # module docstring / preembedded.map_row's docstring on
                # prior_url/prior_chunk_index threading). Also (re)compute
                # the article-level STEM decision ONCE here, from this
                # first-seen chunk, and reuse it for every later chunk of
                # the same article (see preembedded.is_stem_row's docstring
                # on why this must not be re-derived per chunk) -- UNLESS
                # this url was already kept earlier in the stream (a
                # cross-category duplicate, see seen_article_ids above),
                # in which case it's rejected outright without re-running
                # the STEM check.
                prior_chunk_index = -1
                if row_url is not None and row_url in seen_article_ids:
                    current_article_kept = False
                else:
                    current_article_kept = is_stem_row(row)
                    if current_article_kept and row_url is not None:
                        seen_article_ids.add(row_url)

            try:
                mapped = map_row(
                    row,
                    article_kept=current_article_kept,
                    prior_url=prior_url,
                    prior_chunk_index=prior_chunk_index,
                    row_index=rows_scanned,
                )
            except DimensionMismatchError as exc:
                log.error("Aborting build: %s (row %d)", exc, rows_scanned)
                raise

            prior_url = row_url
            if mapped is not None:
                prior_chunk_index = mapped.chunk_index
                pending.append(mapped)

            need_flush = len(pending) >= batch_articles * 5 or scanned_since_checkpoint >= checkpoint_scanned
            if need_flush:
                flush()
                checkpoint()
                scanned_since_checkpoint = 0

            if passages_written - last_logged_kept >= log_every:
                elapsed = time.time() - start
                rate = rows_scanned / elapsed if elapsed else 0.0
                log.info(
                    "scanned=%d kept_articles=%d passages=%d elapsed=%.0fs (%.1f rows/s)",
                    rows_scanned, articles_kept, passages_written, elapsed, rate,
                )
                last_logged_kept = passages_written

            if max_passages is not None and passages_written >= max_passages:
                break
        else:
            stream_exhausted = True
    finally:
        flush(final=True)
        checkpoint()
        conn.close()

    complete = stream_exhausted or (max_passages is not None and passages_written >= max_passages)
    return {
        "rows_scanned": rows_scanned,
        "articles_kept": articles_kept,
        "passages_written": passages_written,
        "complete": complete,
        "elapsed_s": time.time() - start,
        "source_dataset": SOURCE_DATASET_ID,
        "source_license": SOURCE_LICENSE,
        "embedding_model": SOURCE_EMBEDDING_MODEL,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-passages", type=int, default=150_000, help="Stop once this many passages are written (default 150000). Use a small value for a smoke test.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help=f"SQLite index path (default {DEFAULT_DB_PATH})")
    parser.add_argument("--batch-articles", type=int, default=200, help="Approx. articles per commit batch (default 200)")
    parser.add_argument("--log-every", type=int, default=5000, help="Log progress every N passages written (default 5000)")
    parser.add_argument("--checkpoint-scanned", type=int, default=5000, help="Force a checkpoint every N rows scanned (default 5000)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if not args.verbose else logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    result = build(
        db_path=args.db_path,
        max_passages=args.max_passages,
        batch_articles=args.batch_articles,
        log_every=args.log_every,
        checkpoint_scanned=args.checkpoint_scanned,
    )
    log.info("Build result: %s", result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
