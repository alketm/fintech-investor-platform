"""Financial statements MCP server."""

import math
from typing import Literal

import yfinance as yf
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("alko-financials", instructions="Company financial statements.")

INCOME_LINES = [
    "Total Revenue",
    "Gross Profit",
    "Operating Income",
    "Net Income",
    "Diluted EPS",
    "EBITDA",
]


@mcp.tool()
def get_income_statement(symbol: str, period: Literal["annual", "quarterly"] = "annual") -> dict:
    """Key income-statement lines (revenue, gross profit, operating income, net income, diluted EPS, EBITDA)
    for a company, most recent period first."""
    ticker = yf.Ticker(symbol.upper())
    df = ticker.quarterly_income_stmt if period == "quarterly" else ticker.income_stmt
    if df is None or df.empty:
        raise ValueError(f"No income statement for {symbol!r}")

    periods = []
    for col in df.columns:
        values = {}
        for line in INCOME_LINES:
            if line in df.index:
                v = df.at[line, col]
                values[line] = None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)
        periods.append({"period_end": str(col.date()), **values})
    return {
        "symbol": symbol.upper(),
        "period": period,
        "currency": (ticker.info or {}).get("financialCurrency"),
        "periods": periods,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
