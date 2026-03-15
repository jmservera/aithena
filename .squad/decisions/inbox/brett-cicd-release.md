# Brett — CI/CD release automation decision

## Context
Issue #204 adds the first container release automation for the six source-built services after issue #199 standardized `VERSION`, `GIT_COMMIT`, and `BUILD_DATE` Docker build args.

## Decision
- Release publication is now driven by stable semver tags only (`vX.Y.Z`).
- `.github/workflows/release.yml` publishes six GHCR images (`ghcr.io/jmservera/aithena-{service}`) using a matrix build and `docker/build-push-action`.
- Every release tag produces four image tags per service: `X.Y.Z`, `X.Y`, `X`, and `latest`.
- The release workflow preserves GitHub Releases by creating a GitHub release with generated notes after all image pushes succeed.
- `.github/workflows/version-check.yml` now validates the root `VERSION` file and verifies that all release Dockerfiles declare `ARG VERSION` on PRs to `dev` and `main`.

## Why
This keeps the squad's semver release flow from DEC-070 aligned across git tags, container image tags, and the repo `VERSION` file. It also keeps the existing GitHub release notes ceremony intact while making container publication repeatable and auditable.
