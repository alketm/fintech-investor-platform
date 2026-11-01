"""Backtest tools with yfinance replaced by a fake price history: no network access."""

import numpy as np
import pandas as pd
import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_backtest import server

DAYS = pd.bdate_range("2019-01-01", "2025-12-31")
PRICES = pd.Series(
    100 * np.cumprod(1 + np.random.default_rng(2).normal(0.0004, 0.012, len(DAYS))), index=DAYS
)


@pytest.fixture(autouse=True)
def fake_history(monkeypatch):
    def history(symbol, start, end):
        if symbol == "NONE":
            return pd.Series(dtype=float)
        return PRICES[(PRICES.index >= start) & (PRICES.index < end)]

    monkeypatch.setattr(server, "_history", history)


@pytest.mark.parametrize(
    ("tool", "params"),
    [
        (server.backtest_moving_average, {"fast": 20, "slow": 100}),
        (server.backtest_time_series_momentum, {"lookback_days": 126, "skip_days": 21}),
        (server.backtest_rsi_mean_reversion, {"period": 14, "lower": 30, "upper": 70, "exit_level": 50}),
    ],
)
def test_long_short_tools(tool, params):
    out = tool(" abc ", "2022-01-01", "2025-01-01", **params)
    assert out["symbol"] == "ABC" and out["start"] >= "2022-01-01"
    assert out["parameters"] == {**params, "cost_bps": 5.0}
    assert set(out["strategy"]) == set(out["buy_and_hold"])
    assert out["equity_curve"][0]["date"] < out["equity_curve"][-1]["date"]
    a = out["activity"]
    assert a["pct_days_long"] + a["pct_days_short"] + a["pct_days_flat"] == pytest.approx(100, abs=0.2)
    assert out["rule"] and "next day" in out["assumptions"]


def test_long_short_reports_spy_benchmark_over_the_same_days():
    out = server.backtest_moving_average("ABC", "2022-01-01", "2025-01-01", fast=20, slow=100)
    # The fake history serves the same prices for every symbol, so SPY matches the symbol's buy and hold.
    assert out["benchmark"] == {"symbol": "SPY", **out["buy_and_hold"]}
    assert set(out["equity_curve"][-1]) == {"date", "strategy", "buy_and_hold", "benchmark"}
    missing = server.backtest_moving_average(
        "ABC", "2022-01-01", "2025-01-01", fast=20, slow=100, benchmark="NONE"
    )
    assert missing["benchmark"] is None and "benchmark" not in missing["equity_curve"][-1]


def test_buy_and_hold_reports_benchmark_and_curve():
    out = server.backtest_buy_and_hold("abc", "2022-01-01", "2025-01-01")
    assert out["symbol"] == "ABC" and out["sharpe_ratio"] is not None
    bench = out["benchmark"]
    assert bench["symbol"] == "SPY" and bench["total_return_pct"] == out["total_return_pct"]
    curve = out["equity_curve"]
    assert curve[0]["buy_and_hold"] == pytest.approx(10_000, rel=0.05)
    assert curve[-1]["buy_and_hold"] == curve[-1]["benchmark"]


def test_signals_are_ready_on_the_first_day():
    out = server.backtest_moving_average("ABC", "2022-01-03", "2023-01-01", fast=50, slow=200)
    assert out["activity"]["pct_days_flat"] == 0  # the warm-up filled the 200-day average
    assert "warning" not in out["parameters"]


def test_parameter_validation_and_missing_data():
    with pytest.raises(ToolError, match="fast < slow"):
        server.backtest_moving_average("ABC", "2022-01-01", "2023-01-01", fast=200, slow=50)
    with pytest.raises(ToolError, match="exit_level"):
        server.backtest_rsi_mean_reversion(
            "ABC", "2022-01-01", "2023-01-01", lower=60, upper=70, exit_level=50
        )
    with pytest.raises(ToolError, match="skip_days"):
        server.backtest_time_series_momentum(
            "ABC", "2022-01-01", "2023-01-01", lookback_days=20, skip_days=30
        )
    with pytest.raises(ToolError, match="No price history"):
        server.backtest_moving_average("NONE", "2022-01-01", "2023-01-01")


async def test_tools_registered():
    async with Client(server.mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert names == {
        "backtest_buy_and_hold",
        "backtest_moving_average",
        "backtest_time_series_momentum",
        "backtest_rsi_mean_reversion",
        "backtest_policy_uncertainty",
    }


def test_policy_uncertainty_tool(monkeypatch):
    rng = np.random.default_rng(4)
    index = pd.Series(1.0 + np.abs(rng.normal(0, 0.3, len(DAYS))), index=DAYS)
    monkeypatch.setattr(
        server, "_policy_uncertainty", lambda start: index[index.index >= start]
    )  # runs to 2025-12
    out = server.backtest_policy_uncertainty("SPY", "2022-01-01", "2025-01-01")
    assert out["parameters"] == {
        "lookback_days": 252,
        "threshold": 0.5,
        "signal_lag_days": 1,
        "cost_bps": 5.0,
    }
    u = out["uncertainty"]
    assert u["value_date"] <= "2025-01-01" and "KCPRU" in u["source"]  # as of the test end, not today
    assert u["pct_days_high"] + u["pct_days_low"] + u["pct_days_neutral"] == pytest.approx(100, abs=0.2)
    assert "Kansas City Fed" in out["rule"]
    with pytest.raises(ToolError, match="lookback_days >= 20"):
        server.backtest_policy_uncertainty("SPY", "2022-01-01", "2025-01-01", lookback_days=5)


def test_policy_uncertainty_needs_fred_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(ToolError, match="FRED_API_KEY is not set"):
        server.backtest_policy_uncertainty("SPY", "2022-01-01", "2025-01-01")
