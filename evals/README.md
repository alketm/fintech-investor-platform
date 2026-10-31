# Evals

Real tasks that check Claude still behaves after changes to `CLAUDE.md` or `.claude/**`.
Aim for 20–50 drawn from recent work. Each production incident gets an eval.

One JSON file per eval:

```json
{
  "id": "short-slug",
  "prompt": "The task as it was given to Claude",
  "checks": ["tests pass", "lint clean", "behavior unchanged", "policy followed"]
}
```

A `check.sh` grader and a CI workflow (`.github/workflows/agent-evals.yml`, run on PRs touching
`CLAUDE.md` or `.claude/**` and nightly) get added once the tech stack and first evals exist.
