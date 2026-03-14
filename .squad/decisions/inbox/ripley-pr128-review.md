# Ripley — PR #128 Review (Status Tab)

**Date:** 2026-07-14
**PR:** #128 "feat(ui): Status tab with indexing progress and service health"
**Author:** @copilot
**Verdict:** ❌ NEEDS CHANGES — stale branch regression

## Decision

PR #128 requested changes due to **stale branch** — branched before PR #123 (router architecture) merged. Merging would delete `TabNav`, all 4 page components, react-router-dom routing, and ~6,300 lines of recently-added code.

**New code quality is good** — `useStatus()` hook and `IndexingStatus.tsx` component are well-built with proper accessibility, TypeScript types, and component decomposition.

**Fix required:** Rebase on current `dev`, wire `IndexingStatus` into the existing `StatusPage.tsx` placeholder, drop App.tsx modifications and duplicate tab CSS.

## Pattern Reinforcement

This is the same stale-branch class of issue seen in PRs #64, #68, #69. Copilot agents branching from old commits continue to produce PRs that would delete recent work. The detection signal remains: check the `--stat` for unexpected deletions of recently-added files.
