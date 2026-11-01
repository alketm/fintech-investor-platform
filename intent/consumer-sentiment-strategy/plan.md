# Plan: Consumer sentiment long-short strategy

**Spec:** ./spec.md

## Files that change
- `mcp_servers/mcp_backtest/src/alko_mcp_backtest/strategies.py` — `sentiment_trend`, `sentiment_trend_positions`.
- `mcp_servers/mcp_backtest/src/alko_mcp_backtest/server.py` — tool; UMCSENT via `alko_mcp_macro.fred`.
- `backend/src/alko_backend/main.py`, `agents.py` — API strategy and agent instructions.
- `frontend/src/api.ts`, `frontend/src/views/StrategyView.tsx` — tile, parameters, 10-year period, reading.
- Tests in each layer.

## Order of work
Rule + tests → tool + tests → backend → UI → live check.

## Risks
- Monthly signals give few trades over 10 years; results are sensitive to a handful of months.
