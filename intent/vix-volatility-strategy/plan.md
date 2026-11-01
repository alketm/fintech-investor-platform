# Plan: VIX versus realized volatility long-short strategy

**Spec:** ./spec.md

## Files that change
- `mcp_servers/mcp_backtest/src/alko_mcp_backtest/strategies.py` — `realized_volatility`, `vix_ratio`,
  `vix_band_signals`, `vix_volatility_positions`.
- `mcp_servers/mcp_backtest/src/alko_mcp_backtest/server.py` — tool; SPY and `^VIX` via `_history`.
- `backend/src/alko_backend/main.py`, `agents.py` — API strategy and agent instructions.
- `frontend/src/api.ts`, `frontend/src/views/StrategyView.tsx` — tile, parameters, volatility readout.
- Tests in each layer.

## Order of work
Rule + tests → tool + tests → backend → UI → live check.

## Risks
- The state depends on its history, so results shift slightly with the warm-up length; a year is used.
