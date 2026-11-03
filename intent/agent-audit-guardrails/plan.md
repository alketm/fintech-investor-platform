# Plan: Agent audit trail, question guardrails and evals

**Spec:** ./spec.md (`intent/agent-audit-guardrails/`, branch `feat/agent-audit-guardrails`)

## Context
The agents leave no record of what was asked, answered, reasoned or spent. Advice rules exist only as prompt text and
nothing measures them, while isolation and spending limits are unenforced. The owner accepted the intent: keep the app
local, add an audit trail with token cost and thinking summaries, screen questions with rules then Haiku, add on-demand
evals, and include the enforcement fixes. Approving this plan also approves the spec (status moves to `approved`), and
this plan is committed as `plan.md`.

## Files that change
**Backend (`backend/src/alko_backend/`)**
- `config.py`: `AUDIT_DB`, `AUDIT_RETENTION_DAYS`, `MODEL_PRICES`, `GUARDRAIL_MODEL`, `MAX_REQUEST_TOKENS`,
  `MAX_DELEGATION_DEPTH`.
- `audit.py` (new): schema, `AuditStore` (init with file modes, retention purge, one-transaction flush off the event
  loop), `RequestAudit` collector, `estimate_cost`, and the `usage` / `show` / `list` CLI.
- `guardrails.py` (new): `Decision`, local rules, Haiku classifier using structured output, fixed decline replies,
  reframe instruction, and the `unscreened` fallback.
- `agents.py`:
  - Add the `RequestAudit` collector, which also holds the shared token count, as an optional `run()` argument, so
    existing callers and tests still work.
  - Build a per-agent `{tool: server}` allowlist from `tools_for`, deny everything else, and remove `server_for_tool`
    (also from `mcp_pool.py`, the `ToolPool` protocol and `FakePool`).
  - Enforce delegation depth and check the budget before each model call.
  - Send `thinking={"type": "adaptive", "display": "summarized"}`, and record usage, thinking, served model, refusals
    and tool timings. `AgentResult` gains a `status`.
  - Add the untrusted-data rule to `COMMON_RULES`.
- `main.py`: create the audit store in `lifespan`, and change `chat` to screen, then decline, reframe or run, and flush
  the audit record in `finally`. Error responses stay as they are; the response gains `request_id` and `guardrail`.
- `eval_runner.py` (new): loads `evals/agents/` cases, runs the `guardrail` and `advice` flows through the real entry
  points, writes `results.jsonl`, traces and `errors.jsonl`, and supports resume and a per-case time limit. Living in
  the package makes it importable from tests. The spec's Evals section gets a note saying so.

**Frontend**
- `frontend/src/components/ChatPanel.tsx`: render images as alt text, with `rel="noopener noreferrer"` on links.
- `frontend/index.html`: CSP meta tag.
- `frontend/src/api.ts`: add the new optional response fields.

**Evals and project files**
- `evals/agents/guardrail_cases.json`, `advice_cases.json`, `advice_rubric.json` (new, drafts for owner review). The
  rubric is JSON because the runner builds the judge's output schema from it.
- `Makefile`: `eval` target requiring `FLOW=`. `.gitignore`: `backend/data/audit/`, `evals/agents/results/`.
- `CLAUDE.md`: audit and guardrail architecture, eval command, new healthy test counts. `README.md`: audit CLI and where
  the data lives.

**Tests**
- `backend/tests/test_audit.py`, `test_guardrails.py`, `test_eval_runner.py` (new); `test_agents.py`, `test_api.py`
  (additions); `conftest.py` (`FakeClaude` gains `usage`, `model`, `_request_id`, `stop_details` and a scripted
  `messages.create` for the classifier, defaulting to `in_scope`); `ChatPanel.test.tsx` (image rendering).

## Order of work
1. `audit.py` and pricing, with tests.
2. Agent loop: context, allowlist, depth, budget, thinking and usage capture, with tests.
3. `guardrails.py`, with tests.
4. Wire up `main.py`; API tests cover acceptance criteria 1, 2, 7, 8 and 10.
5. Frontend image handling and CSP, with tests, then check in the browser under `make dev`.
6. Eval runner and draft cases, tested with oracle and null runs and no API calls.
7. Docs, then full `make lint`, `make test`, `make build`.
8. **Stop for owner sign-off before anything paid:**
   - one measured chat to confirm `MAX_REQUEST_TOKENS`;
   - eval cases, rubric, judge model (proposed `claude-sonnet-5-5`), then a small pilot with its measured cost;
   - the full baseline run only after that.

Commits go on the feature branch at logical points, and the work reaches `main` through a PR.

## Risks
- **Usage accounting on fallbacks:** settled from the API docs: `usage.iterations` is the per-attempt source of truth
  and top-level `usage` covers only the returned attempt, so totals sum the iterations when present. Attempts declined
  before any output may not be billed, so costs on those calls can read slightly high.
- **Thinking summaries** may be empty on some calls, so they're stored as-is. They also add to the audit database's size.
- **Summaries in the tool loop:** the display change must not alter how `response.content` is passed back. Covered by a
  test on the second request's messages.
- **Rules can over-match:** they're kept deliberately narrow, with `guardrail` eval cases for near-misses such as "how
  do limit orders work?".
- **False declines annoy; missed ones are low-harm:** reframe is preferred when it's unclear. The eval reports both rates.
- **CSP in dev:** Vite needs inline scripts and websocket access, which the spec allows. Checked in the browser, not
  just in tests. jsdom doesn't enforce CSP, so tests can't catch this.
- **Parallel specialists can overrun the budget** by whatever is already in flight. The spec accepts this.
- **Existing test `test_chat_adds_app_context`** indexes the content blocks, and must keep passing as written. An
  existing test will only be changed if the spec requires it, and any such change will be called out.
- **PR #2 overlap:** a small likely conflict in `CLAUDE.md` when both merge.

## Proof
- `make test` (no API key or network, backed by fakes), `make lint`, `make build`, with output pasted in the PR.
- Each of the 13 acceptance criteria maps to a named test, or to the browser check for criterion 11.
- `git check-ignore` confirms the database and results are ignored; a test confirms mode `0600` and no key values in the
  database.
- Browser preview under `make dev`: no CSP violations in the console, and a reply containing a markdown image makes no
  network request. Runs against a stubbed reply if no paid call has been approved yet.
- After sign-off: one real chat, inspected with `audit show`, confirming tokens, thinking and served model are present
  and non-zero; the `verifier` agent checks the spec's criteria; CI passes on the PR.
