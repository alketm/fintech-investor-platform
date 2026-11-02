# Plan: High-yield credit spread event study

**Spec:** ./spec.md

## Files that change
- `mcp_servers/mcp_event_study/src/alko_mcp_event_study/analytics.py` — `detect_spread_widening`,
  `summarize_cars`.
- `mcp_servers/mcp_event_study/src/alko_mcp_event_study/server.py` — tool; spread via `alko_mcp_macro.fred`.
- `mcp_servers/mcp_event_study/pyproject.toml` — depend on `alko-mcp-macro` (shared FRED client).
- `backend/src/alko_backend/config.py` — pass `FRED_API_KEY` to the event study server.
- `backend/src/alko_backend/main.py`, `agents.py` — endpoint and agent instructions.
- `frontend/src/api.ts`, `frontend/src/views/StrategyView.tsx` — tile, inputs, result view.
- Tests in each layer.

## Order of work
Detection + tests → tool + tests → backend → UI → live check.

## Risks
- FRED serves only about three years of ICE BofA history, so a 10-year lookback really covers ~3 years;
  the tool reports the actual start.
- Spread spikes are rare and cluster in crises, so results rest on a handful of events.
- When the symbol is the benchmark, abnormal returns are near zero by construction; total returns still apply.
