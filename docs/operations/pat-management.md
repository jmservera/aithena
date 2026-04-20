# PAT & Secret Management Guide

This document inventories every Personal Access Token (PAT) and external secret used in the Aithena CI/CD workflows, describes the required permissions, and provides creation, rotation, and consolidation guidance.

> **Automated monitoring:** The [`pat-health-check.yml`](../../.github/workflows/pat-health-check.yml) workflow runs on the 1st of each month and validates all three PATs. It opens a GitHub issue with the `token-expired` label when a token is invalid.

---

## Secret inventory

| Secret name | Provider | Workflows | Purpose |
|---|---|---|---|
| `COPILOT_PAT` | GitHub (classic PAT) | `release-docs.yml`, `pat-health-check.yml` | Authenticates the Copilot CLI (`@github/copilot`) to generate release documentation |
| `COPILOT_ASSIGN_TOKEN` | GitHub (classic PAT) | `squad-issue-assign.yml`, `squad-heartbeat.yml`, `pat-health-check.yml` | Assigns the `@copilot` coding agent to issues via the GitHub API |
| `HF_TOKEN` | HuggingFace | `build-containers.yml`, `pre-release.yml`, `release.yml`, `integration-test.yml`, `pat-health-check.yml` | Downloads gated/private models from HuggingFace Hub during container builds and tests |
| `GITHUB_TOKEN` | GitHub (automatic) | Most workflows | Default Actions token — used for container registry auth, PR comments, issue management, and `gh` CLI calls |

---

## Detailed usage

### `COPILOT_PAT`

**Where it is used:**

- **`release-docs.yml`** — passed as `COPILOT_GITHUB_TOKEN` env var to authenticate the `@github/copilot` npm package, which generates release notes from PR/issue data.
- **`pat-health-check.yml`** — validated monthly by calling the GitHub `/user` API endpoint.

**Required permissions (classic PAT):**

| Scope | Reason |
|---|---|
| `repo` | Read repository data (PRs, issues, milestones) for release note generation |

**What happens when it expires:**

- `release-docs.yml` detects the failure and falls back to a **template-based release document** (no AI-generated content). A PR comment warns about the fallback, and an issue with the `token-expired` label is created.
- **Failure mode:** Graceful degradation — releases still proceed but with placeholder documentation that requires manual completion.

---

### `COPILOT_ASSIGN_TOKEN`

**Where it is used:**

- **`squad-issue-assign.yml`** — used as the `github-token` for the `actions/github-script` step that assigns `@copilot` to issues labeled `squad:copilot`. A standard `GITHUB_TOKEN` cannot assign the Copilot coding agent.
- **`squad-heartbeat.yml`** — used (with `GITHUB_TOKEN` fallback) to assign `@copilot` to issues triaged by the Ralph agent. Includes a separate diagnostic step that opens an issue if the token is missing.
- **`pat-health-check.yml`** — validated monthly.

**Required permissions (classic PAT):**

| Scope | Reason |
|---|---|
| `repo` | Full repo access required to assign collaborators (including `@copilot`) to issues |

> **Why not a fine-grained PAT?** Assigning the `@copilot` coding agent currently requires the classic `repo` scope. Fine-grained PATs with `issues: write` alone are insufficient because the assignment endpoint needs collaborator-level access.

**What happens when it expires:**

- `squad-issue-assign.yml` fails silently at the assignment step and creates an issue with the `token-expired` label.
- `squad-heartbeat.yml` falls back to `GITHUB_TOKEN`, which lacks permission to assign `@copilot`. A warning issue is created.
- **Failure mode:** Degraded — issues are labeled and commented but `@copilot` is not auto-assigned; a maintainer must assign manually.

---

### `HF_TOKEN`

**Where it is used:**

- **`build-containers.yml`** — passed as a Docker build argument (`HF_TOKEN`) so the embeddings server container can download gated models at build time.
- **`pre-release.yml`** — same as above, for pre-release container builds.
- **`release.yml`** — same as above, for release container builds.
- **`integration-test.yml`** — passed as an environment variable (`HF_TOKEN`) for integration tests that may pull models.
- **`pat-health-check.yml`** — validated monthly by calling the HuggingFace `/api/whoami-v2` endpoint.

**Required permissions (HuggingFace token):**

| Permission | Reason |
|---|---|
| `read` (Read access to your personal resources) | Download models from HuggingFace Hub, including gated models that require acceptance of terms |

> **Note:** If the models used are not gated, a `read`-scoped token is sufficient. If gated models are used, you must first accept the model's terms on huggingface.co while logged in with the token owner's account.

**What happens when it expires:**

- Container builds fail during the model download step. The Docker build exits with a non-zero code, and the workflow fails visibly in the Actions tab.
- Integration tests that require model access also fail.
- **Failure mode:** Loud — build and test workflows fail and block PRs/releases.

---

### `GITHUB_TOKEN`

**Automatic token — no manual management required.**

This token is automatically provisioned by GitHub Actions for each workflow run. It is scoped to the repository and its permissions are configured per-workflow via the `permissions:` key.

Workflows that use `GITHUB_TOKEN`:

