"""Long-short strategy signals and the backtest engine. Free of I/O so they can be unit tested.

Positions are +1 (long), -1 (short) or 0 (flat), decided from the close of day t and held over day t+1, so a
signal never trades on the return that produced it. `closes` include warm-up history before the test start.
"""

import numpy as np
import pandas as pd

from alko_mcp_backtest.analytics import align_benchmark

TRADING_DAYS = 252


# --- signals ---------------------------------------------------------------------------------------------


def moving_average_positions(closes: pd.Series, fast: int, slow: int) -> pd.Series:
    diff = closes.rolling(fast).mean() - closes.rolling(slow).mean()
    return np.sign(diff).fillna(0.0)


def time_series_momentum_positions(closes: pd.Series, lookback_days: int, skip_days: int) -> pd.Series:
    """Sign of the return from `lookback_days` ago to `skip_days` ago, re-decided on each month's last day."""
    momentum = closes.shift(skip_days) / closes.shift(lookback_days) - 1
    month = closes.index.to_period("M")
    last_day_of_month = closes.index.to_series().groupby(month).transform("max") == closes.index
    signal = np.sign(momentum).where(last_day_of_month)
    return signal.ffill().fillna(0.0)


def rsi(closes: pd.Series, period: int) -> pd.Series:
    """Wilder's RSI series."""
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss
    return (100 - 100 / (1 + rs)).where(loss != 0, 100.0).where(gain.notna())


def rsi_mean_reversion_positions(
    closes: pd.Series, period: int, lower: float, upper: float, exit_level: float
) -> pd.Series:
    """Long below `lower`, short above `upper`; a position closes when RSI crosses back through `exit_level`."""
    values = rsi(closes, period)
    pos, out = 0.0, []
    for v in values:
        if np.isnan(v):
            out.append(0.0)
            continue
        if pos == 1 and v >= exit_level:
            pos = 0.0
        elif pos == -1 and v <= exit_level:
            pos = 0.0
        if pos == 0:
            pos = 1.0 if v < lower else -1.0 if v > upper else 0.0
        out.append(pos)
    return pd.Series(out, index=closes.index)


def uncertainty_ratio(closes: pd.Series, uncertainty: pd.Series, ma_days: int, lag_days: int) -> pd.DataFrame:
    """An uncertainty index on each trading day (the value from `lag_days` trading days before, last published
    value carried forward), its `ma_days` trading-day moving average and the index as a multiple of that
    average."""
    aligned = uncertainty.reindex(closes.index.union(uncertainty.index)).ffill().reindex(closes.index)
    lagged = aligned.shift(lag_days)
    ma = lagged.rolling(ma_days).mean()
    return pd.DataFrame({"value": lagged, "moving_average": ma, "ratio": lagged / ma.where(ma > 0)})


def policy_uncertainty_positions(
    closes: pd.Series,
    uncertainty: pd.Series,
    ma_days: int,
    short_above: float,
    long_below: float,
    exit_level: float,
    lag_days: int,
) -> pd.Series:
    """`ratio_band_signals` on the uncertainty index as a multiple of its moving average: high uncertainty is
    short, low is long."""
    ratio = uncertainty_ratio(closes, uncertainty, ma_days, lag_days)["ratio"]
    return ratio_band_signals(ratio, short_above, long_below, exit_level).fillna(0.0)


def sentiment_band_signals(
    ratio_pct: pd.Series, short_below_pct: float, long_above_pct: float, exit_pct: float
) -> pd.Series:
    """Positions from sentiment as a % of its moving average, one step per month, starting neutral.

    From neutral: short below `short_below_pct`, long above `long_above_pct`, else stay neutral.
    From long: neutral once below `exit_pct`. From short: neutral once above `exit_pct`.
    One transition per month, so leaving a long or short always passes through neutral.
    Months without a ratio (no full average yet) give NaN and keep the state neutral.
    """
    state, out = 0.0, []
    for r in ratio_pct:
        if np.isnan(r):
            out.append(np.nan)
            continue
        if state == 0:
            state = -1.0 if r < short_below_pct else 1.0 if r > long_above_pct else 0.0
        elif state == 1 and r < exit_pct:
            state = 0.0
        elif state == -1 and r > exit_pct:
            state = 0.0
        out.append(state)
    return pd.Series(out, index=ratio_pct.index)


