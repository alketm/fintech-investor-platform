# Spec: Macro MCP server

**Intent:** ./intent.md
**Status:** approved

## Data
FRED series (latest value, prior value, change, date): Fed funds (FEDFUNDS), 2y and 10y Treasury (DGS2,
DGS10), 10y–2y and 10y–3m spreads (T10Y2Y, T10Y3M), CPI and core CPI YoY (CPIAUCSL, CPILFESL), core PCE YoY
(PCEPILFE), 10y breakeven inflation (T10YIE), unemployment (UNRATE), payroll change (PAYEMS), initial claims
(ICSA), real GDP growth (A191RL1Q225SBEA), industrial production YoY (INDPRO), housing starts (HOUST), Sahm
rule (SAHMREALTIME), financial conditions (NFCI), high-yield spread (BAMLH0A0HYM2), UMich sentiment
(UMCSENT), retail sales YoY (RSAFS), real consumer spending YoY (PCEC96), savings rate (PSAVERT), credit-card
delinquency (DRCCLACBS).

yfinance: VIX, S&P 500, dollar index, WTI oil, copper, gold, and consumer discretionary vs staples (XLY/XLP).

## Tools
`symbol` is optional everywhere. When given, results add a `stock` section; ETFs are allowed.

| Tool | Output |
| --- | --- |
| `get_economic_indicators(symbol)` | Indicators grouped as rates, inflation, labor, growth, housing, financial conditions, consumer: each with value, units, date, prior value and change. With a symbol: its sector and the indicator groups most relevant to that sector |
| `analyze_macro_environment(symbol)` | Rule-based reads: growth (expanding/slowing/contracting), inflation (trend and vs 2% target), policy (real Fed funds rate, curve shape), stress (VIX, HY spread, NFCI), recession signals (Sahm rule, curve inversion), market signals (oil, dollar, copper/gold over 3 months), each with the evidence used; an overall regime label. With a symbol: sector, beta to the S&P 500, and correlations of the stock's monthly returns with changes in the 10y yield, oil and the dollar over 5 years |
| `analyze_consumer_sentiment(symbol)` | UMich sentiment level, 1- and 12-month change and percentile since 1978; spending (retail sales, real consumption), savings rate, credit-card delinquency, unemployment; market view from XLY/XLP over 3 and 12 months; an overall consumer read. With a symbol: whether its sector is consumer-sensitive, and correlation of its monthly returns with sentiment changes and XLY/XLP |

Every result includes `as_of` dates per series and the rule thresholds used. Missing series give null
values, not failures. Without `FRED_API_KEY` the tools return a tool error explaining how to set it.

## Acceptance criteria
1. Unit tests for the signal rules, percentile, correlations and sector mapping with known inputs.
2. Tool tests with fake FRED and yfinance data, no network or key; missing-key error reaches an MCP client.
3. With a key: all three tools return live data with and without a symbol; the Macro agent answers a question.
