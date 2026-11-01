"""Backtest statistics, kept free of I/O so they can be unit tested."""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def buy_and_hold_stats(prices: pd.Series, initial_capital: float = 10_000.0) -> dict:
    """Stats for buying at the first price and holding to the last. `prices` must be date-indexed closes."""
    prices = prices.dropna()
    if len(prices) < 2:
        raise ValueError("Need at least two prices")

    returns = prices.pct_change().dropna()
    growth = prices / prices.iloc[0]
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    total_return = growth.iloc[-1] - 1
    cagr = growth.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    drawdown = growth / growth.cummax() - 1
    vol = returns.std() * np.sqrt(TRADING_DAYS)

    return {
        "start": str(prices.index[0].date()),
        "end": str(prices.index[-1].date()),
        "trading_days": int(len(prices)),
        "total_return_pct": round(float(total_return) * 100, 3),
        "cagr_pct": round(float(cagr) * 100, 3),
        "annualized_volatility_pct": round(float(vol) * 100, 3),
        "sharpe_ratio": round(float(returns.mean() * TRADING_DAYS / vol), 2) if vol > 0 else None,
        "max_drawdown_pct": round(float(drawdown.min()) * 100, 3),
        "initial_capital": initial_capital,
        "final_value": round(float(initial_capital * growth.iloc[-1]), 2),
    }


def align_benchmark(benchmark: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """Benchmark closes on the given trading dates, carrying the last close over any date it lacks."""
    return benchmark.dropna().sort_index().reindex(dates, method="ffill")


def weekly_equity_curve(prices: dict[str, pd.Series], initial_capital: float) -> list[dict]:
    """Weekly (Friday) value of `initial_capital` invested at the first price of each series."""
    frame = pd.DataFrame({k: initial_capital * v / v.iloc[0] for k, v in prices.items()})
    weekly = frame.resample("W-FRI").last().dropna()
    return [
        {"date": str(ts.date()), **{k: round(float(v), 2) for k, v in row.items()}}
        for ts, row in weekly.iterrows()
    ]
