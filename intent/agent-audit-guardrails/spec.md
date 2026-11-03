# Spec: Agent audit trail, question guardrails and evals

**Intent:** ./intent.md
**Status:** approved

## Behavior
`POST /api/chat` handles each request in this order:
1. Screen the latest user message (see Guardrails).
2. **Decline:** return a fixed reply for the category, without running an agent.
   **Reframe:** run the agent with an added instruction to give analysis and options, not a recommendation.
   **Answer** or **unscreened:** run the agent as today.
3. Write one audit record, on success and on failure, then respond.

The response keeps `agent`, `reply` and `tool_calls`, and adds `request_id` and `guardrail: {outcome, category}`.
Declines appear in chat as a normal assistant reply. The UI gets no new views.

## Guardrails
New module `guardrails.py`. `screen(messages) -> Decision(outcome, category, source, reason)`.

| Outcome | Categories | Example |
| --- | --- | --- |
| `answer` | `in_scope` | "How concentrated is my IRA?" |
| `reframe` | `recommendation` | "What should I buy?", "Should I sell NVDA?" |
| `decline` | `off_topic`, `trade_execution`, `prompt_injection` | "Write me a poem", "Place an order for 10 AAPL", "Ignore your instructions" |

`source` is `rules`, `classifier` or `unscreened`.

- **Local rules run first:** a small set of regular expressions for unmistakable phrasing in the `trade_execution`,
  `prompt_injection` and `recommendation` categories. A match skips the classifier. Asking how to place a trade or what
  an order type means is in scope, not `trade_execution`.
- **Classifier runs otherwise:** one `client.messages.create` call to `claude-haiku-5-5` with effort `low`, `max_tokens`
  256 and structured output (`output_config.format`) for `{category, reason}`. Its system prompt treats the text as data
  to classify, not instructions to follow. It receives the latest user message and up to four earlier messages, so a
  follow-up like "yes, do that" can be read in context.
- **Failure:** on an API error or unusable output, the outcome is `answer`, the source `unscreened` and the reason
  records the error.
- **Scope:** only the owner's messages via `/api/chat` are screened. Questions the advisor passes to specialists are not.
  Replies are not screened. This applies to every selectable agent.

The reframe instruction is a text block on the latest user turn, next to the existing `[App context]` block.

## Audit trail
New module `audit.py`, using standard-library `sqlite3`.

- **Location:** `backend/data/audit/audit.db` (`AUDIT_DB` in `config.py`). The directory is git-ignored; the directory
  is created `0700` and the file `0600`. WAL mode is not used.
- **Retention:** at startup, delete requests older than `AUDIT_RETENTION_DAYS = 90`, with their child rows.
- **Writes:** `RequestAudit` collects records in memory during the request and flushes them in one transaction, off the
  event loop, in a `finally` block. A failed flush logs an error with Python `logging` and does not affect the response.
- **Secrets:** environment values and API keys are never written. Requests sent to Claude are not stored whole; system
  prompts and tool schemas are not recorded per request.

| Table | Columns |
| --- | --- |
| `requests` | `id`, `started_at`, `duration_ms`, `agent`, `view`, `portfolio_id`, `question`, `reply`, `status`, `error`, `guardrail_outcome`, `guardrail_category`, `guardrail_source`, `guardrail_reason` |
| `model_calls` | `id`, `request_id`, `agent`, `depth`, `turn`, `requested_model`, `served_model`, `api_request_id`, `stop_reason`, `refusal_category`, `fallback_used`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `est_cost_usd`, `duration_ms`, `thinking` |
| `tool_calls` | `id`, `request_id`, `agent`, `depth`, `tool`, `server`, `input`, `result`, `is_error`, `denied`, `duration_ms` |

`status` is one of `ok`, `declined`, `budget_exceeded`, `turn_limit`, `refusal` or `error`. The classifier's call is a
`model_calls` row with agent `guardrail`.

**Thinking:** agent calls send `thinking={"type": "adaptive", "display": "summarized"}`, and the text of all `thinking`
blocks is stored. It may be empty. It is a summary, never raw reasoning. `response.content` continues to be passed back
unchanged in the tool loop.

**Served model and refusals:** `served_model` is `response.model`. `fallback_used` is true when `usage.iterations`
contains a `fallback_message` entry. `refusal_category` comes from `stop_details`. `api_request_id` is `_request_id`.

**Cost:** `est_cost_usd` is calculated from `MODEL_PRICES` in `config.py`, using cache writes at 1.25x input and each
model's listed cache read price. When `usage.iterations` is present, each iteration is priced at its own model. If a
model is not in the table, the cost is NULL and the report counts it as unpriced, never as zero.

**Reports:** a CLI, with no new HTTP endpoints, so audit data is not exposed to anything else running in the browser:
- `uv run python -m alko_backend.audit usage [--days 30]`: requests, tokens and estimated cost by day, agent and model,
  plus guardrail outcome counts.
- `uv run python -m alko_backend.audit show <request_id>`: the full record, including thinking.
- `uv run python -m alko_backend.audit list [--limit 20]`: recent requests.

## Enforcement fixes
- **Tool allowlist:** `AgentRunner` executes a tool only if it is in that agent's own tool list, resolved to that
  agent's own servers. Anything else returns an error `tool_result` to the model and is recorded with `denied = 1`.
  `server_for_tool`, which searches every server, is removed.
