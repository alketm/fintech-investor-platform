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


def test_run_backtest_benchmark_fills_missing_days_and_uses_test_period():
    closes = daily([100, 110, 99, 99, 108.9])
    positions = daily([1, 1, 1, 1, 1])
    # Benchmark lacks the third day and has a warm-up day before the test start.
    bench = pd.Series(
        [50.0, 100, 120, 90], index=[closes.index[0] - pd.Timedelta(days=3), *closes.index[[0, 1, 3]]]
    )
    out = st.run_backtest(closes, positions, closes.index[0], 10_000, cost_bps=0, benchmark=bench)
    # 100 -> 120 -> (120 carried) -> 90 -> (90 carried): -10%
    assert out["benchmark"]["total_return_pct"] == pytest.approx(-10.0, abs=0.01)
    assert out["equity_curve"][-1]["benchmark"] == pytest.approx(9_000, abs=0.01)
    assert st.run_backtest(closes, positions, closes.index[0], 10_000, cost_bps=0)["benchmark"] is None


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


def test_policy_uncertainty_positions_follow_zscore_with_lag():
    closes = daily([100.0] * 60)
    index = daily([1.0] * 40 + [5.0] * 10 + [0.0] * 10)  # calm, then a spike, then unusually low
    pos = st.policy_uncertainty_positions(closes, index, lookback_days=30, threshold=0.5, lag_days=1)
    first_spike = closes.index[40]
    assert pos[first_spike] == 0  # the spike is only known with a one-day lag
    assert pos[closes.index[41]] == -1  # high uncertainty -> short
    assert pos[closes.index[51]] == 1  # unusually low -> long
    assert (pos.iloc[:15] == 0).all()  # not enough history for a z-score yet


def test_uncertainty_index_is_aligned_to_trading_days():
    closes = daily([100.0] * 5, start="2025-01-06")  # Mon..Fri
    index = pd.Series([1.0, 3.0], index=pd.to_datetime(["2025-01-03", "2025-01-08"]))  # Fri before, Wed
    z = st.uncertainty_zscore(closes, index, lookback_days=2, lag_days=0)
    aligned = index.reindex(closes.index.union(index.index)).ffill().reindex(closes.index)
    assert aligned.tolist() == [1.0, 1.0, 3.0, 3.0, 3.0] and len(z) == 5


def test_sentiment_trend_positions_rebalance_at_month_end():
    # Monthly readings dated the 1st: above the 3-month average in March, below in April.
    sentiment = pd.Series(
        [70.0, 70, 76, 64, 64],
        index=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01"]),
    )
    closes = pd.Series(100.0, index=pd.bdate_range("2024-03-01", "2024-05-31"))
    pos = st.sentiment_trend_positions(closes, sentiment, ma_months=3, lag_months=0)
    assert (
        pos[:"2024-03-28"] == 0
    ).all()  # no decision until March's reading is final at its last trading day
    assert pos["2024-03-29"] == 1 and (pos["2024-04-01":"2024-04-29"] == 1).all()
    assert pos["2024-04-30"] == -1 and (pos["2024-05-01":] == -1).all()  # May: 64 < 68 (avg of 76, 64, 64)

    lagged = st.sentiment_trend_positions(closes, sentiment, ma_months=3, lag_months=1)
    assert lagged["2024-03-29"] == 0 and lagged["2024-04-30"] == 1 and lagged["2024-05-31"] == -1


def test_sentiment_trend_table_shifts_by_release_lag():
    sentiment = pd.Series([70.0, 70, 76], index=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]))
    trend = st.sentiment_trend(sentiment, 3, 1).dropna()
    assert list(trend.index.astype(str)) == ["2024-04"]
    assert trend.iloc[0].to_dict() == {"value": 76.0, "moving_average": 72.0, "signal": 1.0}
