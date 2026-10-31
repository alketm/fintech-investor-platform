# Intent: Market MCP server

**Status:** accepted
**Owner:** alketm

## Problem
Agents can quote a single price but can't describe how the market is doing, which sectors lead, what's moving
today, or how a stock is trending technically and relative to the market.

## Proposed outcome
A `market` MCP server with `get_market_summary`, `get_stock_analysis`, `get_market_movers`,
`get_sector_performance` and `get_historical_data`, and a Market agent the advisor can delegate to.

## Affected users and systems
- New `mcp_servers/market`; backend config, dependencies and agents.

## Constraints
- yfinance only (prices delayed ~15 minutes; screeners are Yahoo's predefined lists).
- Technical indicators are descriptive, not trading signals.

## Open questions
- None.
