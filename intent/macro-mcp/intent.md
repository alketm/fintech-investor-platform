# Intent: Macro MCP server

**Status:** accepted
**Owner:** alketm

## Problem
Agents have no view of the economy: rates, inflation, jobs, growth, consumer health or market stress. They
can't say how the macro backdrop affects a holding.

## Proposed outcome
A `macro` MCP server with `analyze_macro_environment`, `get_economic_indicators` and
`analyze_consumer_sentiment`, plus a Macro agent the advisor can delegate to. `symbol` is optional: without
it the tools describe the market-wide picture; with it they add how that stock relates to it.

## Affected users and systems
- New `mcp_servers/macro`; backend config, dependencies, agents and environment handling.

## Constraints
- Official statistics from the FRED API with the owner's API key (`FRED_API_KEY`, never committed);
  market signals from yfinance.
- FRED allows 120 requests a minute; cache series in memory.

## Open questions
- None.
