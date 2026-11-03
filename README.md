# FinTech Co - Investor Platform

A private, local workspace for understanding your own investment portfolios. See your brokerage and IRA holdings in one
place, test strategy ideas against history, and ask AI analysts questions grounded in live market data.

It runs on your own machine for a single user, and covers US stocks and ETFs. It gives analysis and options for you to
decide on: it can't place trades or act on your accounts, and it isn't financial advice.

## What you can do
- **Portfolio:** see each account's holdings, value and unrealized gains at current prices.
- **Analysis:** see allocation by holding and asset type, your largest position, and gains by position.
- **Strategies:** test ideas against historical data.
  - **Backtests:** buy and hold, plus long-short moving-average crossover, time-series momentum, RSI mean reversion,
    Monetary Policy Uncertainty, consumer sentiment and VIX versus realized volatility strategies.
  - **Event studies:** how a stock reacted around a chosen date, earnings announcements, its own large moves and
    high-yield credit spread spikes.
- **Ask an agent:** chat from any view with the investment advisor, which draws on the specialists and combines their
  answers, or go straight to one specialist:

| Specialist | Covers |
| --- | --- |
| ETF | Costs, holdings, overlap, sector exposure, performance and risk |
| Stock | Current prices and market data |
| News | Recent headlines and sell-side analyst ratings |
| Financial statements | Growth, profitability, financial health, efficiency and valuation |
| Backtest | Strategy results compared with buy and hold |
| Event study | Abnormal returns around events, and their significance |
| Institutional ownership | Largest holders, and insider and institutional buying or selling |
| Macro | Growth, inflation, policy, market stress and consumer health |
| Market | Market and sector moves, daily movers, and a stock's technicals |

## Guardrails
- **Questions are screened:** requests for a recommendation get analysis and options instead. Off-topic questions,
  requests to place trades and attempts to override the agents' rules are declined.
- **Agents are limited:** each specialist can only use its own data tools, and each chat has a token budget.
- **Chats are on record:** each chat is logged locally, including tools used, thinking summaries, tokens and estimated
  cost.

Screening can make mistakes, and results depend on third-party data that can be late or wrong. Backtests are simulations
of the past with stated limits, not forecasts.

## Get started
You'll need [uv](https://docs.astral.sh/uv/) with Python 3.12, Node with npm, an
[Anthropic API key](https://console.anthropic.com/) for chat, and a free
[FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) for the macro data and the strategies that use it.

```bash
make install
```

```bash
export ANTHROPIC_API_KEY=...
```

```bash
export FRED_API_KEY=...
```

```bash
make dev
```

Then open <http://localhost:5173>. Instead of exporting the keys, you can put `KEY=value` lines in a git-ignored `.env`
file at the project root.

**Your holdings:** edit `backend/data/portfolios.json` with your own positions. The app reads this file and doesn't
connect to your broker. It's tracked in git, so keep the repo private if you enter real positions.

## Your data
- **What leaves your machine:** chat questions and your holdings go to the Claude API, and ticker symbols go to the
  market data sources (yfinance and FRED).
- **Audit log:** chats are stored in `backend/data/audit/audit.db`. The file is git-ignored and readable only by your
  user, and requests older than 90 days are removed and overwritten at startup. It isn't encrypted, it contains your
  holdings, and backups of this folder will copy it.

```bash
uv run python -m alko_backend.audit usage --days 30
```

```bash
uv run python -m alko_backend.audit list
```

```bash
uv run python -m alko_backend.audit show <request_id>
```

Costs in these reports are estimates from a local price table, not your Anthropic bill.

## How it's built
| Path | What it is |
| --- | --- |
| `frontend/` | Browser UI (Vite, React and TypeScript) |
| `backend/` | API server, agents, guardrails and audit log (FastAPI, Claude API) |
| `mcp_servers/` | One MCP server per data domain, the only place market data comes from |
| `evals/agents/` | Test cases that measure the guardrails and agent replies |

## Contributing
Contributors should start with [CLAUDE.md](CLAUDE.md), which covers the commands, workflow and conventions. After
cloning, enable the repo's git hooks:

```bash
git config core.hooksPath .githooks
```

`make test`, `make lint` and `make build` run the checks. `make eval FLOW=guardrail` or `make eval FLOW=advice` measures
agent behaviour against the real API, which costs money, so add `ARGS="--limit 5"` for a small pilot.

## License
[Apache 2.0](LICENSE)
