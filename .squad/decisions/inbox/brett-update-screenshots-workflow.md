# Decision: Cross-Workflow Artifact Download Pattern

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-25
**Context:** Issue #532 / PR #537

## Decision

For `workflow_run`-triggered workflows that need artifacts from the triggering run, use `actions/github-script` with the GitHub REST API (`actions.listWorkflowRunArtifacts` + `actions.downloadArtifact`) instead of `actions/download-artifact`.

## Rationale

`actions/download-artifact` only works for artifacts uploaded within the same workflow run. When a workflow is triggered by `workflow_run`, it runs in a separate context and cannot access the parent run's artifacts directly. The REST API approach is the supported pattern for cross-workflow artifact consumption.

## Impact

Any future workflows using `workflow_run` triggers that need artifacts should follow the pattern in `update-screenshots.yml`.
