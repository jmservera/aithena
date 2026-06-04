# Decision: PR #1638 Assignment Permission Unblock

**Author:** Ripley (Lead)  
**Date:** 2026-06-03T22:02:03.765+00:00  
**Status:** Implemented  
**Scope:** Squad PR-label assignment workflow

## Context

PR #1638 was blocked by a failed `assign-work` check after the `Squad Issue Assign` workflow found `squad:brett` but could not create the PR assignment comment with the default PR-event token.

## Decision

Use the established PR #1643 workflow-permission pattern already merged to `dev`: PR-label routing runs in the base-repository `pull_request_target` context with explicit `pull-requests: write` permission, while remaining limited to trusted metadata routing.

## Follow-up Practice

When the blocker is stale automation on a behind branch, refresh the PR branch onto `dev`, retrigger the routing label if needed, and merge only after review threads are resolved and the new head checks pass.
