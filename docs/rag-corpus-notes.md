# RAG corpus notes: G0.5 pre-embedded STEM-Wikipedia corpus

Written 2026-07-22. Records the corpus choice, license, embedding model,
and build provenance for the throughput fix described below. Companion to
docs/recursive-rag-plan.md (G0 phase) -- this documents the G0.5 patch to
that phase's build path, not a change to the retrieval design itself.

## The problem

`benchmark/build_rag_index.py` (the G0 from-scratch build) streams HF
`wikimedia/wikipedia` (config `20231101.en`), keeps STEM-topical articles,
and embeds every kept chunk locally with `BAAI/bge-small-en-v1.5` on CPU.
Observed throughput on this build machine: ~1.6 kept-articles/s (a partial
run reached 15,900 kept articles / 48,256 passages after ~2h17m). A
200k-article target corpus at that rate is a many-hour build -- impractical
for this project's timeline. Embedding compute, not I/O or the STEM
filter, is the bottleneck (both are cheap regex/tokenization operations).

## The fix: ingest an already-embedded corpus

Rather than compute embeddings locally, `benchmark/build_rag_index_
preembedded.py` (via `quorumqa.rag.preembedded`) ingests a HF dataset that
ships passage text **and precomputed embedding vectors together**,
writing both directly into `quorumqa.rag.store`'s existing SQLite schema
with zero local embedding compute. Build time is then bounded by HF
download bandwidth, not CPU.

## Chosen dataset

