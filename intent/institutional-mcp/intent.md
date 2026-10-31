# Intent: Institutional MCP server

**Status:** accepted
**Owner:** alketm

## Problem
Agents can't see who owns a stock: how much is held by institutions and insiders, who the largest holders are,
and whether those holders are buying or selling.

## Proposed outcome
A new `institutional` MCP server with `get_institutional_ownership`, `get_top_institutional_holders` and
`get_institutional_ownership_changes`, and an Institutional agent the advisor can delegate to.

## Affected users and systems
- New `mcp_servers/institutional`; backend config, dependencies and agents.

## Constraints
- yfinance only: an ownership summary plus the top 10 institutions and top 10 mutual funds from 13F filings,
  which lag the quarter by up to 45 days. Changes can only be measured for those holders.

## Open questions
- None.
