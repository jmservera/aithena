# PRD: Pre-Release Container Testing

**Status:** Proposed  
**Author:** Juanma / Copilot  
**Target:** v1.16.0  

## Problem

Today, Docker images are only built and pushed to `ghcr.io` **after** merging to `main` and pushing a semver tag (`v*.*.*`). This means there is no way to pull and run the exact release containers locally for end-to-end validation before committing to a release. The CI integration test builds from source (`docker compose build`), which does not exercise the same artifact that reaches production.

This gap means:

- **No local smoke test with production images** — issues in Dockerfiles, multi-stage builds, or layer caching only surface post-release.
- **No rollback window** — once tagged, the release is published and images are public.
- **No parity testing** — `docker compose build` (CI) ≠ `docker compose pull` (production). Build-arg defaults, layer ordering, and base image resolution can differ.

## Proposed Solution

Add a **pre-release container workflow** that builds and pushes all 6 Aithena service images to `ghcr.io` with a release-candidate tag, triggered from the `dev` branch before merging to `main`.

### Tag Format

```
ghcr.io/jmservera/aithena-{service}:{version}-rc.{n}
```

Example: `ghcr.io/jmservera/aithena-solr-search:1.16.0-rc.1`

The `{version}` is read from the `VERSION` file. The `{n}` is an auto-incrementing counter (based on existing RC tags for that version) or manually specified.

### Workflow Trigger

| Trigger | When | Use Case |
|---------|------|----------|
| **Manual** (`workflow_dispatch`) | Any time from `dev` branch | Primary: operator requests RC build before release |
| **Automatic** | Release PR opened/updated (PR to `main`) | Convenience: every release PR gets an RC |

Manual trigger is the primary mechanism. The operator specifies the RC number (default: auto-increment).

### Local Testing Flow

```
# 1. Operator triggers RC build (GitHub UI or CLI)
gh workflow run pre-release.yml --ref dev -f rc_number=1

# 2. Wait for build (~15-20 min for all 6 images)

# 3. Pull RC containers locally
export VERSION=1.16.0-rc.1
docker compose -f docker/compose.prod.yml pull

# 4. Run the stack
docker compose -f docker/compose.prod.yml up -d

# 5. Run local E2E tests or manual validation
pytest e2e/ -v

# 6. If issues found → fix on dev → trigger RC .2
# 7. If all good → merge PR to main → tag final release
```

### Workflow Design

```yaml
name: Pre-release containers

on:
  workflow_dispatch:
    inputs:
      rc_number:
        description: 'Release candidate number (auto if empty)'
        required: false
        type: string
  pull_request:
    branches: [main]
    types: [opened, synchronize]

jobs:
  build-rc:
    # Same matrix as release.yml (6 services)
    # Same build args, same Dockerfiles
    # Tag: {version}-rc.{n}
    # NO 'latest' tag (RC must never overwrite latest)
```

### Services

The same 6 services as the release workflow:

| Service | Image |
|---------|-------|
| admin | `ghcr.io/jmservera/aithena-admin` |
| aithena-ui | `ghcr.io/jmservera/aithena-aithena-ui` |
| document-indexer | `ghcr.io/jmservera/aithena-document-indexer` |
| document-lister | `ghcr.io/jmservera/aithena-document-lister` |
| embeddings-server | `ghcr.io/jmservera/aithena-embeddings-server` |
| solr-search | `ghcr.io/jmservera/aithena-solr-search` |

### Smoke Tests

After pushing RC images, run the same per-container smoke tests as the release workflow (health check endpoints, startup validation). This validates the built images before the operator pulls them.

### docker/compose.prod.yml Compatibility

No changes needed. The existing `${VERSION:-latest}` substitution already supports RC tags:

```bash
VERSION=1.16.0-rc.1 docker compose -f docker/compose.prod.yml up -d
```

### RC Image Retention

- RC images remain in `ghcr.io` indefinitely (they are lightweight references to shared layers).
- Optionally, add a cleanup job that deletes RC tags older than 30 days after the final release is published.

## Acceptance Criteria

1. **Manual trigger works** — operator can run `gh workflow run pre-release.yml --ref dev` and all 6 images are pushed with `-rc.N` tags.
2. **Auto-trigger on release PR** — opening/updating a PR to `main` builds RC images automatically.
3. **Local pull works** — `VERSION=X.Y.Z-rc.N docker compose -f docker/compose.prod.yml pull` succeeds for all services.
4. **Smoke tests pass** — per-container health checks run against RC images in CI.
5. **No latest overwrite** — RC builds never tag images as `latest`, `{major}`, or `{major}.{minor}`.
6. **Parity with release** — RC build uses identical Dockerfiles, build args, and base images as the release workflow.
7. **RC number auto-increment** — if no RC number specified, workflow finds the highest existing RC for that version and increments.

## Out of Scope

- **Staging environment deployment** — this PRD covers image building only, not automated deployment to a staging cluster.
- **Automated E2E in CI against RC images** — the existing integration test workflow covers E2E from source; running E2E against pulled RC images is a future enhancement.
- **Signing/attestation** — container signing (cosign/sigstore) is a separate initiative.

## Implementation Notes

- The workflow should share as much as possible with `release.yml` (same matrix, same Dockerfile paths, same build args) to ensure parity. Consider extracting a reusable workflow (`.github/workflows/build-containers.yml`) called by both `release.yml` and `pre-release.yml`.
- The `HF_TOKEN` secret is needed for `embeddings-server` (downloads model weights at build time). The pre-release workflow needs the same secret access.
- Build caching (`type=gha`) should be shared between RC and release builds to avoid redundant layer rebuilds.

## Release Process (Updated)

```
dev branch
  │
  ├── PR to main opened
  │     └── RC images built automatically (v1.16.0-rc.1)
  │
  ├── Operator pulls RC locally
  │     └── VERSION=1.16.0-rc.1 docker compose -f docker/compose.prod.yml up -d
  │     └── Manual E2E validation
  │
  ├── Issues found? Fix on dev → new RC (v1.16.0-rc.2)
  │
  ├── All good → merge PR to main
  │
  └── Tag v1.16.0 → release.yml builds final images
        └── Tags: 1.16.0, 1.16, 1, latest
```

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| RC images consume registry storage | Low — layers are shared with final release | Optional cleanup job post-release |
| RC auto-trigger on every PR push floods registry | Medium — noisy PRs generate many RCs | Only auto-trigger on PRs targeting `main` (release PRs only) |
| Build parity drift between RC and release workflows | High — defeats the purpose | Extract shared reusable workflow; lint for drift in CI |
| HF_TOKEN exposure in PR-triggered workflow | Medium — fork PRs could access secrets | Restrict auto-trigger to non-fork PRs (`pull_request` not `pull_request_target`); manual trigger is primary |
