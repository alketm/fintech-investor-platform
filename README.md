# FinTech Co - Investor Platform

Project scaffolding follows the AI-native SDLC playbook
(<https://claude.com/resources/articles/the-ai-native-sdlc-playbook>).

| Path | Purpose |
| --- | --- |
| `CLAUDE.md` | Shared context for Claude: commands, conventions, verification rules |
| `REVIEW.md` | Policy for AI code review on PRs |
| `intent/` | One folder per feature holding `intent.md` → `spec.md` → `plan.md` |
| `.claude/settings.json` | Team hooks and permissions (committed) |
| `.claude/hooks/` | Hook scripts referenced from settings |
| `.claude/agents/` | Subagent definitions (e.g. `verifier.md`) |
| `.claude/skills/` | Project skills, one folder per skill with a `SKILL.md` |
| `evals/` | Real tasks used to check Claude's config still behaves, one JSON file each |
| `docs/lessons.md` | Post-mortem lessons |
| `.github/` | Code owners, PR template and CI workflow |
| `frontend/` | Browser UI (Vite + React) |
| `backend/` | API server and agents (FastAPI) |
| `mcp_servers/` | One MCP server per data domain, each named `mcp_<domain>` |

## Lifecycle
Plan (`intent.md`) → Design (`spec.md`) → Build (`plan.md`, code on a branch) → Test → PR review → merge to `main`.
Each stage ends with a commit, so git history is the audit trail.

## Run it
```bash
make install
export ANTHROPIC_API_KEY=...   # for chat
export FRED_API_KEY=...        # for mcp_macro and mcp_backtest (free: fred.stlouisfed.org/docs/api/api_key.html)
make dev                       # UI at http://localhost:5173
```

Instead of exporting, you can put `KEY=value` lines in a `.env` file at the project root (git-ignored).

## Audit trail
Each chat is recorded in `backend/data/audit/audit.db`: questions, replies, tool calls, thinking summaries, tokens and
estimated cost. The file is git-ignored, readable only by your user, and requests older than 90 days are removed and
overwritten at startup. It's plain text on this machine and contains your holdings, so backups of this folder will copy it.

```bash
uv run python -m alko_backend.audit usage --days 30
uv run python -m alko_backend.audit list
uv run python -m alko_backend.audit show <request_id>
```

## Evals
`make eval FLOW=guardrail` or `make eval FLOW=advice` runs the cases in `evals/agents/` against the real API, which
costs money. Add `ARGS="--limit 5"` for a small pilot. Results go to the git-ignored `evals/agents/results/`.

## Local setup
After cloning, enable the repo's git hooks (blocks direct commits on `main`):

```bash
git config core.hooksPath .githooks
```
