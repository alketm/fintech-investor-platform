# Intent: Analyst ratings in the News MCP server

**Status:** accepted
**Owner:** alketm

## Problem
Agents can see headlines but not what sell-side analysts think of a stock: consensus rating, price targets and
recent upgrades or downgrades.

## Proposed outcome
A `get_analyst_ratings(symbol)` tool on the News MCP server, backed by yfinance.

## Affected users and systems
- `mcp_servers/news`, the News agent (and the advisor through it).

## Constraints
- yfinance only. ETFs and thinly covered stocks have no analyst data; say so instead of returning empty numbers.

## Open questions
- None.
