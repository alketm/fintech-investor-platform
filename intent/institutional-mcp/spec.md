# Spec: Institutional MCP server

**Intent:** ./intent.md
**Status:** approved

## Tools
All take one `symbol`. Symbols with no ownership data (including ETFs) return a tool error.

| Tool | Output |
| --- | --- |
| `get_institutional_ownership(symbol)` | institutions % of shares and of float, insiders %, other (retail and unreported) %, number of institutions, shares outstanding, float, implied institutional shares, and the combined % held by the top 10 institutions |
| `get_top_institutional_holders(symbol)` | top 10 institutions and top 10 mutual funds: holder, date reported, % held, shares, value, % change in shares since the prior filing |
| `get_institutional_ownership_changes(symbol)` | per holder (top institutions and funds): shares now, estimated prior shares, change in shares, % change, direction (increased / decreased / unchanged); summary per group: buyers vs sellers count, net change in shares and as % of shares outstanding; largest increases and decreases |

Prior shares are estimated as `shares / (1 + pct_change)`. Changes under 0.1% count as unchanged. Every result
includes `as_of` (latest report date) and a note that 13F data lags by up to 45 days and only covers the top
holders shown.

## Agent
`institutional` — Institutional ownership analyst, uses only the institutional server; the advisor gets
`ask_institutional`.

## Acceptance criteria
1. Unit tests with fake holder data cover all three tools, the prior-share estimate, the unchanged threshold,
   and the ETF / no-data error (including through an MCP client).
2. Backend `/api/health` lists the server with three tools; `/api/agents` lists the new agent.
3. Live calls return data for AAPL and an error for VTI; the Institutional agent answers a question with them.
