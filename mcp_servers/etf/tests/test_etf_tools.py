"""Tool tests with yfinance replaced by fakes: no network access."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from alko_mcp_etf import server

INFO = {
    "VTI": {
        "quoteType": "ETF",
        "longName": "Vanguard Total Stock Market",
        "netExpenseRatio": 0.03,
        "totalAssets": 2.0e12,
        "yield": 0.0106,
        "fundInceptionDate": 990662400,
    },
    "BND": {"quoteType": "ETF", "longName": "Vanguard Total Bond Market", "netExpenseRatio": 0.03},
    "AAPL": {"quoteType": "EQUITY"},
    "NOPE": {},
}


def _fake_ticker(symbol):
    funds = SimpleNamespace(
        top_holdings=pd.DataFrame(
            {"Name": ["Apple", "Microsoft"], "Holding Percent": [0.066, 0.052]}, index=["AAPL", "MSFT"]
        ),
        sector_weightings={"technology": 0.3, "healthcare": 0.1, "realestate": 0.0},
        asset_classes={"stockPosition": 0.99, "cashPosition": 0.01},
        fund_operations=pd.DataFrame({symbol: [0.02]}, index=["Annual Holdings Turnover"]),
    )
    return SimpleNamespace(info=INFO.get(symbol, {}), funds_data=funds)


def _fake_download(symbols, start):
    idx = pd.bdate_range("2025-06-02", periods=300)
    rng = np.random.default_rng(0)
    close, adj = {}, {}
    for s in symbols:
        if s == "NOPE":
            close[s] = adj[s] = pd.Series(np.nan, index=idx)
        elif s == "^IRX":
            close[s] = adj[s] = pd.Series(4.0, index=idx)
        else:
            prices = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(idx)))
            close[s], adj[s] = pd.Series(prices, index=idx), pd.Series(prices * 0.98, index=idx)
    return pd.DataFrame(close), pd.DataFrame(adj)


@pytest.fixture(autouse=True)
def fake_yfinance(monkeypatch):
    monkeypatch.setattr(server, "_ticker", _fake_ticker)
    monkeypatch.setattr(server, "_download", _fake_download)


def test_symbols_are_normalized_and_validated():
    assert server._symbols([" vti", "VTI", "bnd", ""]) == ["VTI", "BND"]
    with pytest.raises(ValueError):
        server._symbols([])
    with pytest.raises(ValueError):
        server._symbols([f"S{i}" for i in range(21)])


def test_basic_info_reports_non_etfs_as_errors():
    out = server.get_etf_basic_info(["vti", "AAPL", "NOPE"])
    assert [r["symbol"] for r in out["results"]] == ["VTI"]
    vti = out["results"][0]
    assert vti["expense_ratio_pct"] == 0.03 and vti["yield_pct"] == 1.06
    assert vti["inception_date"] == "2001-05-24" and vti["annual_turnover_pct"] == 2.0
    assert "Not an ETF" in out["errors"]["AAPL"] and out["errors"]["NOPE"] == "Unknown symbol"


def test_top_holdings():
    holdings = server.get_etf_top_holdings(["VTI"])["results"][0]
    assert holdings["holdings"][0] == {"symbol": "AAPL", "name": "Apple", "weight_pct": 6.6}
    assert holdings["top10_weight_pct"] == 11.8


def test_top_holdings_missing_data_gets_a_note(monkeypatch):
    def no_holdings(symbol):
        ticker = _fake_ticker(symbol)
        ticker.funds_data.top_holdings = pd.DataFrame(columns=["Name", "Holding Percent"])
        return ticker

    monkeypatch.setattr(server, "_ticker", no_holdings)
    bnd = server.get_etf_top_holdings(["BND"])["results"][0]
    assert bnd["holdings"] == [] and bnd["top10_weight_pct"] is None and "note" in bnd


def test_sector_breakdown():
    sectors = server.get_etf_sector_breakdown(["VTI"])["results"][0]
    assert [s["sector"] for s in sectors["sectors"]] == ["technology", "healthcare"]
    assert sectors["asset_classes"] == {"stock": 99.0, "cash": 1.0}


def test_performance_and_history_batch_with_errors():
    perf = server.get_etf_performance(["VTI", "BND", "NOPE"], "1y")
    assert [r["symbol"] for r in perf["results"]] == ["VTI", "BND"]
    assert "NOPE" in perf["errors"] and perf["window"] == "1y"

    history = server.get_etf_price_history(["VTI"], "1y")
    assert history["interval"] == "weekly"
    assert 55 <= len(history["results"][0]["points"]) <= 65


def test_risk_metrics_uses_t_bill_rate_and_benchmark():
    out = server.get_etf_risk_metrics(["VTI", "NOPE"], "1y")
    assert out["risk_free_rate_pct"] == 4.0 and "^IRX" in out["risk_free_rate_source"]
    assert out["benchmark"] == "SPY"
    vti = out["results"][0]
    assert vti["beta"] is not None and vti["sharpe_ratio"] is not None
    assert "NOPE" in out["errors"]
