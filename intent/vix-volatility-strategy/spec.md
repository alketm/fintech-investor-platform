# Spec: VIX versus realized volatility long-short strategy

**Intent:** ./intent.md
**Status:** approved

## Data
- SPY realized volatility: standard deviation of daily returns over `window_days` (default 20), annualized
  with √252, in percentage points.
- VIX close (`^VIX`), carried over to any SPY trading day it lacks.
- Ratio = VIX / realized volatility, both as of the same close.

## Rule
Each day at the close, one step through this state machine, starting neutral:
- From neutral: short above `short_above` (2.0), long below `long_below` (1.7), else stay neutral.
- From short: neutral once below `exit_level` (1.8).
- From long: neutral once above `exit_level` (1.8).

One transition per day, so a long or short always passes through neutral before reversing. The position applies
to the chosen symbol from the next trading day. A year of warm-up before the start fills the volatility window
and settles the state. Requires 0 < `long_below` <= `exit_level` <= `short_above`.

## Tool
`backtest_vix_volatility(symbol, start, end, window_days=20, short_above=2.0, long_below=1.7, exit_level=1.8,
initial_capital=10000, cost_bps=5, benchmark="SPY")` returns the standard long-short output plus `volatility`:
the VIX, realized volatility, ratio and signal as of the test end, and the median ratio over the test.

## API and UI
`POST /api/strategy/long-short` accepts `strategy: vix_volatility` with those four parameters. The Strategy view
gets a "VIX vs realized volatility" tile with them as inputs.

## Acceptance criteria
1. Unit tests: realized volatility scale, every state-machine transition, alignment to the traded symbol.
2. Tool test with fake prices and VIX; missing SPY or VIX gives a clear tool error.
3. Live backtest through the Strategy view.
