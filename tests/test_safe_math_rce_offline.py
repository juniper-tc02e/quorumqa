"""Model-generated text must never execute as Python.

WHY. An external review on 2026-08-03 found that `sympy.sympify()` -- which
evaluates its argument as Python -- was being called directly on model output
at two sites:

    src/quorumqa/tools/mcp_server.py   the Verifier's CAS tool
    benchmark/math_grade.py            the open-answer grader

Reproduced with a non-mutating probe: `sympify("__import__('pathlib')...")`
wrote a file to disk. Both sites checked `isinstance(result, sympy.Expr)` only
AFTER evaluation, which is no defence. The grader path was the worse of the
two -- a payload could execute AND return a value the grader scored as correct.

The repo already had the right answer for the NUMERIC path since July
(`safe_eval`, an AST allowlist, whose docstring says the Verifier "must never
become an arbitrary code execution path"). The symbolic path was added later
beside it and skipped that discipline. These tests exist so it cannot happen a
third time.

Offline: no API calls, no network. The probes are non-destructive (they write
to a temp file which is deleted).
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from quorumqa.tools.safe_math import (
    MAX_EXPONENT, MAX_INPUT_CHARS, UnsafeExpression,
    assert_safe, is_safe, safe_sympify,
)


def _probe_path(name: str) -> pathlib.Path:
    p = pathlib.Path(tempfile.gettempdir()) / name
    if p.exists():
        p.unlink()
    return p


#: Each entry is a real escape technique, not a synthetic string.
ATTACKS = [
    ("import + write", "__import__('pathlib').Path('/tmp/x').write_text('X')"),
    ("os.system", "__import__('os').system('echo pwned')"),
    ("subclass escape", "().__class__.__bases__[0].__subclasses__()"),
    ("attribute access", "(1).__class__"),
    ("eval", "eval('1+1')"),
    ("exec", "exec('x=1')"),
    ("open", "open('/etc/passwd').read()"),
    ("getattr", "getattr(1, 'real')"),
    ("comprehension", "[x for x in range(10)]"),
    ("lambda", "(lambda: 1)()"),
    ("f-string", "f'{1+1}'"),
    ("string literal", "'hello'"),
    ("subscript", "[1,2,3][0]"),
    ("walrus", "(y := 1)"),
]


@pytest.mark.parametrize("label,payload", ATTACKS, ids=[a[0] for a in ATTACKS])
def test_attacks_are_rejected_by_the_allowlist(label, payload):
    assert not is_safe(payload), f"{label} passed the allowlist"
    with pytest.raises(UnsafeExpression):
        assert_safe(payload)
    assert safe_sympify(payload) is None


def test_the_actual_rce_no_longer_executes_at_either_call_site():
    """The end-to-end probe, run against the real functions rather than the
    allowlist in isolation -- a guard that is not wired in guards nothing."""
    marker = _probe_path("quorumqa_rce_test_marker.txt")
    payload = f"__import__('pathlib').Path(r'{marker}').write_text('EXECUTED')"

    from quorumqa.tools.mcp_server import _parse_sympy_expr
    assert _parse_sympy_expr(payload) is None
    assert not marker.exists(), "CAS tool executed model-controlled code"

    from benchmark import math_grade
    for name in ("_parse_expr", "_to_expr", "_sympy_parse"):
        fn = getattr(math_grade, name, None)
        if fn is not None:
            fn(payload)
    assert not marker.exists(), "grader executed model-controlled code"


def test_memory_bombs_are_rejected_without_evaluating_them():
    """9**9**9 needs no function call and no timeout can undo it -- the thread
    helper is daemon=True, so it abandons work it cannot kill."""
    assert not is_safe("9**9**9**9")
    assert not is_safe(f"2**{MAX_EXPONENT + 1}")
    assert not is_safe("x" * (MAX_INPUT_CHARS + 1))
    assert is_safe("2**10"), "ordinary exponents must still work"


LEGITIMATE = [
    "2*x + 3", "sqrt(2)", "pi", "E", "Rational(1,2)", "3.14*r**2",
    "sin(x)**2 + cos(x)**2", "log(x)/log(2)", "-4/3*pi*r**3",
    "factorial(5)", "Abs(-3)", "(a+b)/(a-b)",
]


@pytest.mark.parametrize("expr", LEGITIMATE)
def test_real_answers_still_parse(expr):
    """A security fix that breaks the tool is not a fix. These are the shapes a
    solver actually produces."""
    assert is_safe(expr), f"legitimate expression rejected: {expr}"
    assert safe_sympify(expr) is not None


def test_no_call_site_uses_bare_sympify():
    """Guards the SOURCE, so a third call site added later fails here rather
    than silently reintroducing the hole. This is exactly how the second one
    got in: the safe helper existed and was not reached for."""
    import benchmark.math_grade as mg
    import quorumqa.tools.mcp_server as mcp
    for mod in (mg, mcp):
        src = open(mod.__file__, encoding="utf-8").read()
        # allow the word in comments/docstrings, forbid the call
        assert "sympy.sympify(" not in src, (
            f"{mod.__name__} calls sympy.sympify directly; use safe_sympify"
        )
