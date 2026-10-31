# Plan: Initial application

**Spec:** ./spec.md

## Files that change
- `pyproject.toml` — uv workspace root (backend + MCP servers), ruff and pytest config.
- `mcp_servers/<name>/` — one package per server (`etf`, `stocks`, `news`, `financials`, `backtest`,
  `event_study`), each `server.py` with one FastMCP tool; pure computation in `analytics.py` where it exists.
- `backend/src/alko_backend/`
  - `main.py` — FastAPI app and lifespan (starts MCP servers).
  - `mcp_pool.py` — stdio MCP client sessions, tool listing and calls.
  - `agents.py` — agent definitions and the Claude tool-use loop; advisor delegates via `ask_<agent>` tools.
  - `portfolios.py` — load seed holdings, valuation and analysis.
  - `routes.py` — REST endpoints.
- `backend/data/portfolios.json` — Brokerage and IRA seed holdings.
- `frontend/` — Vite + React + TypeScript; three views and a chat panel.
- `Makefile` — install, dev, build, test, lint.
- `CLAUDE.md` — real commands and architecture.

## Order of work
1. Workspace and MCP servers; unit tests for backtest and event-study math.
2. Backend: MCP pool, portfolios, agents, routes; tests with a fake MCP pool.
3. Frontend views and chat.
4. Makefile and CLAUDE.md.
5. End-to-end run against live data and the Claude API.

- `.claude/launch.json` — backend and frontend dev servers for the desktop app's browser preview.

## Risks
- yfinance response shapes change (notably news). Tools normalize defensively.
- *Found during build:* `Ticker.news` returns nothing, so the news server falls back to `yf.Search`, whose
  articles often only mention the ticker in passing. The tool returns `related_tickers` so agents can judge
  relevance; a better news source is a follow-up.
- Six stdio subprocesses per backend process; acceptable for a single-user dev app.

## Proof
- `make test`, `make lint`, `make build` output.
- Live run: health endpoint, portfolio and analysis endpoints, backtest and event study, one advisor chat and
  one focused-agent chat.
