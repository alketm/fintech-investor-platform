# Spec: Initial application

**Intent:** ./intent.md
**Status:** approved

## Behavior
**Portfolio view** — pick Brokerage or IRA; table of holdings (symbol, type, shares, cost basis, last price,
market value, gain/loss) and portfolio totals. Prices come from the Stocks MCP server.

**Portfolio analysis view** — for the selected portfolio: allocation by holding and by asset type (stock / ETF),
largest position weight, and unrealized gain/loss by position.

**Strategy view** — two forms:
- *Backtest*: buy-and-hold of a symbol between two dates → total return, CAGR, annualized volatility,
  max drawdown, final value of $10,000.
- *Event study*: symbol, event date, benchmark (default SPY) → market-model abnormal returns and cumulative
  abnormal return (CAR) over a ±N trading-day window.

**Chat** — a panel available on every view. The user picks an agent (Advisor or a focused agent). The current
view and selected portfolio are sent as context. Replies are plain text/markdown.

## Agents
| Agent | MCP servers | Role |
| --- | --- | --- |
| `advisor` | none directly; delegates to every focused agent | Main agent, knows the portfolios, synthesizes |
| `etf` | etf | ETF profiles |
| `stocks` | stocks | Quotes and company basics |
| `news` | news | Recent headlines |
| `financials` | financials | Financial statements |
| `backtest` | backtest | Strategy backtests |
| `event_study` | event_study | Event studies |

All agents use `claude-opus-5-5` with adaptive thinking, server-side refusal fallback, and an explicit
`effort` of `medium`.

## MCP servers (one simple tool each)
| Server | Tool | Input | Output |
| --- | --- | --- | --- |
| etf | `get_etf_profile` | symbol | name, category, expense ratio, total assets, yield, top holdings |
| stocks | `get_quote` | symbol | price, previous close, change %, currency, market cap |
| news | `get_news` | symbol, limit | list of {title, publisher, published, related_tickers, link} |
| financials | `get_income_statement` | symbol, period (annual/quarterly) | key income-statement lines per period |
| backtest | `backtest_buy_and_hold` | symbol, start, end, initial_capital | stats listed above |
| event_study | `run_event_study` | symbol, event_date, benchmark, window | alpha, beta, AR/CAR series, CAR |

Servers run over stdio and are started by the backend.

## Data and interfaces
- Holdings: `backend/data/portfolios.json` (seed data, edited by hand).
- REST API (backend, port 8000):
  - `GET /api/health`
  - `GET /api/portfolios` → list of {id, name}
  - `GET /api/portfolios/{id}` → holdings with prices and totals
  - `GET /api/portfolios/{id}/analysis` → allocation and concentration
  - `POST /api/strategy/backtest`, `POST /api/strategy/event-study` → MCP tool output
  - `GET /api/agents` → list of agents
  - `POST /api/chat` {agent, messages[{role, content}], context{view, portfolio_id}} → {reply}
- Frontend (Vite, port 5173) proxies `/api` to the backend.

## Security and compliance
- `ANTHROPIC_API_KEY` read from the environment only; never committed.
- Agents present analysis with its assumptions and limits; they never claim certainty about future returns and
  never place trades.
- No user data leaves the machine except calls to the Claude API and the market-data source.

## Acceptance criteria
1. `make test` and `make lint` pass.
2. Backend starts and `GET /api/health` reports all six MCP servers connected with their tools.
3. Portfolio view shows both portfolios with live prices.
4. Analysis view shows allocation that sums to 100%.
5. Strategy view returns backtest stats and event-study CAR for a real symbol.
6. Chat returns a reply from the advisor and from at least one focused agent.

## Concerns routed to owners
| Concern | Owner | Resolution |
| --- | --- | --- |
| yfinance is unofficial and rate-limited | alketm | Accept for development; revisit before wider use |
