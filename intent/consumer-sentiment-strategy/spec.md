# Spec: Consumer sentiment long-short strategy

**Intent:** ./intent.md
**Status:** approved

## Data
University of Michigan consumer sentiment index (FRED `UMCSENT`, monthly, dated the first of the month). The
final reading for month M is released late in M, so it is treated as known at M's last trading day.

## Rule
On each month's last trading day, take the latest usable reading as a % of its `ma_months` moving average
(default 3, including that reading) and move one step through this state machine, starting neutral:
- From neutral: short below `short_below_pct` (95), long above `long_above_pct` (97), else stay neutral.
- From long: neutral once below `exit_pct` (96).
- From short: neutral once above `exit_pct` (96).

One transition per month, so a long or short always passes through neutral before reversing. The state runs
from the earliest reading (1978), so results don't depend on where the data request starts. The position is
held over the next month. Requires 0 < `short_below_pct` <= `exit_pct` <= `long_above_pct`.

## Tool
`backtest_consumer_sentiment(symbol, start, end, ma_months=3, short_below_pct=95, long_above_pct=97,
exit_pct=96, release_lag_months=0, initial_capital=10000, cost_bps=5, benchmark="SPY")` returns the standard
long-short output plus `sentiment`: the reading month, value, moving average, value as a % of the average and
the signal behind the last decision as of the test end.

## API and UI
`POST /api/strategy/long-short` accepts `strategy: consumer_sentiment` with `ma_months`, `short_below_pct`,
`long_above_pct`, `exit_pct`, `release_lag_months`. The Strategy view's "Consumer sentiment bands" tile sets
the period to the last 10 years.

## Acceptance criteria
1. Unit tests: every state-machine transition, month-end rebalancing, release lag.
2. Tool test with fake prices and index; missing FRED key gives a clear tool error.
3. Live 10-year backtest through the Strategy view.
