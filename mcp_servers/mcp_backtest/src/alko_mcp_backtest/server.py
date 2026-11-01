"""Backtest MCP server: buy and hold plus long-short rule-based strategies."""

import pandas as pd
import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_backtest import strategies
from alko_mcp_backtest.analytics import align_benchmark, buy_and_hold_stats, weekly_equity_curve
from alko_mcp_macro import fred

mcp = MCPServer(
    "mcp_backtest",
    instructions="Historical backtests on daily dividend-adjusted closes: buy and hold, and long-short "
    "strategies (moving-average crossover, time-series momentum, RSI mean reversion, Kansas City Fed policy-rate "
    "uncertainty, University of Michigan consumer sentiment trend). Every backtest also reports buying and holding a benchmark (SPY by default) over the same "
    "days. Results are simulations, not recommendations.",
)


# yfinance access, replaced in tests.
def _history(symbol: str, start: str, end: str) -> pd.Series:
    history = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=True)
    if history.empty:
        return pd.Series(dtype=float)
    closes = history["Close"]
    closes.index = pd.DatetimeIndex(closes.index).tz_localize(None)
    return closes


def _policy_uncertainty(start: str) -> pd.Series:
    """Kansas City Fed's Measure of Policy Rate Uncertainty (FRED KCPRU), daily."""
    try:
        return fred.series("KCPRU", start=start)
    except fred.FredError as e:
        raise ToolError(str(e)) from e


def _benchmark(benchmark: str, start: str, end: str) -> pd.Series | None:
    """Benchmark closes, or None when there are none: a missing benchmark shouldn't sink the backtest."""
    closes = _history(benchmark, start, end)
    return None if closes.empty else closes


def _consumer_sentiment(start: str) -> pd.Series:
    """University of Michigan consumer sentiment index (FRED UMCSENT), monthly, dated the first of the month."""
    try:
        return fred.series("UMCSENT", start=start)
    except fred.FredError as e:
        raise ToolError(str(e)) from e


@mcp.tool()
def backtest_buy_and_hold(
    symbol: str, start: str, end: str, initial_capital: float = 10_000.0, benchmark: str = "SPY"
) -> dict:
    """Backtest buying a ticker on `start` and holding until `end` (dates as YYYY-MM-DD), using dividend-adjusted
    daily closes. Returns total return, CAGR, annualized volatility, Sharpe, max drawdown and final value, the same
    for buying and holding `benchmark` over the same days, and a weekly equity curve of both."""
    symbol, benchmark = symbol.strip().upper(), benchmark.strip().upper()
    closes = _history(symbol, start, end)
    if closes.empty:
        raise ToolError(f"No price history for {symbol!r} between {start} and {end}")
    try:
        stats = buy_and_hold_stats(closes, initial_capital)
    except ValueError as e:  # expected data problems: report the reason to the caller
        raise ToolError(str(e)) from e
    prices = {"buy_and_hold": closes}
    bench_stats = None
    if (bench := _benchmark(benchmark, start, end)) is not None:
        aligned = align_benchmark(bench, closes.index).dropna()
        if len(aligned) >= 2:
            bench_stats = {"symbol": benchmark, **buy_and_hold_stats(aligned, initial_capital)}
            prices["benchmark"] = aligned
    return {
        "symbol": symbol,
        "strategy": "buy_and_hold",
        **stats,
        "benchmark": bench_stats,
        "equity_curve": weekly_equity_curve(prices, initial_capital),
    }


def _long_short(
    symbol: str,
    start: str,
    end: str,
    warmup_days: int,
    signal,
    initial_capital: float,
    cost_bps: float,
    rule: str,
    params: dict,
    benchmark: str,
) -> dict:
    symbol, benchmark = symbol.strip().upper(), benchmark.strip().upper()
    try:
        start_ts = pd.Timestamp(start)
        pd.Timestamp(end)
    except ValueError as e:
        raise ToolError(f"Dates must be YYYY-MM-DD: {e}") from e
    if cost_bps < 0 or initial_capital <= 0:
        raise ToolError("cost_bps must be >= 0 and initial_capital > 0")
    # Warm-up in calendar days so indicators are ready on the first test day.
    warm_start = (start_ts - pd.Timedelta(days=int(warmup_days * 1.5) + 30)).strftime("%Y-%m-%d")
    closes = _history(symbol, warm_start, end)
    if closes.empty:
        raise ToolError(f"No price history for {symbol} between {start} and {end}")
    if (closes.index < start_ts).sum() < warmup_days:
        params = {
            **params,
            "warning": "Less history before the start than the indicator needs; early signals may be flat.",
        }
    try:
        result = strategies.run_backtest(
            closes,
            signal(closes),
            start_ts,
            initial_capital,
            cost_bps,
            _benchmark(benchmark, warm_start, end),
        )
    except ValueError as e:
        raise ToolError(str(e)) from e
    if result["benchmark"] is not None:
        result["benchmark"] = {"symbol": benchmark, **result["benchmark"]}
    return {"symbol": symbol, "rule": rule, "parameters": {**params, "cost_bps": cost_bps}, **result}


