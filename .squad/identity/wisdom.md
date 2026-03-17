---
last_updated: 2026-03-17T18:00:00Z
---

# Team Wisdom

Reusable patterns and heuristics learned through work. NOT transcripts — each entry is a distilled, actionable insight.

## Patterns

<!-- Append entries below. Format: **Pattern:** description. **Context:** when it applies. -->

**Pattern:** Review Copilot PR comments before merging. Every PR gets `copilot-pull-request-reviewer` comments — apply valid suggestions, resolve invalid ones with a comment. No unreviewed comments at merge time.
**Context:** Every PR merge. Non-negotiable quality gate.

**Pattern:** Don't rush PR merges with `--admin` bypass. Speed caused us to ship 3 milestones (v1.0.1–v1.2.0) without proper releases, changelogs, or version bumps. Take the time to review.
**Context:** All PR merges, especially batch operations like Ralph rounds.

**Pattern:** When merging Dependabot PRs, still review Copilot's comments — major version bumps may have breaking API changes that Copilot catches.
**Context:** Dependabot PRs (currently 18 open).

**Pattern:** After spawning an agent to create a PR, the agent's job isn't done at push — they must also review the Copilot feedback that arrives after the push and address it before the PR is merge-ready.
**Context:** All agent-created PRs.

**Pattern:** Sequential milestone releases matter. We accumulated 3 unreleased milestones before the retro caught it. Ship each milestone fully (VERSION bump, tag, GitHub release, close milestone) before moving to the next.
**Context:** Release boundaries.

**Pattern:** Dev→main PRs use `--merge` (regular merge commit), never `--squash`. Feature PRs to dev use squash merge.
**Context:** Release merges to main.

**Pattern:** The integration test workflow only triggers on PRs to dev — for dev→main PRs, trigger it manually with `workflow_dispatch`.
**Context:** v1.4.0 release PR #432 was blocked by this.
