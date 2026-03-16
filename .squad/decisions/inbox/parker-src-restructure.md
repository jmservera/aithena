# Parker — src/ Restructure Follow-up

**Date:** 2026-03-16  
**Issue:** #222

## Decision

Keep `solr-search` image builds rooted at the repository root after moving services into `src/`, and update the Dockerfile/COPY paths instead of changing the build context.

## Why

`src/solr-search/Dockerfile` still depends on files addressed from the repo root during image builds. Keeping `context: .` in Compose/release automation minimizes build-logic churn while preserving existing behavior, with only declarative path updates inside the Dockerfile (`COPY src/solr-search/...`).

## Additional notes

- `installer/` remains at the repository root and now imports `src/solr-search` explicitly.
- Installer-related tests under `src/solr-search/tests/` must resolve the repo root above `src/` (`parents[3]`) before importing `installer.setup`.
- Local uv virtual environments may need to be recreated after the move because console-script shebangs capture the old absolute directory path.
