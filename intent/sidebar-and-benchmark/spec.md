# Spec: Sidebar navigation and SPY benchmark in backtests

**Intent:** ./intent.md
**Status:** approved

## Backtest tools
All five backtest tools take `benchmark` (default `SPY`). Benchmark closes are aligned to the symbol's trading
days (last close carried over gaps) and reported as `benchmark: {symbol, ...stats}`, or `null` when the
benchmark has no data.
- Long-short tools: `benchmark` has the same stats as `strategy` / `buy_and_hold`; `equity_curve` gains a
  `benchmark` column.
- `backtest_buy_and_hold`: adds `sharpe_ratio`, `benchmark` and a weekly `equity_curve` (`buy_and_hold`,
  `benchmark`).

## UI
- Left sidebar with the brand and the three views (Strategy is labelled "Strategies"); the top bar shows the view
  title, portfolio picker and chat button. Below 900px the sidebar becomes a top bar.
- Backtest results: one metrics table (total return, CAGR, volatility, Sharpe, max drawdown, final value) with a
  column per series, and one equity chart: long-short strategy, symbol buy and hold, SPY buy and hold. The SPY
  column and line are omitted when the symbol is SPY or the benchmark is missing.

## Acceptance criteria
1. Engine test: benchmark alignment across a missing day, stats from the test start.
2. Tool tests: benchmark in long-short and buy-and-hold output; missing benchmark gives `null`.
3. View tests: three columns and three chart lines for long-short; two for buy and hold.
4. Live check in the browser.
