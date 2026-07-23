"""Open-answer math equivalence grader for the QuorumQA hard-math path.

WHY THIS EXISTS (and why not math_verify): the whole point of an open-answer
math track is to test whether deliberation helps on genuinely hard math,
where the flagship has real headroom -- distractor-MC framing saturates the
flagship (MATH-500/GSM8K pilots hit 100%), so it cannot discriminate. Open
answers need an equivalence grader that accepts "0.5" for "\\frac{1}{2}",
"\\sqrt{20}" for "2\\sqrt{5}", "2\\pi+18" for "18+2\\pi", etc.

HuggingFace's `math_verify` is the usual choice but is UNUSABLE on this
Windows environment: its parse/verify path wraps sympy in a multiprocessing
timeout that spawn-storms (WinError 87) and returns [] for every input,
including `\\boxed{...}`. One of its dependencies, `latex2sympy2_extended`,
works standalone here, so this module builds a focused grader on that +
sympy, with a thread-based (not multiprocessing) timeout so it degrades
safely on pathological inputs.

Scope: targets the answer shapes MATH-500 actually uses -- integers,
decimals, LaTeX fractions, radicals, pi-multiples, simple polynomials,
coordinate tuples, and comma-separated multi-valued answers. Not a universal
CAS oracle; it is a benchmark grader tuned to a known answer distribution,
and `grade()` fails CLOSED (returns False) on anything it cannot confidently
parse, so a lenient parse never inflates accuracy.
"""

from __future__ import annotations

import re
import threading

import sympy

try:
    from latex2sympy2_extended import latex2sympy
except Exception:  # pragma: no cover - dependency probe
    latex2sympy = None

_TOL = 1e-9


def _run_with_timeout(fn, seconds: float = 3.0):
    """Thread-based timeout (Windows-safe; no signals, no multiprocessing).
    Returns fn() or None if it overruns / raises."""
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


# --- normalization ---------------------------------------------------------

_BOXED_RE = re.compile(r"\\boxed\s*\{")


def _strip_boxed(s: str) -> str:
    """Remove a wrapping \\boxed{...}, keeping the inner content (brace-matched)."""
    m = _BOXED_RE.search(s)
    if not m:
        return s
    start = m.end()  # first char inside the brace
    depth = 1
    i = start
    while i < len(s) and depth:
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return s[:m.start()] + s[start:i] + s[i + 1:]


_THOUSANDS_RE = re.compile(r"(?<=\d),(?=\d{3}(?:,|\b))")


def _normalize(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = _strip_boxed(s)
    # LaTeX literals for currency/percent must be removed BEFORE the bare `$`
    # delimiter strip, or `\$` leaves a stray backslash.
    s = s.replace("\\$", "").replace("\\%", "").replace("%", "")
    # surrounding math delimiters
    s = s.replace("$", "")
    s = s.replace("\\left", "").replace("\\right", "")
    # LaTeX spacing / thin-space commands (also the \! in \$32,\!348)
    s = s.replace("\\!", "").replace("\\,", "").replace("\\;", "").replace("\\ ", " ")
    s = s.replace("\\quad", " ").replace("\\qquad", " ")
    # degree marks: 145^\circ / 145^{\circ} -> 145
    s = re.sub(r"\^\s*\{?\s*\\circ\s*\}?", "", s)
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    # strip a leading "x =" / "y=" answer label
    s = re.sub(r"^\s*[a-zA-Z]\s*=\s*", "", s)
    # thousands separators only: a comma between a digit and exactly three more
    # digits (32,348 -> 32348). Applied repeatedly for 1,234,567. Leaves tuple
    # commas ("1,-2", "6,31,-1") untouched.
    while _THOUSANDS_RE.search(s):
        s = _THOUSANDS_RE.sub("", s)
    s = s.strip().rstrip(".")
    return s.strip()


def _to_expr(s: str):
    """Parse a normalized answer string into a sympy object. Tries
    latex2sympy first (handles \\frac, \\sqrt, \\pi, ^), then sympy.sympify on
    a light ASCII-ified form. Returns None on failure."""
    if not s:
        return None

    def attempt():
        if latex2sympy is not None and ("\\" in s or "{" in s or "^" in s):
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


def _numeric_equal(a, b) -> bool:
    def attempt():
        try:
            da = complex(sympy.N(a, 30))
            db = complex(sympy.N(b, 30))
        except Exception:
            return False
        return abs(da - db) <= _TOL * (1 + abs(db))
    return bool(_run_with_timeout(attempt, 3.0))


def _symbolic_equal(a, b) -> bool:
    def attempt():
        try:
            return sympy.simplify(a - b) == 0
        except Exception:
            return False
    return bool(_run_with_timeout(attempt, 3.0))


def _split_tuple(s: str):
    """If s is a top-level comma-separated list (optionally parenthesized),
    return its element strings; else None."""
    t = s.strip()
    paren = t.startswith("(") and t.endswith(")")
    brack = t.startswith("[") and t.endswith("]")
    inner = t[1:-1] if (paren or brack) else t
    parts, depth, cur = [], 0, ""
    for ch in inner:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    parts = [p.strip() for p in parts if p.strip() != ""]
    if len(parts) <= 1:
        return None
    return parts


def grade(gold: str, pred: str, tol: float = _TOL) -> bool:
    """True iff `pred` is mathematically equivalent to the gold answer.
    Fails closed: returns False on any parse/compare failure so a bad parse
    can never inflate measured accuracy."""
    if gold is None or pred is None:
        return False
    g_raw, p_raw = _normalize(gold), _normalize(pred)
    if g_raw == p_raw and g_raw != "":
        return True

    # multi-valued / tuple answers: compare element sets (order-insensitive)
    g_parts, p_parts = _split_tuple(g_raw), _split_tuple(p_raw)
    if g_parts is not None or p_parts is not None:
        if g_parts is None or p_parts is None or len(g_parts) != len(p_parts):
            return False
        used = [False] * len(p_parts)
        for gp in g_parts:
            hit = False
            for j, pp in enumerate(p_parts):
                if not used[j] and grade(gp, pp, tol):
                    used[j] = True
                    hit = True
                    break
            if not hit:
                return False
        return True

    ge, pe = _to_expr(g_raw), _to_expr(p_raw)
    if ge is None or pe is None:
        return False
    if _symbolic_equal(ge, pe):
        return True
    return _numeric_equal(ge, pe)
