# Decision: DRY_RUN mode must bypass all infrastructure-dependent checks

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-24
**Status:** IMPLEMENTED
**PR:** #981 (Closes #962)

## Context

The monthly restore drill runs `DRY_RUN=1` in CI where no Docker containers, encryption keys, or services exist. Restore scripts had DRY_RUN guards inside individual restore functions but not around pre-flight infrastructure checks (encryption key existence, Solr health, search API verification).

## Decision

In `DRY_RUN=1` mode, restore scripts must:
1. Skip or warn (never exit fatally) on infrastructure pre-flight checks: encryption keys, service health checks, API verification
2. Treat missing backup files and failed checksums as non-fatal warnings — the separate verify script handles structural validation
3. Preserve all production (non-dry-run) behavior unchanged

The gold-standard pattern is the one `restore-medium.sh` already uses: `if check_health; then restore; else warn; fi`.

## Impact

- **All team members:** When adding new pre-flight checks to BCDR scripts, wrap infrastructure-dependent checks in DRY_RUN guards
- **Lambert:** Monthly restore drill should now pass in CI — verify after merge
- **Future BCDR work:** Follow the medium tier's graceful degradation pattern for all new restore scripts
