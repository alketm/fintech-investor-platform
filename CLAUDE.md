# Alko Investment Advisor

Keep this file under a page. When Claude makes the same mistake twice, the correction goes here.
Changes to this file are reviewed like code.

## Commands
Python 3.12 via uv, Node via npm; both live in `~/.local/bin` (the Makefile adds it to PATH).
- `make install` — `uv sync --all-packages` + `npm install`
- `make dev` — backend on :8000 and UI on :5173. Needs `ANTHROPIC_API_KEY` for chat.
- `make test` — pytest then vitest. Healthy: `60 passed` and `Tests  4 passed`. Exits non-zero on failure.
- `make lint` — ruff check, ruff format --check, oxlint, `tsc -b`. Healthy: `All checks passed!`, no tsc output.
- `make build` — frontend bundle. Healthy: `✓ built in …`
- Health check with backend running: `curl localhost:8000/api/health` lists six MCP servers and their tools.

## Workflow
Every feature moves through `intent/<feature>/`:
1. `intent.md` — problem, outcome, affected users/systems, constraints, open questions. Product owner accepts it.
2. `spec.md` — written from the accepted intent; committed alongside it.
3. `plan.md` — produced in plan mode before any code is edited. If implementation departs from the plan, update `plan.md` in the same commit.

- Work on a branch, never on `main`. Changes reach `main` only through a reviewed PR.
- Parallel tasks each get their own worktree (`claude --worktree <name>`).
- Bug fixes: write a failing test, confirm it fails for the expected reason, commit it, then fix the code without editing the test.

## Verification
Run build, test and lint before reporting any task complete, and paste the output.
If a test fails, fix the code, not the test. Never skip or delete a failing test.

## Conventions
- Never commit secrets, API keys or `.env` files.
- Never edit generated code (`src/gen/` once it exists).
- Domain: this product deals with investment information. Anything user-facing that could read as financial advice
  must follow the compliance rules in the relevant `spec.md`; flag it in review if unsure.

## Architecture
- `frontend/` — Vite + React + TS. Views: `src/views/` (Portfolio, Analysis, Strategy); chat in `src/components/ChatPanel.tsx`.
- `backend/` — FastAPI (`alko_backend.main`). Starts every MCP server over stdio at startup (`mcp_pool.py`).
  Agents in `agents.py`: `advisor` only delegates (`ask_<agent>` tools); each focused agent only sees its own
  MCP server's tools. Holdings seed: `backend/data/portfolios.json`.
- `mcp_servers/<name>/` — one uv package per data domain; tools in `server.py`, pure math in `analytics.py`.
  Market data only comes from here (yfinance), never directly from the backend.
- Adding an MCP server: new package, add to `MCP_SERVERS` in `backend/src/alko_backend/config.py` and to
  `backend/pyproject.toml`, then give a focused agent its name in `servers`.

## Things Claude gets wrong
- `mcp` is 2.x: the server class is `MCPServer` from `mcp.server.mcpserver` (not FastMCP); types are snake_case
  (`input_schema`, `structured_content`). Raise `ToolError` (`mcp.server.mcpserver.exceptions`) for expected
  tool failures: any other exception reaches the caller only as "Error executing tool <name>".
- Claude model is `claude-opus-5-5`: thinking can't be disabled and forced `tool_choice` is rejected; tune `effort`.
- MCP server test dirs have no `__init__.py`; give shared test helpers a unique module name
  (e.g. `financials_fixtures.py`) or pytest's `tests` packages collide.
- yfinance `Ticker.news` is often empty; the news server falls back to `yf.Search`.
