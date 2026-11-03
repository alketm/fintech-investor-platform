"""get_news with yfinance replaced by fakes: no network access."""

from types import SimpleNamespace

import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError
from yfinance.exceptions import YFDataException

from alko_mcp_news import server

DOWN = YFDataException("*** YAHOO! FINANCE IS CURRENTLY DOWN! ***")
TICKER_ARTICLE = {"title": "From Ticker", "publisher": "Wire"}
SEARCH_ARTICLE = {"title": "From Search", "publisher": "Wire"}


class FailingTicker:
    @property
    def news(self):
        raise DOWN


def _search_returning(items):
    return lambda symbol, news_count: SimpleNamespace(news=items)


def _failing_search(symbol, news_count):
    raise DOWN


def _titles(out):
    return [a["title"] for a in out["articles"]]


def test_ticker_news_is_used_when_available(monkeypatch):
    monkeypatch.setattr(server, "_ticker", lambda s: SimpleNamespace(news=[TICKER_ARTICLE]))
    monkeypatch.setattr(server.yf, "Search", _failing_search)
    assert _titles(server.get_news("nvda")) == ["From Ticker"]


def test_empty_ticker_news_falls_back_to_search(monkeypatch):
    monkeypatch.setattr(server, "_ticker", lambda s: SimpleNamespace(news=[]))
    monkeypatch.setattr(server.yf, "Search", _search_returning([SEARCH_ARTICLE]))
    assert _titles(server.get_news("NVDA")) == ["From Search"]


def test_ticker_failure_falls_back_to_search(monkeypatch):
    monkeypatch.setattr(server, "_ticker", lambda s: FailingTicker())
    monkeypatch.setattr(server.yf, "Search", _search_returning([SEARCH_ARTICLE]))
    out = server.get_news("nvda")
    assert out["symbol"] == "NVDA"
    assert _titles(out) == ["From Search"]


def test_both_sources_failing_is_a_tool_error(monkeypatch):
    monkeypatch.setattr(server, "_ticker", lambda s: FailingTicker())
    monkeypatch.setattr(server.yf, "Search", _failing_search)
    with pytest.raises(ToolError, match="News unavailable for NVDA"):
        server.get_news("NVDA")


def test_search_failure_after_empty_ticker_news_is_a_tool_error(monkeypatch):
    monkeypatch.setattr(server, "_ticker", lambda s: SimpleNamespace(news=[]))
    monkeypatch.setattr(server.yf, "Search", _failing_search)
    with pytest.raises(ToolError, match="News unavailable for NVDA"):
        server.get_news("NVDA")


async def test_failure_message_reaches_mcp_client(monkeypatch):
    # Only ToolError messages survive to the client in mcp 2.x; anything else is masked.
    monkeypatch.setattr(server, "_ticker", lambda s: FailingTicker())
    monkeypatch.setattr(server.yf, "Search", _failing_search)
    async with Client(server.mcp) as client:
        result = await client.call_tool("get_news", {"symbol": "NVDA"})
    assert result.is_error
    assert "News unavailable for NVDA" in result.content[0].text
