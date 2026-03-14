# Newt — v0.4 documentation suite

**Author:** Newt (Product Manager)  
**Date:** 2026-03-14  
**Status:** Proposed for inbox merge

## Decision

Create the missing v0.4.0 documentation suite as release-ready product artifacts:

- `docs/features/v0.4.0.md`
- `docs/user-manual.md`
- `docs/admin-manual.md`
- `docs/images/.gitkeep`
- README updates for features and documentation links

## Why

The v0.4.0 release had approved product scope but was missing the user-facing and operator-facing documentation expected for a release sign-off. The new docs close that gap without inventing behavior that is not present in the current codebase.

## Notes

- Feature claims were limited to behavior verified in the React UI, search API, Docker Compose config, document lister, and metadata extraction logic.
- Screenshot references were added as placeholders only, with a clear note that real captures should be taken once the stack is running.
- The docs deliberately avoid presenting the current Library tab as a finished browse feature.

## Follow-up

When a running stack is available, capture and replace the placeholder images in `docs/images/`.
