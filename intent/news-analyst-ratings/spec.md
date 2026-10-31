# Spec: get_analyst_ratings

**Intent:** ./intent.md
**Status:** approved

## Behavior
`get_analyst_ratings(symbol)` returns:

| Field | Content |
| --- | --- |
| `consensus` | `rating` (e.g. buy), `mean_score` (1 = strong buy … 5 = strong sell), `analyst_count` |
| `price_targets` | `current_price`, `low`, `high`, `mean`, `median`, `upside_to_mean_pct` |
| `rating_trend` | per month (`0m` = this month, `-1m`, …): strong buy / buy / hold / sell / strong sell counts and total |
| `recent_changes` | the 10 most recent analyst actions in the last 90 days: date, firm, action (upgrade, downgrade, initiated, maintained, reiterated), from/to grade, price-target action, current/prior target |

Symbols with no analyst coverage (including ETFs) return a tool error: "No analyst coverage for SYMBOL".
Missing pieces (e.g. no price targets) come back as null rather than failing the call.

## Acceptance criteria
1. Unit tests with fake yfinance data cover the full output, the 90-day/10-row limit, a prior target of 0
   becoming null, and the no-coverage error.
2. Live call returns data for AAPL and the no-coverage error for VTI.
3. The News agent answers "what do analysts think of X" using the tool.
