import os
from pathlib import Path

MODEL = "claude-opus-5-5"
EFFORT = "medium"
MAX_AGENT_TURNS = 12

ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT / ".env"  # git-ignored; holds secrets such as FRED_API_KEY
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"

# MCP server name -> Python module run over stdio.
MCP_SERVERS = {
    "mcp_etf": "alko_mcp_etf.server",
    "mcp_stocks": "alko_mcp_stocks.server",
    "mcp_news": "alko_mcp_news.server",
    "mcp_financials": "alko_mcp_financials.server",
    "mcp_backtest": "alko_mcp_backtest.server",
    "mcp_event_study": "alko_mcp_event_study.server",
    "mcp_institutional": "alko_mcp_institutional.server",
    "mcp_macro": "alko_mcp_macro.server",
    "mcp_market": "alko_mcp_market.server",
}

# MCP servers start with a minimal environment; these variables are passed through to the named server only.
MCP_SERVER_ENV = {"mcp_macro": ("FRED_API_KEY",), "mcp_backtest": ("FRED_API_KEY",)}


def load_env_file(path: Path = ENV_FILE) -> None:
    """Set KEY=VALUE lines from a .env file without overriding variables already in the environment."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))
