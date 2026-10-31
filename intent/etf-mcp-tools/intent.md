# Intent: ETF MCP server tools

**Status:** accepted
**Owner:** alketm

## Problem
The ETF MCP server has one catch-all tool (`get_etf_profile`). Agents can't compare several ETFs, see
performance or risk over a period, or look at sector exposure.

## Proposed outcome
Six focused tools that each take a list of symbols:
`get_etf_basic_info`, `get_etf_performance`, `get_etf_price_history`, `get_etf_top_holdings`,
`get_etf_sector_breakdown`, `get_etf_risk_metrics`.

## Affected users and systems
- `mcp_servers/etf`, the ETF agent (and the advisor through it).

## Constraints
- yfinance stays the data source.
- One bad symbol must not fail the whole request.

## Open questions
- None blocking.
