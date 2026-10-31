import numpy as np
import pandas as pd
import pytest

from alko_mcp_backtest import strategies as st


def daily(values, start="2025-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_moving_average_positions():
    up = st.moving_average_positions(daily(np.linspace(100, 200, 60)), 5, 20)
    assert (up.iloc[:19] == 0).all() and (up.iloc[19:] == 1).all()
    down = st.moving_average_positions(daily(np.linspace(200, 100, 60)), 5, 20)
    assert (down.iloc[19:] == -1).all()


def test_time_series_momentum_only_changes_at_month_end():
    prices = daily(list(np.linspace(100, 200, 150)) + list(np.linspace(200, 80, 150)))
    pos = st.time_series_momentum_positions(prices, lookback_days=60, skip_days=5)
    changes = pos[pos.diff().fillna(0) != 0].index
    month_ends = prices.index.to_series().groupby(prices.index.to_period("M")).max()
    assert len(changes) >= 2 and set(changes) <= set(month_ends)
    assert pos.iloc[100] == 1 and pos.iloc[-1] == -1


def test_rsi_series():
    assert st.rsi(daily(range(1, 40)), 14).iloc[-1] == 100.0
    assert np.isnan(st.rsi(daily(range(1, 40)), 14).iloc[5])


def test_rsi_mean_reversion_enters_and_exits():
    # Steady fall pushes RSI under 30 (long); a rebound lifts it back over 50 (exit), then a rally over 70 (short).
    prices = daily(
        list(np.linspace(100, 70, 30)) + list(np.linspace(70, 80, 10)) + list(np.linspace(80, 130, 30))
    )
    pos = st.rsi_mean_reversion_positions(prices, 14, 30, 70, 50)
    r = st.rsi(prices, 14)
    first_long = pos[pos == 1].index[0]
    assert r[first_long] < 30
    exit_day = pos[(pos.shift(1) == 1) & (pos == 0)].index[0]
    assert r[exit_day] >= 50
    assert (pos == -1).any() and r[pos[pos == -1].index[0]] > 70


def test_run_backtest_next_day_execution_costs_and_trades():
    closes = daily([100, 110, 99, 99, 108.9])
    positions = daily([1, -1, 0, 1, 1])  # decided at each close
    out = st.run_backtest(closes, positions, closes.index[0], 10_000, cost_bps=0)
    # held over days 2-5 = [1, -1, 0, 1] against returns [+10%, -10%, 0, +10%]
    assert out["strategy"]["total_return_pct"] == pytest.approx(33.1, abs=0.01)
    assert out["buy_and_hold"]["total_return_pct"] == pytest.approx(8.9, abs=0.01)
    activity = out["activity"]
    assert activity["position_changes"] == 4
    assert (activity["pct_days_long"], activity["pct_days_short"], activity["pct_days_flat"]) == (
        50.0,
        25.0,
        25.0,
    )
    assert activity["closed_trades"] == 2 and activity["win_rate_pct"] == 100.0
    assert activity["current_position"] == "long"
    assert [t["side"] for t in out["recent_trades"]] == ["long", "short", "long"] and out["recent_trades"][
        -1
    ]["open"]

    with_costs = st.run_backtest(closes, positions, closes.index[0], 10_000, cost_bps=10)
    # turnover [1, 2, 1, 1] at 10 bps
    expected = (1.1 - 0.001) * (1.1 - 0.002) * (1 - 0.001) * (1.1 - 0.001) - 1
    assert with_costs["strategy"]["total_return_pct"] == pytest.approx(expected * 100, abs=0.01)
    assert with_costs["activity"]["total_costs"] > 0


def test_run_backtest_uses_warmup_signal_on_first_day():
    closes = daily([100, 100, 100, 110, 121])
    positions = daily([0, 0, -1, -1, -1])
    out = st.run_backtest(closes, positions, closes.index[2], 10_000, cost_bps=0)
    assert out["start"] == str(closes.index[2].date())
    assert out["strategy"]["total_return_pct"] == pytest.approx(
        -19.0, abs=0.01
    )  # short through +10%, +10%: 0.9*0.9


def test_stats_drawdown_counts_drop_from_start():
    s = st.stats(pd.Series([-0.5, 0.2]), 1000)
    assert s["max_drawdown_pct"] == -50.0 and s["final_value"] == 600.0


def test_run_backtest_needs_data():
    with pytest.raises(ValueError):
        st.run_backtest(daily([1, 2]), daily([1, 1]), pd.Timestamp("2025-01-01"), 1000, 0)
