# Plan: Long-short strategies and event studies

**Spec:** ./spec.md

## Files that change
- `mcp_servers/backtest/src/alko_mcp_backtest/strategies.py` (new) — signals, next-day positions, P&L, stats.
- `mcp_servers/backtest/src/alko_mcp_backtest/server.py` — three tools; price download with warm-up.
- `mcp_servers/event_study/src/alko_mcp_event_study/analytics.py` — per-event abnormal returns reusable across
  events, aggregation, earnings day-0 timing, large-move detection.
- `mcp_servers/event_study/src/alko_mcp_event_study/server.py` — two tools.
- `backend/src/alko_backend/main.py` — three endpoints; `agents.py` — backtest/event-study instructions.
- `frontend/src/api.ts`, `frontend/src/views/StrategyView.tsx`, new `frontend/src/components/LineChart.tsx`,
  `frontend/src/index.css`.
- Tests in each package; `CLAUDE.md` counts.

## Order of work
Strategies + tests → event studies + tests → API → UI → live checks in the browser.

## Risks
- yfinance earnings history is limited (~12–24 quarters); fewer events give noisier averages, so t-stats and
  counts are always shown.

## Proof
`make test`, `make lint`, `make build`, live MCP calls, and screenshots of the Strategy view.
