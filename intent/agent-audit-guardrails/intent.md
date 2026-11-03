# Intent: Agent audit trail, question guardrails and evals

**Status:** accepted
**Owner:** alketm

## Problem
The agents run with no record of what they did. There is no way to see what was asked, what an agent answered, which
tools it used, how it reasoned, which model served it or what it cost. The advice rules exist only as prompt text, and
nothing measures whether they hold. Agent isolation is shown to the model but not enforced, one chat message has no
spending limit, and news text can reach the model and chat UI without being treated as untrusted.

## Proposed outcome
- **Audit trail:** every chat request records the question, reply, each model call, each tool call, the agent that
  made it, thinking summaries, stop reason, refusals and the model that actually served it.
- **Token consumption:** input, output and cache tokens with estimated cost, per model call, per request and over time.
- **Question guardrails:** every question is screened by local rules, then `claude-haiku-5-5`, and gets one outcome:
  - answer normally when in scope;
  - reframe requests for a recommendation ("what should I buy?") into analysis and options for the owner to decide;
  - decline off-topic requests, requests to place trades, and prompt-injection attempts.
- **Evals:** a repeatable suite that runs through the real chat entry point and measures guardrail classification and
  whether agent replies follow the advice rules.
- **Enforcement fixes:** agents can only run their own tools, delegation cannot recurse, each request has a token
  budget, tool and news content is treated as data, and chat blocks remote images with a CSP in place.

## Affected users and systems
- Single user (the owner), local only.
- `backend/` (agent loop, chat endpoint, config, new audit and guardrail modules, tests), `frontend/` (chat rendering,
  `index.html`), `evals/`, `.gitignore`.
- MCP servers are unchanged.

## Constraints
- **Local only:** the backend stays bound to `127.0.0.1`. No auth, hosted storage or telemetry backend.
- **Audit data stays on this machine:** a git-ignored SQLite database, purged after 90 days at startup. It holds full
  question, reply and thinking text, including holdings, unencrypted. It never holds API keys.
- **Thinking is summaries only:** the API never returns raw reasoning. Requesting summaries does not change billing.
- **Costs are estimates:** calculated from a local price table, not taken from Anthropic billing.
- **Evals cost money:** they run on demand with an explicit command, not in CI or `make test`. Eval cases and grading
  need the owner's sign-off before the first paid run. Automated tests keep using the fake Claude client.
- **Compliance:** the guardrail supports the existing rule that agents give analysis and options and never place
  trades. It does not make the product suitable for other users, and is not a legal or regulatory review.
- **Screening limits:** the screen covers the question only and can be wrong. Agent prompt rules stay in place.

## Open questions
- Budget size per request: proposed in the spec from a measured chat, adjustable in `config.py`.
- If Haiku screening fails (API error): proposed to answer anyway and record the question as `unscreened`, since local
  rules and agent prompt rules still apply. A failed audit write likewise logs an error and does not block the chat.
