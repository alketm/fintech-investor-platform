# Spec: ETF MCP server tools

**Intent:** ./intent.md
**Status:** approved

## Behavior
Every tool takes `symbol_list` (1–20 tickers; trimmed, upper-cased, de-duplicated) and returns
`{"results": [...one entry per valid symbol...], "errors": {symbol: reason}}`, plus `window` where it applies.
Non-ETF symbols are reported in `errors` by the info tools.

`window` is one of `1mo`, `3mo`, `6mo`, `ytd`, `1y`, `3y`, `5y`, `10y`, `max` (default `1y`).

| Tool | Per-symbol output |
| --- | --- |
| `get_etf_basic_info(symbol_list)` | name, family, category, legal type, exchange, currency, inception date, expense ratio %, total assets, yield %, NAV, turnover % |
| `get_etf_performance(symbol_list, window)` | start/end date and price, price return %, total return % (dividends reinvested), annualized return % (windows ≥ 1 year), trading days |
| `get_etf_price_history(symbol_list, window)` | interval and points `{date, close, adj_close}`; daily up to 6mo/ytd, weekly for 1y–5y, monthly for 10y/max |
| `get_etf_top_holdings(symbol_list)` | top 10 holdings `{symbol, name, weight_pct}` and their combined weight |
| `get_etf_sector_breakdown(symbol_list)` | sectors `{sector, weight_pct}` sorted descending (zero weights dropped) and asset classes (stock/bond/cash/other %) |
| `get_etf_risk_metrics(symbol_list, window, benchmark="SPY")` | annualized volatility, downside deviation, max drawdown with peak/trough dates, beta and correlation vs benchmark, Sharpe, Sortino, 1-day historical VaR 95% and CVaR 95% |

Risk metrics use daily dividend-adjusted returns. The risk-free rate is the average 13-week T-bill yield
(`^IRX`) over the window, falling back to 0 if unavailable; the rate used is returned.

`get_etf_profile` is removed; `get_etf_basic_info` + `get_etf_top_holdings` replace it.

## Acceptance criteria
1. Pure calculations (performance, risk, resampling) have unit tests with known answers.
2. Tool tests cover batching, symbol normalization and per-symbol errors without network access.
3. All six tools return real data for `["VTI", "QQQ", "BND"]` over MCP, and an invalid symbol lands in `errors`.
4. The ETF agent answers a comparison question using the new tools.
