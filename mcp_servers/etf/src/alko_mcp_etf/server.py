"""ETF MCP server: fund profiles."""

import math

import yfinance as yf
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("alko-etf", instructions="ETF profiles: category, costs, size and top holdings.")


def _num(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return float(value)


@mcp.tool()
def get_etf_profile(symbol: str) -> dict:
    """Profile of an ETF (e.g. VTI, QQQ): name, category, expense ratio, total assets, yield and top holdings."""
    ticker = yf.Ticker(symbol.upper())
    info = ticker.info or {}
    if info.get("quoteType") not in (None, "ETF"):
        raise ValueError(f"{symbol!r} is a {info.get('quoteType')}, not an ETF")

    top_holdings = []
    try:
        holdings = ticker.funds_data.top_holdings
        for sym, row in holdings.head(10).iterrows():
            top_holdings.append(
                {
                    "symbol": sym,
                    "name": row.get("Name"),
                    "weight_pct": round(float(row.get("Holding Percent")) * 100, 2),
                }
            )
    except Exception:  # funds_data is unavailable for some funds
        pass

    expense = _num(info.get("netExpenseRatio")) or _num(info.get("annualReportExpenseRatio"))
    yld = _num(info.get("yield"))
    return {
        "symbol": symbol.upper(),
        "name": info.get("longName") or info.get("shortName"),
        "category": info.get("category"),
        "fund_family": info.get("fundFamily"),
        "expense_ratio_pct": expense,
        "total_assets": _num(info.get("totalAssets")),
        "yield_pct": round(yld * 100, 3) if yld is not None else None,
        "top_holdings": top_holdings,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
