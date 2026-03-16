# Squad Decisions Archive

**Last updated:** 2026-03-16  
**Archived:** Decisions older than 30 days, moved from decisions.md to reduce file size.

------

# Decision: Container Version Metadata Baseline

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-03-15  
**Status:** Proposed  
**Issue:** #199 — Versioning infrastructure

## Context

The v0.7.0 milestone needs a single, repeatable way to stamp every source-built container with release metadata. Without a shared convention, local builds, CI builds, and tagged releases can drift, making support and debugging harder.

## Decision

Use a repo-root `VERSION` file as the default application version source, overridden by an exact git tag when present. Pass `VERSION`, `GIT_COMMIT`, and `BUILD_DATE` through Docker Compose build args into every source-built Dockerfile, and bake them into both OCI labels and runtime environment variables.

## Rationale

- Keeps release numbering aligned with the semver tagging flow on `dev` → `main`
- Gives operators a stable fallback (`VERSION`) before a release tag exists
- Makes image provenance visible both from container registries (OCI labels) and inside running containers (`ENV`)
- Uses one metadata contract across Python, Node, and nginx-based images

## Impact

- Source-built services now share one image metadata schema
- `buildall.sh` can build tagged and untagged snapshots consistently
- CI/CD can override any of the three variables without patching Dockerfiles

## Next steps

1. Reuse the same metadata contract in release workflows that publish images
2. Surface the runtime `VERSION` in application health/status endpoints where useful


# Decision: Documentation-First Release Process

**Author:** Newt (Product Manager)  
**Date:** 2026-03-20  
**Status:** Proposed  
**Issue:** Release documentation requirements for v0.6.0 and beyond

## Context

v0.5.0 failed to include release documentation until after approval—a process failure that nearly resulted in shipping without user-facing guides. v0.6.0 shipped 5 major features but documentation was not prepared ahead of time, forcing backfill work.

To prevent this pattern, Newt proposes a formalized documentation-first release process.

## Decision

Documentation for a release must be complete and reviewed before the release ships to production. All user-facing features must have:

1. Migration guides (if applicable)
2. API or feature documentation
3. Example usage or screenshots
4. Known limitations or caveats

Documentation review is part of the release gate (see `release-gate` skill).

## Rationale

- Prevents shipping features without guidance
- Catches undocumented edge cases before release
- Makes support and feedback easier for users
- Reduces post-release documentation backfill

## Impact

- Release checklists now include documentation sign-off
- Newt has authority to block releases missing docs
- Squad members must write docs in parallel with code (not after)

## Next steps

1. Apply to v0.7.0 release planning
2. Link from release PRs to documentation PRs
