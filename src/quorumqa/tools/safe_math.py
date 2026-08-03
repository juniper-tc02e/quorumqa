import ast
import operator

# Whitelisted operators only -- no function calls, no attribute access, no
# name lookups beyond CONSTANTS below. This is deliberately not a general
# `eval()`: the Verifier tool must never become an arbitrary code execution
# path just because it's reachable from model-generated tool-call arguments.
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

CONSTANTS = {
    "speed_of_light": 2.99792458e8,  # m/s
    "planck_constant": 6.62607015e-34,  # J*s
    "elementary_charge": 1.602176634e-19,  # C
    "avogadro_number": 6.02214076e23,  # 1/mol
    "boltzmann_constant": 1.380649e-23,  # J/K
    "gas_constant": 8.31446261815324,  # J/(mol*K)
    "gravitational_constant": 6.6743e-11,  # m^3/(kg*s^2)
    "electron_mass": 9.1093837015e-31,  # kg
    "proton_mass": 1.67262192369e-27,  # kg
    "vacuum_permittivity": 8.8541878128e-12,  # F/m
    "pi": 3.14159265358979323846,
    "e": 2.71828182845904523536,
}


class SafeEvalError(ValueError):
    pass


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in CONSTANTS:
        return CONSTANTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise SafeEvalError(f"Disallowed expression element: {ast.dump(node)}")


def safe_eval(expression: str) -> float:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise SafeEvalError(f"Could not parse expression: {exc}") from exc
    return _eval_node(tree.body)


# ---------------------------------------------------------------------------
# Symbolic path -- added 2026-08-03 after an external review found an RCE
# ---------------------------------------------------------------------------
#
# `safe_eval` above has guarded the calculator since July, and its docstring
# says exactly why: "the Verifier tool must never become an arbitrary code
# execution path just because it's reachable from model-generated tool-call
# arguments." That discipline was correct and it held.
#
# What happened is narrower and more instructive: a SECOND path was added
# beside it. `sympy_check` needs symbolic comparison (`simplify(lhs - rhs) == 0`)
# which `safe_eval` cannot do -- it returns floats -- so `_parse_sympy_expr`
# called `sympy.sympify()` on model text directly, and `benchmark/math_grade.py`
# copied the same shape. `sympify` evaluates its argument as Python.
#
# Reproduced 2026-08-03, non-mutating probe:
#     sympify("__import__('pathlib').Path(p).write_text('EXECUTED')")
#     -> file written to disk
#
# The grader path was worse than the tool path: a payload could execute AND
# return a value the grader then scored as correct.
#
# The 3-second `_run_with_timeout` did not contain it. That helper runs work in
# a `daemon=True` thread and abandons it on overrun -- Python cannot kill a
# thread -- so a hostile expression keeps consuming CPU and memory after the
# "timeout" returns, and repeated calls accumulate live threads.
#
# So the symbolic path gets the same treatment the numeric path already had:
# nothing reaches SymPy until every AST node has been checked against an
# allowlist. Unrecognised node types fail CLOSED.

MAX_INPUT_CHARS = 512      # a real answer expression is far shorter
MAX_AST_NODES = 300        # blocks deeply nested products/sums
MAX_EXPONENT = 1_000       # 2**1000 is merely big; 9**9**9 is a memory bomb
MAX_POW_DEPTH = 2          # a**b is fine, a**b**c is not

#: Bare names a mathematical answer may legitimately use.
ALLOWED_NAMES = frozenset({
    "pi", "E", "I", "oo", "zoo", "nan",
    "GoldenRatio", "EulerGamma", "Catalan",
})

#: Functions it may legitimately call. Deliberately absent: anything reflective
#: (`Symbol`, `lambdify`, `parse_expr`) and anything from builtins.
ALLOWED_FUNCS = frozenset({
    "sqrt", "cbrt", "exp", "log", "ln",
    "sin", "cos", "tan", "cot", "sec", "csc",
    "asin", "acos", "atan", "atan2",
    "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
    "Abs", "abs", "sign", "floor", "ceiling",
    "factorial", "binomial", "gamma",
    "Rational", "Integer", "Float", "Max", "Min", "root",
})

