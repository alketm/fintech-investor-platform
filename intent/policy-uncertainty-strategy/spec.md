# Spec: Policy-rate uncertainty strategy

**Intent:** ./intent.md
**Status:** approved

## Data
Kansas City Fed's Measure of Policy Rate Uncertainty (FRED `KCPRU`, daily, percentage points): option-implied
uncertainty about the policy rate a year ahead, built like the VIX from Eurodollar (before 2023) and SOFR
options.

## Rule
z = (KC PRU − its trailing `lookback_days` mean) / its trailing standard deviation, using the value from
`signal_lag_days` trading days earlier (default 1). Short when z > `threshold`, long when z < −`threshold`,
flat otherwise. Positions follow the existing engine (decided at a close, held the next day, costs per change).

## Tool
`backtest_policy_uncertainty(symbol, start, end, lookback_days=252, threshold=0.5, signal_lag_days=1,
initial_capital=10000, cost_bps=5)` returns the standard long-short output plus `uncertainty`: latest KC PRU
value and date, latest z-score, and the % of test days the signal was high / low / neutral.

## API and UI
`POST /api/strategy/long-short` accepts `strategy: policy_uncertainty` with `lookback_days`, `threshold`,
`signal_lag_days`. The Strategy view gets a fifth tile, "Policy-rate uncertainty".

## Acceptance criteria
1. Unit tests: z-score rule, the signal lag (no same-day use), alignment of index dates to trading days.
2. Tool test with fake prices and index; missing FRED key gives a clear tool error.
3. Live backtest on SPY through the API and the Strategy view.
