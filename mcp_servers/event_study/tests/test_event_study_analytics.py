import numpy as np
import pandas as pd
import pytest

from alko_mcp_event_study.analytics import market_model_event_study


def _prices(returns, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(returns) + 1)
    return pd.Series(100 * np.cumprod(np.r_[1.0, 1 + np.asarray(returns)]), index=idx)


def test_recovers_beta_and_event_jump():
    rng = np.random.default_rng(0)
    bench_r = rng.normal(0, 0.01, 200)
    stock_r = 1.5 * bench_r + rng.normal(0, 0.001, 200)
    stock_r[170] += 0.05  # 5% abnormal jump on the event day
    stock, bench = _prices(stock_r), _prices(bench_r)
    event_date = stock.index[171]  # return at position 170 is dated on price index 171

    result = market_model_event_study(stock, bench, event_date, window=3)

    assert result["beta"] == pytest.approx(1.5, abs=0.05)
    assert len(result["series"]) == 7
    day0 = next(p for p in result["series"] if p["day"] == 0)
    assert day0["abnormal_return_pct"] == pytest.approx(5.0, abs=0.5)
    assert result["car_pct"] == pytest.approx(5.0, abs=1.0)
    assert result["car_t_stat"] > 3


def test_rejects_short_history():
    flat = _prices(np.full(30, 0.001))
    with pytest.raises(ValueError):
        market_model_event_study(flat, flat, flat.index[20], window=3)
