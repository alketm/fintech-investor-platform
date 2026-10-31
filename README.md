# Alko Investment Advisor

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
| `.github/` | Code owners and PR template |

## Lifecycle
Plan (`intent.md`) → Design (`spec.md`) → Build (`plan.md`, code on a branch) → Test → PR review → merge to `main`.
Each stage ends with a commit, so git history is the audit trail.

## Local setup
After cloning, enable the repo's git hooks (blocks direct commits on `main`):

```bash
git config core.hooksPath .githooks
```
