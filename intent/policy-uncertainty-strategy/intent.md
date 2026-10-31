# Intent: Policy-rate uncertainty long-short strategy

**Status:** accepted
**Owner:** alketm

## Problem
The long-short strategies only use price signals. There is no way to test whether monetary policy uncertainty
helps time an asset.

## Proposed outcome
A long-short backtest driven by the Kansas City Fed's Policy Rate Uncertainty index (KC PRU), available to the
Backtest agent, the API and the Strategy view.

## Affected users and systems
- `mcp_servers/backtest`, backend API and server environment, Strategy view.

## Constraints
- KC PRU from FRED (series KCPRU) using the existing FRED client and `FRED_API_KEY`.
- No look-ahead: the signal uses the index value from before the trading close.

## Open questions
- Whether the asset should be risk-on (stocks) or risk-off (bonds) is left to the user via the symbol; the rule
  is the same.
