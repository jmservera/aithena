# PRD: Reduce General Complexity – Dockerfiles, Scripts, Environment Files, and Test Infrastructure

> **Status**: PRD complete — ready for phased decomposition and implementation  
> **Target Release**: v2.6  
> **Author**: Newt (Product Manager)  
> **Last Updated**: 2026-06-12  
> **Related Issue**: #1452  
> **Research**: Complete. Findings: 5 near-identical Dockerfiles, 18 shell scripts, 3 env templates, 3 test frameworks, scattered config docs, fragile build scripts.

---

## 1. Executive Summary

The aithena infrastructure (Docker, build, test, and environment setup) has accumulated technical debt across six key areas: Docker image duplication, shell script sprawl, environment file confusion, fragmented test infrastructure, scattered documentation, and build script fragility. This PRD proposes a **systematic consolidation and unification** to reduce maintenance burden, lower cognitive load for new operators, and establish a single source of truth for each operational concern.

**Current pain points:**
- Developers must maintain 5 nearly-identical Python service Dockerfiles individually
- Operators must navigate 18 different shell scripts without a unified CLI interface
- Environment setup requires choosing between 3 overlapping `.env` templates
- Test runs demand knowledge of 3 separate frameworks (Playwright, Pytest E2E, Node stress)
- Configuration guidance is scattered across setup, admin, and operator guides
- Build system (`buildall.sh`) relies on hard-coded service lists and manual maintenance

**Expected outcomes:**
- Single Docker base image with service-specific overlays (15% complexity reduction)
- Unified `manage.sh` CLI for all operational tasks (eliminate 18-script search)
- Single `.env.example` with inline documentation (reduce operator confusion)
- Makefile-based test targets (one command per test suite)
- Single-source-of-truth config documentation (linked from admin manual)
- Dynamic service discovery in build system (reduce maintenance friction)

---

## 2. Problem Statement

### 2.1 Current State

| Area | Issue | Current | Impact |
|------|-------|---------|--------|
| **Docker** | 5 near-identical Python Dockerfiles | `document-indexer/`, `document-lister/`, `solr-search/`, `embeddings-server/`, `admin/` | New service addition requires copy-paste; drift over time; security patches slow to apply |
| **Shell scripts** | 18 scripts scattered in `/scripts/` | No unified CLI; users must `ls scripts/` to discover | Operator confusion; hard to automate; inconsistent naming and error handling |
| **Environment files** | 3 overlapping templates | `.env.example`, `.env.local`, `.compose.env` | Unclear which to use; manual entry errors; missing optional config guidance |
| **Test infrastructure** | 3 separate frameworks | Playwright (UI), Pytest E2E (backend), Node stress tests | No single "run all tests" entrypoint; CI must hardcode framework paths; difficult to add new tests |
| **Documentation** | Config guidance scattered | Setup, admin manual, operator guide, topology docs | Operators must search multiple docs; inconsistent recommendations |
| **Build scripts** | `buildall.sh` fragile | Hard-coded service list; requires manual edit when adding services | New services require editing build script; risk of incomplete builds |

### 2.2 Operator Friction Scenarios

1. **Add a new Python service:** Create Dockerfile → copy from existing → maintain manually → remember to update `buildall.sh` → update docs if env config changed → (3 places to maintain, drift likely)
2. **Debug a service issue:** Find the right script in `/scripts/` → read its logic → trace environment variables across 3 files → (cognitive load high, slow iteration)
3. **Run tests locally:** `cd src/aithena-ui && npm run test` + `cd src/solr-search && pytest e2e` + `npm run stress-test` → (no single command; different frameworks; hard to verify all pass)
4. **Deploy to new environment:** Read setup guide → reference admin manual → check `.env.example` → guess which values are required → (trial-and-error, error-prone)
5. **Update Docker base image:** Edit 5 Dockerfiles + rebuild 5 images + verify 5 outputs → (5× the work)

---

## 3. Goals

### Primary Goals (Phase 1–2)

