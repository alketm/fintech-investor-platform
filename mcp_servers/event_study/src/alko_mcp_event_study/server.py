"""Event study MCP server."""

from datetime import timedelta

import pandas as pd
import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from alko_mcp_event_study.analytics import market_model_event_study

mcp = MCPServer("alko-event-study", instructions="Event studies measuring abnormal returns around a date.")


@mcp.tool()
def run_event_study(symbol: str, event_date: str, benchmark: str = "SPY", window: int = 5) -> dict:
    """Market-model event study: abnormal returns of `symbol` vs `benchmark` over ±`window` trading days around
    `event_date` (YYYY-MM-DD), with the model fitted on the ~120 trading days before. Returns alpha, beta, the
    daily abnormal-return and cumulative-abnormal-return (CAR) series, total CAR and its t-statistic."""
    window = max(1, min(window, 30))
    day = pd.Timestamp(event_date)
    start = (day - timedelta(days=300)).strftime("%Y-%m-%d")
    end = (day + timedelta(days=window * 2 + 10)).strftime("%Y-%m-%d")
    closes = {
        s: yf.Ticker(s).history(start=start, end=end, auto_adjust=True)["Close"].tz_localize(None)
        for s in (symbol.upper(), benchmark.upper())
    }
    try:
        result = market_model_event_study(
            closes[symbol.upper()], closes[benchmark.upper()], day, window=window
        )
    except ValueError as e:  # expected data problems: report the reason to the caller
        raise ToolError(str(e)) from e
    return {"symbol": symbol.upper(), "benchmark": benchmark.upper(), "event_date": event_date, **result}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
