"""MCP server exposing the Verifier agent's tools.

Run standalone for testing:
    python -m quorumqa.tools.mcp_server

The orchestrator spawns this as a subprocess and talks to it over stdio via
quorumqa.tools.mcp_client -- this is a real Model Context Protocol server,
not a bespoke function-calling shim, so the Verifier's tool use is a genuine
MCP integration end to end.
"""

from mcp.server.fastmcp import FastMCP

from quorumqa.tools.safe_math import CONSTANTS, SafeEvalError, safe_eval

mcp = FastMCP("quorumqa-verifier-tools")


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


if __name__ == "__main__":
    mcp.run()
