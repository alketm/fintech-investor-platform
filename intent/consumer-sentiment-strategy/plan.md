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

## Change: exits on the average's direction
The owner asked that a long exit when the 3-month average goes down and a short exit when it goes up.
`sentiment_trend` now also returns the average's change and goes flat in those cases; the tool, rule text,
Strategy tile and sentiment readout describe the exits. Tests cover both exits.

## Change: band signals
The owner replaced the rule with bands on sentiment as a % of its 3-month average (short below 95%, long above
97%, back to neutral across 96%). `sentiment_band_signals` is the state machine; it replaces the
average-direction exits. The tool fetches UMCSENT from 1978 so the state doesn't depend on the test start.
