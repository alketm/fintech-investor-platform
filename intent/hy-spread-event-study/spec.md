# Spec: High-yield credit spread event study

**Intent:** ./intent.md
**Status:** approved

## Data
ICE BofA US High Yield Index option-adjusted spread (FRED `BAMLH0A0HYM2`, daily, percentage points). FRED only
carries about the last three years of ICE BofA data, so the tool reports `spread_history_start` and says so in
its note when that is later than the lookback asks for.

## Events
A day is an event when the spread is above `threshold` (default 1.25) times its `ma_days` (default 21) moving
average, that day included, and the day before was not: a spell above the threshold counts once. An event
within `window` days of the previous kept event is skipped so windows don't overlap. Only events in the last
`lookback_years` (default 10) count.

## Measurement
Day 0 is the first trading day after the spread date. Market-model abnormal returns against `benchmark`
(default SPY) use the existing estimation window (120 days, ending 10 days before the event window). Reported:
- average abnormal CAR over days 0 to +`window` with t-stat, % positive, and the average abnormal path from
  -`window` to +`window`;
- average total (not market-adjusted) return over the same days, with t-stat;
- each event: spread, average, ratio, day 0, day-0 abnormal return, abnormal CAR and total return.

## Tool, API and UI
`run_credit_spread_event_study(symbol, threshold=1.25, ma_days=21, benchmark="SPY", window=10,
lookback_years=10)`. `POST /api/strategy/event-study/credit-spread` with the same fields. The Strategy view gets
a "High-yield spread spikes" event tile with threshold, average and lookback inputs.

## Acceptance criteria
1. Unit tests: crossings counted once, overlap skipping, CAR summary.
2. Tool test with a fake spread and planted next-day drops; missing FRED key gives a clear tool error.
3. Live run through the Strategy view.
