"""Multi-event analytics and the earnings / large-move tools on synthetic data with planted effects."""

import numpy as np
import pandas as pd
import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_event_study import analytics as a
from alko_mcp_event_study import server

DAYS = pd.bdate_range("2023-01-02", periods=900)


def _ew(values):
    idx = pd.bdate_range("2025-01-01", periods=len(values))
    return a.EventWindow(0, pd.Series(values, index=idx), 0.0, 1.0, 0.01, 120)


def test_day0_position_respects_after_close():
    idx = pd.bdate_range("2025-01-06", periods=5)  # Mon..Fri
    assert a.day0_position(idx, pd.Timestamp("2025-01-07 08:00")) == 1
    assert a.day0_position(idx, pd.Timestamp("2025-01-07 16:30"), after_close=True) == 2
    assert a.day0_position(idx, pd.Timestamp("2025-01-04")) == 0  # Saturday -> Monday
    assert a.day0_position(idx, pd.Timestamp("2025-02-01")) is None


def test_aggregate():
    agg = a.aggregate([_ew([0.01, 0.02, 0.0]), _ew([0.0, 0.04, 0.02])], window=1)
    assert agg["events"] == 2 and agg["average_car_pct"] == 4.5 and agg["pct_positive"] == 100.0
    assert agg["t_stat"] == pytest.approx(3.0, abs=0.01)
    assert [p["abnormal_return_pct"] for p in agg["average_path"]] == [0.5, 3.0, 1.0]
    post = a.aggregate([_ew([0.01, 0.02, 0.0]), _ew([0.0, 0.04, 0.02])], window=1, car_from=1)
    assert post["average_car_pct"] == 1.0 and post["car_days"] == "+1 to +1"
    assert a.aggregate([], 1) is None


def test_detect_large_moves_skips_overlaps():
    r = pd.Series(np.tile([0.01, -0.01], 100), index=pd.bdate_range("2025-01-01", periods=200))
    r.iloc[100], r.iloc[103], r.iloc[150] = 0.08, -0.08, -0.09
    events = a.detect_large_moves(r, threshold_sigma=3, vol_days=60, min_gap=5)
    assert [e["date"] for e in events] == [str(r.index[100].date()), str(r.index[150].date())]
    assert [e["direction"] for e in events] == ["up", "down"] and events[0]["sigma_multiple"] > 3


# --- tools with fake yfinance ----------------------------------------------------------------------------

RNG = np.random.default_rng(7)
BENCH_R = RNG.normal(0.0004, 0.01, len(DAYS))
EARNINGS = [
    pd.Timestamp(d, tz="America/New_York")
    for d in (
        "2024-01-25 16:05",
        "2024-04-25 07:00",
        "2024-07-25 16:00",
        "2024-10-24 16:00",
        "2025-01-30 16:00",
    )
]


def _day0_index(ts):
    return a.day0_position(DAYS, ts, after_close=ts.hour >= 16)


STOCK_R = 1.2 * BENCH_R + RNG.normal(0, 0.004, len(DAYS))
for i, ts in enumerate(EARNINGS):
    STOCK_R[_day0_index(ts)] += 0.06 if i != 1 else -0.05  # beats jump +6%, the miss drops 5%
BIG_DAYS = [300, 420, 560, 700]
for pos in BIG_DAYS:
    STOCK_R[pos] += 0.09
    STOCK_R[pos + 1 : pos + 6] += 0.006  # 3% drift after each up move


def _prices(r):
    return pd.Series(100 * np.cumprod(1 + r), index=DAYS)


def _fake_closes(symbol, start, end):
    s = _prices(BENCH_R if symbol == "SPY" else STOCK_R)
    return s[(s.index >= start) & (s.index < end)]


def _fake_earnings(symbol, limit):
    future = pd.Timestamp("2026-11-02 16:00", tz="America/New_York")
    idx = pd.DatetimeIndex([future, *reversed(EARNINGS)], name="Earnings Date")
    return pd.DataFrame(
        {
            "EPS Estimate": [2.0, 1.5, 1.4, 1.3, 1.2, 1.1],
            "Reported EPS": [np.nan, 1.6, 1.5, 1.4, 1.1, 1.2],
            "Surprise(%)": [np.nan, 6.7, 7.1, 7.7, -8.3, 9.1],
        },
        index=idx,
    )


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(server, "_closes", _fake_closes)
    monkeypatch.setattr(server, "_earnings_dates", _fake_earnings)
    monkeypatch.setattr(server, "_today", lambda: DAYS[-1])


def test_earnings_event_study():
    out = server.run_earnings_event_study("abc", window=3)
    events = out["events"]
    assert len(events) == 5  # the future date has no reported EPS
    first = events[0]
    assert first["timing"] == "after close" and first["day0"] == "2024-01-26"  # next trading day
    assert events[1]["timing"] == "before open" and events[1]["day0"] == "2024-04-25"
    assert first["day0_abnormal_pct"] == pytest.approx(6.0, abs=1.5)
    assert out["beats"]["events"] == 4 and out["misses"]["events"] == 1
    assert out["beats"]["average_car_pct"] > 3 > -3 > out["misses"]["average_car_pct"]
    day0 = next(p for p in out["aggregate"]["average_path"] if p["day"] == 0)
    assert day0["abnormal_return_pct"] > 2


def test_large_move_event_study_finds_continuation():
    out = server.run_large_move_event_study("ABC", threshold_sigma=3, window=5, lookback_years=5)
    up = out["up_moves"]
    planted = {str(DAYS[p].date()) for p in BIG_DAYS}
    found = {e["date"]: e for e in out["events"] if e["date"] in planted}
    assert len(found) == len(BIG_DAYS)
    # Each planted move is followed by 5 days of +0.6% drift (3% in all); noise adds about ±1% per event.
    posts = [e["post_car_pct"] for e in found.values()]
    assert all(p > 0 for p in posts) and sum(posts) / len(posts) == pytest.approx(3.0, abs=1.0)
    # The earnings jumps also count as up moves but have no drift, so the group average is lower but positive.
    assert up["average_car_pct"] > 0 and up["read"] in {"continuation", "no significant drift"}
    assert all(e["post_car_pct"] is not None for e in out["events"])


def test_large_move_errors():
    with pytest.raises(ToolError, match="threshold_sigma"):
        server.run_large_move_event_study("ABC", threshold_sigma=0)
    with pytest.raises(ToolError, match="No moves above"):
        server.run_large_move_event_study("ABC", threshold_sigma=50)


async def test_new_tools_registered_and_errors_reach_client(monkeypatch):
    monkeypatch.setattr(server, "_earnings_dates", lambda s, n: pd.DataFrame())
    async with Client(server.mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("run_earnings_event_study", {"symbol": "VTI"})
    assert names == {"run_event_study", "run_earnings_event_study", "run_large_move_event_study"}
    assert result.is_error and "No earnings history for VTI" in result.content[0].text
