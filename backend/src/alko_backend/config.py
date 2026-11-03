import os
from pathlib import Path

MODEL = "claude-opus-5-5"
EFFORT = "medium"
MAX_AGENT_TURNS = 12
MAX_DELEGATION_DEPTH = 1
MAX_REQUEST_TOKENS = (
    500_000  # shared by every model call in one chat request; a broad five-specialist chat used 62k
)
GUARDRAIL_MODEL = "claude-haiku-5-5"

ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT / ".env"  # git-ignored; holds secrets such as FRED_API_KEY
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"
AUDIT_DB = DATA_DIR / "audit" / "audit.db"  # git-ignored; holds questions, replies and thinking summaries
AUDIT_RETENTION_DAYS = 90

# USD per million tokens: (input, output, cache read). Cache writes cost 1.25x input.
# Used for estimates only; a model missing from this table is reported as unpriced.
MODEL_PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4-8": (5.00, 25.00, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}

# SPDR sector ETFs offered on the strategy page next to the portfolio holdings.
SECTOR_ETFS = {
    "XLY": "Consumer Discretionary",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLK": "Technology",
}

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
MCP_SERVER_ENV = {
    "mcp_macro": ("FRED_API_KEY",),
    "mcp_backtest": ("FRED_API_KEY",),
    "mcp_event_study": ("FRED_API_KEY",),
}


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
