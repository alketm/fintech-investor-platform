# Plan: ETF MCP server tools

**Spec:** ./spec.md

## Files that change
- `mcp_servers/etf/src/alko_mcp_etf/analytics.py` (new) — window start dates, performance, risk metrics, resampling.
- `mcp_servers/etf/src/alko_mcp_etf/server.py` — six tools; yfinance access behind `_download` / `_ticker`
  so tests can replace them.
- `mcp_servers/etf/tests/` — analytics and tool tests.
- `backend/src/alko_backend/agents.py` — ETF agent instructions mention comparison, performance and risk.

## Order of work
Analytics + tests → tools + tests → live MCP check → agent check.

## Risks
- yfinance fund data can be missing for some funds; fields come back as null rather than failing.

## Proof
`make test`, `make lint`, a live MCP call of each tool, and one ETF-agent chat.
