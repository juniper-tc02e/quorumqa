"""MCP server exposing the Verifier agent's tools.

Run standalone for testing:
    python -m quorumqa.tools.mcp_server

The orchestrator spawns this as a subprocess and talks to it over stdio via
quorumqa.tools.mcp_client -- this is a real Model Context Protocol server,
not a bespoke function-calling shim, so the Verifier's tool use is a genuine
MCP integration end to end.
"""

import os
import threading
from pathlib import Path

import sympy
from mcp.server.fastmcp import FastMCP

from quorumqa.tools.safe_math import CONSTANTS, SafeEvalError, safe_eval

try:
    from latex2sympy2_extended import latex2sympy
except Exception:  # pragma: no cover - dependency probe
    latex2sympy = None

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


# ---------------------------------------------------------------------------
# sympy_check / substitute_check -- docs/reasoning-supercharge-plan.md W1 Arm
# B (verified_gate_cas): a DETERMINISTIC, offline computational-equality
# check, no network, no model call, thread-safe (no shared/global mutable
# state -- every call's timeout box and RNG-free parse are local to that
# call). Both tools FAIL SAFE: any parse/evaluation failure returns
# status="unparseable" rather than raising, so a malformed relation from an
# upstream extraction model can never crash the caller -- the verified_gate_
# cas lever treats "unparseable" the same as "not checkable" (accept the
# panel's answer).
#
# Parsing mirrors benchmark/math_grade.py's _to_expr two-stage strategy
# (latex2sympy2_extended first when the string looks LaTeX-flavored, then
# sympy.sympify on a light ASCII-ified fallback) but is reimplemented here
# standalone rather than imported, so this MCP server (part of the shipped
# src/quorumqa package) has no dependency on the benchmark/ script tree.
# ---------------------------------------------------------------------------

_SYMPY_CHECK_TOL = 1e-9


def _run_with_timeout(fn, seconds: float = 3.0):
    """Thread-based timeout (Windows-safe -- no signals, no
    multiprocessing). Returns fn(), or None if it raises or overruns.
    Never raises itself."""
    box: dict = {}

    def worker():
        try:
            box["v"] = fn()
        except Exception:
            box["v"] = None

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        return None
    return box.get("v")


def _looks_like_latex(s: str) -> bool:
    return "\\" in s or "{" in s or "^" in s


def _parse_sympy_expr(s: str):
    """Best-effort parse of `s` into a sympy expression. Returns None on any
    failure -- never raises. Tries latex2sympy2_extended first when `s`
    looks LaTeX-flavored, then falls back to sympy.sympify on a light
    ASCII-ified form (\\pi -> pi, \\cdot/\\times -> *, {}->(), ^->**)."""
    s = (s or "").strip()
    if not s:
        return None

    def attempt():
        if latex2sympy is not None and _looks_like_latex(s):
            try:
                return latex2sympy(s)
            except Exception:
                pass
        ascii_s = (
            s.replace("\\pi", "pi").replace("\\cdot", "*").replace("\\times", "*")
            .replace("{", "(").replace("}", ")").replace("^", "**")
        )
        try:
            return sympy.sympify(ascii_s, rational=True)
        except Exception:
            return None

    return _run_with_timeout(attempt, 3.0)


def _split_equation(s: str):
    """Splits a single top-level "LHS = RHS" equation into (lhs_str,
    rhs_str). Returns None if `s` doesn't contain exactly one bare `=` --
    deliberately naive so this never misfires on `==`, `<=`, `>=`, `!=`
    (refuses rather than misinterprets)."""
    if s.count("=") != 1:
        return None
    if any(tok in s for tok in ("==", "<=", ">=", "!=")):
        return None
    lhs, rhs = s.split("=", 1)
    return lhs.strip(), rhs.strip()


def _relation_to_difference(relation: str):
    """Turns a relation string into a single sympy expression that should
    equal zero when the relation holds: an "LHS = RHS" equation becomes
    LHS - RHS; a bare expression is assumed to already be in that
    equals-zero difference form. Returns None if either side fails to
    parse."""
    split = _split_equation(relation)
    if split is not None:
        lhs_s, rhs_s = split
        lhs = _parse_sympy_expr(lhs_s)
        rhs = _parse_sympy_expr(rhs_s)
        if lhs is None or rhs is None:
            return None
        return lhs - rhs
    return _parse_sympy_expr(relation)


def _values_equal(a, b, tol: float = _SYMPY_CHECK_TOL) -> bool:
    """Numeric equality within relative tolerance `tol`, falling back to
    symbolic simplification if numeric evaluation fails (e.g. free symbols
    remain). Never raises."""

    def attempt():
        try:
            da = complex(sympy.N(a, 30))
            db = complex(sympy.N(b, 30))
            return abs(da - db) <= tol * (1 + abs(db))
        except Exception:
            pass
        try:
            return bool(sympy.simplify(a - b) == 0)
        except Exception:
            return False

    return bool(_run_with_timeout(attempt, 3.0))


