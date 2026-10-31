# Plan: Institutional MCP server

**Spec:** ./spec.md

## Files that change
- `mcp_servers/institutional/` (new package): `server.py` (tools, yfinance behind `_ticker`), `analytics.py`
  (holder tables and change math), tests.
- `backend/pyproject.toml`, `backend/src/alko_backend/config.py` — register the server.
- `backend/src/alko_backend/agents.py` — Institutional agent.
- `CLAUDE.md` — test count.

## Order of work
Package + tests → backend wiring → `uv sync` → live MCP and agent check.

## Risks
- `pctChange` may be missing or NaN for new positions; those rows report no change estimate.

## Proof
`make test`, `make lint`, health and agents endpoints, live tool calls, one agent chat.
