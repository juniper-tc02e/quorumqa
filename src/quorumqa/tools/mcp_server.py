"""MCP server exposing the Verifier agent's tools.

Run standalone for testing:
    python -m quorumqa.tools.mcp_server

The orchestrator spawns this as a subprocess and talks to it over stdio via
quorumqa.tools.mcp_client -- this is a real Model Context Protocol server,
not a bespoke function-calling shim, so the Verifier's tool use is a genuine
MCP integration end to end.
"""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from quorumqa.tools.safe_math import CONSTANTS, SafeEvalError, safe_eval

mcp = FastMCP("quorumqa-verifier-tools")

# src/quorumqa/tools/mcp_server.py -> parents[3] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_RAG_DB_PATH = _REPO_ROOT / "benchmark" / "data" / "rag_index.sqlite3"

# One RagIndex (and its in-memory dense-vector cache) per resolved DB path,
# reused across calls for the lifetime of this server process.
_rag_index_cache: dict = {}


def _rag_db_path() -> Path:
    override = os.environ.get("QUORUMQA_RAG_DB")
    return Path(override) if override else _DEFAULT_RAG_DB_PATH


@mcp.tool()
def lookup_constant(name: str) -> dict:
    """Look up a physical/mathematical constant by name (e.g. 'speed_of_light', 'avogadro_number', 'pi').

    Returns the numeric value, or a list of available names if not found.
    Never used to look up exam question content -- constants only.
    """
    key = name.strip().lower().replace(" ", "_")
    if key in CONSTANTS:
        return {"found": True, "name": key, "value": CONSTANTS[key]}
    return {"found": False, "requested": name, "available": sorted(CONSTANTS.keys())}


@mcp.tool()
def safe_calculate(expression: str) -> dict:
    """Evaluate a numeric arithmetic expression (+ - * / ** % //, parentheses, and named constants).

    No function calls, no variable assignment, no code execution beyond
    arithmetic -- rejects anything else with an error message.
    """
    try:
        value = safe_eval(expression)
        return {"ok": True, "expression": expression, "value": value}
    except SafeEvalError as exc:
        return {"ok": False, "expression": expression, "error": str(exc)}


@mcp.tool()
def search_corpus(query: str, k: int = 5) -> dict:
    """Search the offline STEM-Wikipedia corpus (docs/recursive-rag-plan.md
    G0) for passages relevant to `query`.

    Hybrid retrieval: SQLite FTS5 BM25 + dense cosine similarity
    (BAAI/bge-small-en-v1.5), fused by reciprocal rank fusion. Returns the
    top-k fused passages, each with title, text, score, and provenance
    (source article URL, corpus snapshot ID).

    This is a no-op with a clear `ok: False` error -- it never raises --
    if the index DB hasn't been built yet (see benchmark/build_rag_index.py)
    or if the dense-embedding dependency isn't installed, so a machine
    without RAG set up never crashes the engine over this tool.
    """
    try:
        from quorumqa.rag import store
    except ImportError as exc:
        return {"ok": False, "error": f"RAG store module unavailable ({exc}). Is quorumqa installed with its rag extras?"}

    db_path = _rag_db_path()
    if not db_path.exists():
        return {
            "ok": False,
            "error": (
                f"RAG index DB not found at {db_path}. Build it first, e.g.: "
                f"python benchmark/build_rag_index.py --max-articles 2000 --db-path {db_path}"
            ),
        }

    cache_key = str(db_path.resolve())
    index = _rag_index_cache.get(cache_key)
    if index is None:
        try:
            index = store.RagIndex.open(db_path)
        except store.IndexNotFoundError as exc:
            return {"ok": False, "error": str(exc)}
        _rag_index_cache[cache_key] = index

    query_vector = None
    try:
        from quorumqa.rag.embeddings import embed_query

        query_vector = embed_query(query)
    except ImportError as exc:
        # Dense deps (sentence-transformers/torch) missing -- degrade to
        # FTS5-only rather than failing the whole tool call.
        pass

    try:
        results = index.search(query, query_vector, k=k)
    except Exception as exc:
        return {"ok": False, "error": f"search_corpus failed: {exc}"}

    return {"ok": True, "query": query, "k": k, "dense": query_vector is not None, "results": results}


if __name__ == "__main__":
    mcp.run()
