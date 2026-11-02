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
        "backtest_consumer_sentiment",
        "backtest_vix_volatility",
    }


def test_policy_uncertainty_tool(monkeypatch):
    rng = np.random.default_rng(4)
    index = pd.Series(1.0 + np.abs(rng.normal(0, 0.3, len(DAYS))), index=DAYS)
    monkeypatch.setattr(
        server, "_policy_uncertainty", lambda start: index[index.index >= start]
    )  # runs to 2025-12
    out = server.backtest_policy_uncertainty("SPY", "2022-01-01", "2025-01-01")
    assert out["parameters"] == {
        "ma_days": 21,
        "short_above": 1.4,
        "long_below": 1.2,
        "exit_level": 1.3,
        "signal_lag_days": 1,
        "cost_bps": 5.0,
    }
    u = out["uncertainty"]
    assert u["value_date"] <= "2025-01-01" and "KCPRU" in u["source"]  # as of the test end, not today
    assert u["ratio_at_end"] == pytest.approx(u["value_at_end"] / u["moving_average_at_end"], abs=0.01)
    assert u["signal_at_end"] == out["activity"]["current_position"]
    a = out["activity"]
    assert a["pct_days_long"] > 0 and a["pct_days_short"] > 0 and a["pct_days_flat"] > 0
    assert "Kansas City Fed" in out["rule"] and "short above 1.4x" in out["rule"]
    with pytest.raises(ToolError, match="ma_days >= 2"):
        server.backtest_policy_uncertainty("SPY", "2022-01-01", "2025-01-01", ma_days=1)
    with pytest.raises(ToolError, match="long_below <= exit_level"):
        server.backtest_policy_uncertainty("SPY", "2022-01-01", "2025-01-01", exit_level=1.1)


def test_policy_uncertainty_needs_fred_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(ToolError, match="FRED_API_KEY is not set"):
        server.backtest_policy_uncertainty("SPY", "2022-01-01", "2025-01-01")


SENTIMENT = pd.Series(
    80 + 25 * np.sin(np.arange(576) / 3), index=pd.date_range("1978-01-01", periods=576, freq="MS")
)


def test_consumer_sentiment_tool(monkeypatch):
    monkeypatch.setattr(server, "_consumer_sentiment", lambda start: SENTIMENT[SENTIMENT.index >= start])
    out = server.backtest_consumer_sentiment("SPY", "2020-01-01", "2025-01-01")
    assert out["parameters"] == {
        "ma_months": 3,
        "short_below_pct": 95.0,
        "long_above_pct": 97.0,
        "exit_pct": 96.0,
        "release_lag_months": 0,
        "cost_bps": 5.0,
    }
    s = out["sentiment"]
    assert s["reading_month"] == "2024-12" and "UMCSENT" in s["source"]  # as of the test end, not today
    assert s["ratio_pct_at_end"] == pytest.approx(
        s["value_at_end"] / s["moving_average_at_end"] * 100, abs=0.2
    )
    assert s["signal_at_end"] == out["activity"]["current_position"]
    a = out["activity"]
    assert a["pct_days_long"] > 0 and a["pct_days_short"] > 0 and a["pct_days_flat"] > 0
    assert "short below 95%" in out["rule"] and "neutral below 96%" in out["rule"]
    with pytest.raises(ToolError, match="ma_months >= 2"):
        server.backtest_consumer_sentiment("SPY", "2020-01-01", "2025-01-01", ma_months=1)
    with pytest.raises(ToolError, match="short_below_pct <= exit_pct"):
        server.backtest_consumer_sentiment("SPY", "2020-01-01", "2025-01-01", exit_pct=98)


def test_consumer_sentiment_starts_its_state_before_the_test(monkeypatch):
    """The band rule depends on its past state, so it runs from the earliest reading, not from the test start."""
    requested = []
    monkeypatch.setattr(
        server,
        "_consumer_sentiment",
        lambda start: requested.append(start) or SENTIMENT[SENTIMENT.index >= start],
    )
    server.backtest_consumer_sentiment("SPY", "2022-01-01", "2025-01-01")
    assert requested == ["1978-01-01"]


def test_consumer_sentiment_needs_fred_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(ToolError, match="FRED_API_KEY is not set"):
        server.backtest_consumer_sentiment("SPY", "2022-01-01", "2025-01-01")


def test_vix_volatility_tool(monkeypatch):
    rv = server.strategies.realized_volatility(PRICES, 20)
    # A VIX that swings between 1.4x and 2.3x realized volatility, so every state is visited.
    vix = (rv * (1.85 + 0.45 * np.sin(np.arange(len(rv)) / 15))).dropna()

    def history(symbol, start, end):
        series = vix if symbol == "^VIX" else PRICES
        return series[(series.index >= start) & (series.index < end)]

    monkeypatch.setattr(server, "_history", history)
    out = server.backtest_vix_volatility("XLK", "2022-01-01", "2025-01-01")
    assert out["parameters"] == {
        "window_days": 20,
        "short_above": 2.0,
        "long_below": 1.7,
        "exit_level": 1.8,
        "cost_bps": 5.0,
    }
    v = out["volatility"]
    assert v["date"] <= "2025-01-01" and v["ratio_at_end"] == pytest.approx(
        v["vix_at_end"] / v["realized_vol_at_end"], abs=0.01
    )
    assert v["signal_at_end"] == out["activity"]["current_position"]
    a = out["activity"]
    assert a["pct_days_long"] > 0 and a["pct_days_short"] > 0 and a["pct_days_flat"] > 0
    assert "short above 2x" in out["rule"] and "long goes neutral above 1.8x" in out["rule"]
    assert "warning" not in out["parameters"]

    with pytest.raises(ToolError, match="long_below <= exit_level"):
        server.backtest_vix_volatility("XLK", "2022-01-01", "2025-01-01", exit_level=2.5)
    monkeypatch.setattr(server, "_history", lambda symbol, start, end: pd.Series(dtype=float))
    with pytest.raises(ToolError, match="No SPY history"):
        server.backtest_vix_volatility("XLK", "2022-01-01", "2025-01-01")
