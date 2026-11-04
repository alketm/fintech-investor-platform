# Intent: Economic Policy Uncertainty long-short strategy

**Status:** accepted
**Owner:** alketm

## Problem
There is no way to test whether broad, news-based economic policy uncertainty helps time an asset. The existing
Monetary Policy Uncertainty strategy uses the Kansas City Fed's option-implied policy-rate index, which is a
different and narrower signal.

## Proposed outcome
A long-short backtest driven by the Baker-Bloom-Davis Economic Policy Uncertainty index (EPU), available to the
Backtest agent, the API and the Strategy view. High EPU is short and low EPU is long.

## Affected users and systems
- `mcp_servers/mcp_backtest`, backend API, Backtest agent, Strategy view.

## Constraints
- EPU from FRED (series USEPUINDXD) using the existing FRED client and `FRED_API_KEY`.
- No look-ahead: the signal only uses readings published before the decision close.
- Results are simulations, never a forecast or recommendation.

## Open questions
None. Direction (high EPU = short) and signal (daily series, smoothed) were decided by the owner.
