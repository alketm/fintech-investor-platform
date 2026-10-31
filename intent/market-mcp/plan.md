# Plan: Market MCP server

**Spec:** ./spec.md

## Files that change
- `mcp_servers/market/` (new): `analytics.py` (windows, returns, indicators, resampling), `server.py` (tools;
  yfinance behind `_download`, `_screen`, `_info`), tests.
- `backend/pyproject.toml`, `backend/src/alko_backend/config.py` — register the server.
- `backend/src/alko_backend/agents.py` — Market agent.
- `CLAUDE.md` — counts.

## Order of work
Analytics + tests → tools + tests → backend wiring → live check.

## Risks
- Yahoo screener availability can change; movers fail with a clear tool error rather than empty lists.

## Proof
`make test`, `make lint`, live calls of all five tools, one advisor chat.
