import pandas as pd
import pytest

from alko_mcp_backtest.analytics import buy_and_hold_stats, weekly_equity_curve


def test_doubling_over_one_year():
    idx = pd.to_datetime(["2025-01-01", "2025-07-01", "2026-01-01"])
    stats = buy_and_hold_stats(pd.Series([100.0, 150.0, 200.0], index=idx))
    assert stats["total_return_pct"] == 100.0
    assert stats["final_value"] == 20_000.0
    assert stats["cagr_pct"] == pytest.approx(100.0, abs=0.2)
    assert stats["max_drawdown_pct"] == 0.0


def test_max_drawdown():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    stats = buy_and_hold_stats(pd.Series([100.0, 120.0, 60.0, 90.0], index=idx))
    assert stats["max_drawdown_pct"] == -50.0
    assert stats["total_return_pct"] == -10.0


def test_needs_two_prices():
    with pytest.raises(ValueError):
        buy_and_hold_stats(pd.Series([100.0], index=pd.to_datetime(["2024-01-01"])))


def test_sharpe_is_none_without_volatility():
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    assert buy_and_hold_stats(pd.Series([100.0, 100.0, 100.0], index=idx))["sharpe_ratio"] is None


def test_weekly_equity_curve_starts_each_series_at_capital():
    idx = pd.bdate_range("2024-01-01", periods=10)
    a = pd.Series(range(100, 110), index=idx, dtype=float)
    curve = weekly_equity_curve({"a": a, "b": a * 2}, 1_000)
    assert [p["date"] for p in curve] == ["2024-01-05", "2024-01-12"]
    assert curve[-1] == {"date": "2024-01-12", "a": 1_090.0, "b": 1_090.0}
