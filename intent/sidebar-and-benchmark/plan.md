# Plan: Sidebar navigation and SPY benchmark in backtests

**Spec:** ./spec.md

## Files that change
- `mcp_servers/mcp_backtest/src/alko_mcp_backtest/analytics.py` — Sharpe in buy-and-hold stats,
  `align_benchmark`, `weekly_equity_curve`.
- `mcp_servers/mcp_backtest/src/alko_mcp_backtest/strategies.py` — optional `benchmark` in `run_backtest`.
- `mcp_servers/mcp_backtest/src/alko_mcp_backtest/server.py` — `benchmark` parameter on every tool.
- `frontend/src/App.tsx`, `frontend/src/index.css` — sidebar layout, third chart color.
- `frontend/src/api.ts`, `frontend/src/views/StrategyView.tsx` — `ComparisonTable`, `EquityChart`.
- Tests in each layer.

## Order of work
Engine + tests → tools + tests → result views → sidebar → live check.

## Risks
- An extra yfinance download per backtest; acceptable.
