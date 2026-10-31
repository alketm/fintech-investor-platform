# Spec: Financials MCP server tools

**Intent:** ./intent.md
**Status:** approved

## Inputs
- `symbol`: one ticker.
- `period`: `annual` (default) or `quarterly`.
- `window`: `1y`, `2y`, `3y` (default) or `max`, counted in fiscal years. yfinance has about 4 annual periods, so
  `max` is usually 3 years of change; the tools report the span actually used.

Statement values are in the company's reporting currency (returned as `currency`). Ratios are plain numbers;
percentages end in `_pct`. Missing inputs give null. ETFs and symbols without statements return a tool error.

## Tools
| Tool | Output |
| --- | --- |
| `get_income_statement(symbol, period)` | Per period: revenue, cost of revenue, gross profit, R&D, SG&A, operating income, EBIT, EBITDA, interest expense, pretax income, tax, net income, diluted EPS, diluted shares |
| `get_balance_sheet(symbol, period)` | Per period: total/current assets, cash, cash + short-term investments, receivables, inventory, net PP&E, goodwill & intangibles, total/current liabilities, payables, total/long-term/net debt, equity, retained earnings, working capital, shares outstanding |
| `get_cash_flow(symbol, period)` | Per period: operating cash flow, capex, free cash flow, D&A, stock-based comp, change in working capital, investing and financing cash flow, dividends, buybacks, debt issued/repaid |
| `get_financial_overview(symbol, window)` | Profile (name, sector, industry, country, employees, market cap, EV); trailing-12-month snapshot (revenue, EBITDA, net income, FCF, margins, EPS, P/E); per-year trend over the window (revenue, net income, FCF, margins); revenue/net income/FCF CAGR |
| `get_growth_analysis(symbol, window)` | Per metric (revenue, gross profit, operating income, net income, diluted EPS, operating cash flow, FCF, equity): yearly values with YoY %, and CAGR % over the window; latest quarter vs the same quarter a year earlier for revenue, net income and EPS |
| `get_health_analysis(symbol)` | Liquidity (current, quick, cash ratios); leverage (debt/equity, debt/assets, liabilities/assets, net debt, net debt/EBITDA); interest coverage; Altman Z-score with zone; Piotroski F-score with each of the 9 signals |
| `get_efficiency_analysis(symbol)` | Asset, fixed-asset, inventory, receivables, payables and working-capital turnover; days inventory/sales/payables outstanding and the cash conversion cycle; R&D and SG&A as % of revenue |
| `get_financial_ratios(symbol)` | Valuation (trailing/forward P/E, PEG, P/B, P/S, EV/EBITDA, EV/revenue, dividend yield, payout ratio, FCF yield); profitability (gross, operating, net, EBITDA, FCF margins; ROE, ROA, ROIC); per share (EPS, book value, FCF) |

Health, efficiency and ratio tools use the latest fiscal year; balance-sheet denominators are averages of the
latest and prior year-end when both exist. Altman Z is skipped (null with a note) for financial-sector
companies. Piotroski uses year-end assets for ROA and reports how many of the 9 signals had data.

## Acceptance criteria
1. Each calculation has a unit test with hand-checked numbers, including missing-data cases.
2. Tool tests run on fake statements with no network access.
3. All eight tools return real data for AAPL; JPM returns data with bank-inappropriate metrics null and noted;
   an ETF returns a tool error.
4. The Financials agent answers a health/valuation question using the new tools.