@mcp.tool()
def backtest_moving_average(
    symbol: str,
    start: str,
    end: str,
    fast: int = 50,
    slow: int = 200,
    initial_capital: float = 10_000.0,
    cost_bps: float = 5.0,
    benchmark: str = "SPY",
) -> dict:
    """Long-short moving-average crossover: long when the `fast`-day average is above the `slow`-day average,
    short when below. Compares with buy and hold: returns, CAGR, volatility, Sharpe, max drawdown, trades, time
    long/short, win rate, costs and a weekly equity curve, plus buying and holding `benchmark` (SPY) over the same
    days. Dates are YYYY-MM-DD; `cost_bps` per position change."""
    if not 1 < fast < slow:
        raise ToolError("Need 1 < fast < slow")
    return _long_short(
        symbol,
        start,
        end,
        slow,
        lambda c: strategies.moving_average_positions(c, fast, slow),
        initial_capital,
        cost_bps,
        f"Long when the {fast}-day average is above the {slow}-day average, short when below.",
        {"fast": fast, "slow": slow},
        benchmark,
    )


@mcp.tool()
def backtest_time_series_momentum(
    symbol: str,
    start: str,
    end: str,
    lookback_days: int = 252,
    skip_days: int = 21,
    initial_capital: float = 10_000.0,
    cost_bps: float = 5.0,
    benchmark: str = "SPY",
) -> dict:
    """Long-short time-series momentum: at each month end, long if the return from `lookback_days` ago to
    `skip_days` ago is positive, short if negative (12-1 month momentum by default). Same outputs as the other
    long-short backtests, compared with buy and hold of the symbol and of `benchmark`."""
    if not 0 <= skip_days < lookback_days:
        raise ToolError("Need 0 <= skip_days < lookback_days")
    return _long_short(
        symbol,
        start,
        end,
        lookback_days,
        lambda c: strategies.time_series_momentum_positions(c, lookback_days, skip_days),
        initial_capital,
        cost_bps,
        f"At each month end, long if the return from {lookback_days} to {skip_days} trading days ago is positive, "
        "short if negative.",
        {"lookback_days": lookback_days, "skip_days": skip_days},
        benchmark,
    )


@mcp.tool()
def backtest_rsi_mean_reversion(
    symbol: str,
    start: str,
    end: str,
    period: int = 14,
    lower: float = 30.0,
    upper: float = 70.0,
    exit_level: float = 50.0,
    initial_capital: float = 10_000.0,
    cost_bps: float = 5.0,
    benchmark: str = "SPY",
) -> dict:
    """Long-short RSI mean reversion: go long when RSI(`period`) falls below `lower`, short when it rises above
    `upper`, and close the position when RSI crosses back through `exit_level`. Same outputs as the other
    long-short backtests, compared with buy and hold of the symbol and of `benchmark`."""
    if not (period > 1 and 0 < lower < exit_level < upper < 100):
        raise ToolError("Need period > 1 and 0 < lower < exit_level < upper < 100")
    return _long_short(
        symbol,
        start,
        end,
        period * 5,
        lambda c: strategies.rsi_mean_reversion_positions(c, period, lower, upper, exit_level),
        initial_capital,
        cost_bps,
        f"Long when RSI({period}) < {lower:g}, short when > {upper:g}; exit when RSI crosses {exit_level:g}.",
        {"period": period, "lower": lower, "upper": upper, "exit_level": exit_level},
        benchmark,
    )


@mcp.tool()
def backtest_policy_uncertainty(
    symbol: str,
    start: str,
    end: str,
    lookback_days: int = 252,
    threshold: float = 0.5,
    signal_lag_days: int = 1,
    initial_capital: float = 10_000.0,
    cost_bps: float = 5.0,
    benchmark: str = "SPY",
) -> dict:
    """Long-short timing with the Kansas City Fed's Policy Rate Uncertainty index (KC PRU, option-implied
    uncertainty about the policy rate, from FRED): z-score of KC PRU against its trailing `lookback_days` mean,
    using the value from `signal_lag_days` trading days earlier. Short the symbol when z > `threshold`
    (unusually high uncertainty), long when z < -`threshold`, flat in between. Same outputs as the other
    long-short backtests plus the latest KC PRU reading and how often each signal applied."""
    if lookback_days < 20 or threshold < 0 or signal_lag_days < 0:
        raise ToolError("Need lookback_days >= 20, threshold >= 0 and signal_lag_days >= 0")
    try:
        warm = pd.Timestamp(start) - pd.Timedelta(days=int(lookback_days * 1.5) + 60)
    except ValueError as e:
        raise ToolError(f"Dates must be YYYY-MM-DD: {e}") from e
    index = _policy_uncertainty(warm.strftime("%Y-%m-%d"))
    if index.empty:
        raise ToolError("No Kansas City Fed policy-rate uncertainty data returned")

    def signal(closes: pd.Series) -> pd.Series:
        return strategies.policy_uncertainty_positions(
            closes, index, lookback_days, threshold, signal_lag_days
        )

    result = _long_short(
        symbol,
        start,
        end,
        lookback_days,
        signal,
        initial_capital,
        cost_bps,
        f"Short when Kansas City Fed policy-rate uncertainty is more than {threshold:g} standard deviations above "
        f"its {lookback_days}-day average, long when more than {threshold:g} below, flat otherwise "
        f"(index lagged {signal_lag_days} trading day{'s' if signal_lag_days != 1 else ''}).",
        {"lookback_days": lookback_days, "threshold": threshold, "signal_lag_days": signal_lag_days},
        benchmark,
    )
    closes = _history(result["symbol"], start, end)
    z = strategies.uncertainty_zscore(closes, index, lookback_days, signal_lag_days).dropna()
    at_end = index[index.index <= closes.index[-1]]  # the reading as of the test's last day, not today
    result["uncertainty"] = {
        "source": "Kansas City Fed's Measure of Policy Rate Uncertainty (FRED KCPRU), percentage points",
        "value_at_end": round(float(at_end.iloc[-1]), 3) if len(at_end) else None,
        "value_date": str(at_end.index[-1].date()) if len(at_end) else None,
        "zscore_at_end": round(float(z.iloc[-1]), 2) if len(z) else None,
        "pct_days_high": round(float((z > threshold).mean()) * 100, 1) if len(z) else None,
        "pct_days_low": round(float((z < -threshold).mean()) * 100, 1) if len(z) else None,
        "pct_days_neutral": round(float(z.abs().le(threshold).mean()) * 100, 1) if len(z) else None,
    }
    return result


