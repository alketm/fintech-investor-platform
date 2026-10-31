"""Backtest MCP server."""

import yfinance as yf
from mcp.server.mcpserver import MCPServer

from alko_mcp_backtest.analytics import buy_and_hold_stats

mcp = MCPServer("alko-backtest", instructions="Historical strategy backtests on daily adjusted closes.")


@mcp.tool()
def backtest_buy_and_hold(symbol: str, start: str, end: str, initial_capital: float = 10_000.0) -> dict:
    """Backtest buying a ticker on `start` and holding until `end` (dates as YYYY-MM-DD), using dividend-adjusted
    daily closes. Returns total return, CAGR, annualized volatility, max drawdown and final value."""
    history = yf.Ticker(symbol.upper()).history(start=start, end=end, auto_adjust=True)
    if history.empty:
        raise ValueError(f"No price history for {symbol!r} between {start} and {end}")
    return {
        "symbol": symbol.upper(),
        "strategy": "buy_and_hold",
        **buy_and_hold_stats(history["Close"], initial_capital),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
