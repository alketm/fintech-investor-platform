"""Market-model event studies (single and multi-event), kept free of I/O so they can be unit tested.

Abnormal return = stock return - (alpha + beta * benchmark return), with alpha and beta fitted on an estimation
window that ends `gap` trading days before the event window starts.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

ESTIMATION_DAYS = 120
GAP = 10


def daily_returns(stock: pd.Series, benchmark: pd.Series) -> pd.DataFrame:
    return pd.concat({"stock": stock, "bench": benchmark}, axis=1, sort=True).pct_change().dropna()


@dataclass
class EventWindow:
    day0: int  # position of day 0 in the returns frame
    abnormal: pd.Series  # abnormal returns indexed by date, from day -window to +window
    alpha: float
    beta: float
    residual_sd: float
    estimation_days: int


def event_window(
    returns: pd.DataFrame, day0: int, window: int, estimation_days: int = ESTIMATION_DAYS, gap: int = GAP
) -> EventWindow:
    est_end = day0 - window - gap
    est_start = est_end - estimation_days
    if est_start < 0:
        raise ValueError("Not enough history before the event for the estimation window")
    if day0 + window >= len(returns):
        raise ValueError("Not enough history after the event for the event window")
    est = returns.iloc[est_start:est_end]
    beta, alpha = np.polyfit(est["bench"], est["stock"], 1)
    residual_sd = float((est["stock"] - (alpha + beta * est["bench"])).std(ddof=2))
    event = returns.iloc[day0 - window : day0 + window + 1]
    return EventWindow(
        day0,
        event["stock"] - (alpha + beta * event["bench"]),
        float(alpha),
        float(beta),
        residual_sd,
        len(est),
    )


def day0_position(index: pd.DatetimeIndex, date: pd.Timestamp, after_close: bool = False) -> int | None:
    """First trading day on or after `date` (strictly after it when the event happened after the close)."""
    date = pd.Timestamp(date.date()) if hasattr(date, "date") else pd.Timestamp(date)
    candidates = np.flatnonzero(index > date) if after_close else np.flatnonzero(index >= date)
    return int(candidates[0]) if len(candidates) else None


def pct(x: float | None, digits: int = 3) -> float | None:
    return None if x is None or np.isnan(x) else round(float(x) * 100, digits)


def market_model_event_study(
    stock: pd.Series,
    benchmark: pd.Series,
    event_date: pd.Timestamp,
    window: int = 5,
    estimation_days: int = ESTIMATION_DAYS,
    gap: int = GAP,
) -> dict:
    """Abnormal returns around one `event_date`. Day 0 is the first trading day on or after it."""
    returns = daily_returns(stock, benchmark)
    day0 = day0_position(returns.index, event_date)
    if day0 is None:
        raise ValueError("Event date is after the available data")
    ew = event_window(returns, day0, window, estimation_days, gap)
    car = ew.abnormal.cumsum()
    t_stat = float(car.iloc[-1] / (ew.residual_sd * np.sqrt(len(car)))) if ew.residual_sd > 0 else None
    return {
        "event_day": str(returns.index[day0].date()),
        "alpha": round(ew.alpha, 6),
        "beta": round(ew.beta, 4),
        "estimation_days": ew.estimation_days,
        "series": [
            {
                "day": d,
                "date": str(ts.date()),
                "abnormal_return_pct": round(float(ar) * 100, 4),
                "car_pct": round(float(c) * 100, 4),
            }
            for d, (ts, ar, c) in enumerate(
                zip(ew.abnormal.index, ew.abnormal, car, strict=True), start=-window
            )
        ],
        "car_pct": round(float(car.iloc[-1]) * 100, 4),
        "car_t_stat": round(t_stat, 3) if t_stat is not None else None,
    }


# --- multi-event aggregation -----------------------------------------------------------------------------


def aggregate(windows: list[EventWindow], window: int, car_from: int | None = None) -> dict | None:
    """Average abnormal return by event day across events, the average CAR, and a cross-sectional t-stat.

    `car_from` sets the first day included in each event's CAR (default -window; use 1 for post-event drift).
    """
    if not windows:
        return None
    car_from = -window if car_from is None else car_from
    matrix = np.array([w.abnormal.values for w in windows])  # events x days
    days = np.arange(-window, window + 1)
    cars = matrix[:, days >= car_from].sum(axis=1)
    n = len(cars)
    sd = cars.std(ddof=1) if n > 1 else np.nan
    mean_ar = matrix.mean(axis=0)
    return {
        "events": n,
        "average_car_pct": pct(cars.mean()),
        "median_car_pct": pct(float(np.median(cars))),
        "pct_positive": round(float((cars > 0).mean()) * 100, 1),
        "t_stat": round(float(cars.mean() / (sd / np.sqrt(n))), 2) if n > 1 and sd > 0 else None,
        "car_days": f"{car_from:+d} to {window:+d}",
        "average_path": [
            {"day": int(d), "abnormal_return_pct": pct(ar), "car_pct": pct(c)}
            for d, ar, c in zip(days, mean_ar, mean_ar.cumsum(), strict=True)
        ],
    }


def window_car(w: EventWindow, window: int, first: int, last: int) -> float:
    days = np.arange(-window, window + 1)
    return float(w.abnormal.values[(days >= first) & (days <= last)].sum())


def detect_large_moves(
    stock_returns: pd.Series, threshold_sigma: float, vol_days: int = 60, min_gap: int = 10
) -> list[dict]:
    """Days whose return exceeds `threshold_sigma` times the prior `vol_days`-day volatility. An event within
    `min_gap` trading days after a kept event is skipped so post-event windows don't overlap."""
    sigma = stock_returns.rolling(vol_days).std().shift(1)
    z = stock_returns / sigma
    events, last = [], None
    for pos in np.flatnonzero((z.abs() > threshold_sigma).fillna(False).values):
        if last is not None and pos - last <= min_gap:
            continue
        events.append(
            {
                "position": int(pos),
                "date": str(stock_returns.index[pos].date()),
                "return_pct": pct(stock_returns.iloc[pos], 2),
                "sigma_multiple": round(float(z.iloc[pos]), 2),
                "direction": "up" if stock_returns.iloc[pos] > 0 else "down",
            }
        )
        last = pos
    return events