@mcp.tool()
def backtest_consumer_sentiment(
    symbol: str,
    start: str,
    end: str,
    ma_months: int = 3,
    short_below_pct: float = 95.0,
    long_above_pct: float = 97.0,
    exit_pct: float = 96.0,
    release_lag_months: int = 0,
    initial_capital: float = 10_000.0,
    cost_bps: float = 5.0,
    benchmark: str = "SPY",
) -> dict:
    """Long-short timing with the University of Michigan consumer sentiment index (FRED UMCSENT, monthly), using
    sentiment as a % of its `ma_months` moving average. At each month end, from neutral: short below
    `short_below_pct`, long above `long_above_pct`, else stay neutral; a long goes neutral once below `exit_pct`
    and a short goes neutral once above `exit_pct`. Positions are held for the next month. A month's reading is
    treated as known at that month's end (the final release comes late in the month); raise
    `release_lag_months` to wait longer. Same outputs as the other long-short backtests plus the sentiment
    reading behind the last signal."""
    if ma_months < 2 or release_lag_months < 0:
        raise ToolError("Need ma_months >= 2 and release_lag_months >= 0")
    if not 0 < short_below_pct <= exit_pct <= long_above_pct:
        raise ToolError("Need 0 < short_below_pct <= exit_pct <= long_above_pct")
    try:
        pd.Timestamp(start)
    except ValueError as e:
        raise ToolError(f"Dates must be YYYY-MM-DD: {e}") from e
    # From the earliest reading: the band rule depends on its past state, so start it well before the test.
    sentiment = _consumer_sentiment("1978-01-01")
    if sentiment.empty:
        raise ToolError("No University of Michigan consumer sentiment data returned")
    bands = (short_below_pct, long_above_pct, exit_pct)

    lag = (
        f" Uses the reading from {release_lag_months} month{'s' if release_lag_months != 1 else ''} earlier."
    )
    result = _long_short(
        symbol,
        start,
        end,
        30,  # enough history to hold the previous month-end's signal on the first day
        lambda c: strategies.sentiment_trend_positions(c, sentiment, ma_months, release_lag_months, *bands),
        initial_capital,
        cost_bps,
        f"Monthly, with University of Michigan consumer sentiment as a % of its {ma_months}-month average: from "
        f"neutral, short below {short_below_pct:g}%, long above {long_above_pct:g}%, else stay neutral; a long "
        f"goes neutral below {exit_pct:g}%, a short goes neutral above {exit_pct:g}%."
        f"{lag if release_lag_months else ''}",
        {
            "ma_months": ma_months,
            "short_below_pct": short_below_pct,
            "long_above_pct": long_above_pct,
            "exit_pct": exit_pct,
            "release_lag_months": release_lag_months,
        },
        benchmark,
    )
    trend = strategies.sentiment_trend(sentiment, ma_months, release_lag_months, *bands).dropna()
    known = trend[trend.index <= pd.Timestamp(result["end"]).to_period("M")]  # as of the test end, not today
    last = known.iloc[-1] if len(known) else None
    result["sentiment"] = {
        "source": "University of Michigan consumer sentiment index (FRED UMCSENT), 1966 Q1 = 100",
        "reading_month": str(known.index[-1] - release_lag_months) if last is not None else None,
        "value_at_end": round(float(last["value"]), 1) if last is not None else None,
        "moving_average_at_end": round(float(last["moving_average"]), 1) if last is not None else None,
        "ratio_pct_at_end": round(float(last["ratio_pct"]), 1) if last is not None else None,
        "signal_at_end": {1.0: "long", -1.0: "short"}.get(float(last["signal"]), "flat")
        if last is not None
        else None,
    }
    return result


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
