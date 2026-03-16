# Decision: remove broken Copilot automation workflows

**Date:** 2026-03-16  
**Author:** @copilot  
**Related workflows:** `.github/workflows/copilot-approve-runs.yml`, `.github/workflows/copilot-pr-ready.yml`

## Context

The current Copilot PR automation does not work in practice:

- `copilot-approve-runs.yml` relies on `pull_request_target`, which is flagged by zizmor as a dangerous trigger.
- `copilot-pr-ready.yml` does not solve the real bottleneck because Copilot-authored PR runs still end up waiting for manual approval.
- Together, these workflows suggest automation exists while the squad still has to intervene manually.

## Decision

Remove both workflows and rely on the existing manual squad process for PR readiness (`gh pr ready <number>` when appropriate).

## Why

A simple manual step is clearer and safer than keeping non-functional automation in a security-sensitive area. This avoids future confusion for reviewers and keeps the repository aligned with the actual operating model used by the team.