1. **Consolidate Dockerfiles** — Extract shared base image; reduce service-specific Dockerfiles to lightweight overlays
2. **Unify shell scripts** — Create `manage.sh` CLI wrapper; deprecate scatter-script pattern; document all operations in one place
3. **Single environment source** — Consolidate to `.env.example`; move framework-specific env vars to `.{service}.env` or in-code; add inline documentation
4. **Standardize test infrastructure** — Create Makefile targets for each test suite; single `make test` runs all; `make test-ui`, `make test-backend`, `make test-stress` for individual runs
5. **Establish config source of truth** — Migrate scattered config guidance to single doc; link from admin manual; include compose examples

### Secondary Goals (Phase 2–3)

6. **Dynamic build detection** — Migrate `buildall.sh` to dynamic service discovery (scan `src/*/Dockerfile`); eliminate manual list maintenance
7. **Standardize error handling** — Script error codes, logging, and exception patterns; make operator debugging easier
8. **CI/CD simplification** — Use unified scripts in GitHub Actions; reduce workflow complexity

---

## 4. Non-Goals

- **Rewrite services in a different language** — Only consolidate existing Docker/build infrastructure
- **Change service architecture** — This is infrastructure consolidation, not refactoring service logic
- **Migrate services to Kubernetes** — Maintain Docker Compose as primary orchestration
- **Add new observability/monitoring** — That is tracked separately (#1351); this PRD focuses on operational friction

---

## 5. Success Metrics

| Metric | Target | Baseline | Success Criteria |
|--------|--------|----------|------------------|
| **File count (scripts/)** | ≤ 4 | 18 | 77% reduction via `manage.sh` consolidation |
| **Dockerfile maintenance** | ±0 changes for new service | 5 edits (copy, modify) | Script + template-based approach; 1–2 edits to extend |
| **Environment templates** | 1 `.env.example` + inline docs | 3 files + 0 docs | Operator can configure without external reference |
| **Test single entrypoint** | `make test` runs all | 3 separate commands | All tests pass in CI with one command |
| **Config doc centralization** | 1 primary doc + links | 3+ docs | Operators go to one place first |
| **Build time for full stack** | ≤ 5 min (no regression) | ~5 min | Dynamic detection doesn't slow build |

---

## 6. Detailed Requirements

### 6.1 Docker Consolidation

#### 6.1.1 Extract Shared Base Image

**Requirement:** Create `Dockerfile.base` that contains shared Python 3.11, UV, system dependencies, and health-check patterns.

**Details:**
- Base from `python:3.11-slim`
- Include: `apt-get` system packages (curl, git, build-essential for uv build)
- Define health-check pattern: `HEALTHCHECK --interval=30s --timeout=10s CMD python -m ping localhost`
- Services: document-indexer, document-lister, solr-search, embeddings-server, admin-backend
- Each service Dockerfile: `FROM aithena:base` → copy service-specific pyproject.toml + entry point

**Expected outcome:** Single base image build (cached in CI); service images build 10–20% faster; patch applied once to base.

**Acceptance Criteria:**
- [ ] `Dockerfile.base` created and tested locally
- [ ] Existing 5 service Dockerfiles reduced to 3–5 lines each
- [ ] `docker build -f Dockerfile.base -t aithena:base .` succeeds
- [ ] Service Dockerfile `FROM aithena:base` builds with no regression
- [ ] Health checks functional on all 5 services
- [ ] Documentation updated with base-image architecture

---

#### 6.1.2 Docker Compose Validation

**Requirement:** Verify compose.yml health checks and service dependencies after base consolidation.

**Details:**
- Run `docker-compose config` to validate syntax
- Verify all 5 service containers start and pass health checks
- Test service-to-service connectivity (embeddings-server from document-indexer, etc.)
- Update compose.yml comments if service entry points or env vars changed

**Expected outcome:** compose.yml validated for new base image; no service startups fail.

**Acceptance Criteria:**
- [ ] `docker-compose up -d` succeeds
- [ ] All 5 Python services report healthy within 60 seconds
- [ ] `docker-compose logs` shows no errors on startup

---

### 6.2 Unified Shell Scripts (`manage.sh` CLI)

#### 6.2.1 Design `manage.sh` CLI Interface

**Requirement:** Create a single-entry `manage.sh` CLI with subcommands for all common operations.

**Commands (proposed):**
```bash
./manage.sh up                    # docker-compose up -d
./manage.sh down                  # docker-compose down
./manage.sh logs <service>        # docker-compose logs -f <service>
./manage.sh build [service]       # build one service or all if omitted
./manage.sh rebuild [service]     # rebuild with --no-cache
./manage.sh health                # check service health
./manage.sh test [suite]          # run tests (ui/backend/stress/all)
./manage.sh shell <service>       # docker exec -it bash
./manage.sh reset                 # down + clean volumes + up (for dev reset)
./manage.sh status                # docker-compose ps
./manage.sh config-check          # validate .env files
./manage.sh docs                  # print documentation index
```

**Details:**
- Wrap `docker-compose`, `docker`, and `make` commands
- Standardize error messages and logging (stderr for errors, stdout for info)
- Exit codes: 0 (success), 1 (error), 127 (command not found)
- Built-in help: `./manage.sh --help` and `./manage.sh <cmd> --help`

**Expected outcome:** Single entry point for all operators; discoverable via `./manage.sh --help`.

**Acceptance Criteria:**
- [ ] `manage.sh` created and executable
- [ ] All 12+ subcommands functional
- [ ] `./manage.sh --help` prints full reference
- [ ] Error handling works (invalid service, missing .env, etc.)
- [ ] Existing `/scripts/*` scripts deprecated and documented in `MIGRATION.md`

---

#### 6.2.2 Migrate Existing Scripts into `manage.sh`

**Requirement:** Consolidate all 18 scripts into `manage.sh`; document mapping in MIGRATION.md.

**Current scripts to consolidate:**
- `buildall.sh`, `build.sh`, `rebuild.sh` → `manage.sh build`
- `docker_stop.sh`, `docker_clean.sh` → `manage.sh down`
- `dev_setup.sh` → `manage.sh config-check` + docs
- Health/monitoring scripts → `manage.sh health` + `manage.sh status`
- Utility scripts (e.g., `reset_services.sh`) → `manage.sh reset`

**Expected outcome:** `/scripts/` directory reduced to 3–4 essential files (manage.sh, Makefile, env templates); all operations discoverable via `manage.sh`.

**Acceptance Criteria:**
- [ ] All 18 scripts functionality preserved in `manage.sh` subcommands
- [ ] `MIGRATION.md` documents old script → new command mapping
- [ ] `manage.sh` tested with all major use cases
- [ ] `/scripts/` cleanup completed (mark old scripts as deprecated)

---

### 6.3 Environment File Unification

#### 6.3.1 Create Single `.env.example`

**Requirement:** Consolidate 3 `.env` templates into one canonical `.env.example` with inline documentation.

**Structure:**
```bash
# .env.example — Aithena Configuration
# Copy to .env and customize for your environment

# === DEPLOYMENT ===
# Deployment mode: dev (local dev), test (CI), prod (operator)
DEPLOY_MODE=dev

# === SERVICES ===
# Python services (backend)
EMBEDDINGS_MODEL=multilingual-e5-base
EMBEDDINGS_DEVICE=cpu  # cpu, cuda, mps
DOCUMENT_INDEXER_WORKERS=4
SOLR_SEARCH_LOG_LEVEL=INFO

# Solr (search)
SOLR_JAVA_MEM=-Xmx4g

# Redis (cache)
REDIS_MAX_MEMORY=256mb

# RabbitMQ (messaging)
RABBITMQ_DEFAULT_USER=guest
RABBITMQ_DEFAULT_PASS=guest

# === UI ===
VITE_API_BASE_URL=http://localhost:8000

# === ADVANCED ===
# Rarely changed; see docs/config/README.md for details
# SOLR_CHROOT=/solr
# DISABLE_SECURITY=false
```

**Details:**
- Group by logical domain (deployment, services, UI, advanced)
- Include defaults for most variables
- Add inline comments with allowed values and rationale
- Link to `docs/config/README.md` for detailed explanation

**Expected outcome:** Operators configure once; inline docs answer 90% of "what is this" questions.

**Acceptance Criteria:**
- [ ] `.env.example` created and documented
- [ ] All 3 previous templates merged without data loss
- [ ] Compose validation: `docker-compose config` passes
- [ ] All services start with default `.env.example` values
- [ ] Inline documentation covers 90% of common questions

---

#### 6.3.2 Service-Specific Environment Documentation

**Requirement:** Document per-service environment variables in `docs/config/`.

**Details:**
- Create `docs/config/services.md` with per-service tables:
  - `EMBEDDINGS_MODEL`, `EMBEDDINGS_DEVICE` → embeddings-server
  - `DOCUMENT_INDEXER_WORKERS` → document-indexer
  - `SOLR_JAVA_MEM`, `SOLR_CHROOT` → Solr
  - (etc. for all 16 services)
- Link from `.env.example` "=== ADVANCED ===" section
- Include migration path if defaults change in a release

**Expected outcome:** Operators have reference material for non-obvious config choices.

**Acceptance Criteria:**
- [ ] `docs/config/services.md` created
- [ ] All 16 services documented
- [ ] `.env.example` links to service docs
- [ ] Release notes reference config changes

---

### 6.4 Test Infrastructure Unification

#### 6.4.1 Create Makefile with Test Targets

**Requirement:** Add `Makefile` to project root with unified test targets.

**Targets (proposed):**
```makefile
.PHONY: test test-ui test-backend test-stress clean help

test:           # Run all test suites
	@echo "Running all tests..."
	@$(MAKE) test-ui test-backend test-stress

test-ui:        # UI tests (Playwright)
	cd src/aithena-ui && npm run test

test-backend:   # Backend E2E tests (Pytest)
	cd src/solr-search && python -m pytest e2e/ -v

test-stress:    # Stress/load tests (Node)
	npm run stress-test

clean:          # Clean test artifacts
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name node_modules -exec rm -rf {} +

help:           # Print this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
```

**Details:**
- CI runs `make test` (single entrypoint for all tests)
- Developers use `make test-ui`, `make test-backend`, etc. during development
- Error handling: any test failure exits non-zero
- Makefile placed at project root; discoverable via `make help`

**Expected outcome:** Single `make test` runs all tests; CI simplified.

**Acceptance Criteria:**
- [ ] `Makefile` created at project root
- [ ] All 3 test suites callable via `make test-*`
- [ ] `make test` runs all suites and fails if any fail
- [ ] GitHub Actions updated to use `make test`
- [ ] Documentation includes Makefile reference

---

#### 6.4.2 Consolidate Test Infrastructure Documentation

**Requirement:** Document test setup and execution in `docs/testing/README.md`.

**Details:**
- Prerequisites (Node, Python, Docker)
- Running tests locally: `make test`, `make test-ui`, etc.
- Interpreting results: pass/fail, coverage, known flakes
- Adding new tests: where to place, framework conventions
- CI expectations: test duration, coverage thresholds

**Expected outcome:** New contributors can run tests without external guidance.

**Acceptance Criteria:**
- [ ] `docs/testing/README.md` created
- [ ] All test commands documented
- [ ] Local setup prerequisites listed
- [ ] CI expectations documented

---

### 6.5 Configuration Documentation Consolidation

#### 6.5.1 Create Single Configuration Source of Truth

**Requirement:** Create `docs/config/README.md` as primary reference for all configuration concerns.

**Sections:**
1. **Quick start** — `.env.example` copy + top 5 config decisions
2. **Environment variables** — All 40+ variables with descriptions, defaults, examples (or link to `services.md`)
3. **Compose customization** — Overriding service images, ports, volumes
4. **Advanced topics** — Solr clustering, security, embeddings model selection
5. **Troubleshooting** — Common misconfigurations and fixes
6. **Operator reference** — Linked from admin manual; covers deployment posture

**Details:**
- Migrate existing guidance from setup, admin, and operator docs
- Use consistent structure and examples
- Link from `.env.example` and admin manual

**Expected outcome:** Operators go to one place first; 80% of questions answered there.

**Acceptance Criteria:**
- [ ] `docs/config/README.md` created
- [ ] All major config topics covered
- [ ] Examples for Solr, embeddings, compose customization included
- [ ] Admin manual links to `docs/config/README.md`
- [ ] No more than 2 levels of link-hopping for any config decision

---

#### 6.5.2 Audit and Consolidate Existing Docs

**Requirement:** Scan existing docs; identify and migrate scattered configuration guidance.

**Known scatter points:**
- `docs/setup/README.md` — Initial setup, env vars
- `docs/admin-manual.md` — Operator responsibilities
- `docs/guides/` — Feature-specific setup (e.g., GPU, WSL2)
- Inline code comments and README fragments
- GitHub issue docs/comments

**Expected outcome:** Configuration guidance centralized; no duplicated information across docs.

**Acceptance Criteria:**
- [ ] `docs/config/`, `docs/setup/`, admin manual reviewed
- [ ] Duplicated guidance identified
- [ ] Single source of truth established per topic
- [ ] Cross-references updated

---

### 6.6 Build Script Robustness

#### 6.6.1 Migrate `buildall.sh` to Dynamic Service Discovery

**Requirement:** Replace hard-coded service list in `buildall.sh` with dynamic detection.

**Approach (proposed):**
```bash
# Old: hard-coded list
SERVICES=("embeddings-server" "solr-search" "document-indexer" "document-lister" "admin-backend")

# New: dynamic discovery
find_services() {
  find src -maxdepth 2 -name "Dockerfile" | sed 's|src/||' | sed 's|/Dockerfile||' | sort
}
```

**Details:**
- Scan `src/*/Dockerfile` to find services
- Reduce `buildall.sh` to ~50 lines (from ~80)
- Preserve error handling, logging, and caching
- Update `manage.sh build` to use same logic

**Expected outcome:** New services auto-discovered; no manual list updates needed.

**Acceptance Criteria:**
- [ ] Dynamic discovery implemented in `buildall.sh`
- [ ] Tested with all 5 current services
- [ ] New service added to `src/newservice/` → auto-built
- [ ] `buildall.sh` reduced by ≥30% (line count)
- [ ] Error handling and logging preserved

---

#### 6.6.2 Integrate Dynamic Build into `manage.sh`

**Requirement:** `manage.sh build` uses dynamic service discovery; support `--all`, `--service X`, and `--quick`.

**Details:**
- `./manage.sh build` → build all discovered services
- `./manage.sh build solr-search` → build single service
- `./manage.sh build --quick` → skip cache, rebuild
- Use same discovery logic as `buildall.sh`

**Expected outcome:** `manage.sh` is single interface for all build operations.

**Acceptance Criteria:**
- [ ] `manage.sh build [service]` works as designed
- [ ] `--quick` flag respected
- [ ] Error messages helpful if service not found
- [ ] All 5 services build successfully

---

## 7. Phasing and Priority

### Phase 1: Foundation (Weeks 1–2) — Quick Wins, Unblock Operations

**Goal:** Get `manage.sh` and `.env.example` in place; operators immediately benefit.

| Issue | Title | Owner | Effort | Risk |
|-------|-------|-------|--------|------|
| 1452a | Write PRD and create issues | Newt | 0.5d | — |
| 1452b | Create `manage.sh` CLI (core subcommands) | Brett/Parker | 2d | Low |
| 1452c | Consolidate to `.env.example` | Brett | 1d | Low |
| 1452d | Create `Makefile` with test targets | Lambert | 1d | Low |
| 1452e | Deprecate old scripts; document migration | Brett | 0.5d | Low |

**Success:** Operators use `./manage.sh up/down/build/test` and configure via `.env.example` with no external reference for 80% of cases.

---

### Phase 2: Documentation & Robustness (Weeks 3–4) — Polish, Centralize Docs

**Goal:** Config docs centralized; build system dynamic; test infrastructure unified.

| Issue | Title | Owner | Effort | Risk |
|-------|-------|-------|--------|------|
| 1452f | Create configuration source of truth (`docs/config/`) | Newt/Dallas | 1.5d | Low |
| 1452g | Migrate `buildall.sh` to dynamic service discovery | Brett | 1d | Low |
| 1452h | Consolidate test infrastructure docs | Lambert | 1d | Low |
| 1452i | Audit and migrate scattered config docs | Newt | 1d | Low |
| 1452j | Update GitHub Actions to use `make test` | Brett | 0.5d | Low |

**Success:** Operators and new contributors can onboard via centralized docs; build system self-discovering.

---

### Phase 3: Docker Consolidation (Weeks 5–6) — Major Refactor, Validate

**Goal:** Reduce Dockerfile duplication; establish patterns for new services.

| Issue | Title | Owner | Effort | Risk |
|-------|-------|-------|--------|------|
| 1452k | Extract shared Docker base image | Brett | 2d | Medium |
| 1452l | Refactor 5 service Dockerfiles to use base | Brett | 2d | Medium |
| 1452m | Validate compose health checks with new base | Lambert | 1d | Low |
| 1452n | Update deployment/build documentation | Newt/Brett | 1d | Low |

**Success:** New Python services use 3-5 line Dockerfile + base image (15% Docker complexity reduction); no regression in build time or container behavior.

---

## 8. Dependencies and Constraints

### 8.1 Internal Dependencies

- **Phase 2 depends on Phase 1:** Config docs reference `.manage.sh` and `.env.example`
- **Phase 3 depends on Phase 1–2:** Docker base should use config from `.env.example` (e.g., `SOLR_JAVA_MEM`)
- **GitHub Actions must be updated after Phase 1:** CI already expects `make test`; ensure consistency

### 8.2 External Dependencies

- No external dependencies (all work is within aithena repo)

### 8.3 Rollback Plan

Each phase is independently deployable and can be rolled back:
- **Phase 1 rollback:** Keep old scripts; `manage.sh` is new — minimal impact
- **Phase 2 rollback:** Revert docs; build system remains functional with old `buildall.sh`
- **Phase 3 rollback:** If base image issues, revert to individual Dockerfiles (cost: maintain 5× code again)

---

## 9. Estimated Effort and Timeline

| Phase | Duration | Owner | Effort (person-days) |
|-------|----------|-------|----------------------|
| Phase 1 | Weeks 1–2 | Brett/Parker/Lambert | 5d |
| Phase 2 | Weeks 3–4 | Newt/Lambert/Brett | 5d |
| Phase 3 | Weeks 5–6 | Brett/Lambert | 5d |
| **Total** | 6 weeks | Squad | **15d** |

**Release target:** v2.6 (post-v2.5 validation; v2.5.1 work completes mid-June, freeing squad).

---

## 10. Success Criteria (Release Gate)

Release v2.6 gates on:

1. ✅ `/scripts/` directory reduced from 18 to ≤ 4 files
2. ✅ All 5 service Dockerfiles use shared base image (no file > 30 lines)
3. ✅ `.env.example` is canonical; 3 old templates removed
4. ✅ `make test` runs all test suites (single CI entrypoint)
5. ✅ `docs/config/README.md` exists; admin manual links to it
6. ✅ No regression in build time (≤ 5 min for full stack)
7. ✅ All tests pass; CI clean
8. ✅ `manage.sh` covers ≥ 80% of operational tasks; documented in `MIGRATION.md`

---

## 11. Appendix: Current Script Inventory

### Scripts to Consolidate into `manage.sh`

| Script | Purpose | New Command |
|--------|---------|-------------|
| `buildall.sh` | Build all services | `manage.sh build` |
| `build.sh` | Build one service | `manage.sh build <svc>` |
| `rebuild.sh` | Force rebuild | `manage.sh rebuild` |
| `docker_stop.sh` | Stop all containers | `manage.sh down` |
| `docker_clean.sh` | Remove stopped containers | `manage.sh clean` |
| `dev_setup.sh` | Dev environment setup | `manage.sh config-check` + docs |
| `reset_services.sh` | Reset to clean state | `manage.sh reset` |
| `health_check.sh` | Check service health | `manage.sh health` |
| `logs.sh` | View service logs | `manage.sh logs <svc>` |
| (×9 more utility scripts) | (Various) | (`manage.sh` subcommands) |

---

## 12. Appendix: Current Environment File Inventory

### Templates to Consolidate into `.env.example`

| File | Variables | Purpose |
|------|-----------|---------|
| `.env.example` | Solr, Redis, RabbitMQ | Canonical template |
| `.env.local` | EMBEDDINGS_MODEL, DEVICE | Dev overrides |
| `docker-compose.env` | DEPLOY_MODE, service ports | Compose-specific |

---

