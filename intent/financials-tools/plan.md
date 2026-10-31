# Plan: Financials MCP server tools

**Spec:** ./spec.md

## Files that change
- `mcp_servers/financials/src/alko_mcp_financials/statements.py` (new) — line-item aliases, value lookup,
  statement payloads.
- `mcp_servers/financials/src/alko_mcp_financials/analytics.py` (new) — trend, growth, health, efficiency and
  ratio calculations on statement DataFrames.
- `mcp_servers/financials/src/alko_mcp_financials/server.py` — eight tools; yfinance behind `_ticker`.
- `mcp_servers/financials/tests/` — analytics and tool tests.
- `backend/src/alko_backend/agents.py` — Financials agent instructions.

## Order of work
Statements + analytics with tests → tools with tests → live MCP check (AAPL, JPM, VTI) → agent check.

## Risks
- yfinance row names vary by company type; lookups use aliases and return null when absent.
- Only ~4 annual periods, so long windows are capped; tools report the span used.

## Proof
`make test`, `make lint`, live calls of all eight tools, one Financials-agent chat.