def summarize_cars(cars: list[float]) -> dict | None:
    """Count, average, median, share positive and cross-sectional t-stat of per-event cumulative returns."""
    if not cars:
        return None
    values = np.array(cars)
    n = len(values)
    sd = values.std(ddof=1) if n > 1 else np.nan
    return {
        "events": n,
        "average_car_pct": pct(values.mean()),
        "median_car_pct": pct(float(np.median(values))),
        "pct_positive": round(float((values > 0).mean()) * 100, 1),
        "t_stat": round(float(values.mean() / (sd / np.sqrt(n))), 2) if n > 1 and sd > 0 else None,
    }


def detect_spread_widening(spread: pd.Series, ma_days: int, threshold: float, min_gap: int) -> list[dict]:
    """Days a spread first rises above `threshold` times its `ma_days`-day moving average (that day included).
    Only crossings count: the day before must have been at or below the threshold, so a spell above it is one
    event. A crossing within `min_gap` observations after a kept event is skipped so windows don't overlap."""
    spread = spread.dropna().sort_index()
    ma = spread.rolling(ma_days).mean()
    ratio = spread / ma
    above = (ratio > threshold).fillna(False)
    crossings = np.flatnonzero((above & ~above.shift(1, fill_value=False)).values)
    events, last = [], None
    for pos in crossings:
        if pos < ma_days or (last is not None and pos - last <= min_gap):
            continue
        events.append(
            {
                "date": str(spread.index[pos].date()),
                "spread": round(float(spread.iloc[pos]), 2),
                "moving_average": round(float(ma.iloc[pos]), 2),
                "ratio": round(float(ratio.iloc[pos]), 3),
            }
        )
        last = pos
    return events
