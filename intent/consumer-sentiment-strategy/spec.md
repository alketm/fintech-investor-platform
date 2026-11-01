# Spec: Consumer sentiment long-short strategy

**Intent:** ./intent.md
**Status:** approved

## Data
University of Michigan consumer sentiment index (FRED `UMCSENT`, monthly, dated the first of the month). The
final reading for month M is released late in M, so it is treated as known at M's last trading day.

## Rule
On each month's last trading day, compare the latest usable reading with its `ma_months` moving average
(default 3, including that reading). Long when above, short when below, flat if equal; held over the next
month. `release_lag_months` (default 0) uses a reading that many months older. Positions follow the existing
engine (decided at a close, held from the next day, costs per change, SPY benchmark).

## Tool
`backtest_consumer_sentiment(symbol, start, end, ma_months=3, release_lag_months=0, initial_capital=10000,
cost_bps=5, benchmark="SPY")` returns the standard long-short output plus `sentiment`: the reading month,
value, moving average and signal behind the last decision as of the test end.

## API and UI
`POST /api/strategy/long-short` accepts `strategy: consumer_sentiment` with `ma_months`, `release_lag_months`.
The Strategy view gets a "Consumer sentiment trend" tile; choosing it sets the period to the last 10 years.

## Acceptance criteria
1. Unit tests: month-end rebalancing, signal above/below the average, release lag.
2. Tool test with fake prices and index; missing FRED key gives a clear tool error.
3. Live 10-year backtest through the Strategy view.
