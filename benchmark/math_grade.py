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


def _split_top(inner: str) -> list[str]:
    """Split `inner` on top-level commas (depth-aware over ()[]{} — the
    backslash in \\{ / \\} is just a char, the { / } drive the depth)."""
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
    return [p.strip() for p in parts if p.strip() != ""]


def _expand_pm(s: str) -> list[str]:
    """Expand every \\pm / \\mp into its two variants (\\pm -> +/-, \\mp ->
    -/+). No symbol -> [s]. Multiple symbols expand combinatorially (capped
    by there being at most a couple in real answers)."""
    stack, out = [s], []
    while stack:
        cur = stack.pop()
        if "\\pm" in cur:
            stack.append(cur.replace("\\pm", "+", 1))
            stack.append(cur.replace("\\pm", "-", 1))
        elif "\\mp" in cur:
            stack.append(cur.replace("\\mp", "-", 1))
            stack.append(cur.replace("\\mp", "+", 1))
        else:
            out.append(cur)
    return out


def _as_seq(s: str):
    """A bracketed ORDERED sequence: coordinate tuple or interval. Returns
    (open_char, close_char, [elements]) with >=2 elements, else None. Brackets
    are significant — (3,4] is an interval distinct from [3,4] or (3,4)."""
    t = s.strip()
    if len(t) >= 2 and t[0] in "([" and t[-1] in ")]":
        elems = _split_top(t[1:-1])
        if len(elems) >= 2:
            return (t[0], t[-1], elems)
    return None


def _as_multiset(s: str):
    """An order-INSENSITIVE set of values: \\{...\\} / {...} braces, a bare
    comma-separated multi-valued answer (roots), or a single \\pm/\\mp
    expression. Each element is \\pm-expanded. Returns the flat value list, or
    None if `s` is not set-like (scalars and bracketed seqs return None)."""
    t = s.strip()
    inner = None
    if t.startswith("\\{") and t.endswith("\\}"):
        inner = t[2:-2]
    elif t.startswith("{") and t.endswith("}"):
        inner = t[1:-1]
    if inner is not None:
        elems = _split_top(inner)
    elif t[:1] in "([":
        return None  # bracketed ordered sequence, handled by _as_seq
    elif "," in t:
        elems = _split_top(t)
        if len(elems) < 2:
            return None
    elif "\\pm" in t or "\\mp" in t:
        elems = [t]
    else:
        return None
    out: list[str] = []
    for e in elems:
        out.extend(_expand_pm(e))
    out = [e.strip() for e in out if e.strip()]
    return out or None


def grade(gold: str, pred: str, tol: float = _TOL) -> bool:
    """True iff `pred` is mathematically equivalent to the gold answer.
    Fails closed: returns False on any parse/compare failure so a bad parse
    can never inflate measured accuracy."""
    if gold is None or pred is None:
        return False
    g_raw, p_raw = _normalize(gold), _normalize(pred)
    if g_raw == p_raw and g_raw != "":
        return True

    # 1) bracketed ordered sequences (tuples / intervals): brackets AND order
    #    are significant -- (3,4] != [3,4] != (3,4), (a,b) != (b,a).
    g_seq, p_seq = _as_seq(g_raw), _as_seq(p_raw)
    if g_seq is not None or p_seq is not None:
        if g_seq is None or p_seq is None:
            return False
        (go, gc, ge), (po, pc, pe) = g_seq, p_seq
        if go != po or gc != pc or len(ge) != len(pe):
            return False
        return all(grade(a, b, tol) for a, b in zip(ge, pe))

    # 2) order-insensitive sets / multi-valued answers / \pm expansions
    g_ms, p_ms = _as_multiset(g_raw), _as_multiset(p_raw)
    if g_ms is not None or p_ms is not None:
        if g_ms is None or p_ms is None or len(g_ms) != len(p_ms):
            return False
        used = [False] * len(p_ms)
        for a in g_ms:
            hit = False
            for j, b in enumerate(p_ms):
                if not used[j] and grade(a, b, tol):
                    used[j] = True
                    hit = True
                    break
            if not hit:
                return False
        return True

    # 3) scalar expressions: symbolic then numeric equivalence
    ge, pe = _to_expr(g_raw), _to_expr(p_raw)
    if ge is None or pe is None:
        return False
    if _symbolic_equal(ge, pe):
        return True
    return _numeric_equal(ge, pe)
