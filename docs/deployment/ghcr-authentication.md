# GitHub Container Registry (GHCR) Authentication Guide

This guide explains how to authenticate with GitHub Container Registry (GHCR) to pull and push Aithena container images. It covers personal authentication for local development, testing production images, and how CI/CD automation handles authentication.

## Table of Contents

- [Overview](#overview)
- [Personal Access Token (PAT) Setup](#personal-access-token-pat-setup)
- [Docker Login](#docker-login)
- [Testing Production Images Locally](#testing-production-images-locally)
- [CI/CD Authentication](#cicd-authentication)
- [Troubleshooting](#troubleshooting)

## Overview

Aithena publishes Docker images to GitHub Container Registry (GHCR) at:

```
ghcr.io/jmservera/aithena-{service}:{VERSION}
```

**Services published:**
- `aithena-ui` — React frontend
- `solr-search` — Search API
- `embeddings-server` — Embeddings inference service
- `document-indexer` — Document indexing worker
- `document-lister` — Library file scanner worker
- `admin` — Admin dashboard (Streamlit)

### When You Need Authentication

**Public read access (no auth):**
- Pull images tagged `latest` or released versions (e.g., `v1.3.0`)
- These are publicly available on GitHub Container Registry

**Private read/write access (requires auth):**
- Pull images tagged `main` or other development branches (if configured as private)
- Push new images to the registry (developers only)
- Access private organizational registries

## Personal Access Token (PAT) Setup

### Step 1: Generate a Personal Access Token

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Fill in the token details:
   - **Note**: `aithena-ghcr-auth` (or descriptive name)
   - **Expiration**: 90 days (recommended for security)
4. **Select scopes** (required for container operations):
   - ✅ `read:packages` — Pull (read) container images
   - ✅ `write:packages` — Push (write) container images
   - ✅ `delete:packages` — Delete container images (optional, for cleanup)
5. Click **Generate token**
6. **Copy the token immediately** — you won't see it again. Store it securely:

   ```bash
   # Example: Save to a secure location (NOT in source code)
   # Use a password manager or secrets vault for production
   export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

### Step 2: Verify Token Permissions

Test that your token has the correct scopes:

```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/user/packages \
  -s | head -20
```

If the response includes container packages, your token is working.

## Docker Login

### Option 1: Interactive Login (Recommended for Development)

```bash
docker login ghcr.io -u USERNAME -p TOKEN
```

Replace:
- `USERNAME`: Your GitHub username
- `TOKEN`: Your Personal Access Token from the previous step

**Example:**
```bash
docker login ghcr.io -u myusername -p ghp_xxxxxxxx
```

Docker stores credentials in `~/.docker/config.json`. To verify:

```bash
cat ~/.docker/config.json | grep ghcr.io
```

### Option 2: Token from stdin (CI/CD-friendly)

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

This avoids storing credentials on the command line history.

### Option 3: Automated Login with Credentials File

Create `.docker/config.json`:

```json
{
  "auths": {
    "ghcr.io": {
      "auth": "BASE64_ENCODED_USERNAME_TOKEN"
    }
  }
}
```

**Generate the base64 string:**
```bash
echo -n "USERNAME:TOKEN" | base64
```

**Example:**
```bash
echo -n "myusername:ghp_xxxxxxxx" | base64
# Outputs: bXl1c2VybmFtZTpnaHBfxxxxxxxx
```

Update `~/.docker/config.json`:
```json
{
  "auths": {
    "ghcr.io": {
      "auth": "bXl1c2VybmFtZTpnaHBfxxxxxxxx"
    }
  }
}
```

### Verify Docker Login

Test that you can pull an image:

```bash
docker pull ghcr.io/jmservera/aithena-solr-search:latest
```

If successful, you're authenticated. If you see `Error response from daemon: unauthorized: authentication required`, your credentials are invalid or expired.

## Testing Production Images Locally

Production images are tagged with semantic versions (e.g., `v1.3.0`) and published to GHCR. To test a production image locally:

### Step 1: Pull the Production Image

```bash
docker pull ghcr.io/jmservera/aithena-{service}:v1.3.0
```

**Example: Pull the solr-search service at v1.3.0**
```bash
docker pull ghcr.io/jmservera/aithena-solr-search:v1.3.0
```

### Step 2: Create `.env.prod` for Production Configuration

Copy the production example and update values:

```bash
cp .env.prod.example .env.prod
# Edit .env.prod with your environment (see docs/deployment/production.md)
```

Required settings:
```bash
# .env.prod
BOOKS_PATH=/data/booklibrary          # Your library path
PUBLIC_ORIGIN=http://localhost        # Public URL
VERSION=1.3.0                         # Must match image tag
AUTH_JWT_SECRET=...                   # Generate with installer
RABBITMQ_PASS=...                     # Generate with installer
REDIS_PASSWORD=...                    # Generate with installer
```

### Step 3: Update `docker/compose.prod.yml` Image Versions

Edit `docker/compose.prod.yml` to specify production images:

```yaml
services:
  solr-search:
    image: ghcr.io/jmservera/aithena-solr-search:v1.3.0
    # ... rest of configuration
  aithena-ui:
    image: ghcr.io/jmservera/aithena-aithena-ui:v1.3.0
    # ... rest of configuration
  admin:
    image: ghcr.io/jmservera/aithena-admin:v1.3.0
    # ... rest of configuration
```

Or use environment variable substitution:

```yaml
services:
  solr-search:
    image: ghcr.io/jmservera/aithena-solr-search:${VERSION:-latest}
```

### Step 4: Start Services with Production Compose

```bash
docker compose -f docker/compose.prod.yml --env-file .env.prod up --build
```

### Step 5: Verify Services Are Running

```bash
docker compose -f docker/compose.prod.yml ps

# Check health
curl http://localhost:8080/health          # solr-search
curl http://localhost:8085/health          # embeddings-server
curl http://localhost:8501/healthz         # admin (Streamlit)
curl http://localhost/                     # nginx → aithena-ui
```

### Common Local Testing Scenarios

**Test a specific service before release:**
```bash
docker run -it --rm \
  -e PUBLIC_ORIGIN=http://localhost \
  ghcr.io/jmservera/aithena-solr-search:v1.3.0
```

**Run full stack with specific version:**
```bash
VERSION=1.3.0 docker compose -f docker/compose.prod.yml up -d
```

**Compare development vs. production images:**
```bash
# Development (from local build)
docker compose up -d

# Production (from GHCR)
VERSION=1.3.0 docker compose -f docker/compose.prod.yml up -d

# View logs
docker compose logs -f solr-search
docker compose -f docker/compose.prod.yml logs -f solr-search
```

## CI/CD Authentication

Aithena's release workflow (`.github/workflows/release.yml`) automatically pushes images to GHCR when you tag a release.

### How CI/CD Authenticates

The release workflow uses GitHub's built-in `GITHUB_TOKEN` secret:

```yaml
- name: Log in to GitHub Container Registry
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

**Key points:**
- **No personal token needed** — GitHub automatically generates a temporary `GITHUB_TOKEN` for each workflow run
- **Automatic permissions** — The token has `packages: write` permission (configured in workflow permissions)
- **Automatic cleanup** — Token expires after workflow completes
- **Tagged releases only** — Images are only pushed when you create a semver tag (e.g., `v1.3.0`)

### Release Workflow Steps

1. **Create a semver tag:**
   ```bash
   git tag -a v1.3.0 -m "Release version 1.3.0"
   git push origin v1.3.0
   ```

2. **Workflow triggers automatically:**
   - Validates tag format (must be `vX.Y.Z`)
   - Builds each service image
   - Logs into GHCR with `GITHUB_TOKEN`
   - Pushes images with tags: `v1.3.0`, `1.3`, `1`, and `latest`
   - Creates release package (`.tar.gz`)

3. **Monitor the workflow:**
   ```bash
   gh run list --workflow release.yml
   gh run view <run-id> --log
   ```

### Image Tags Generated by CI/CD

For tag `v1.3.0`, the workflow generates:
- `ghcr.io/jmservera/aithena-{service}:1.3.0` — Full version
- `ghcr.io/jmservera/aithena-{service}:1.3` — Minor version
- `ghcr.io/jmservera/aithena-{service}:1` — Major version
- `ghcr.io/jmservera/aithena-{service}:latest` — Latest release

## Troubleshooting

### `Error response from daemon: unauthorized: authentication required`

**Cause:** Docker is not authenticated with GHCR.

**Solution:**
```bash
docker login ghcr.io -u USERNAME -p TOKEN
# Then retry:
docker pull ghcr.io/jmservera/aithena-solr-search:latest
```

### `Error: token_not_valid` or `bad_credentials`

**Cause:** Personal Access Token is invalid, expired, or has insufficient scopes.

**Solution:**
1. Generate a new PAT at [github.com/settings/tokens](https://github.com/settings/tokens)
2. Ensure scopes include `read:packages` and `write:packages`
3. Update docker credentials:
   ```bash
   docker logout ghcr.io
   docker login ghcr.io -u USERNAME -p NEW_TOKEN
   ```

### `Error response from daemon: image not found`

**Cause:** Image doesn't exist at the specified tag or version.

**Solution:**
1. Verify image exists:
   ```bash
   docker search ghcr.io/jmservera/aithena-solr-search
   ```
2. Check published releases:
   ```bash
   curl https://api.github.com/users/jmservera/packages \
     -H "Authorization: Bearer $GITHUB_TOKEN" | jq '.[] | select(.name | contains("aithena"))'
   ```
3. Use `latest` if your version doesn't exist:
   ```bash
   docker pull ghcr.io/jmservera/aithena-solr-search:latest
   ```

### `No space left on device` when pulling images

**Cause:** Docker's storage is full.

**Solution:**
```bash
# Clean up unused images and containers
docker system prune -a --volumes

# Check disk usage
docker system df

# If needed, configure Docker to use a different storage location
# (See Docker documentation for your OS)
```

### PAT has insufficient permissions

**Cause:** Token scopes are missing `read:packages` or `write:packages`.

**Solution:**
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Find your token and click **Edit**
3. Add missing scopes: `read:packages`, `write:packages`
4. Save changes
5. Refresh docker login:
   ```bash
   docker logout ghcr.io
   docker login ghcr.io -u USERNAME -p TOKEN
   ```

### Release workflow fails with authentication error

**Cause:** Workflow permissions are not set correctly.

**Solution:**
Verify `.github/workflows/release.yml` has:
```yaml
permissions:
  contents: read
  packages: write  # This enables GHCR push
```

If missing, submit a PR to add `packages: write` to the workflow.

### How to revoke compromised credentials

If your PAT is exposed:

1. **Immediately revoke the token:**
   - Go to [github.com/settings/tokens](https://github.com/settings/tokens)
   - Find the token and click **Delete**

2. **Generate a new token** with the same scopes

3. **Update local credentials:**
   ```bash
   docker logout ghcr.io
   docker login ghcr.io -u USERNAME -p NEW_TOKEN
   ```

## See Also

- [GitHub Container Registry Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Production Deployment Guide](production.md)
- [Release Process](../release-notes-v1.3.0.md)
- [CI/CD Workflows](.github/workflows/)