def sentiment_trend(
    sentiment: pd.Series,
    ma_months: int,
    lag_months: int,
    short_below_pct: float = 95.0,
    long_above_pct: float = 97.0,
    exit_pct: float = 96.0,
) -> pd.DataFrame:
    """Monthly sentiment, its `ma_months` moving average, sentiment as a % of that average and the
    `sentiment_band_signals` signal, indexed by the month the signal can first be used: a reading for month M is
    final by the end of M, so with `lag_months` = 0 it sets the position from M's last trading day."""
    s = sentiment.dropna().sort_index()
    s.index = s.index.to_period("M")
    s = s[~s.index.duplicated(keep="last")].asfreq("M")
    ma = s.rolling(ma_months).mean()
    ratio = s / ma * 100
    signal = sentiment_band_signals(ratio, short_below_pct, long_above_pct, exit_pct)
    frame = pd.DataFrame({"value": s, "moving_average": ma, "ratio_pct": ratio, "signal": signal})
    frame.index = frame.index + lag_months
    return frame


def sentiment_trend_positions(
    closes: pd.Series,
    sentiment: pd.Series,
    ma_months: int,
    lag_months: int,
    short_below_pct: float = 95.0,
    long_above_pct: float = 97.0,
    exit_pct: float = 96.0,
) -> pd.Series:
    """`sentiment_trend` signal, re-decided on each month's last day."""
    month = closes.index.to_period("M")
    last_day_of_month = closes.index.to_series().groupby(month).transform("max") == closes.index
    signal = sentiment_trend(sentiment, ma_months, lag_months, short_below_pct, long_above_pct, exit_pct)[
        "signal"
    ]
    decided = pd.Series(signal.reindex(month).values, index=closes.index).where(last_day_of_month)
    return decided.ffill().fillna(0.0)


def realized_volatility(closes: pd.Series, window: int) -> pd.Series:
    """Rolling standard deviation of daily returns over `window` days, annualized, in percentage points."""
    return closes.pct_change().rolling(window).std() * np.sqrt(TRADING_DAYS) * 100


def vix_ratio(spy: pd.Series, vix: pd.Series, window: int) -> pd.DataFrame:
    """VIX close, SPY realized volatility and their ratio on SPY's trading days (VIX carried over any gap)."""
    vix_on_spy_days = align_benchmark(vix, spy.index)
    rv = realized_volatility(spy, window)
    return pd.DataFrame(
        {"vix": vix_on_spy_days, "realized_vol": rv, "ratio": vix_on_spy_days / rv.where(rv > 0)}
    )


def ratio_band_signals(
    ratio: pd.Series, short_above: float, long_below: float, exit_level: float
) -> pd.Series:
    """Positions from a ratio where high means short, one step per day, starting neutral.

    From neutral: short above `short_above`, long below `long_below`, else stay neutral.
    From short: neutral once below `exit_level`. From long: neutral once above `exit_level`.
    One transition per day, so leaving a long or short always passes through neutral.
    Days without a ratio (no full volatility window yet) give NaN and keep the state neutral.
    """
    state, out = 0.0, []
    for r in ratio:
        if np.isnan(r):
            out.append(np.nan)
            continue
        if state == 0:
            state = -1.0 if r > short_above else 1.0 if r < long_below else 0.0
        elif state == -1 and r < exit_level:
            state = 0.0
        elif state == 1 and r > exit_level:
            state = 0.0
        out.append(state)
    return pd.Series(out, index=ratio.index)


def vix_volatility_positions(
    closes: pd.Series,
    spy: pd.Series,
    vix: pd.Series,
    window: int,
    short_above: float,
    long_below: float,
    exit_level: float,
) -> pd.Series:
    """`ratio_band_signals` on VIX / realized volatility, decided at each SPY close and applied to the traded symbol's trading days."""
    ratio = vix_ratio(spy, vix, window)["ratio"]
    signals = ratio_band_signals(ratio, short_above, long_below, exit_level)
    return align_benchmark(signals.dropna(), closes.index).fillna(0.0)


# --- engine ----------------------------------------------------------------------------------------------


