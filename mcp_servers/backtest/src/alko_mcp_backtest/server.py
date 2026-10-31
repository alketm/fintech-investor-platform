"""Backtest MCP server: buy and hold plus long-short rule-based strategies."""

import pandas as pd
import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_backtest import strategies
from alko_mcp_backtest.analytics import buy_and_hold_stats

mcp = MCPServer(
    "alko-backtest",
    instructions="Historical backtests on daily dividend-adjusted closes: buy and hold, and long-short "
    "strategies (moving-average crossover, time-series momentum, RSI mean reversion). Results are simulations, "
    "not recommendations.",
)


# yfinance access, replaced in tests.
def _history(symbol: str, start: str, end: str) -> pd.Series:
    history = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=True)
    if history.empty:
        return pd.Series(dtype=float)
    closes = history["Close"]
    closes.index = pd.DatetimeIndex(closes.index).tz_localize(None)
    return closes


@mcp.tool()
def backtest_buy_and_hold(symbol: str, start: str, end: str, initial_capital: float = 10_000.0) -> dict:
    """Backtest buying a ticker on `start` and holding until `end` (dates as YYYY-MM-DD), using dividend-adjusted
    daily closes. Returns total return, CAGR, annualized volatility, max drawdown and final value."""
    closes = _history(symbol.upper(), start, end)
    if closes.empty:
        raise ToolError(f"No price history for {symbol!r} between {start} and {end}")
    try:
        stats = buy_and_hold_stats(closes, initial_capital)
    except ValueError as e:  # expected data problems: report the reason to the caller
        raise ToolError(str(e)) from e
    return {"symbol": symbol.upper(), "strategy": "buy_and_hold", **stats}


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
) -> dict:
    symbol = symbol.strip().upper()
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
        result = strategies.run_backtest(closes, signal(closes), start_ts, initial_capital, cost_bps)
    except ValueError as e:
        raise ToolError(str(e)) from e
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
) -> dict:
    """Long-short moving-average crossover: long when the `fast`-day average is above the `slow`-day average,
    short when below. Compares with buy and hold: returns, CAGR, volatility, Sharpe, max drawdown, trades, time
    long/short, win rate, costs and a weekly equity curve. Dates are YYYY-MM-DD; `cost_bps` per position change."""
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
) -> dict:
    """Long-short time-series momentum: at each month end, long if the return from `lookback_days` ago to
    `skip_days` ago is positive, short if negative (12-1 month momentum by default). Same outputs as the other
    long-short backtests, compared with buy and hold."""
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
) -> dict:
    """Long-short RSI mean reversion: go long when RSI(`period`) falls below `lower`, short when it rises above
    `upper`, and close the position when RSI crosses back through `exit_level`. Same outputs as the other
    long-short backtests, compared with buy and hold."""
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
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
