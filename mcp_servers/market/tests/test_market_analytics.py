import numpy as np
import pandas as pd
import pytest

from alko_mcp_market import analytics as a


def daily(values, start="2025-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_fetch_start():
    today = pd.Timestamp("2026-10-31")
    assert a.fetch_start("1mo", today) == pd.Timestamp("2026-09-23")
    assert a.fetch_start("ytd", today) == pd.Timestamp("2025-12-25")
    assert a.fetch_start("1mo", today, min_days=400) == pd.Timestamp("2025-09-26")
    assert a.fetch_start("max", today) is None


def test_base_index_and_returns():
    s = daily(range(100, 160))  # 60 business days from 2025-01-01
    assert a.base_index(s, "1d") == 58 and a.window_return(s, "1d") == pytest.approx(0.633, abs=0.001)
    assert a.base_index(s, "5d") == 54
    assert a.base_index(s, "max") == 0
    one_month = a.base_index(s, "1mo")
    assert s.index[one_month] <= s.index[-1] - pd.DateOffset(months=1) < s.index[one_month + 1]
    assert a.window_return(daily([100.0]), "1mo") is None


def test_rsi():
    assert a.rsi(daily(range(1, 30))) == 100.0
    assert 45 < a.rsi(daily([10, 11] * 20)) < 60  # balanced moves; ends on an up day
    assert a.rsi(daily([1, 2, 3])) is None


def test_macd():
    rising = a.macd(daily(np.linspace(100, 150, 60)))
    assert rising["state"] == "bullish" and rising["macd"] > 0
    assert a.macd(daily(range(10))) is None


def test_moving_averages_and_cross():
    up = a.moving_averages(daily(range(1, 251)))
    assert up["ma50"] == 225.5 and up["ma200"] == 150.5
    assert up["cross"].startswith("golden") and up["last_cross_date"] is None
    v_shape = daily(list(range(300, 100, -1)) + list(range(100, 400)))
    m = a.moving_averages(v_shape)
    assert m["cross"].startswith("golden") and m["last_cross_date"] is not None
    assert a.moving_averages(daily(range(1, 30)))["ma50"] is None


@pytest.mark.parametrize(
    ("args", "label"),
    [
        ((5, 10, 110, 100), "uptrend"),
        ((-5, -10, 90, 100), "downtrend"),
        ((5, -10, 90, 100), "mixed"),
        ((None, 1, 1, 1), None),
    ],
)
def test_trend_label(args, label):
    assert a.trend_label(*args) == label


def test_risk_measures():
    assert a.volatility(daily([100.0] * 30)) == 0.0
    assert a.max_drawdown(daily([100, 120, 60, 90])) == -50.0
    rng = np.random.default_rng(0)
    r = rng.normal(0, 0.01, 100)
    market = daily(100 * np.cumprod(1 + r))
    stock = daily(100 * np.cumprod(1 + 2 * r))
    assert a.beta(stock, market) == pytest.approx(2.0, abs=0.01)


def test_resample_ohlcv_weekly():
    idx = pd.bdate_range("2025-01-01", periods=8)  # Wed 1st .. Fri 10th
    df = pd.DataFrame(
        {
            "Open": range(1, 9),
            "High": range(11, 19),
            "Low": range(0, 8),
            "Close": range(2, 10),
            "Volume": [100] * 8,
        },
        index=idx,
        dtype=float,
    )
    bars = a.resample_ohlcv(df, "W-FRI")
    assert [str(d.date()) for d in bars.index] == ["2025-01-03", "2025-01-10"]
    first = bars.iloc[0]
    assert (first.Open, first.High, first.Low, first.Close, first.Volume) == (1, 13, 0, 4, 300)
    assert a.resample_ohlcv(df, None).equals(df)
