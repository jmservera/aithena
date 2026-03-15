# Aithena — Copilot Instructions

## Project Overview

Aithena is a book library search engine with semantic and keyword search. It's a multi-service Docker Compose application with a React frontend, multiple Python backend services, and infrastructure components (Solr, Redis, RabbitMQ, Nginx).

## Service Architecture

| Service | Technology | Directory | Port (dev) |
|---------|-----------|-----------|------------|
| **aithena-ui** | React 18 + Vite + TypeScript | `aithena-ui/` | 5173 |
| **solr-search** | Python 3.11 + FastAPI | `solr-search/` | 8080 |
| **embeddings-server** | Python 3.11 + FastAPI | `embeddings-server/` | 8085 |
| **document-indexer** | Python 3.11 (RabbitMQ consumer) | `document-indexer/` | — |
| **document-lister** | Python 3.11 (RabbitMQ consumer) | `document-lister/` | — |
| **admin** | Python 3.11 + Streamlit | `admin/` | 8501 |
| **nginx** | Nginx reverse proxy | `nginx/` | 80 |
| **solr** | SolrCloud (3-node + ZooKeeper) | `solr/` | 8983 |
| **redis** | Redis | — | 6379 |
| **rabbitmq** | RabbitMQ | `rabbitmq/` | 5672/15672 |

**Data flow:** File library → document-lister → RabbitMQ → document-indexer → Solr → solr-search API → aithena-ui

**Key:** The admin dashboard is **Streamlit** (Python), NOT React. Don't assign admin work to a frontend/React developer.

## Build, Test, and Lint Commands

### Frontend (aithena-ui)
```bash
cd aithena-ui
npm run lint          # ESLint
npm run format:check  # Prettier
npm run build         # TypeScript + Vite build
npm test              # Vitest (uses jsdom, React Testing Library)
npx vitest run        # Alternative: run tests without watch mode
```

### Python Services (solr-search, document-indexer, document-lister, admin)
```bash
cd solr-search && uv run pytest -v --tb=short          # 78+ tests
cd document-indexer && uv run pytest -v --tb=short      # unit tests
cd solr-search && uv run ruff check .                   # lint
cd document-indexer && uv run ruff check .              # lint
```

All Python services use `pyproject.toml` + `uv.lock` (install with `uv sync --frozen`) **except** `embeddings-server`, which uses only `requirements.txt`.

### Ruff Configuration (all Python)
Global `ruff.toml`: line-length=120, target py311, rules: E, F, W, I, UP, B, SIM, S (bandit). Tests may use `assert` (S101 suppressed).

### Docker Compose Validation
```bash
# Docker daemon is NOT available in this codespace. Use:
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"
bash -n buildall.sh   # validate shell scripts
```

### Full Build
```bash
./buildall.sh   # reads VERSION file, exports build args, runs docker compose up --build
```

## Environment Constraints

- **No Docker daemon** in this codespace. Never run `docker build`, `docker compose up`, or `docker compose config`. Validate YAML with Python's yaml module instead.
- **Docker base images** are minimal. Debian-based images (embeddings-server, solr-search) don't include `wget` — add it if health checks need it. Alpine-based images (document-lister, document-indexer) don't include `procps`.
- Health checks are defined in `docker-compose.yml` (not Dockerfiles), per `.checkov.yml` policy.

## Versioning

- `VERSION` file at repo root is the source of truth (currently `0.7.0`).
- `buildall.sh` exports `VERSION`, `GIT_COMMIT`, `BUILD_DATE` as Docker build args.
- All Dockerfiles accept these as `ARG` and set OCI labels.
- Python services expose `/version` endpoints (with `include_in_schema=False`).
- Frontend gets version via Vite's `define: { __APP_VERSION__: ... }`.

## Branching and PR Strategy

**⚠️ CRITICAL: All PRs MUST target the `dev` branch. NEVER target `main`.**

```bash
# Always create PRs against dev:
gh pr create --base dev --title "..." --body "..."
```

- `dev` is the active development branch.
- `main` is production-only — merges from `dev` happen at release boundaries.
- Feature branches: `squad/{issue-number}-{kebab-case-slug}` or `copilot/{slug}`.

### Merging Multiple PRs

When merging PRs sequentially, expect "base branch was modified" errors. Solutions:
- Use `gh pr merge --admin` to bypass branch protection
- Or retry with a short delay between merges
- If conflicts occur, rebase the PR branch onto dev before merging

## Python Service Conventions

- **Framework:** FastAPI with Pydantic for API services (solr-search, embeddings-server)
- **Config:** Dataclass-based `config.py` using environment variables
- **Internal endpoints** (health, version, admin): use `include_in_schema=False`
- **Redis:** Use `scan_iter()` (never `KEYS`), `mget()` (never per-key `get()` in loops), `ConnectionPool` singleton with double-checked locking
- **Security:** Streaming reads for file uploads (8KB chunks), rate limiting for public endpoints

## Frontend Conventions

- React 18 + TypeScript + Vite
- Tests: Vitest + jsdom + React Testing Library (test files in `src/__tests__/`)
- Formatting: Prettier (check with `npm run format:check`)
- Dev proxy: Vite proxies API calls to `http://localhost:8080`
- Component structure: `src/Components/`, hooks in `src/hooks/`, pages in `src/pages/`

---

# Copilot Coding Agent — Squad Instructions

This project uses **Squad**, an AI team framework. When picking up issues autonomously, follow these guidelines.

## Team Context

Before starting work on any issue:

1. Read `.squad/team.md` for the team roster, member roles, and your capability profile.
2. Read `.squad/routing.md` for work routing rules.
3. If the issue has a `squad:{member}` label, read that member's charter at `.squad/agents/{member}/charter.md` to understand their domain expertise and coding style — work in their voice.

## Capability Self-Check

Before starting work, check your capability profile in `.squad/team.md` under the **Coding Agent → Capabilities** section.

- **🟢 Good fit** — proceed autonomously.
- **🟡 Needs review** — proceed, but note in the PR description that a squad member should review.
- **🔴 Not suitable** — do NOT start work. Instead, comment on the issue:
  ```
  🤖 This issue doesn't match my capability profile (reason: {why}). Suggesting reassignment to a squad member.
  ```

## Branch Naming

Use the squad branch convention:
```
squad/{issue-number}-{kebab-case-slug}
```
Example: `squad/42-fix-login-validation`

## PR Guidelines

When opening a PR:
- **Always target `dev`**: `gh pr create --base dev`
- Reference the issue: `Closes #{issue-number}`
- If the issue had a `squad:{member}` label, mention the member: `Working as {member} ({role})`
- If this is a 🟡 needs-review task, add to the PR description: `⚠️ This task was flagged as "needs review" — please have a squad member review before merging.`
- Follow any project conventions in `.squad/decisions.md`

## Decisions

If you make a decision that affects other team members, write it to:
```
.squad/decisions/inbox/copilot-{brief-slug}.md
```
The Scribe will merge it into the shared decisions file.
