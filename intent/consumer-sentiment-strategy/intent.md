# Intent: Consumer sentiment long-short strategy

**Status:** accepted
**Owner:** alketm

## Problem
The macro long-short strategies only use policy-rate uncertainty. There is no way to test whether the trend in
consumer sentiment helps time a stock or ETF.

## Proposed outcome
A long-short backtest on the University of Michigan consumer sentiment index over the past 10 years: long the
symbol when the index is above its 3-month moving average, short when below, rebalanced monthly. Available to
the Backtest agent, the API and the Strategy view.

## Affected users and systems
- `mcp_servers/mcp_backtest`, backend API and agent instructions, Strategy view.

## Constraints
- Data from FRED (series UMCSENT) with the existing FRED client and `FRED_API_KEY`.
- No look-ahead: a month's reading is used only once it is final.

## Open questions
- None.
