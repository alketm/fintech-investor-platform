import json
from types import SimpleNamespace

import pytest

PRICES = {
    "AAPL": 200.0,
    "MSFT": 400.0,
    "NVDA": 100.0,
    "VTI": 250.0,
    "QQQ": 400.0,
    "VOO": 500.0,
    "SCHD": 80.0,
    "BND": 72.0,
    "VXUS": 60.0,
    "JNJ": 160.0,
}


class FakePool:
    """Stands in for McpPool: one stocks tool and one backtest tool, no subprocesses."""

    def __init__(self):
        self.tools = {
            "mcp_stocks": [SimpleNamespace(name="get_quote")],
            "mcp_backtest": [SimpleNamespace(name="backtest_buy_and_hold")],
        }
        self.calls = []

    def anthropic_tools(self, server):
        return [
            {"name": t.name, "description": "", "input_schema": {"type": "object"}}
            for t in self.tools[server]
        ]

    def server_for_tool(self, name):
        return next((s for s, ts in self.tools.items() if any(t.name == name for t in ts)), None)

    async def call(self, server, tool, args):
        self.calls.append((server, tool, args))
        if tool == "get_quote":
            return json.dumps({"symbol": args["symbol"], "price": PRICES[args["symbol"]]}), False
        return json.dumps({"total_return_pct": 42.0}), False

    async def call_json(self, server, tool, args):
        text, _ = await self.call(server, tool, args)
        return json.loads(text)


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use(id, name, input):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=input)


class FakeClaude:
    """Replays scripted responses keyed by agent role and records each request."""

    def __init__(self, script):
        self.script = script  # role name -> list of content-block lists
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        role = next(r for r in self.script if f"Your role: {r}." in kwargs["system"][0]["text"])
        content = self.script[role].pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return SimpleNamespace(stop_reason=stop, content=content)


@pytest.fixture
def pool():
    return FakePool()