def stats(returns: pd.Series, initial_capital: float) -> dict:
    """Stats for daily returns (first element is the first day after the start)."""
    growth = (1 + returns).cumprod()
    years = len(returns) / TRADING_DAYS
    total = growth.iloc[-1] - 1
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    drawdown = growth / growth.cummax().clip(lower=1) - 1
    return {
        "total_return_pct": round(float(total) * 100, 2),
        "cagr_pct": round(float((1 + total) ** (1 / years) - 1) * 100, 2)
        if years > 0 and total > -1
        else None,
        "annualized_volatility_pct": round(float(vol) * 100, 2),
        "sharpe_ratio": round(float(returns.mean() * TRADING_DAYS / vol), 2) if vol > 0 else None,
        "max_drawdown_pct": round(float(drawdown.min()) * 100, 2),
        "final_value": round(float(initial_capital * growth.iloc[-1]), 2),
    }


def _trades(held: pd.Series, strategy_returns: pd.Series) -> list[dict]:
    """Runs of a constant non-zero position; the last run is open if it lasts to the final day."""
    trades, start = [], None
    values = held.values
    for i, v in enumerate(values):
        if start is not None and v != values[start]:
            trades.append((start, i - 1))
            start = None
        if start is None and v != 0:
            start = i
    if start is not None:
        trades.append((start, len(values) - 1))
    out = []
    for s, e in trades:
        r = float((1 + strategy_returns.iloc[s : e + 1]).prod() - 1)
        out.append(
            {
                "side": "long" if values[s] > 0 else "short",
                "entry": str(held.index[s].date()),
                "exit": str(held.index[e].date()),
                "return_pct": round(r * 100, 2),
                "open": e == len(values) - 1,
            }
        )
    return out


def run_backtest(
    closes: pd.Series,
    positions: pd.Series,
    start: pd.Timestamp,
    initial_capital: float,
    cost_bps: float,
    benchmark: pd.Series | None = None,
) -> dict:
    """Simulate `positions` on `closes` from `start`. With `benchmark` closes, also report buying and holding
    the benchmark over the same trading days (stats under "benchmark", a "benchmark" column in the curve)."""
    closes, positions = closes.dropna(), positions.reindex(closes.index).fillna(0.0)
    in_range = closes.index >= start
    if in_range.sum() < 3:
        raise ValueError("Need at least three trading days in the test period")
    c = closes[in_range]
    # Position held on each day after the first = the signal at the previous close; flat before the start.
    held = positions[in_range].shift(1).iloc[1:]
    returns = c.pct_change().iloc[1:]
    turnover = held.diff().abs()
    turnover.iloc[0] = abs(held.iloc[0])
    costs = turnover * cost_bps / 10_000
    strategy = held * returns - costs

    equity = initial_capital * (1 + strategy).cumprod()
    prior_equity = equity.shift(1).fillna(initial_capital)
    trades = _trades(held, strategy)
    closed = [t for t in trades if not t["open"]]
    columns = {"strategy": equity, "buy_and_hold": initial_capital * (1 + returns).cumprod()}
    benchmark_returns = None
    if benchmark is not None:
        aligned = align_benchmark(benchmark, c.index)
        benchmark_returns = aligned.pct_change().iloc[1:].fillna(0.0)
        columns["benchmark"] = initial_capital * (1 + benchmark_returns).cumprod()
    curve = pd.DataFrame(columns).resample("W-FRI").last().dropna()

    return {
        "start": str(c.index[0].date()),
        "end": str(c.index[-1].date()),
        "trading_days": int(len(returns)),
        "strategy": stats(strategy, initial_capital),
        "buy_and_hold": stats(returns, initial_capital),
        "benchmark": stats(benchmark_returns, initial_capital) if benchmark_returns is not None else None,
        "activity": {
            "position_changes": int((turnover > 0).sum()),
            "pct_days_long": round(float((held > 0).mean()) * 100, 1),
            "pct_days_short": round(float((held < 0).mean()) * 100, 1),
            "pct_days_flat": round(float((held == 0).mean()) * 100, 1),
            "closed_trades": len(closed),
            "win_rate_pct": round(sum(t["return_pct"] > 0 for t in closed) / len(closed) * 100, 1)
            if closed
            else None,
            "total_costs": round(float((costs * prior_equity).sum()), 2),
            "current_position": {1.0: "long", -1.0: "short"}.get(float(positions.iloc[-1]), "flat"),
        },
        "recent_trades": trades[-10:],
        "equity_curve": [
            {"date": str(ts.date()), **{k: round(float(v), 2) for k, v in r.items()}}
            for ts, r in curve.iterrows()
        ],
        "assumptions": "Signals at a close trade from the next day; costs charged per unit of position change; "
        "0% risk-free rate in Sharpe; no short-borrow costs, dividends on shorts, or taxes. Prices are "
        "dividend-adjusted.",
    }
