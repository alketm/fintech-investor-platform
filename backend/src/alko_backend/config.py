from pathlib import Path

MODEL = "claude-opus-5-5"
EFFORT = "medium"
MAX_AGENT_TURNS = 12

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"

# MCP server name -> Python module run over stdio.
MCP_SERVERS = {
    "etf": "alko_mcp_etf.server",
    "stocks": "alko_mcp_stocks.server",
    "news": "alko_mcp_news.server",
    "financials": "alko_mcp_financials.server",
    "backtest": "alko_mcp_backtest.server",
    "event_study": "alko_mcp_event_study.server",
    "institutional": "alko_mcp_institutional.server",
}
