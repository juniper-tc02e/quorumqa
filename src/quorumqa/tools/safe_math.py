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
