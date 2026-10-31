# Intent: Long-short strategies and event studies

**Status:** accepted
**Owner:** alketm

## Problem
The Strategy view and agents can only backtest buy-and-hold and study a single event date. There is no way to
test rule-based long-short strategies, or to measure how a stock typically reacts to earnings or to large
price moves.

## Proposed outcome
- Long-short backtests: moving-average crossover, time-series momentum, RSI mean reversion.
- Event studies across many events: earnings announcements and large daily moves.
- Available to agents (MCP tools), the API, and the Strategy view.

## Affected users and systems
- `mcp_servers/backtest`, `mcp_servers/event_study`, backend API and agent instructions, frontend Strategy view.

## Constraints
- yfinance daily data. No look-ahead: signals at a close trade from the next day.
- Results are historical simulations, not recommendations; short-borrow costs and taxes are ignored.

## Open questions
- None.