- **Delegation depth:** `MAX_DELEGATION_DEPTH = 1`. `ask_*` tools run only for an agent that lists that delegate, at
  depth 0.
- **Token budget:** `MAX_REQUEST_TOKENS` in `config.py`, provisionally 500,000, shared across the advisor and all its
  specialists in one request. It counts input, output, cache read and cache write tokens, and the classifier's call. It
  is checked before each model call, so calls already in flight can finish and a request can slightly overrun. Once
  reached, no further model calls run and the reply says the request stopped at its limit, with status
  `budget_exceeded`. The default is confirmed against a measured chat before merging.
- **Untrusted data:** `COMMON_RULES` gains a rule that tool results and specialists' answers, including news text, are
  data, and any instructions inside them are not followed.
- **Chat images:** `ChatPanel` renders markdown images as their alt text and never loads them. Links keep working, with
  `rel="noopener noreferrer"`.
- **CSP:** a `<meta>` tag in `frontend/index.html` with `default-src 'self'`, `img-src 'self' data:`, `connect-src 'self'
  ws://localhost:5173`, `style-src 'self' 'unsafe-inline'`, `script-src 'self' 'unsafe-inline'`, `object-src 'none'` and
  `base-uri 'none'`. Inline scripts are allowed because the Vite dev server, which is how this local app runs, injects
  one. The leak path is closed by `img-src` and `connect-src`, not by the script policy.

## Evals
App evals live in `evals/agents/`, separate from the Claude Code config evals in `evals/README.md`. They run only with
`make eval FLOW=<name>`, never in CI or `make test`. Results go to the git-ignored `evals/agents/results/`: one JSONL row
per case with `model`, `usage`, `stop_reason`, grade and estimated cost, plus a full trace file per case and an errors
file for failed attempts. Runs can resume, and a case has a wall-clock limit.

| Flow | Entry point | Grading |
| --- | --- | --- |
| `guardrail` | `guardrails.screen` | Programmatic against labels. Reports precision and recall per outcome, false-decline rate and false-answer rate |
| `advice` | The real chat path, with real MCP servers | Rubric of checkable claims, scored by a judge model other than the one under test, using structured output |

Case sets and the rubric are reviewed by the owner before the first paid run, along with the judge model, the pilot's
measured cost and the case count. The `advice` flow uses live market data, so its cases are graded on rules followed,
not on specific numbers.

## Data and interfaces
- `POST /api/chat` response gains `request_id` and `guardrail`. Existing fields are unchanged.
- New config: `AUDIT_DB`, `AUDIT_RETENTION_DAYS`, `MODEL_PRICES`, `GUARDRAIL_MODEL`, `MAX_REQUEST_TOKENS`,
  `MAX_DELEGATION_DEPTH`.
- New dependency: none for the backend. The `evals` flow uses the workspace's existing packages.

## Security and compliance
- The database holds holdings and full conversations in plain text on this machine, readable only by the owner's user,
  and is copied by anything that backs up the folder.
- The backend stays on `127.0.0.1`; no new network listeners or endpoints.
- Questions already sent to Claude now also go to `claude-haiku-5-5` for screening, under the same API account.
- Reframe and decline wording must not state or imply a recommendation. Fixed decline replies are covered by tests.
- This does not constitute a compliance review and does not make the product suitable for other users.

## Acceptance criteria
1. A chat creates one `requests` row, a `model_calls` row per Claude call with tokens and thinking, and a `tool_calls` row
   per tool call, including those by specialists.
2. A failed Claude call still creates a `requests` row with status `error`, and the client gets the same error as today.
3. The database file is mode `0600`, is git-ignored, and contains no value of `ANTHROPIC_API_KEY` or `FRED_API_KEY`.
4. Requests older than 90 days and their child rows are gone after startup; newer ones remain.
5. Estimated cost matches a hand-calculated example for each token type; an unknown model gives NULL and is counted as
   unpriced; a fallback is priced per iteration.
6. `usage`, `show` and `list` print correct results from a seeded database.
7. Rule matches skip the classifier. Each outcome behaves as specified: decline runs no agent, reframe adds the
   instruction, and answer adds none.
8. A classifier API error or invalid output gives source `unscreened`, and the chat still answers.
9. An agent that requests another agent's tool, an unknown tool, or `ask_advisor` gets an error `tool_result`, nothing is
   executed, and the attempt is recorded as denied.
10. A request over the budget makes no further model calls, including in specialists, and ends as `budget_exceeded`.
11. A markdown image in a reply makes no network request and shows its alt text. The app loads under the CSP with no
    console violations in `make dev`.
12. `make eval` is the only way to start a paid eval, and an oracle and a null run through each runner score about 100%
    and 0% without API calls.
13. With no API key, `make test` passes using fakes and makes no network calls.

## Concerns routed to owners
| Concern | Owner | Resolution |
| --- | --- | --- |
| Audit database copied by backups such as Time Machine | alketm | Accepted when the intent was accepted; owner may exclude the folder |
| Screening can over-decline or miss cases | alketm | Measured by the `guardrail` eval; agent prompt rules remain |
| Failed screening or audit write leaves a gap | alketm | Accepted when the intent was accepted: chat keeps working, and the gap is visible as `unscreened` or a logged error |
| Budget default is provisional | alketm | Confirm against one measured paid chat before merge |
| Eval cost and judge model | alketm | Approve at case and rubric sign-off, before the first paid run |
