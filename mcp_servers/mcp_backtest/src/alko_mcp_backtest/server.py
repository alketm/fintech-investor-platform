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
    "uncertainty). Every backtest also reports buying and holding a benchmark (SPY by default) over the same "
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
