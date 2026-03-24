# Copilot Coding Agent — Squad Instructions

You are working on a project that uses **Squad**, an AI team framework. When picking up issues autonomously, follow these guidelines.

## Quality Gates (MANDATORY)

**Before EVERY commit, you MUST run the verify script:**

```bash
.squad/scripts/verify.sh
```

This auto-detects which services you changed and runs lint + format + tests. **In normal setups, failing checks will cause the pre-commit hook to block your commit, but some missing-tool or missing-dependency cases may only produce warnings.**

Per-language quick reference:
- **Python** (document-indexer, document-lister, embeddings-server, solr-search, admin):
  - `ruff check src/{service}/` — lint
  - `ruff format --check src/{service}/` — format
  - `cd src/{service} && uv run pytest --tb=short -q` — test
  - Auto-fix: `ruff check --fix src/{service}/ && ruff format src/{service}/`
- **TypeScript** (aithena-ui):
  - `cd src/aithena-ui && npm run lint` — lint
  - `cd src/aithena-ui && npm run format:check` — format
  - `cd src/aithena-ui && npx vitest run` — test
  - Auto-fix: `npm run lint -- --fix && npm run format`

**Never use `git commit --no-verify`.** If checks fail, fix the code.

Read `.squad/quality-gates.md` for full details.

## Team Context

Before starting work on any issue:

1. Read `.squad/team.md` for the team roster, member roles, and your capability profile.
2. Read `.squad/routing.md` for work routing rules.
3. If the issue has a `squad:{member}` label, read that member's charter at `.squad/agents/{member}/charter.md` to understand their domain expertise and coding style — work in their voice.

## Capability Self-Check

Before starting work, check your capability profile in `.squad/team.md` under the **Coding Agent → Capabilities** section.

- **🟢 Good fit** — proceed autonomously.
- **🟡 Needs review** — proceed, but note in the PR description that a squad member should review.
- **🔴 Not suitable** — do NOT start work. Instead, comment on the issue:
  ```
  🤖 This issue doesn't match my capability profile (reason: {why}). Suggesting reassignment to a squad member.
  ```

## Branch Naming

Use the squad branch convention:
```
squad/{issue-number}-{kebab-case-slug}
```
Example: `squad/42-fix-login-validation`

## PR Guidelines

When opening a PR:
- Reference the issue: `Closes #{issue-number}`
- If the issue had a `squad:{member}` label, mention the member: `Working as {member} ({role})`
- If this is a 🟡 needs-review task, add to the PR description: `⚠️ This task was flagged as "needs review" — please have a squad member review before merging.`
- Follow any project conventions in `.squad/decisions.md`

## Decisions

If you make a decision that affects other team members, write it to:
```
.squad/decisions/inbox/copilot-{brief-slug}.md
```
The Scribe will merge it into the shared decisions file.
