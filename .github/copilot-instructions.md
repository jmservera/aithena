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

## Workflow Tips

These tips capture patterns that have proven effective when working in this repo. Apply them to keep merge sweeps fast and review cycles short.

1. **Don't poll CI with `sleep N && gh run view` loops.** Use `gh pr checks <PR> --watch --interval 30` — it streams check status and exits when done. For long waits, run the watcher in a detached background shell so completion arrives as a notification instead of burning context on sleeps.

2. **Use `npx @bradygaster/squad-cli watch` for persistent assignment polling.** When the heartbeat workflow is unreliable or you're away from the terminal, `npx @bradygaster/squad-cli watch --interval 60` keeps picking up assigned issues/PRs. See `.github/agents/squad.agent.md` → "Watch Mode (`squad watch`)" for the full reference.

3. **Enable `SQUAD_WORKTREES=1` for parallel agent work.** When spawning multiple agents (e.g., dependabot batch + PR review fixes in parallel), worktree mode avoids branch-stomping in the main checkout. If you need a worktree manually, follow the convention in `.copilot/skills/git-workflow/SKILL.md` — sibling directories from `origin/dev`, e.g. `git worktree add ../aithena-<issue> -b squad/<issue>-<slug> origin/dev`.

4. **Run a critique pass before pushing review-comment fixes.** Bot review iteration cycles cost ≈40 min per round-trip (rebase + CI). A 30-second self-critique pass before each push typically catches the majority of issues a bot reviewer would flag, collapsing 3–4 rounds into 1–2. Agents running the Copilot CLI can invoke the built-in `rubber-duck` sub-agent via the `task` tool for the same effect.

5. **Remember: squash-merge does NOT auto-close referenced PRs.** After merging a batched PR that supersedes others, manually run `gh pr close <N> --comment "Superseded by #<batch>" --delete-branch` for each. This is a recurring gotcha during dependabot sweeps.

6. **Resolve review threads via GraphQL `resolveReviewThread`.** Branch protection requires threads resolved before merge. Iterate over `pullRequest.reviewThreads.nodes` and call the mutation per thread ID — `gh pr review` alone does not resolve them.

7. **Standard merge runbook for stacked / batched PRs**: resolve review threads → confirm required checks have passed → `gh pr merge <N> --admin --merge` (or `--squash`) → close superseded PRs → delete branches. **Do not rebase each follow-up PR onto the freshly updated base just to re-trigger CI** when the changes are independent — see `.copilot/skills/branch-protection-strict-mode/SKILL.md` for the `--admin` bypass pattern and the cascading-BEHIND behavior.
