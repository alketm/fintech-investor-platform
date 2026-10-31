# Alko Investment Advisor

Keep this file under a page. When Claude makes the same mistake twice, the correction goes here.
Changes to this file are reviewed like code.

## Commands
Tech stack not chosen yet. When it is, list each command with an example of healthy output:
- `make build` — TODO
- `make test` — TODO (must exit non-zero on failure)
- `make lint` — TODO

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
TODO once the stack exists — one line per top-level directory.

## Things Claude gets wrong
(Add entries as they come up.)
