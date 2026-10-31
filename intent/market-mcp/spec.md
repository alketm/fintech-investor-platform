# Spec: Market MCP server

**Intent:** ./intent.md
**Status:** approved

## Inputs
`window`: `1d`, `5d` (trading days), `1mo`, `3mo`, `6mo`, `ytd`, `1y`, `3y`, `5y`, `10y`, `max`. Defaults:
`1mo` for the market summary and sectors, `1y` for stock analysis and history. Returns compare the last close
with the last close on or before the window start.

## Tools
| Tool | Output |
| --- | --- |
| `get_market_summary(window)` | S&P 500, Dow, Nasdaq Composite, Russell 2000: last close, 1-day and window change %; VIX level and change; 10y yield and change in points; dollar index, WTI oil, gold change %; S&P 500 vs its 50/200-day averages; breadth: how many of the 11 sector ETFs rose, leader and laggard |
| `get_stock_analysis(symbol, window)` | price, window return, return vs S&P 500 and vs its sector ETF; 52-week high/low and distance; 50/200-day averages, price vs each, golden/death cross; RSI(14); MACD(12,26,9) and signal; annualized volatility, max drawdown and beta over the window; latest volume vs 3-month average; a rule-based trend label with the rules |
| `get_market_movers()` | today's top 10 gainers, losers and most active US stocks: symbol, name, price, change %, volume, volume vs 3-month average, market cap |
| `get_sector_performance(window)` | 11 SPDR sector ETFs: window and 1-day change %, relative to the S&P 500, ranked, plus leader/laggard and spread |
| `get_historical_data(symbol, window)` | OHLCV points (daily up to 6mo/ytd, weekly 1y–5y, monthly 10y/max) and a summary: start/end, return, high, low, average volume |

Unknown symbols and missing data return tool errors with the reason.

## Acceptance criteria
1. Unit tests: window base selection, returns, RSI, MACD, moving averages and crosses, trend rules, OHLCV
   resampling, drawdown and beta, with known answers.
2. Tool tests with fake price and screener data, no network; errors reach an MCP client.
3. Live: all five tools return data; the Market agent answers through the advisor.
