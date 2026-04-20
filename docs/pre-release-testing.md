# Pre-Release Testing Workflow

This guide covers the release candidate (RC) workflow for Aithena: triggering RC builds, testing locally, validating before final release, and handling failures.

**Audience:** Operators and developers validating a release before it goes to production.

## Overview

Before tagging a final release on `main`, you can build and test release candidate (RC) images directly from the `dev` branch. The pre-release workflow builds all six service containers with an RC tag (e.g., `1.16.0-rc.1`) and pushes them to the GitHub Container Registry. You then pull those images locally with `docker/compose.prod.yml` to run validation.

```
dev branch
    │
    ▼
┌──────────────────────┐     ┌──────────────────────┐     ┌─────────────┐
│ Trigger pre-release  │────▶│ RC images built       │────▶│ Local test  │
│ (workflow_dispatch)  │     │ ghcr.io/…:1.16.0-rc.1│     │ with Compose│
└──────────────────────┘     └──────────────────────┘     └──────┬──────┘
                                                                  │
                                             ┌────────────────────┴────────────┐
                                             │                                 │
                                        Pass ▼                            Fail ▼
                                  ┌─────────────────┐              ┌─────────────────┐
                                  │ Merge dev→main  │              │ Fix on dev,      │
                                  │ Tag vX.Y.Z      │              │ rebuild RC       │
                                  └─────────────────┘              └─────────────────┘
```

### Services

The workflow builds these six container images:

| Service | Image |
|---------|-------|
| admin | `ghcr.io/jmservera/aithena-admin` |
| aithena-ui | `ghcr.io/jmservera/aithena-aithena-ui` |
| document-indexer | `ghcr.io/jmservera/aithena-document-indexer` |
| document-lister | `ghcr.io/jmservera/aithena-document-lister` |
| embeddings-server | `ghcr.io/jmservera/aithena-embeddings-server` |
| solr-search | `ghcr.io/jmservera/aithena-solr-search` |

**Tag format:** `{version}-rc.{n}` — for example, `1.16.0-rc.1`, `1.16.0-rc.2`.

## Step 1: Trigger an RC Build

### Via GitHub Actions UI

