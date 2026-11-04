# Spec: Economic Policy Uncertainty strategy

**Intent:** ./intent.md
**Status:** approved

## Data
Economic Policy Uncertainty Index for the United States (Baker, Bloom and Davis; FRED `USEPUINDXD`, daily including
weekends, from 1985). News-based and very noisy: daily readings swung between about 100 and 700 in autumn 2026.

A reading is first published the following morning (the 2026-11-03 reading appeared on 2026-11-04), so it is usable
at the next day's close. FRED serves the current vintage, so any revisions to past readings are not modelled.

## Rule
Each trading day, take the `fast_days` (default 30) calendar-day average of EPU as a multiple of its `slow_days`
(default 365) calendar-day average, using readings up to `signal_lag_days` (default 1, minimum 1) calendar days
before that close. Calendar days keep weekend readings in the averages. Gaps carry the last published value. Then
move one step through this state machine, starting neutral:
- From neutral: short above `short_above` (1.25), long below `long_below` (0.85), else stay neutral.
- From short: neutral once below `exit_level` (1.0).
- From long: neutral once above `exit_level` (1.0).

One transition per day, so a long or short always passes through neutral before reversing. Positions follow the
existing engine (decided at a close, held the next day, costs per change). Two years of warm-up settle the state.
Requires 2 <= `fast_days` < `slow_days` and 0 < `long_below` <= `exit_level` <= `short_above`.

The default bands were chosen from the signal's distribution only, with no returns looked at, using a monthly
approximation over 2010-2026 (median ratio 0.96; about 35% long, 18% short, 47% flat; about 3.3 position changes a
year). The live daily rule on SPY from 2010 to 2026-11-02 has the same median ratio but trades more: 38.5% long,
25.6% short, 35.9% flat and 103 position changes, about 6 a year. The defaults were kept as chosen, not refitted.

## Tool
`backtest_economic_policy_uncertainty(symbol, start, end, fast_days=30, slow_days=365, short_above=1.25,
long_below=0.85, exit_level=1.0, signal_lag_days=1, initial_capital=10000, cost_bps=5, benchmark="SPY")` returns the
standard long-short output plus `epu`: source, the date, fast and slow averages, ratio and signal as of the test
end, and the median ratio over the test. `assumptions` also states the current-vintage limit.

## API and UI
`POST /api/strategy/long-short` accepts `strategy: economic_policy_uncertainty` with those five parameters. The
Strategy view's tile is named "Economic Policy Uncertainty".

## Acceptance criteria
1. Unit tests: calendar-day averages include weekend readings, the signal lag (no same-day use), gaps carried over,
   bands fire end to end.
2. Tool test with fake prices and index; invalid parameters are rejected; missing FRED key gives a clear tool error.
3. API maps the strategy and its parameters; Strategy view shows the thresholds as parameters.
4. Live backtest on SPY through the API, and through the Strategy view on VOO (its symbol list has no SPY).
