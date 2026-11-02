# Intent: High-yield credit spread event study

**Status:** accepted
**Owner:** alketm

## Problem
The event studies cover a chosen date, earnings and a stock's own large moves. There is no way to see how a stock
or ETF behaves after credit markets come under sudden stress.

## Proposed outcome
An event study whose events are days when the Bank of America (ICE BofA) US High Yield option-adjusted spread
rises above 1.25 times its 21-day moving average. Available to the Event study agent, the API and the Strategy
view.

## Affected users and systems
- `mcp_servers/mcp_event_study` (now also reads FRED), backend API, server environment and agent instructions,
  Strategy view.

## Constraints
- Spread from FRED (series BAMLH0A0HYM2) with the shared FRED client and `FRED_API_KEY`.
- No look-ahead: the spread for a day is published after it, so the reaction is measured from the next day.

## Open questions
- None.