1. Go to **Actions** → **Pre-Release Build** in the repository.
2. Click **Run workflow**.
3. Select the `dev` branch.
4. Enter the target **version** (e.g., `1.16.0`). This should match the value in the `VERSION` file.
5. Optionally enter an **RC number**. Leave blank to auto-increment (see [RC Auto-Increment](#rc-auto-increment-behavior) below).
6. Click **Run workflow**.

### Via `gh` CLI

```bash
# Auto-increment RC number
gh workflow run pre-release.yml \
  --ref dev \
  -f version=1.16.0

# Explicit RC number
gh workflow run pre-release.yml \
  --ref dev \
  -f version=1.16.0 \
  -f rc_number=3
```

### Monitor the build

```bash
# Watch the latest run
gh run list --workflow=pre-release.yml --limit 3

# Stream logs for a specific run
gh run watch <run-id>
```

## RC Auto-Increment Behavior

When you omit the `rc_number` input, the workflow automatically determines the next RC number:

1. Queries the GitHub Container Registry for existing tags on `aithena-admin`.
2. Finds all tags matching `{version}-rc.{N}` for the requested version.
3. Takes the highest `N` found and sets the new RC number to `N + 1`.
4. If no RC tags exist for this version, starts at `rc.1`.

**Example:** If `1.16.0-rc.1` and `1.16.0-rc.2` already exist, the next build automatically becomes `1.16.0-rc.3`.

This means you can trigger multiple RC builds without manually tracking the number — just leave the field blank and the workflow handles it.

## Step 2: Pull and Test RC Images Locally

### Prerequisites

- Docker and Docker Compose installed
- Access to GitHub Container Registry (`ghcr.io`)
- A configured `.env` file for the stack (see [Admin Manual](admin-manual.md))

### Authenticate with GHCR

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u <your-github-username> --password-stdin
```

### Pull RC images

Set the `VERSION` environment variable to the full RC tag and pull:

```bash
export VERSION=1.16.0-rc.1

# Pull all service images
docker compose -f docker/compose.prod.yml pull
```

The `docker/compose.prod.yml` file references images as:

```yaml
image: ghcr.io/jmservera/aithena-{service}:${VERSION:-latest}
```

Setting `VERSION` causes all services to use the matching RC tag.

### Start the stack

```bash
VERSION=1.16.0-rc.1 docker compose -f docker/compose.prod.yml up -d
```

### Verify images are correct

```bash
docker compose -f docker/compose.prod.yml ps --format "table {{.Name}}\t{{.Image}}\t{{.Status}}"
```

Confirm every custom service image shows the expected `-rc.1` tag.

## Step 3: Validation Checklist

Run through these checks before approving an RC for final release.

### Infrastructure health

- [ ] All containers are running: `docker compose -f docker/compose.prod.yml ps`
- [ ] `solr-init` completed successfully (exits with code 0)
- [ ] SolrCloud shows 3 live nodes in the admin UI
- [ ] RabbitMQ management UI is accessible
- [ ] Redis is reachable

### Service health endpoints

```bash
# solr-search API
curl -s http://localhost/v1/status/ | jq .

# Check version reported by services
curl -s http://localhost/v1/status/ | jq .version
```

Verify the reported version matches the RC tag.

### Core functionality

- [ ] **Login:** Create a user or log in with existing credentials
- [ ] **Search:** Run a keyword search and verify results appear
- [ ] **Document viewing:** Open a PDF from search results
- [ ] **Indexing pipeline:** Add a test PDF to the book library and verify it gets indexed
  - Check `document-lister` logs: `docker compose -f docker/compose.prod.yml logs document-lister --tail 50`
  - Check `document-indexer` logs: `docker compose -f docker/compose.prod.yml logs document-indexer --tail 50`
- [ ] **Admin panel:** Access the Streamlit admin dashboard and verify status pages load
- [ ] **Embeddings:** Verify embeddings-server responds (check admin status page or logs)

### Regression checks

- [ ] Auth-protected endpoints reject unauthenticated requests
- [ ] File uploads work (if applicable)
- [ ] Multilingual search returns results for non-English queries
- [ ] No OOM errors in `document-indexer` logs for large PDFs

### End-to-end test suite (optional)

If you have the E2E environment configured:

```bash
# Run Playwright E2E tests against the RC stack
docker compose -f docker/compose.e2e.yml up --abort-on-container-exit
```

## Step 4: After Validation

### RC passes → proceed to release

1. Merge `dev` into `main` via a PR.
2. Tag the release on `main`:

   ```bash
   git checkout main
   git pull origin main
   git tag v1.16.0
   git push origin v1.16.0
   ```

3. The `release.yml` workflow builds final images with semver tags (`1.16.0`, `1.16`, `1`, `latest`) and publishes a GitHub Release.

### RC fails → fix and rebuild

1. **Stop the test stack:**

   ```bash
   VERSION=1.16.0-rc.1 docker compose -f docker/compose.prod.yml down
   ```

2. **Fix the issue on `dev`** — commit and push the fix.
3. **Trigger a new RC build** — leave the RC number blank to auto-increment:

   ```bash
   gh workflow run pre-release.yml --ref dev -f version=1.16.0
   ```

   This creates `1.16.0-rc.2` (or the next available number).

4. **Re-test** by pulling and validating the new RC:

   ```bash
   VERSION=1.16.0-rc.2 docker compose -f docker/compose.prod.yml pull
   VERSION=1.16.0-rc.2 docker compose -f docker/compose.prod.yml up -d
   ```

5. Repeat until the RC passes all checks.

### Rollback to a previous version

If an RC introduces issues and you need to revert to a known-good version:

```bash
# Stop the RC stack
VERSION=1.16.0-rc.1 docker compose -f docker/compose.prod.yml down

# Start with the last stable release
VERSION=1.15.0 docker compose -f docker/compose.prod.yml pull
VERSION=1.15.0 docker compose -f docker/compose.prod.yml up -d
```

## Security: HF_TOKEN Handling

The `embeddings-server` image requires a [HuggingFace Hub](https://huggingface.co/) token (`HF_TOKEN`) at **build time** to download model weights.

**Key points:**

- `HF_TOKEN` is passed as a Docker **build secret**, not a build argument. It is not baked into any image layer.
- The token is stored as a GitHub Actions secret and injected only during the build step.
- You do **not** need `HF_TOKEN` to _pull_ or _run_ the pre-built RC images — only to build them from source.
- If `HF_TOKEN` is missing or invalid, the `embeddings-server` build will fail. Check the workflow logs for authentication errors.

To add or rotate the token: go to **Settings → Secrets and variables → Actions** in the GitHub repository and update the `HF_TOKEN` secret.

## Related Documentation

- [Release Pipeline](release-pipeline.md) — full `dev → main → tag` release flow
- [Admin Manual](admin-manual.md) — deployment, configuration, and monitoring
- [User Manual](user-manual.md) — end-user guide
