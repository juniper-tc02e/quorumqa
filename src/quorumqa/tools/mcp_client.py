import json
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class VerifierToolSession:
    """Holds one live MCP session against tools/mcp_server.py for the
    lifetime of a benchmark run, so we don't pay subprocess-spawn cost per
    question."""

    def __init__(self, session: ClientSession):
        self._session = session

    async def call(self, tool_name: str, arguments: dict) -> dict:
        result = await self._session.call_tool(tool_name, arguments)
        if result.isError:
            text = "; ".join(c.text for c in result.content if hasattr(c, "text"))
            return {"ok": False, "error": text or "MCP tool call failed"}
        for block in result.content:
            if hasattr(block, "text"):
                try:
                    return json.loads(block.text)
                except json.JSONDecodeError:
                    return {"ok": True, "raw": block.text}
        return {"ok": False, "error": "empty tool result"}

    async def list_tools(self) -> list[str]:
        resp = await self._session.list_tools()
        return [t.name for t in resp.tools]


@asynccontextmanager
async def verifier_tool_session():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "quorumqa.tools.mcp_server"],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield VerifierToolSession(session)
