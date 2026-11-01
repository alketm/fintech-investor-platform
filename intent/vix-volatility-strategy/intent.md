# Intent: VIX versus realized volatility long-short strategy

**Status:** accepted
**Owner:** alketm

## Problem
There is no strategy that uses the gap between implied volatility (the VIX) and the volatility the market has
actually delivered.

## Proposed outcome
A daily long-short backtest that compares the VIX close with SPY's 20-day realized volatility and moves between
short, neutral and long using fixed bands on their ratio. Available to the Backtest agent, the API and the
Strategy view.

## Affected users and systems
- `mcp_servers/mcp_backtest`, backend API and agent instructions, Strategy view.

## Constraints
- VIX (`^VIX`) and SPY closes from yfinance, like the other price data.
- No look-ahead: a decision at a close applies from the next day.

## Open questions
- None.
