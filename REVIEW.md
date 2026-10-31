# Review policy

Used by AI review on every PR. Findings do not approve or block a PR on their own;
branch protection still requires approval from a code owner.

## Passes
1. **Bugs** — logic errors, broken edge cases, regressions.
2. **Security** — secrets in the diff, injection, authz gaps, unsafe handling of user financial data.
3. **Compliance** — the change matches its `intent/<feature>/spec.md` and `plan.md`; user-facing content
   respects the product's financial-advice and disclosure rules; `CLAUDE.md` is still accurate.

## Severity
- **Important** — reserve for findings that would break behavior, leak data or breach a policy.
- **Nit** — everything else. Report at most five nits per review; summarize the rest as a count.

## Exclusions
- Generated code (`src/gen/`).
- Anything CI already enforces (formatting, lint).