@mcp.tool()
def sympy_check(relation: str, candidate: str) -> dict:
    """Deterministically check a candidate answer against a symbolic/
    numeric relation. No network, never raises -- fails safe to
    status="unparseable" on anything it cannot confidently parse.

    `relation` is a sympy-parseable equation ("LHS = RHS", e.g.
    "2*3 + 4 = 10") -- ideally with the candidate answer's value already
    substituted in by the caller, so the equation is self-checking -- or a
    bare expression assumed to equal zero when the relation holds (e.g.
    "x**2 - 9"), in which case it must have AT MOST ONE free symbol, and
    `candidate` supplies the value substituted for it. `candidate` is
    ignored when `relation` already has no free symbols (a fully
    substituted equation needs no further substitution).

    Returns {"status": "pass"|"fail"|"unparseable", "detail": "..."}.
    """
    expr = _relation_to_difference(relation)
    if expr is None:
        return {"status": "unparseable", "detail": f"could not parse relation {relation!r}"}

    free_symbols = getattr(expr, "free_symbols", set())
    if free_symbols:
        if len(free_symbols) > 1:
            return {
                "status": "unparseable",
                "detail": f"relation {relation!r} has {len(free_symbols)} free symbols, expected at most 1",
            }
        candidate_value = _parse_sympy_expr(candidate)
        if candidate_value is None:
            return {"status": "unparseable", "detail": f"could not parse candidate {candidate!r}"}
        symbol = next(iter(free_symbols))
        try:
            expr = expr.subs(symbol, candidate_value)
        except Exception as exc:
            return {"status": "unparseable", "detail": f"substitution failed: {exc}"}

    holds = _values_equal(expr, sympy.Integer(0))
    if holds:
        return {"status": "pass", "detail": f"relation holds (evaluated to ~0): {relation!r} candidate={candidate!r}"}
    return {"status": "fail", "detail": f"relation does not hold: {relation!r} candidate={candidate!r} -> {expr}"}


@mcp.tool()
def substitute_check(equation: str, variable: str, value: str) -> dict:
    """Substitute `value` for `variable` in `equation` ("LHS = RHS") and
    check the two sides are equal within 1e-9 relative tolerance.
    Deterministic, no network, never raises -- fails safe to
    status="unparseable" on anything it cannot confidently parse.

    Returns {"status": "pass"|"fail"|"unparseable", "detail": "..."}.
    """
    split = _split_equation(equation)
    if split is None:
        return {"status": "unparseable", "detail": f"could not split {equation!r} into a single LHS = RHS equation"}
    lhs_s, rhs_s = split
    lhs = _parse_sympy_expr(lhs_s)
    rhs = _parse_sympy_expr(rhs_s)
    if lhs is None or rhs is None:
        return {"status": "unparseable", "detail": f"could not parse equation {equation!r}"}

    value_expr = _parse_sympy_expr(value)
    if value_expr is None:
        return {"status": "unparseable", "detail": f"could not parse value {value!r}"}

    symbol_name = (variable or "").strip()
    if not symbol_name:
        return {"status": "unparseable", "detail": "no variable name given"}
    symbol = sympy.Symbol(symbol_name)

    try:
        lhs_sub = lhs.subs(symbol, value_expr)
        rhs_sub = rhs.subs(symbol, value_expr)
    except Exception as exc:
        return {"status": "unparseable", "detail": f"substitution failed: {exc}"}

    holds = _values_equal(lhs_sub, rhs_sub)
    if holds:
        return {"status": "pass", "detail": f"{lhs_s} == {rhs_s} at {variable}={value}"}
    return {"status": "fail", "detail": f"{lhs_s} != {rhs_s} at {variable}={value} ({lhs_sub} vs {rhs_sub})"}


@mcp.tool()
def search_corpus(query: str, k: int = 5) -> dict:
    """Search the offline STEM-Wikipedia corpus (docs/recursive-rag-plan.md
    G0/G0.5) for passages relevant to `query`.

    Hybrid retrieval: SQLite FTS5 BM25 + dense cosine similarity, fused by
    reciprocal rank fusion. The dense query encoder is picked to match
    whichever embedding model the OPEN index DB was actually built with
    (recorded in its build_progress.embedding_model row at build time --
    see quorumqa.rag.embeddings.get_query_embedder) rather than assuming a
    single hardcoded model: the from-scratch build path
    (benchmark/build_rag_index.py) uses BAAI/bge-small-en-v1.5 (384-dim);
    the pre-embedded G0.5 corpus loader (benchmark/build_rag_index_
    preembedded.py, docs/rag-corpus-notes.md) uses
    mixedbread-ai/mxbai-embed-large-v1 (1024-dim). Returns the top-k fused
    passages, each with title, text, score, and provenance (source article
    URL, corpus snapshot ID).

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

    embedding_model = store.get_progress(index.conn).get("embedding_model")

    query_vector = None
    try:
        from quorumqa.rag.embeddings import get_query_embedder

        query_vector = get_query_embedder(embedding_model)(query)
    except ImportError:
        # Dense deps (sentence-transformers/torch) missing -- degrade to
        # FTS5-only rather than failing the whole tool call.
        pass
    except ValueError as exc:
        # embedding_model is set but unrecognized (e.g. a DB built by a
        # future loader this server predates) -- degrade to FTS5-only
        # rather than guessing a mismatched encoder and returning
        # meaningless dense scores.
        return {"ok": False, "error": f"search_corpus failed: {exc}"}

    try:
        results = index.search(query, query_vector, k=k)
    except Exception as exc:
        return {"ok": False, "error": f"search_corpus failed: {exc}"}

    return {"ok": True, "query": query, "k": k, "dense": query_vector is not None, "results": results}


if __name__ == "__main__":
    mcp.run()
