# Tools live in ~/.local/bin (uv, node) when installed per-user.
export PATH := $(HOME)/.local/bin:$(PATH)

.PHONY: install dev backend frontend build test lint format eval

install:  ## Install Python (uv workspace) and frontend dependencies
	uv sync --all-packages
	cd frontend && npm install

backend:  ## API server on :8000 (starts the nine MCP servers)
	uv run uvicorn alko_backend.main:app --port 8000 --reload --reload-dir backend/src

frontend:  ## UI dev server on :5173, proxies /api to :8000
	cd frontend && npm run dev

dev:  ## Backend and frontend together
	$(MAKE) -j2 backend frontend

build:  ## Type-check and bundle the frontend
	cd frontend && npm run build

test:  ## All tests; exits non-zero on failure
	uv run pytest -q
	cd frontend && npm test

lint:  ## Ruff + oxlint + TypeScript type check
	uv run ruff check .
	uv run ruff format --check .
	cd frontend && npm run lint && npm run typecheck

format:
	uv run ruff check --fix .
	uv run ruff format .

eval:  ## Paid API calls: make eval FLOW=guardrail|advice [ARGS="--limit 5"]. Never run by test or CI.
	@test -n "$(FLOW)" || (echo "Set FLOW=guardrail or FLOW=advice" >&2; exit 2)
	uv run python -m alko_backend.eval_runner --flow $(FLOW) $(ARGS)
