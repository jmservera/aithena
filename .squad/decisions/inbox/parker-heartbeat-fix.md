# Decision: Dependabot PR Routing in ralph-triage.js

**Author:** Parker  
**Date:** 2026-03-30  
**Status:** Implemented

## Context

The heartbeat workflow lost Dependabot PR auto-assignment when inline JS was refactored to `ralph-triage.js`. PRs were silently filtered out by `isUntriagedIssue()`.

## Decision

Added a separate Dependabot PR triage pipeline alongside the existing issue triage. The classification uses a two-tier member lookup:

1. **Routing rules** (from `routing.md`) — matches dependency domain keywords against work type columns
2. **Role-based fallback** (from `team.md` roster) — matches against member role text

This makes it resilient to routing table format changes while still respecting routing.md as the source of truth when available.

## Dependency domain patterns

File and title patterns map PRs to six domains: python-backend, frontend-js, github-actions, docker-infra, security, testing. Each domain carries both `workTypeKeywords` (for routing rules) and `roleKeywords` (for roster fallback).

## Impact

- `pull-requests: write` permission added to heartbeat workflow
- New triage results include PRs alongside issues (same JSON format, uses `issueNumber` field since GitHub's label API works for both)
- No changes to existing issue triage logic
