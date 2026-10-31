"""Stocks MCP server: quotes and company basics."""

import math

import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("mcp_stocks", instructions="Stock and ETF price quotes.")


def _num(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return float(value)


@mcp.tool()
def get_quote(symbol: str) -> dict:
    """Latest price quote for a stock or ETF ticker (e.g. AAPL, VTI).

    Returns price, previous close, change percent, currency and market cap.
    """
    ticker = yf.Ticker(symbol.upper())
    fast = ticker.fast_info
    price = _num(fast.get("lastPrice"))
    prev = _num(fast.get("previousClose"))
    if price is None:
        raise ToolError(f"No price data for {symbol!r}")
    change_pct = (price / prev - 1) * 100 if prev else None
    return {
        "symbol": symbol.upper(),
        "price": round(price, 4),
        "previous_close": prev,
        "change_pct": round(change_pct, 3) if change_pct is not None else None,
        "currency": fast.get("currency"),
        "market_cap": _num(fast.get("marketCap")),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
