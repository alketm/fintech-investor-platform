# Intent: Financials MCP server tools

**Status:** accepted
**Owner:** alketm

## Problem
The Financials MCP server only returns a few income-statement lines. Agents can't see balance sheets or cash
flows, or judge a company's growth, financial health, efficiency or valuation.

## Proposed outcome
Eight tools on the Financials server: `get_financial_overview`, `get_income_statement`, `get_balance_sheet`,
`get_cash_flow`, `get_growth_analysis`, `get_health_analysis`, `get_efficiency_analysis`,
`get_financial_ratios`.

## Affected users and systems
- `mcp_servers/financials`, the Financials agent (and the advisor through it).

## Constraints
- yfinance only: about 4 annual periods and 5–7 quarters of statements.
- Banks and insurers lack several line items; affected metrics are null with a note, never a wrong number.

## Open questions
- None.
