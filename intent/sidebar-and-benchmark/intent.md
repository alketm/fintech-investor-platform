# Intent: Sidebar navigation and SPY benchmark in backtests

**Status:** accepted
**Owner:** alketm

## Problem
The view tabs sit in the top bar, which gets crowded. Backtest results compare a strategy only with buying and
holding the same symbol, so there is no market reference point.

## Proposed outcome
- Portfolio, Analysis and Strategies move to a left sidebar menu.
- Every backtest shows its metrics next to buying and holding the symbol and buying and holding SPY, and charts
  all of them together.

## Affected users and systems
- `mcp_servers/mcp_backtest`, frontend layout and Strategy view.

## Constraints
- The benchmark covers the same trading days as the test; a missing benchmark must not fail the backtest.

## Open questions
- None.