| Workflow | Permissions used |
|---|---|
| `build-containers.yml` | `packages: write` (GHCR login) |
| `pre-release.yml` | `packages: write` (GHCR login), `contents: read` |
| `release.yml` | `packages: write` (GHCR login) |
| `release-docs.yml` | `contents: write`, `pull-requests: write`, `issues: write` |
| `squad-promote.yml` | `contents: write`, `pull-requests: write` |
| `squad-release.yml` | `contents: read` (gh CLI) |
| `squad-insider-release.yml` | `contents: read` (gh CLI) |
| `squad-heartbeat.yml` | `issues: write` |
| `security-review.yml` | `security-events: read` |
| `monthly-restore-drill.yml` | `issues: write` |

No rotation or creation steps are needed for `GITHUB_TOKEN`.

---

## Step-by-step creation guides

### Creating `COPILOT_PAT`

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**.
2. Click **Generate new token (classic)**.
3. Set a descriptive name: `aithena-copilot-cli`.
4. Set expiration to **90 days** (recommended) or your organization's maximum.
5. Select scope: **`repo`**.
6. Click **Generate token** and copy the value.
7. Go to the repository **Settings → Secrets and variables → Actions**.
8. Create or update the secret `COPILOT_PAT` with the token value.

### Creating `COPILOT_ASSIGN_TOKEN`

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**.
2. Click **Generate new token (classic)**.
3. Set a descriptive name: `aithena-copilot-assign`.
4. Set expiration to **90 days** (recommended).
5. Select scope: **`repo`**.
6. Click **Generate token** and copy the value.
7. Go to the repository **Settings → Secrets and variables → Actions**.
8. Create or update the secret `COPILOT_ASSIGN_TOKEN` with the token value.

### Creating `HF_TOKEN`

1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
2. Click **New token**.
3. Set a descriptive name: `aithena-ci`.
4. Select permission: **Read**.
5. Click **Generate**.
6. If you use gated models, visit each model page on HuggingFace and accept the access terms while logged in.
7. Go to the repository **Settings → Secrets and variables → Actions**.
8. Create or update the secret `HF_TOKEN` with the token value.

> **Tip:** HuggingFace tokens do not expire by default, but can be revoked. Set a calendar reminder to review access quarterly.

---

## Rotation recommendations

| Secret | Recommended cycle | Reminder method |
|---|---|---|
| `COPILOT_PAT` | Every 90 days | Set GitHub PAT expiration + `pat-health-check.yml` monthly validation |
| `COPILOT_ASSIGN_TOKEN` | Every 90 days | Set GitHub PAT expiration + `pat-health-check.yml` monthly validation |
| `HF_TOKEN` | Quarterly review | HuggingFace tokens don't auto-expire; set a calendar reminder |

### Rotation procedure

1. Create a **new** token following the creation guide above (do not revoke the old one yet).
2. Update the repository secret with the new token value.
3. Trigger `pat-health-check.yml` manually (**Actions → PAT Health Check → Run workflow**) to confirm the new token is valid.
4. Revoke the old token only after confirming the new one works.

---

## Consolidation analysis

### Can `COPILOT_PAT` and `COPILOT_ASSIGN_TOKEN` be merged?

**Yes — these two tokens can be consolidated into a single PAT.**

Both require the classic `repo` scope and serve GitHub API authentication purposes:

| Aspect | `COPILOT_PAT` | `COPILOT_ASSIGN_TOKEN` |
|---|---|---|
| Provider | GitHub classic PAT | GitHub classic PAT |
| Scope needed | `repo` | `repo` |
| Used by | Copilot CLI (release-docs) | `actions/github-script` (issue assignment) |
| Owner requirement | Any repo collaborator | Any repo collaborator |

**Consolidation approach:**

1. Create a single classic PAT with the `repo` scope, named `aithena-copilot` (or similar).
2. Store it as **both** `COPILOT_PAT` and `COPILOT_ASSIGN_TOKEN` repository secrets (same value).
3. Optionally, refactor workflows to use a single secret name (e.g., `COPILOT_PAT`) — but keeping two secret names pointing to the same token is simpler and avoids workflow changes.

**Benefits:**
- One token to create, rotate, and monitor instead of two.
- Reduces the risk of one expiring while the other is still valid.

**Why not merge with `HF_TOKEN`?**
- `HF_TOKEN` authenticates against HuggingFace, not GitHub. It cannot be consolidated with the GitHub PATs.

**Why not replace with `GITHUB_TOKEN`?**
- `GITHUB_TOKEN` cannot authenticate the Copilot CLI (which needs a user-scoped PAT).
- `GITHUB_TOKEN` cannot assign the `@copilot` coding agent to issues (requires collaborator-level PAT).

---

## Summary

| Secret | Can be eliminated? | Action |
|---|---|---|
| `COPILOT_PAT` | No, but can share a token with `COPILOT_ASSIGN_TOKEN` | Consolidate to one PAT stored in both secrets |
| `COPILOT_ASSIGN_TOKEN` | No, but can share a token with `COPILOT_PAT` | Consolidate to one PAT stored in both secrets |
| `HF_TOKEN` | No | Different provider (HuggingFace) |
| `GITHUB_TOKEN` | N/A | Automatic, no management needed |

**Minimum PATs required: 2** (one GitHub classic PAT with `repo` scope, one HuggingFace read token) — down from 3 separate tokens today.
