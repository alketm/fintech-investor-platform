# Plan: Economic Policy Uncertainty strategy

**Spec:** ./spec.md

## Files that change
- `mcp_servers/mcp_backtest/src/alko_mcp_backtest/strategies.py`: `epu_ratio`, `epu_positions`, reusing
  `ratio_band_signals`.
- `mcp_servers/mcp_backtest/src/alko_mcp_backtest/server.py`: `_economic_policy_uncertainty`,
  `backtest_economic_policy_uncertainty`, server instructions.
- `backend/src/alko_backend/main.py`, `agents.py`: request literal, tool map, integer params, Backtest agent text.
- `frontend/src/api.ts`, `frontend/src/views/StrategyView.tsx`: strategy id, result type, tile, parameters, stats.
- Tests alongside each; `README.md`; `CLAUDE.md` healthy test counts.

## Order of work
1. Signal functions and unit tests.
2. Tool and tool tests.
3. Backend mapping and test.
4. Strategy view and test.
5. README and `CLAUDE.md`.

## Risks
- Look-ahead: guarded by rejecting a lag below 1 and a test that a day's own reading can't move that day's position.
- Noisy input: guarded by the 30-day/365-day averages and hysteresis bands. The defaults come from a monthly
  approximation, so the live daily run is checked against it.
- `uncertainty_ratio` works on trading days and would drop weekend readings, so EPU gets its own calendar-day helper.

## Proof
`make build`, `make test`, `make lint`, then a live SPY backtest through the API and the Strategy view.
