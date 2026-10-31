"""Macro tools with FRED and yfinance replaced by fakes: no network access or API key."""

import numpy as np
import pandas as pd
import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_macro import analytics as a
from alko_mcp_macro import fred, server

MONTHS = pd.date_range(end="2026-09-30", periods=120, freq="ME")
DAYS = pd.bdate_range(end="2026-10-30", periods=1300)


def _fake_fred(keys):
    rng = np.random.default_rng(0)
    base = {
        "real_gdp_growth": 2.5,
        "payrolls_change": 150,
        "industrial_production_yoy": 1.0,
        "core_cpi_yoy": 3.0,
        "core_pce_yoy": 2.8,
        "fed_funds": 4.5,
        "curve_10y_2y": 0.4,
        "curve_10y_3m": 0.2,
        "high_yield_spread": 3.2,
        "financial_conditions": -0.4,
        "sahm_rule": 0.2,
        "unemployment": 4.2,
        "card_delinquency": 3.0,
        "real_consumption_yoy": 2.5,
    }
    out = {}
    for k in keys:
        if k == "consumer_sentiment":
            out[k] = pd.Series(70 + rng.normal(0, 5, len(MONTHS)), index=MONTHS)
        elif k == "housing_starts":
            out[k] = pd.Series(dtype=float)  # a series that failed to load
        else:
            out[k] = pd.Series(base.get(k, 1.0), index=MONTHS, dtype=float)
    return out


def _fake_closes(names, symbol=None):
    rng = np.random.default_rng(1)
    cols = {n: 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(DAYS))) for n in names}
    if "vix" in cols:
        cols["vix"] = np.full(len(DAYS), 18.0)
    if symbol:
        cols[symbol] = 100 * np.cumprod(1 + rng.normal(0.0005, 0.015, len(DAYS)))
    return pd.DataFrame(cols, index=DAYS)


INFO = {
    "AAPL": {
        "quoteType": "EQUITY",
        "longName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
    },
    "AMZN": {"quoteType": "EQUITY", "longName": "Amazon", "sector": "Consumer Cyclical"},
    "NOPE": {},
}


@pytest.fixture
def fakes(monkeypatch):
    monkeypatch.setattr(server, "_fred", _fake_fred)
    monkeypatch.setattr(server, "_closes", _fake_closes)
    monkeypatch.setattr(server, "_info", lambda s: INFO[s])


def test_economic_indicators_market_wide(fakes):
    out = server.get_economic_indicators()
    groups = out["indicators"]
    assert set(groups) == {i.group for i in a.INDICATORS}
    assert (
        groups["rates"]["fed_funds"]["value"] == 4.5
        and groups["rates"]["fed_funds"]["fred_series"] == "FEDFUNDS"
    )
    assert groups["housing"]["housing_starts"]["value"] is None  # missing series is null, not a failure
    assert "stock" not in out


def test_economic_indicators_with_symbol(fakes):
    stock = server.get_economic_indicators(" aapl ")["stock"]
    assert stock["sector"] == "Technology" and stock["most_relevant_groups"] == ["rates", "growth"]
    with pytest.raises(ToolError, match="Unknown symbol NOPE"):
        server.get_economic_indicators("NOPE")


def test_macro_environment(fakes):
    out = server.analyze_macro_environment()
    assert out["regime"] == "overheating risk"  # expanding, core inflation above target and not falling
    assert out["policy"]["stance"] == "restrictive"  # 4.5 - 2.8 = 1.7
    assert out["stress"]["label"] == "calm" and out["recession"]["risk"] == "low"
    assert set(out["market_signals"]) >= {"oil_3m_pct", "dollar_3m_pct", "copper_to_gold_3m_pct"}
    assert "stock" not in out

    stock = server.analyze_macro_environment("AAPL")["stock"]
    assert stock["beta_to_sp500"] is not None
    assert set(stock["correlation_with"]) == {"us10y_yield_change", "oil_return", "dollar_return"}


def test_consumer_sentiment(fakes):
    out = server.analyze_consumer_sentiment()
    assert out["read"]["label"] in {"strong", "mixed", "weak"}
    assert out["sentiment"]["percentile_since_1978"] is not None
    assert out["market_view"]["discretionary_vs_staples_12m_pct"] is not None

    stock = server.analyze_consumer_sentiment("AMZN")["stock"]
    assert stock["consumer_sensitivity"] == "high"
    assert set(stock["correlation_with"]) == {"sentiment_change", "discretionary_vs_staples"}


async def test_missing_key_message_reaches_client(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    async with Client(server.mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("get_economic_indicators", {})
    assert names == {"analyze_macro_environment", "get_economic_indicators", "analyze_consumer_sentiment"}
    assert result.is_error and "FRED_API_KEY is not set" in result.content[0].text


def test_fred_many_raises_when_every_series_fails(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test-key")

    def fail(*args):
        raise fred.FredError("FRED request for X failed (HTTP 400).")

    monkeypatch.setattr(fred, "series", fail)
    with pytest.raises(fred.FredError):
        fred.many({"a": ("A", "lin", "2020-01-01"), "b": ("B", "lin", "2020-01-01")})


def test_fred_errors_never_contain_the_key():
    assert fred._redact("bad api_key=secret123 given", "secret123") == "bad api_key=*** given"
