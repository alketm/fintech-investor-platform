"""Long-lived MCP client sessions, one stdio subprocess per server."""

import json
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from alko_backend.config import MCP_SERVER_ENV, MCP_SERVERS


class ToolError(RuntimeError):
    pass


class McpPool:
    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self.tools: dict[str, list[Any]] = {}

    async def start(self, stack: AsyncExitStack, servers: dict[str, str] = MCP_SERVERS) -> None:
        for name, module in servers.items():
            env = {"PYTHONWARNINGS": "ignore"}
            env |= {var: os.environ[var] for var in MCP_SERVER_ENV.get(name, ()) if var in os.environ}
            params = StdioServerParameters(command=sys.executable, args=["-m", module], env=env)
            client = await stack.enter_async_context(Client(params))
            self._clients[name] = client
            self.tools[name] = (await client.list_tools()).tools

    def anthropic_tools(self, server: str) -> list[dict]:
        """This server's tools in Claude API tool format."""
        return [
            {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
            for t in self.tools[server]
        ]

    async def call(self, server: str, tool: str, args: dict) -> tuple[str, bool]:
        """Call a tool; returns (text, is_error). The text is what the model sees."""
        result = await self._clients[server].call_tool(tool, args)
        text = "\n".join(c.text for c in result.content if c.type == "text")
        if not text and result.structured_content is not None:
            text = json.dumps(result.structured_content)
        return text, bool(result.is_error)

    async def call_json(self, server: str, tool: str, args: dict) -> dict:
        """Call a tool from application code and parse its JSON result."""
        text, is_error = await self.call(server, tool, args)
        if is_error:
            raise ToolError(text)
        return json.loads(text)