**`Laz4rz/wikipedia_stem_small_rag_embeddings`**
(https://huggingface.co/datasets/Laz4rz/wikipedia_stem_small_rag_embeddings),
pinned revision `e51169b853c6f03b256521d535a991826c8a4bbf`.

| Property | Value |
|---|---|
| Source content | Wikipedia articles pre-filtered to STEM fields (per the dataset card, derived from HF `millawell/wikipedia_field_of_science`) |
| License | **CC-BY-SA-3.0**, explicitly declared in the dataset's `license:` card metadata (verified via the HF datasets-server `/info` API and the repo's own README frontmatter) |
| Rows (chunks) | 518,092 total in the source dataset; this build ingests a subset (see "What we actually loaded" below) |
| Chunking | ~512-token chunks, title-prefixed, paragraph-preserving splits of longer articles (per the dataset README) |
| Columns | `text`, `category`, `url`, `title`, `embeddings` (float64 sequence) |
| Embedding model | **`mixedbread-ai/mxbai-embed-large-v1`** (per the dataset card: "Embedded using mixedbread-ai/mxbai-embed-large-v1, with truncation to 512 tokens") |
| Embedding dimension | **1024** (verified directly against live rows via the datasets-server `/rows` API) |
| Embedding model license | Apache-2.0 (verified via the HF model API's `cardData.license`), locally runnable via `sentence-transformers` -- no paid API calls |
| Embedding vector norm | NOT L2-normalized in the source (observed norm ~16-17 on live rows) -- normalized to unit length by this project's loader at ingest time; cosine similarity is scale-invariant per vector, so this is lossless |

### Candidates checked and rejected

- **`Cohere/wikipedia-2023-11-embed-multilingual-v3`** (renamed to
  `CohereLabs/wikipedia-2023-11-embed-multilingual-v3`) and
  **`Cohere/wikipedia-22-12-en-embeddings`**: embedded with Cohere's
  hosted `embed-multilingual-v3`/`embed-multilingual-22-12` models --
  **not runnable locally**, and this project's constraint is no paid
  model API calls. Query-time re-encoding would require the same paid
  Cohere API, which is a hard blocker per the task constraints.
- **`567-labs/wikipedia-embedding-bge-small-en-v1.5-five-percent`** (and
  its `-sample` sibling): embedded with **`BAAI/bge-small-en-v1.5`** --
  the SAME model this project's from-scratch build already uses (exact
  dimension match, 384-dim, zero query-encoder change needed). Rejected
  anyway: **the dataset card carries no `license:` field at all** (checked
  via both the HF API's `cardData` and the raw README frontmatter) --
  fails this task's explicit "clear open license" requirement, even
  though the underlying Wikipedia text is CC-BY-SA and the embedding
  model is Apache-2.0. Noted here in case a future pass wants to revisit
  this once/if the uploader adds an explicit license (it would be the
  lower-friction choice, since it needs no query-encoder change).
- **`tommymarto/STEM-wikipedia-22-12-en-embeddings-all-MiniLM-L6-v2`**:
  already STEM-filtered (2.25M paragraphs), embedded with
  `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0, local, 384-dim).
  A reasonable second choice, but its HF card also has no `license:` tag
  for the dataset itself (only inferred from the constituent parts, same
  gap as 567-labs above) -- `Laz4rz`'s explicit `cc-by-sa-3.0` tag made it
  the cleaner pick.

## Critical constraint: query encoder must match the index

The embedding model used to BUILD an index (`mxbai-embed-large-v1`,
1024-dim, for this corpus) must be the SAME model used to encode queries
at search time -- embedding spaces from different models are not
comparable, and this project's default query encoder
(`BAAI/bge-small-en-v1.5`, 384-dim) is a **different model** used by the
from-scratch build path.

This is handled structurally, not just by convention:

1. `quorumqa.rag.store`'s `build_progress` table gained an
   `embedding_model` column (migration in `store.ensure_schema`). Every
   index built by `build_rag_index_preembedded.py` records
   `mixedbread-ai/mxbai-embed-large-v1` there; the from-scratch builder's
   indexes leave it unset (implicitly bge-small, the only model that
   existed when they were built).
2. `quorumqa.rag.embeddings.get_query_embedder(model_name)` dispatches to
   the matching query-embedding function (`embed_query` for
   bge-small/`None`, `embed_query_mxbai` for mxbai), raising `ValueError`
   for anything unrecognized rather than silently guessing.
3. `quorumqa.tools.mcp_server.search_corpus` reads the OPEN index's
   recorded `embedding_model` and calls `get_query_embedder` before
   embedding the query -- the right encoder is picked automatically per
   index, not hardcoded.
4. As a last-resort trip wire, `RagIndex.dense_search` already raised
   (pre-existing code) if the query vector's dimension doesn't match the
   index's stored dimension -- this still fires if the wiring above is
   ever bypassed (e.g. a hand-rolled caller that skips
   `get_query_embedder`).

`mxbai-embed-large-v1`'s model card specifies a retrieval query prompt
("Represent this sentence for searching relevant passages: ") that must
be applied to queries but NOT to indexed passages -- `embed_query_mxbai`
applies it via `prompt_name="query"`; indexed text is embedded (by the
dataset's original authors) without any prefix.

## Firewall compliance (docs/recursive-rag-plan.md section 4)

- **Never index benchmark-derived content.** This corpus is general
  Wikipedia STEM content sourced from `millawell/wikipedia_field_of_science`
  -- independent of and unrelated to any QuorumQA benchmark's question
  set, question dump, or answer key.
- **Labeled numbers.** The build records a `snapshot_id` of
  `Laz4rz/wikipedia_stem_small_rag_embeddings@e51169b853c6f03b256521d535a991826c8a4bbf`
  in `build_progress`, distinct from the from-scratch build's
  `wikimedia/wikipedia:20231101.en` snapshot ID -- any reported retrieval
  result must cite which snapshot was live.
- **Category exclusion.** The source dataset's own README flags one of
  its categories as off-topic ("there is also Business&Economics...").
  `quorumqa.rag.preembedded.EXCLUDED_CATEGORIES` drops it, and every kept
  article is additionally re-checked against this project's own STEM
  keyword rule (`quorumqa.rag.subset.is_stem_article`, unchanged from the
  from-scratch builder) on its title+first-chunk text -- decided ONCE per
  article (not per chunk, since re-deriving per chunk would incorrectly
  drop valid continuation chunks whose local text doesn't repeat a
  keyword) so an accepted article contributes ALL its chunks.

## Known data-quality issue found and fixed: cross-category duplicates

The source dataset repeats the SAME Wikipedia article, non-contiguously,
under more than one field-of-science category bucket -- e.g. the CRISPR
article was observed present 3 times (presumably tagged under multiple
science-field categories upstream, in `millawell/wikipedia_field_of_science`).
An early build without a dedup guard visibly surfaced this: the same
article occupied 2 of the top-3 slots for a test query. `quorumqa.rag.
preembedded`'s per-row mapping has no cross-row state, so the guard lives
in `build_rag_index_preembedded.py`'s `build()`: a `seen_article_ids` set,
seeded from whatever's already in the target DB (so a resumed build still
catches a duplicate of an article written in an earlier run) and grown as
new articles are kept, rejects any later reoccurrence of an already-kept
article url outright. Covered by
`tests/test_build_rag_index_preembedded.py` (dedup within one run, and
dedup seeded from pre-existing DB rows).

## Known data-quality caveat (upstream, not introduced by this loader)

A small fraction of passages contain a Unicode replacement character
(`�`) in place of typographic punctuation (en/em dashes, curly
quotes) -- e.g. "Robert Cecil Hayes (19 January 1900�3 September
1977)" where a real en dash belongs. This was verified present in the
UPSTREAM dataset itself (confirmed via the raw HF datasets-server `/rows`
JSON, independent of this project's loader code), most likely from an
encoding mismatch when the dataset's original author built it. It is
cosmetic -- it does not corrupt the (already-computed) embedding vectors,
and does not measurably affect BM25/FTS matching since these are
non-searchable punctuation characters, not content words. Not fixed here
(no reliable general repair without re-deriving the original bytes);
flagged for anyone doing close text-quality review.

## What we actually loaded

Run command:
```
python benchmark/build_rag_index_preembedded.py \
  --max-passages 150000 \
  --db-path benchmark/data/rag_index_preembedded.sqlite3
```
(Re-running the same command resumes an interrupted build via the
`build_progress` checkpoint, same resumability contract as the
from-scratch builder.)

<!-- BUILD_RESULT_PLACEHOLDER -->

The index DB itself (`benchmark/data/rag_index_preembedded.sqlite3`) is
gitignored, same as the from-scratch build's `rag_index.sqlite3` --
rebuild via the command above rather than committing a multi-hundred-MB
binary.

## Verifying `search_corpus`

```
python benchmark/verify_rag_search.py --db-path benchmark/data/rag_index_preembedded.sqlite3
```
Runs 5 hardcoded STEM queries through the real `quorumqa.tools.mcp_server.
search_corpus` function (same code path the Verifier's tool rack calls),
prints top-3 titles+scores per query, and reports latency.

<!-- QUERY_RESULT_PLACEHOLDER -->

## Using this index

The from-scratch build's small partial index remains at its original path
(`benchmark/data/rag_index.sqlite3`, bge-small-embedded, ~48k passages as
of this writeup) and stays `mcp_server.py`'s DEFAULT db path -- this
avoids touching a path an already-running background build process may
still be writing to. To use the larger pre-embedded corpus instead, point
the `QUORUMQA_RAG_DB` environment variable at it:

```
export QUORUMQA_RAG_DB=benchmark/data/rag_index_preembedded.sqlite3
```

Once the from-scratch background build is confirmed stopped/finished, a
follow-up change can promote this path to `mcp_server.py`'s default (or
retire the from-scratch path in favor of it) -- left as a deliberate
follow-up rather than done here, to avoid racing a live process.
