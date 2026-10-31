import numpy as np
import pandas as pd
import pytest

from alko_mcp_macro import analytics as a


def monthly(values, end="2026-09-30"):
    return pd.Series(values, index=pd.date_range(end=end, periods=len(values), freq="ME"), dtype=float)


def test_latest_and_offsets():
    s = monthly([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13])
    assert a.latest(s) == {"value": 13.0, "date": "2026-09-30", "prior": 12.0, "change": 1.0}
    assert a.latest(pd.Series(dtype=float))["value"] is None
    assert a.value_at_offset(s, 12) == 1.0
    assert a.pct_change_over(s, 12) == 1200.0
    assert a.percentile(monthly([1, 2, 3, 4])) == 100.0
    assert a.percentile(monthly([4, 3, 2, 1])) == 25.0


@pytest.mark.parametrize(
    ("gdp", "payrolls", "indpro", "label"),
    [
        ([-1.0], [150, 150, 150], [1.0], "contracting"),
        ([2.5], [50, 60, 70], [1.0], "slowing"),
        ([2.5], [150, 150, 150], [-0.5], "slowing"),
        ([2.5], [150, 200, 250], [1.0], "expanding"),
    ],
)
def test_growth_read(gdp, payrolls, indpro, label):
    assert a.growth_read(monthly(gdp), monthly(payrolls), monthly(indpro))["label"] == label


def test_inflation_read():
    core_cpi = monthly([3.5, 3.4, 3.3, 3.2, 3.1, 3.05, 3.0])  # 6 months ago 3.5 -> now 3.0
    r = a.inflation_read(core_cpi, monthly([2.8]))
    assert (r["trend"], r["vs_target"], r["label"]) == ("falling", "above target", "above target, falling")
    assert a.inflation_read(monthly([2.0] * 7), monthly([2.0]))["label"] == "near target, stable"


def test_policy_read():
    r = a.policy_read(monthly([5.0]), monthly([2.8]), monthly([0.3]), monthly([-0.1]))
    assert r["stance"] == "restrictive" and r["curve"] == "inverted"
    assert r["evidence"]["real_fed_funds_pct"] == 2.2
    assert (
        a.policy_read(monthly([2.0]), monthly([2.5]), monthly([1.0]), monthly([1.2]))["stance"]
        == "accommodative"
    )


def test_stress_read():
    assert a.stress_read(25.0, monthly([4.0]), monthly([-0.5]))["label"] == "elevated"
    assert a.stress_read(35.0, monthly([4.0]), monthly([-0.5]))["label"] == "high"
    assert a.stress_read(15.0, monthly([3.5]), monthly([-0.5]))["label"] == "calm"
    assert a.stress_read(None, pd.Series(dtype=float), pd.Series(dtype=float))["label"] is None


def test_recession_read():
    assert a.recession_read(monthly([0.6]), monthly([1.0] * 12))["risk"] == "high"
    curve = monthly([1.0] * 8 + [-0.2] * 4)
    r = a.recession_read(monthly([0.1]), curve)
    assert r["risk"] == "moderate" and r["evidence"]["months_10y_3m_inverted_last_12"] == 4
    assert a.recession_read(monthly([0.1]), monthly([1.0] * 12))["risk"] == "low"


@pytest.mark.parametrize(
    ("growth", "trend", "level", "expected"),
    [
        ("expanding", "falling", "above target", "steady expansion"),
        ("expanding", "rising", "above target", "overheating risk"),
        ("slowing", "stable", "above target", "stagflation risk"),
        ("slowing", "falling", "above target", "slowdown with easing inflation"),
        ("contracting", "rising", "above target", "contraction"),
        (None, None, None, "unclear"),
    ],
)
def test_regime(growth, trend, level, expected):
    assert a.regime(growth, trend, level) == expected


def test_consumer_read_scoring():
    strong = a.consumer_read(
        monthly(list(range(1, 21))),  # latest is the 100th percentile
        monthly([3.0]),
        monthly([3.0] * 13),
        monthly([4.0] * 12),
        xly_xlp_3m=2.0,
    )
    assert strong["label"] == "strong" and strong["score"] == 3
    weak = a.consumer_read(
        monthly(list(range(20, 0, -1))),  # latest is the lowest
        monthly([-0.5]),
        monthly([2.0] * 12 + [3.0]),  # delinquencies up over a year
        monthly([3.5] * 11 + [4.2]),  # 0.7 above its 12-month low
        xly_xlp_3m=-1.0,
    )
    assert weak["label"] == "weak" and weak["score"] == -5


def test_beta_and_correlation():
    rng = np.random.default_rng(3)
    market = monthly(rng.normal(0.01, 0.04, 60))
    stock = market * 2
    assert a.beta(stock, market) == pytest.approx(2.0)
    assert a.correlation(stock, market) == pytest.approx(1.0)
    assert a.correlation(stock.iloc[:10], market.iloc[:10]) is None  # under 24 months


def test_monthly_change_and_returns():
    daily = pd.Series([4.0, 4.1, 4.3], index=pd.to_datetime(["2026-01-15", "2026-01-30", "2026-02-27"]))
    assert a.monthly_change(daily).round(2).tolist() == [0.2]
    assert a.monthly_returns(
        pd.Series([100.0, 110.0], index=pd.to_datetime(["2026-01-30", "2026-02-27"]))
    ).round(3).tolist() == [0.1]