_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name,
    ast.Call, ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
    ast.UAdd, ast.USub,
)


class UnsafeExpression(ValueError):
    """Raised when an expression contains anything outside the allowlist."""


def _pow_depth(node: ast.AST) -> int:
    """Nesting depth of `**`, so 9**9**9 is rejected structurally."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
        return 1 + max(_pow_depth(node.left), _pow_depth(node.right))
    return max((_pow_depth(c) for c in ast.iter_child_nodes(node)), default=0)


def assert_safe(expr: str) -> ast.Expression:
    """Prove every node of `expr` is allowlisted, or raise UnsafeExpression.

    Each rejection below closes a specific attack:
      Attribute      -- ().__class__.__bases__[0].__subclasses__(), the standard
                        sandbox escape. Blocked at the root: no attribute access.
      Call to an
      unlisted name  -- __import__, eval, exec, open, getattr, compile.
      Subscript      -- indexing into __subclasses__() results.
      str constants  -- how f-strings and getattr tricks carry payloads; also
                        never a mathematical answer.
      big exponents  -- a memory bomb needing no function call at all.
    """
    if not isinstance(expr, str):
        raise UnsafeExpression("expression must be a string")
    if len(expr) > MAX_INPUT_CHARS:
        raise UnsafeExpression(f"expression exceeds {MAX_INPUT_CHARS} chars")
    if "\x00" in expr:
        raise UnsafeExpression("null byte in expression")

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise UnsafeExpression(f"not a parseable expression: {e}") from None

    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise UnsafeExpression(f"{len(nodes)} AST nodes, max {MAX_AST_NODES}")

    for node in nodes:
        if not isinstance(node, _ALLOWED_NODES):
            raise UnsafeExpression(f"disallowed syntax: {type(node).__name__}")

        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, complex)):
            raise UnsafeExpression(
                f"only numeric literals allowed, got {type(node.value).__name__}")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise UnsafeExpression("only direct calls to named functions")
            if node.func.id not in ALLOWED_FUNCS:
                raise UnsafeExpression(f"function not allowed: {node.func.id}")
            if node.keywords:
                raise UnsafeExpression("keyword arguments not allowed")

        if isinstance(node, ast.Name):
            ok = (node.id in ALLOWED_NAMES or node.id in ALLOWED_FUNCS
                  or (len(node.id) <= 2 and node.id.isalpha()))
            if not ok:
                raise UnsafeExpression(
                    f"name not allowed: {node.id!r} (symbols must be 1-2 letters)")

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            exp = node.right
            if isinstance(exp, ast.UnaryOp) and isinstance(exp.op, ast.USub):
                exp = exp.operand
            if isinstance(exp, ast.Constant) and isinstance(exp.value, (int, float)):
                if abs(exp.value) > MAX_EXPONENT:
                    raise UnsafeExpression(
                        f"exponent {exp.value} exceeds {MAX_EXPONENT}")

    if _pow_depth(tree) > MAX_POW_DEPTH:
        raise UnsafeExpression(f"nested ** deeper than {MAX_POW_DEPTH}")

    return tree


def is_safe(expr: str) -> bool:
    try:
        assert_safe(expr)
        return True
    except UnsafeExpression:
        return False


def safe_sympify(expr: str, **kwargs):
    """`sympy.sympify` behind the allowlist. Returns None on anything rejected.

    Fails CLOSED and never raises, preserving the "never raises -- fails safe to
    unparseable" contract that `verified_gate_cas` depends on.
    """
    if not is_safe(expr):
        return None
    import sympy
    try:
        return sympy.sympify(expr, **kwargs)
    except Exception:
        return None
