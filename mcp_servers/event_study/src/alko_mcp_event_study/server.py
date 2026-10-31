"""Event study MCP server: single events, earnings announcements and large daily moves."""

from datetime import timedelta

import pandas as pd
import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_event_study import analytics as a

mcp = MCPServer(
    "alko-event-study",
    instructions="Market-model event studies: abnormal returns (stock return minus what the benchmark explains) "
    "around a date, around past earnings announcements, and after large daily moves.",
)
MARKET_CLOSE_HOUR = 16  # US/Eastern


# --- yfinance access (replaced in tests) -----------------------------------------------------------------


def _closes(symbol: str, start: str, end: str) -> pd.Series:
    history = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=True)
    if history.empty:
        return pd.Series(dtype=float)
    closes = history["Close"]
    closes.index = pd.DatetimeIndex(closes.index).tz_localize(None)
    return closes


def _earnings_dates(symbol: str, limit: int) -> pd.DataFrame:
    return yf.Ticker(symbol).get_earnings_dates(limit=limit)


def _today() -> pd.Timestamp:
    return pd.Timestamp.today()


# --- helpers ---------------------------------------------------------------------------------------------


def _returns(symbol: str, benchmark: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    stock, bench = _closes(symbol, s, e), _closes(benchmark, s, e)
    if stock.empty:
        raise ToolError(f"No price history for {symbol}")
    if bench.empty:
        raise ToolError(f"No price history for benchmark {benchmark}")
    return a.daily_returns(stock, bench)


def _num(x, digits=2):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(x) else round(x, digits)


# --- tools -----------------------------------------------------------------------------------------------


@mcp.tool()
def run_event_study(symbol: str, event_date: str, benchmark: str = "SPY", window: int = 5) -> dict:
    """Market-model event study: abnormal returns of `symbol` vs `benchmark` over ±`window` trading days around
    `event_date` (YYYY-MM-DD), with the model fitted on the ~120 trading days before. Returns alpha, beta, the
    daily abnormal-return and cumulative-abnormal-return (CAR) series, total CAR and its t-statistic."""
    window = max(1, min(window, 30))
    day = pd.Timestamp(event_date)
    start = (day - timedelta(days=300)).strftime("%Y-%m-%d")
    end = (day + timedelta(days=window * 2 + 10)).strftime("%Y-%m-%d")
    stock, bench = _closes(symbol.upper(), start, end), _closes(benchmark.upper(), start, end)
    try:
        result = a.market_model_event_study(stock, bench, day, window=window)
    except ValueError as e:  # expected data problems: report the reason to the caller
        raise ToolError(str(e)) from e
    return {"symbol": symbol.upper(), "benchmark": benchmark.upper(), "event_date": event_date, **result}


@mcp.tool()
def run_earnings_event_study(
    symbol: str, benchmark: str = "SPY", window: int = 5, max_events: int = 12
) -> dict:
    """How a stock has reacted to its past earnings announcements (up to `max_events`, default 12). Day 0 is the
    announcement day, or the next trading day for reports at or after the 4pm ET close. Per event: EPS estimate,
    actual and surprise %, day-0 abnormal return, CAR over days -1..+1 and -window..+window. Aggregate: average
    abnormal return by day, average CAR, t-statistic across events and % positive, overall and split into EPS beats
    and misses."""
    symbol, benchmark = symbol.strip().upper(), benchmark.strip().upper()
    window, max_events = max(1, min(window, 20)), max(1, min(max_events, 40))
    try:
        dates = _earnings_dates(symbol, max_events + 8)
    except Exception as e:
        raise ToolError(f"No earnings history for {symbol}: {e}") from e
    if dates is None or dates.empty or "Reported EPS" not in dates.columns:
        raise ToolError(f"No earnings history for {symbol}")
    past = dates[dates["Reported EPS"].notna()].sort_index().tail(max_events)
    if past.empty:
        raise ToolError(f"No reported earnings for {symbol}")

    first = pd.Timestamp(past.index[0].date())
    returns = _returns(symbol, benchmark, first - pd.Timedelta(days=300), _today() + pd.Timedelta(days=1))

    events, windows, beats, misses, skipped = [], [], [], [], []
    for ts, row in past.iterrows():
        local = pd.Timestamp(ts)
        after_close = local.hour >= MARKET_CLOSE_HOUR
        timing = "after close" if after_close else "before open" if local.hour < 10 else "during market"
        day0 = a.day0_position(returns.index, local, after_close=after_close)
        try:
            if day0 is None:
                raise ValueError("Event is after the available data")
            ew = a.event_window(returns, day0, window)
        except ValueError as e:
            skipped.append({"date": str(local.date()), "reason": str(e)})
            continue
        surprise = _num(row.get("Surprise(%)"))
        windows.append(ew)
        (
            beats
            if surprise is not None and surprise > 0
            else misses
            if surprise is not None and surprise < 0
            else []
        ).append(ew)
        events.append(
            {
                "announced": str(local.date()),
                "timing": timing,
                "day0": str(returns.index[day0].date()),
                "eps_estimate": _num(row.get("EPS Estimate")),
                "eps_actual": _num(row.get("Reported EPS")),
                "surprise_pct": surprise,
                "day0_abnormal_pct": a.pct(a.window_car(ew, window, 0, 0), 2),
                "car_m1_p1_pct": a.pct(a.window_car(ew, window, -1, 1), 2),
                "car_window_pct": a.pct(a.window_car(ew, window, -window, window), 2),
            }
        )
    if not windows:
        raise ToolError(f"Not enough price history around {symbol}'s earnings dates")
    return {
        "symbol": symbol,
        "benchmark": benchmark,
        "window": window,
        "aggregate": a.aggregate(windows, window),
        "beats": a.aggregate(beats, window),
        "misses": a.aggregate(misses, window),
        "events": events,
        "skipped": skipped,
        "note": "Abnormal returns use a market model fitted on 120 trading days ending 10 days before each event "
        "window. Few events make averages noisy; read the t-statistic and event count.",
    }


def _drift_read(direction: str, agg: dict | None) -> str | None:
    if not agg or agg["t_stat"] is None:
        return None
    car, t = agg["average_car_pct"], agg["t_stat"]
    if abs(t) < 2:
        return "no significant drift"
    same_way = (car > 0) == (direction == "up")
    return "continuation" if same_way else "reversal"


@mcp.tool()
def run_large_move_event_study(
    symbol: str,
    threshold_sigma: float = 2.5,
    benchmark: str = "SPY",
    window: int = 10,
    lookback_years: int = 5,
) -> dict:
    """What happens after a stock's large daily moves: finds days over the last `lookback_years` whose return
    exceeded `threshold_sigma` times the prior 60-day volatility (events within `window` days of an earlier one
    are skipped), then measures the abnormal return over the following `window` days. Results are split into up
    and down moves: count, average move, average post-event CAR, % continuing in the move's direction,
    t-statistic, and a continuation / reversal / no-significant-drift read; plus the event list."""
    symbol, benchmark = symbol.strip().upper(), benchmark.strip().upper()
    window, lookback_years = max(1, min(window, 30)), max(1, min(lookback_years, 20))
    if threshold_sigma <= 0:
        raise ToolError("threshold_sigma must be positive")
    today = _today()
    since = today - pd.DateOffset(years=lookback_years)
    returns = _returns(symbol, benchmark, since - pd.Timedelta(days=400), today + pd.Timedelta(days=1))

    detected = a.detect_large_moves(returns["stock"], threshold_sigma, min_gap=window)
    detected = [e for e in detected if returns.index[e["position"]] >= since]
    groups: dict[str, list] = {"up": [], "down": []}
    events, skipped = [], []
    for e in detected:
        try:
            ew = a.event_window(returns, e["position"], window)
        except ValueError as err:
            skipped.append({"date": e["date"], "reason": str(err)})
            continue
        post = a.window_car(ew, window, 1, window)
        groups[e["direction"]].append((ew, post))
        events.append(
            {
                **{k: v for k, v in e.items() if k != "position"},
                "day0_abnormal_pct": a.pct(a.window_car(ew, window, 0, 0), 2),
                "post_car_pct": a.pct(post, 2),
            }
        )

    summary = {}
    for direction, items in groups.items():
        agg = a.aggregate([w for w, _ in items], window, car_from=1)
        if agg:
            moves = [ev["return_pct"] for ev in events if ev["direction"] == direction]
            continuing = sum((p > 0) == (direction == "up") for _, p in items)
            agg = {
                **{k: v for k, v in agg.items() if k != "average_path"},
                "average_move_pct": round(sum(moves) / len(moves), 2),
                "pct_continuing": round(continuing / len(items) * 100, 1),
                "read": _drift_read(direction, agg),
                "average_path": agg["average_path"],
            }
        summary[f"{direction}_moves"] = agg
    if not events:
        raise ToolError(
            f"No moves above {threshold_sigma} sigma for {symbol} in the last {lookback_years} years"
        )
    return {
        "symbol": symbol,
        "benchmark": benchmark,
        "threshold_sigma": threshold_sigma,
        "window": window,
        "since": str(since.date()),
        **summary,
        "events": events[-30:],
        "skipped": skipped,
        "note": "Post-event CAR covers days +1 to +window and excludes the move itself. |t| >= 2 is treated as "
        "significant; a handful of events is not enough to rely on.",
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
