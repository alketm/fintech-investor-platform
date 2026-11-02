"""High-yield spread spike detection and the credit-spread event study tool, on synthetic data."""

import numpy as np
import pandas as pd
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_event_study import analytics as a
from alko_mcp_event_study import server

DAYS = pd.bdate_range("2023-01-02", periods=900)
REAL_HY_SPREAD = server._hy_spread  # before the fixture replaces it
SPIKES = [300, 305, 500, 700]  # 305 overlaps the 300 event's window and is skipped


def _spread():
    values = np.full(len(DAYS), 4.0)
    for pos in SPIKES:
        values[pos] = 6.0  # 1.4x the average of 4.0
    values[500:510] = 6.0  # a ten-day spell above the threshold is one event
    return pd.Series(values, index=DAYS)


RNG = np.random.default_rng(9)
BENCH_R = RNG.normal(0.0003, 0.01, len(DAYS))
STOCK_R = BENCH_R + RNG.normal(0, 0.003, len(DAYS))
for pos in (300, 500, 700):
    STOCK_R[pos + 1] -= 0.04  # day 0 is the trading day after the spread reading


def _fake_closes(symbol, start, end):
    s = pd.Series(100 * np.cumprod(1 + (BENCH_R if symbol == "SPY" else STOCK_R)), index=DAYS)
    return s[(s.index >= start) & (s.index < end)]


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(server, "_closes", _fake_closes)
    monkeypatch.setattr(server, "_hy_spread", lambda start: _spread()[_spread().index >= start])
    monkeypatch.setattr(server, "_today", lambda: DAYS[-1])


def test_detect_spread_widening_counts_crossings_once_and_skips_overlaps():
    events = a.detect_spread_widening(_spread(), ma_days=21, threshold=1.25, min_gap=10)
    assert [e["date"] for e in events] == [str(DAYS[p].date()) for p in (300, 500, 700)]
    first = events[0]
    assert first["spread"] == 6.0 and first["ratio"] == pytest.approx(
        6.0 / ((4.0 * 20 + 6.0) / 21), abs=0.001
    )
    # A 1.25x threshold isn't met when the spike is smaller.
    assert a.detect_spread_widening(_spread() * 0 + 4.0, 21, 1.25, 10) == []


def test_summarize_cars():
    out = a.summarize_cars([0.02, -0.01, 0.03])
    assert out["events"] == 3 and out["average_car_pct"] == pytest.approx(1.333, abs=0.001)
    assert out["pct_positive"] == pytest.approx(66.7) and out["t_stat"] is not None
    assert a.summarize_cars([]) is None


def test_credit_spread_event_study_measures_the_next_day_reaction():
    out = server.run_credit_spread_event_study("abc", window=5)
    assert out["symbol"] == "ABC" and out["threshold"] == 1.25 and out["ma_days"] == 21
    assert [e["date"] for e in out["events"]] == [str(DAYS[p].date()) for p in (300, 500, 700)]
    assert all(
        e["day0"] == str(DAYS[d + 1].date()) for e, d in zip(out["events"], (300, 500, 700), strict=True)
    )
    assert all(e["day0_abnormal_pct"] == pytest.approx(-4.0, abs=1.0) for e in out["events"])
    abnormal = out["abnormal"]
    assert abnormal["events"] == 3 and abnormal["car_days"] == "+0 to +5"
    assert abnormal["average_car_pct"] == pytest.approx(-4.0, abs=1.5)
    assert out["total"]["events"] == 3 and "BAMLH0A0HYM2" in out["series"]
    assert out["spread_history_start"] == "2023-01-02"
    assert out["note"].startswith("Spread history available from 2023-01-02 only")  # asked for 10 years


def test_credit_spread_errors(monkeypatch):
    with pytest.raises(ToolError, match="threshold > 1"):
        server.run_credit_spread_event_study("ABC", threshold=0.9)
    with pytest.raises(ToolError, match="No high-yield spread spikes above 2x"):
        server.run_credit_spread_event_study("ABC", threshold=2.0)
    monkeypatch.setattr(server, "_hy_spread", REAL_HY_SPREAD)
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(ToolError, match="FRED_API_KEY is not set"):
        server.run_credit_spread_event_study("ABC")
