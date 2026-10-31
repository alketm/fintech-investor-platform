# Spec: Long-short strategies and event studies

**Intent:** ./intent.md
**Status:** approved

## Long-short backtests (backtest server)
Common inputs: `symbol`, `start`, `end` (YYYY-MM-DD), `initial_capital` (10,000), `cost_bps` (5, charged on
each unit of position change). Positions are +1 long, −1 short or 0 flat, set from the close of day t and held
over day t+1. Indicators use history before `start` (a warm-up) so the first day already has a signal.

| Tool | Rule | Parameters (defaults) |
| --- | --- | --- |
| `backtest_moving_average` | long when the fast average is above the slow, short when below | `fast` 50, `slow` 200 |
| `backtest_time_series_momentum` | long when the trailing return (skipping the latest month) is positive, short when negative; rebalanced monthly | `lookback_days` 252, `skip_days` 21 |
| `backtest_rsi_mean_reversion` | long when RSI drops below `lower`, short when above `upper`; exit when RSI crosses `exit_level` | `period` 14, `lower` 30, `upper` 70, `exit_level` 50 |

Output for each: the rule and parameters; strategy and buy-and-hold stats (total return, CAGR, annualized
volatility, Sharpe with a 0% risk-free rate, max drawdown, final value); trades (position changes), % of days
long / short / flat, win rate of closed trades, total costs; a weekly equity curve for both; notes on
assumptions.

## Event studies (event_study server)
Market model per event: alpha and beta fitted on 120 trading days ending 10 days before the event window.

| Tool | Events | Output |
| --- | --- | --- |
| `run_earnings_event_study(symbol, benchmark, window, max_events)` | past earnings dates (default last 12). Day 0 is the announcement day, or the next trading day for reports at or after 4pm ET | per event: date, EPS estimate/actual/surprise %, day-0 abnormal return, CAR[−1,+1] and CAR[−window,+window]; aggregate: average abnormal return by day, average CAR, t-statistic across events, % positive; the same split by beats vs misses |
| `run_large_move_event_study(symbol, threshold_sigma, benchmark, window, lookback_years)` | days whose return exceeds `threshold_sigma` (2.5) times the trailing 60-day volatility, over `lookback_years` (5); events closer than `window` days to an earlier one are skipped | events split into up and down moves; per group: count, average day-0 move, average post-event CAR over +1..+window, % continuing in the move's direction, t-statistic; a continuation/reversal read; the event list |

`window` defaults to 5 (earnings) and 10 (large moves). Existing `backtest_buy_and_hold` and `run_event_study`
stay unchanged.

## API and UI
- `POST /api/strategy/long-short` `{strategy: moving_average | time_series_momentum | rsi_mean_reversion,
  symbol, start, end, initial_capital, cost_bps, params}`.
- `POST /api/strategy/event-study/earnings`, `POST /api/strategy/event-study/large-moves`.
- Strategy view: the backtest card gets a strategy picker (buy and hold plus the three) with per-strategy
  parameters, a stats table (strategy vs buy and hold) and an equity-curve chart. The event study card gets a
  type picker (single date, earnings, large moves) with matching inputs and results.

## Acceptance criteria
1. Unit tests with known answers: position rules for each strategy, next-day execution, costs, trade counting,
   earnings day-0 timing, large-move detection and de-overlapping, multi-event aggregation.
2. API tests for the new endpoints with a fake pool; frontend test for the strategy picker request.
3. Live: each strategy and both event studies run for a real symbol through MCP and in the Strategy view.
