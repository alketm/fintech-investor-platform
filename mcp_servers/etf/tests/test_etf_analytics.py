import numpy as np
import pandas as pd
import pytest

from alko_mcp_etf import analytics


def _series(values, start="2025-01-01", freq="B"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=freq), dtype=float)


def test_window_start():
    today = pd.Timestamp("2026-10-31 15:30")
    assert analytics.window_start("ytd", today) == pd.Timestamp("2026-01-01")
    assert analytics.window_start("3mo", today) == pd.Timestamp("2026-07-31")
    assert analytics.window_start("3y", today) == pd.Timestamp("2023-10-31")
    assert analytics.window_start("max", today) is None


def test_resample_rule():
    assert analytics.resample_rule("6mo") == ("daily", None)
    assert analytics.resample_rule("3y") == ("weekly", "W-FRI")
    assert analytics.resample_rule("max") == ("monthly", "ME")


def test_performance_separates_price_and_total_return():
    idx = pd.to_datetime(["2025-01-02", "2025-07-01", "2026-01-02"])
    close = pd.Series([100.0, 105.0, 110.0], index=idx)
    adj = pd.Series([95.0, 101.0, 110.0], index=idx)  # earlier adjusted prices lower: dividends paid
    result = analytics.performance(close, adj)
    assert result["price_return_pct"] == 10.0
    assert result["total_return_pct"] == pytest.approx(15.789, abs=0.001)
    assert result["annualized_return_pct"] == pytest.approx(15.789, abs=0.05)
    assert result["start_date"] == "2025-01-02" and result["trading_days"] == 3


def test_performance_skips_annualizing_short_windows():
    s = _series([100.0, 101.0, 102.0])
    assert analytics.performance(s, s)["annualized_return_pct"] is None


def test_risk_metrics_known_values():
    rng = np.random.default_rng(1)
    bench_r = rng.normal(0.0004, 0.01, 500)
    etf_r = 0.8 * bench_r + rng.normal(0, 0.002, 500)
    bench = _series(100 * np.cumprod(np.r_[1, 1 + bench_r]))
    etf = _series(100 * np.cumprod(np.r_[1, 1 + etf_r]))

    m = analytics.risk_metrics(etf, bench, risk_free_annual=0.0)

    assert m["beta"] == pytest.approx(0.8, abs=0.03)
    assert m["correlation"] > 0.95
    assert m["annualized_volatility_pct"] == pytest.approx(
        np.std(etf_r, ddof=1) * np.sqrt(252) * 100, rel=1e-3
    )
    assert m["var_95_1d_pct"] == pytest.approx(np.quantile(etf_r, 0.05) * 100, abs=0.01)
    assert m["cvar_95_1d_pct"] <= m["var_95_1d_pct"] < 0
    assert m["max_drawdown_pct"] < 0
    assert m["max_drawdown_peak"] <= m["max_drawdown_trough"]
    assert m["daily_returns"] == 500


def test_max_drawdown_dates():
    s = _series([100, 120, 90, 60, 80, 130] + [130] * 20)
    m = analytics.risk_metrics(s, s, 0.0)
    assert m["max_drawdown_pct"] == -50.0
    assert m["max_drawdown_peak"] == str(s.index[1].date())
    assert m["max_drawdown_trough"] == str(s.index[3].date())
    assert m["beta"] == 1.0


def test_risk_metrics_needs_enough_history():
    with pytest.raises(ValueError):
        analytics.risk_metrics(_series(range(1, 10)), _series(range(1, 10)), 0.0)


def test_price_points_weekly_uses_last_trading_day():
    close = _series(range(1, 11))  # 2025-01-01 (Wed) .. 2025-01-14 (Tue), business days
    points = analytics.price_points(close, close, "W-FRI")
    assert [p["date"] for p in points] == ["2025-01-03", "2025-01-10", "2025-01-14"]
    assert points[0]["close"] == 3.0
