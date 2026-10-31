# Plan: Macro MCP server

**Spec:** ./spec.md

## Files that change
- `mcp_servers/macro/` (new): `fred.py` (FRED API client with cache), `market.py` (yfinance series),
  `analytics.py` (signal rules, percentile, correlations, sector map), `server.py` (tools), tests.
- `backend/src/alko_backend/config.py` — register the server; load a git-ignored `.env`; per-server env.
- `backend/src/alko_backend/mcp_pool.py` — pass `FRED_API_KEY` to the macro server only.
- `backend/src/alko_backend/agents.py` — Macro agent.
- `backend/pyproject.toml`, `CLAUDE.md`, `README.md`.

## Order of work
Analytics + tests → FRED/market clients → tools + tests → backend wiring → live check once the key is set.

## Risks
- Rule-based regime labels are simple heuristics; every label returns its evidence and thresholds.
- FRED revises data; values are as of the call.

## Proof
`make test`, `make lint`, live calls with and without a symbol, one Macro-agent chat.
