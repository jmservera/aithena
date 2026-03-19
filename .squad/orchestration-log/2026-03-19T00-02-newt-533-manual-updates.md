# Orchestration: Newt (Product Manager) — Update manuals with screenshot refs (#533)

**Date:** 2026-03-19  
**Agent:** Newt (Product Manager)  
**Issue:** #533  
**Mode:** background  
**Outcome:** PR #538

## Task

Update user-manual.md and admin-manual.md with inline screenshot references (relative paths to docs/screenshots/). Goal: 10 refs in user manual, 3 refs in admin manual.

## Expected Outcome

- PR #538 created and ready for review
- user-manual.md: 10 inline references to screenshots
- admin-manual.md: 3 inline references to screenshots
- Format: `![Description](../screenshots/filename.png)` (relative paths for portability)
- Each reference includes descriptive alt text and surrounding context
- Test: Build docs locally to verify all references resolve
- Manuals render correctly in release documentation pipeline

## Dependencies

- **Depends on:** Brett #532 (screenshots must exist in docs/screenshots/ before references)

## Status

- QUEUED: Awaiting agent execution (blocked until #532 completes)
