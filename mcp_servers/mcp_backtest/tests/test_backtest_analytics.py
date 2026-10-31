import pandas as pd
import pytest

from alko_mcp_backtest.analytics import buy_and_hold_stats


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
