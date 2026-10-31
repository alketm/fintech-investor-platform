"""ETF performance and risk calculations, kept free of I/O so they can be unit tested."""

from typing import Literal

import numpy as np
import pandas as pd

Window = Literal["1mo", "3mo", "6mo", "ytd", "1y", "3y", "5y", "10y", "max"]
TRADING_DAYS = 252

_OFFSETS = {
    "1mo": pd.DateOffset(months=1),
    "3mo": pd.DateOffset(months=3),
    "6mo": pd.DateOffset(months=6),
    "1y": pd.DateOffset(years=1),
    "3y": pd.DateOffset(years=3),
    "5y": pd.DateOffset(years=5),
    "10y": pd.DateOffset(years=10),
}


def window_start(window: Window, today: pd.Timestamp) -> pd.Timestamp | None:
    """First calendar date of the window; None means all available history."""
    today = today.normalize()
    if window == "max":
        return None
    if window == "ytd":
        return pd.Timestamp(year=today.year, month=1, day=1)
    return today - _OFFSETS[window]


def resample_rule(window: Window) -> tuple[str, str | None]:
    """(interval label, pandas resample rule) for price history; None keeps daily points."""
    if window in ("1mo", "3mo", "6mo", "ytd"):
        return "daily", None
    if window in ("1y", "3y", "5y"):
        return "weekly", "W-FRI"
    return "monthly", "ME"


def _pct(x: float | None, digits: int = 3) -> float | None:
    return None if x is None or not np.isfinite(x) else round(float(x) * 100, digits)


def performance(close: pd.Series, adj_close: pd.Series) -> dict:
    """Price return (close) and total return (dividend-adjusted close) between the first and last date."""
    close, adj_close = close.dropna(), adj_close.dropna()
    if len(adj_close) < 2:
        raise ValueError("Not enough price history in this window")
    years = (adj_close.index[-1] - adj_close.index[0]).days / 365.25
    total = adj_close.iloc[-1] / adj_close.iloc[0] - 1
    return {
        "start_date": str(adj_close.index[0].date()),
        "end_date": str(adj_close.index[-1].date()),
        "start_price": round(float(close.iloc[0]), 4),
        "end_price": round(float(close.iloc[-1]), 4),
        "price_return_pct": _pct(close.iloc[-1] / close.iloc[0] - 1),
        "total_return_pct": _pct(total),
        # Annualizing a sub-year return overstates it, so only report it for a year or more.
        "annualized_return_pct": _pct((1 + total) ** (1 / years) - 1) if years >= 0.99 else None,
        "trading_days": int(len(adj_close)),
    }


def risk_metrics(adj_close: pd.Series, benchmark_adj_close: pd.Series, risk_free_annual: float) -> dict:
    """Risk statistics from daily dividend-adjusted closes. `risk_free_annual` is a decimal (0.04 = 4%)."""
    prices = adj_close.dropna()
    returns = prices.pct_change().dropna()
    if len(returns) < 20:
        raise ValueError("Need at least 20 daily returns for risk metrics")

    rf_daily = (1 + risk_free_annual) ** (1 / TRADING_DAYS) - 1
    excess = returns - rf_daily
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    downside = np.sqrt((np.minimum(excess, 0) ** 2).mean()) * np.sqrt(TRADING_DAYS)
    ann_excess = excess.mean() * TRADING_DAYS

    growth = prices / prices.iloc[0]
    drawdown = growth / growth.cummax() - 1
    trough = drawdown.idxmin()
    peak = growth.loc[:trough].idxmax()

    pair = pd.concat(
        {"etf": returns, "bench": benchmark_adj_close.dropna().pct_change()}, axis=1, sort=True
    ).dropna()
    beta = corr = None
    if len(pair) >= 20 and pair["bench"].var() > 0:
        beta = pair["etf"].cov(pair["bench"]) / pair["bench"].var()
        corr = pair["etf"].corr(pair["bench"])

    var_95 = returns.quantile(0.05)
    return {
        "annualized_volatility_pct": _pct(vol),
        "downside_deviation_pct": _pct(downside),
        "max_drawdown_pct": _pct(drawdown.min()),
        "max_drawdown_peak": str(peak.date()),
        "max_drawdown_trough": str(trough.date()),
        "beta": round(float(beta), 3) if beta is not None else None,
        "correlation": round(float(corr), 3) if corr is not None else None,
        "sharpe_ratio": round(float(ann_excess / vol), 3) if vol > 0 else None,
        "sortino_ratio": round(float(ann_excess / downside), 3) if downside > 0 else None,
        "var_95_1d_pct": _pct(var_95),
        "cvar_95_1d_pct": _pct(returns[returns <= var_95].mean()),
        "daily_returns": int(len(returns)),
    }


def price_points(close: pd.Series, adj_close: pd.Series, rule: str | None) -> list[dict]:
    frame = pd.concat({"close": close, "adj_close": adj_close}, axis=1, sort=True).dropna()
    if rule:
        # Label each period with the last trading day actually in it, not the calendar period end.
        frame = frame.groupby(pd.Grouper(freq=rule)).tail(1)
    return [
        {"date": str(ts.date()), "close": round(float(r.close), 4), "adj_close": round(float(r.adj_close), 4)}
        for ts, r in frame.iterrows()
    ]
