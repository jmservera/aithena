# Orchestration: Brett (Infra) — Add release-screenshots artifact (#531)

**Date:** 2026-03-19  
**Agent:** Brett (Infrastructure Engineer)  
**Issue:** #531  
**Mode:** background  
**Outcome:** PR #536

## Task

Add `release-screenshots` artifact CI step to extract PNGs from integration test run, compress, and upload with 90-day retention policy.

## Expected Outcome

- PR #536 created and ready for review
- Artifact extracts all PNG files from integration test artifacts
- Compression configured (gzip)
- Retention: 90 days
- Integrated into existing integration-test.yml or new workflow
- Documentation: CI gates and storage constraints noted

## Dependencies

- None (foundational infrastructure)

## Status

- QUEUED: Awaiting agent execution
