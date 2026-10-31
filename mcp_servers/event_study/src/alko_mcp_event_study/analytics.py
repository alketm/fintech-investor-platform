"""Market-model event study, kept free of I/O so it can be unit tested."""

import numpy as np
import pandas as pd


def market_model_event_study(
    stock: pd.Series,
    benchmark: pd.Series,
    event_date: pd.Timestamp,
    window: int = 5,
    estimation_days: int = 120,
    gap: int = 10,
) -> dict:
    """Abnormal returns around `event_date` using a market model fitted on a pre-event estimation window.

    `stock` and `benchmark` are date-indexed closes. Day 0 is the first trading day on or after `event_date`.
    The estimation window ends `gap` trading days before the event window starts.
    """
    returns = pd.concat({"stock": stock, "bench": benchmark}, axis=1).pct_change().dropna()
    after = returns.index[returns.index >= event_date]
    if len(after) == 0:
        raise ValueError("Event date is after the available data")
    day0 = returns.index.get_loc(after[0])

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
    abnormal = event["stock"] - (alpha + beta * event["bench"])
    car = abnormal.cumsum()
    t_stat = float(car.iloc[-1] / (residual_sd * np.sqrt(len(abnormal)))) if residual_sd > 0 else None

    return {
        "event_day": str(returns.index[day0].date()),
        "alpha": round(float(alpha), 6),
        "beta": round(float(beta), 4),
        "estimation_days": int(len(est)),
        "series": [
            {
                "day": d,
                "date": str(ts.date()),
                "abnormal_return_pct": round(float(ar) * 100, 4),
                "car_pct": round(float(c) * 100, 4),
            }
            for d, (ts, ar, c) in enumerate(zip(event.index, abnormal, car, strict=True), start=-window)
        ],
        "car_pct": round(float(car.iloc[-1]) * 100, 4),
        "car_t_stat": round(t_stat, 3) if t_stat is not None else None,
    }
