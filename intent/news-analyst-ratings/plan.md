# Plan: get_analyst_ratings

**Spec:** ./spec.md

## Files that change
- `mcp_servers/news/src/alko_mcp_news/server.py` — the tool; yfinance access behind `_ticker` for tests.
- `mcp_servers/news/tests/test_analyst_ratings.py` (new).
- `backend/src/alko_backend/agents.py` — News agent description and instructions cover analyst ratings.

## Order of work
Tool + tests → live MCP check → News agent check.

## Risks
- yfinance's `upgrades_downgrades` column names may change; missing columns become null.

- *Found during build:* in mcp 2.x only `ToolError` messages reach the client; every server raised
  `ValueError`, so expected errors arrived as a bare "Error executing tool". All six servers now raise
  `ToolError` for expected failures, with an in-process client test guarding it.

## Proof
`make test`, `make lint`, live MCP calls for AAPL and VTI, one News-agent chat.
