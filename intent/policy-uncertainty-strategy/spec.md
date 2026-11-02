# Spec: Monetary Policy Uncertainty strategy

**Intent:** ./intent.md
**Status:** approved

## Data
Kansas City Fed's Measure of Policy Rate Uncertainty (FRED `KCPRU`, daily, percentage points): option-implied
uncertainty about the policy rate a year ahead, built like the VIX from Eurodollar (before 2023) and SOFR
options.

## Rule
Each trading day, take KC PRU from `signal_lag_days` trading days earlier (default 1; last published value
carried over gaps) as a multiple of its `ma_days` trading-day moving average (default 21), and move one step
through this state machine, starting neutral:
- From neutral: short above `short_above` (1.4), long below `long_below` (1.2), else stay neutral.
- From short: neutral once below `exit_level` (1.3).
- From long: neutral once above `exit_level` (1.3).

One transition per day, so a long or short always passes through neutral before reversing. Positions follow the
existing engine (decided at a close, held the next day, costs per change). A year of warm-up settles the state.
Requires 0 < `long_below` <= `exit_level` <= `short_above`. Replaces the earlier z-score rule.

## Tool
`backtest_policy_uncertainty(symbol, start, end, ma_days=21, short_above=1.4, long_below=1.2, exit_level=1.3,
signal_lag_days=1, initial_capital=10000, cost_bps=5, benchmark="SPY")` returns the standard long-short output
plus `uncertainty`: KC PRU, its average, the ratio and the signal as of the test end, and the median ratio over
the test.

## API and UI
`POST /api/strategy/long-short` accepts `strategy: policy_uncertainty` with those five parameters. The Strategy
view's tile is named "Monetary Policy Uncertainty".

## Acceptance criteria
1. Unit tests: every band transition, the signal lag (no same-day use), alignment of index dates to trading days.
2. Tool test with fake prices and index; missing FRED key gives a clear tool error.
3. Live backtest on SPY through the API and the Strategy view.
