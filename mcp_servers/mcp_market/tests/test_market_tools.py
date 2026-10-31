"""Market tools with yfinance replaced by fakes: no network access."""

import numpy as np
import pandas as pd
import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_market import server

DAYS = pd.bdate_range(end="2026-10-30", periods=600)


def _fake_download(symbols, start):
    cols = {}
    for i, sym in enumerate(symbols):
        if sym == "NOPRICE":
            continue
        rng = np.random.default_rng(i)
        close = 100 * np.cumprod(1 + rng.normal(0.0004 + 0.0002 * i, 0.01, len(DAYS)))
        cols[("Open", sym)] = close * 0.995
        cols[("High", sym)] = close * 1.01
        cols[("Low", sym)] = close * 0.99
        cols[("Close", sym)] = close
        cols[("Volume", sym)] = np.full(len(DAYS), 1_000_000.0)
    if not cols:
        return pd.DataFrame()  # what yfinance returns when nothing downloads
    df = pd.DataFrame(cols, index=DAYS)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    return df


QUOTE = {
    "symbol": "ABC",
    "shortName": "ABC Corp",
    "regularMarketPrice": 10.0,
    "regularMarketChangePercent": 12.3456,
    "regularMarketVolume": 3_000_000,
    "averageDailyVolume3Month": 1_000_000,
    "marketCap": 5e9,
}
INFO = {
    "AAPL": {"quoteType": "EQUITY", "longName": "Apple Inc.", "sector": "Technology"},
    "NOPRICE": {"quoteType": "EQUITY"},
    "ZZZZ": {},
}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(server, "_download", _fake_download)
    monkeypatch.setattr(server, "_screen", lambda name, count: [QUOTE] * count)
    monkeypatch.setattr(server, "_info", lambda s: INFO[s])
    monkeypatch.setattr(server, "_today", lambda: pd.Timestamp("2026-10-31"))


def test_market_summary():
    out = server.get_market_summary("3mo")
    assert set(out["indices"]) == set(server.INDICES.values())
    sp = out["indices"]["S&P 500"]
    assert sp["last"] is not None and sp["change_window_pct"] is not None and sp["change_1d_pct"] is not None
    assert out["volatility_and_rates"]["vix"]["change_window_points"] is not None
    assert (
        isinstance(out["breadth"]["sectors_up"], int)
        and out["breadth"]["sectors_total"] == 11
        and out["breadth"]["leader"] in server.SECTORS.values()
    )
    assert out["sp500_trend"]["cross"] is not None and out["as_of"] == "2026-10-30"


def test_sector_performance_ranked():
    out = server.get_sector_performance("ytd")
    changes = [s["change_window_pct"] for s in out["sectors"]]
    assert len(changes) == 11 and changes == sorted(changes, reverse=True)
    assert out["leader"] == out["sectors"][0]["sector"]
    first = out["sectors"][0]
    assert first["vs_sp500_pct_points"] == pytest.approx(
        first["change_window_pct"] - out["sp500_change_window_pct"], abs=0.001
    )


def test_market_movers():
    out = server.get_market_movers()
    assert set(out) >= {"gainers", "losers", "most_active"} and len(out["gainers"]) == 10
    assert out["gainers"][0] == {
        "symbol": "ABC",
        "name": "ABC Corp",
        "price": 10.0,
        "change_pct": 12.35,
        "volume": 3_000_000,
        "volume_vs_3m_avg": 3.0,
        "market_cap": 5e9,
    }


def test_market_movers_screener_failure(monkeypatch):
    def broken(name, count):
        raise RuntimeError("HTTP 503")

    monkeypatch.setattr(server, "_screen", broken)
    with pytest.raises(ToolError, match="screener day_gainers unavailable"):
        server.get_market_movers()


def test_stock_analysis():
    out = server.get_stock_analysis(" aapl ", "6mo")
    assert out["symbol"] == "AAPL" and out["performance"]["sector_etf"] == "XLK"
    assert out["performance"]["vs_sector_pct_points"] is not None
    assert out["range_52w"]["below_high_pct"] <= 0 <= out["range_52w"]["above_low_pct"]
    assert out["moving_averages"]["ma200"] is not None and out["momentum"]["rsi14"] is not None
    assert out["risk"]["beta_vs_sp500"] is not None and out["volume"]["vs_3m_avg"] == 1.0
    assert out["trend"] in {"uptrend", "downtrend", "mixed"} and "RSI" in out["rules"]


def test_stock_analysis_errors():
    with pytest.raises(ToolError, match="Unknown symbol ZZZZ"):
        server.get_stock_analysis("ZZZZ")
    with pytest.raises(ToolError, match="No price history for NOPRICE"):
        server.get_stock_analysis("NOPRICE")


def test_historical_data_weekly():
    out = server.get_historical_data("AAPL", "1y")
    assert out["interval"] == "weekly" and 50 <= len(out["bars"]) <= 54
    bar = out["bars"][0]
    assert set(bar) == {"date", "open", "high", "low", "close", "volume"}
    assert out["bars"][1]["volume"] == 5_000_000  # a full week; the first bar may be partial
    assert out["summary"]["end"] == "2026-10-30" and out["summary"]["avg_daily_volume"] == 1_000_000
    assert server.get_historical_data("AAPL", "1mo")["interval"] == "daily"


async def test_tools_registered_and_errors_reach_client():
    async with Client(server.mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("get_historical_data", {"symbol": "NOPRICE"})
    assert names == {
        "get_market_summary",
        "get_stock_analysis",
        "get_market_movers",
        "get_sector_performance",
        "get_historical_data",
    }
    assert result.is_error and "No price history for NOPRICE" in result.content[0].text
