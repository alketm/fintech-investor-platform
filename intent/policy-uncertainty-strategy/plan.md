# Plan: Policy-rate uncertainty strategy

**Spec:** ./spec.md

## Files that change
- `mcp_servers/backtest/src/alko_mcp_backtest/strategies.py` — `policy_uncertainty_positions`.
- `mcp_servers/backtest/src/alko_mcp_backtest/server.py` — tool; KC PRU via `alko_mcp_macro.fred`.
- `mcp_servers/backtest/pyproject.toml` — depend on `alko-mcp-macro` (shared FRED client).
- `backend/src/alko_backend/config.py` — pass `FRED_API_KEY` to the backtest server too.
- `backend/src/alko_backend/main.py`, `agents.py` — API strategy and agent instructions.
- `frontend/src/api.ts`, `frontend/src/views/StrategyView.tsx` — tile and parameters.
- Tests in each layer.

## Order of work
Rule + tests → tool + tests → backend → UI → live check.

## Risks
- Reusing the macro package's FRED client couples two servers; acceptable for one shared HTTP helper.

## Proof
`make test`, `make lint`, `make build`, live API run and Strategy view screenshot.

## Change: Monetary Policy Uncertainty bands
The owner renamed the strategy "Monetary Policy Uncertainty" and replaced the z-score rule with bands on KC PRU
as a multiple of its 21-day average (short above 1.4x, long below 1.2x, back to neutral across 1.3x). The band
state machine is shared with the VIX strategy as `ratio_band_signals`. The API id and tool name stay
`policy_uncertainty` / `backtest_policy_uncertainty`.
