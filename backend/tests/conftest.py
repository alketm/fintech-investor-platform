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


def thinking_block(thinking):
    return SimpleNamespace(type="thinking", thinking=thinking, signature="sig")


USAGE = {
    "input_tokens": 100,
    "output_tokens": 10,
    "cache_read_input_tokens": 5,
    "cache_creation_input_tokens": 2,
}
USAGE_TOTAL = sum(USAGE.values())


def fake_response(content, stop_reason, model="claude-opus-5-5"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        model=model,
        usage=SimpleNamespace(**USAGE),
        stop_details=None,
        _request_id="req_test",
    )


class FakeClaude:
    """Replays scripted responses keyed by agent role and records each request.

    Script entries are content-block lists, or an exception to raise. The guardrail classifier's calls are
    separate: `classifier` holds the replies to give, and it answers in_scope once they run out.
    """

    def __init__(self, script, classifier=()):
        self.script = script  # role name -> list of content-block lists
        self.requests = []
        self.classifier = list(classifier)
        self.classifier_requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.messages = SimpleNamespace(create=self._classify)

    async def _classify(self, **kwargs):
        self.classifier_requests.append(kwargs)
        reply = self.classifier.pop(0) if self.classifier else '{"category": "in_scope", "reason": "ok"}'
        if isinstance(reply, Exception):
            raise reply
        return fake_response([text_block(reply)], "end_turn", kwargs["model"])

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        role = next(r for r in self.script if f"Your role: {r}." in kwargs["system"][0]["text"])
        content = self.script[role].pop(0)
        if isinstance(content, Exception):
            raise content
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return fake_response(content, stop)


@pytest.fixture
def pool():
    return FakePool()
