# v1.0.0 src/ Directory Restructure Plan

**Issue:** #222 — Move all microservices into src/ directory  
**Related:** #223, #224, #225 (validation tasks)  
**Status:** ✅ Research Complete — Ready for Implementation  
**Authored by:** Ripley (Lead)  
**Date:** 2025-03-16

---

## Executive Summary

This plan outlines a restructuring of the aithena repository to move all service directories (9 total) into a new `src/` subdirectory, while keeping configuration files, documentation, and CI/CD assets at the root. This declutters the repo root from 21+ top-level items to ~10, improving clarity while maintaining backward-compatibility in paths and build processes.

**No build logic changes required** — all references are declarative path updates in YAML, shell scripts, and markdown documentation.

---

## Current State: Root Directory Inventory

### Moving to src/ (9 items)
1. ✅ `admin/` — Streamlit Python service
2. ✅ `aithena-ui/` — React 18 + Vite frontend
3. ✅ `document-indexer/` — Python RabbitMQ consumer
4. ✅ `document-lister/` — Python file watcher + RabbitMQ producer
5. ✅ `embeddings-server/` — Python embeddings API
6. ✅ `nginx/` — Nginx reverse proxy config
7. ✅ `rabbitmq/` — RabbitMQ broker config
8. ✅ `solr-search/` — Python FastAPI search API
9. ✅ `solr/` — SolrCloud configuration

### Staying at Root (infrastructure & meta, ~10 items)
- `.github/` — GitHub Actions workflows and agents
- `.squad/` — Squad team framework
- `docs/` — User/admin manuals, release notes
- `e2e/` — End-to-end tests (Python + Playwright)
- `LICENSE`, `README.md`, `VERSION` — Project metadata
- `buildall.sh` — Build orchestration script
- `docker-compose*.yml` — Three compose files (main, override, e2e)
- `ruff.toml` — Python linting config (global, not service-specific)
- `.env.example`, `.gitignore`, etc. — Standard repo config

### Edge Case: `installer/` Directory
**Status:** ✅ **STAYS AT ROOT**

**Reasoning:**
- The installer module is a **bootstrap tool** used by CI/CD (integration-test.yml), development (buildall.sh), and deployment
- It imports from `solr-search` at runtime: `sys.path.append(str(SOLR_SEARCH_DIR))` where `SOLR_SEARCH_DIR = ROOT / "solr-search"`
- Moving it into `src/installer/` would require updating:
  - `installer/setup.py` — change `ROOT / "solr-search"` to `ROOT / "src" / "solr-search"`
  - `.github/workflows/integration-test.yml` — change `--project solr-search` references
- **Cost:** 2 small edits; **Benefit:** negligible (installer is small)
- **Decision:** Keep at root. It serves infrastructure role like `buildall.sh`, not a service role. Can be revisited in a future cleanup if installer itself becomes a "service" with its own build/test cycle.

---

## Implementation Map: Path Updates Required

### 1. Docker Compose Files (3 files)

#### `docker-compose.yml`
**Lines with path references:**
```yaml
Line 55:   - ./rabbitmq/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
Line 82:   build: context: ./embeddings-server
Line 115:  build: context: ./document-lister
Line 160:  build: context: ./document-indexer
Line 214:  build: dockerfile: ./solr-search/Dockerfile
Line 281:  build: context: ./admin
Line 359:  build: context: ./aithena-ui
Line 428:  - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
Line 429:  - ./nginx/html:/usr/share/nginx/html:ro
Line 683:  - ./solr/books:/configsets/books:ro
Line 684:  - ./solr/add-conf-overlay.sh:/scripts/add-conf-overlay.sh:ro
```

**Update pattern:** `./service-name/` → `./src/service-name/`

#### `docker-compose.override.yml`
**Lines with port overrides** — no path updates needed (only service port mappings).

#### `docker-compose.e2e.yml`
**No path updates needed** (only environment and volume overrides).

---

### 2. Build Script: `buildall.sh`

**Line 30-35:** Python service directory list
```bash
python_service_dirs=(
  "admin"                  → "src/admin"
  "document-indexer"       → "src/document-indexer"
  "document-lister"        → "src/document-lister"
  "embeddings-server"      → "src/embeddings-server"
  "solr-search"            → "src/solr-search"
)
```

**Impact:** 5 simple string replacements. Build orchestration unchanged.

---

### 3. GitHub Workflows (5 files in `.github/workflows/`)

#### `ci.yml`
**Affected sections:**
- `document-indexer-tests` job: `working-directory: document-indexer` → `src/document-indexer`
- `cache-dependency-glob` references
- Same for `solr-search-tests`

**Count:** ~6 path updates

#### `integration-test.yml`
**Affected sections:**
- `working-directory: e2e` stays (e2e is at root)
- `working-directory: e2e/playwright` stays
- `uv run --project solr-search` — **Does NOT change** (uv projects are resolved by `pyproject.toml` location, and changing the working directory before the uv call handles it)

**Count:** No changes needed (project paths are implicit once working-directory is set)

#### `lint-frontend.yml`
**Affected sections:**
- `working-directory: aithena-ui` → `src/aithena-ui`
- `cache-dependency-path: aithena-ui/package-lock.json` → `src/aithena-ui/package-lock.json`

**Count:** 4 path updates

#### `version-check.yml`
**Affected section:**
- Dockerfile list in run step:
```yaml
dockerfiles=(
  admin/Dockerfile                → src/admin/Dockerfile
  aithena-ui/Dockerfile           → src/aithena-ui/Dockerfile
  document-indexer/Dockerfile     → src/document-indexer/Dockerfile
  document-lister/Dockerfile      → src/document-lister/Dockerfile
  embeddings-server/Dockerfile    → src/embeddings-server/Dockerfile
  solr-search/Dockerfile          → src/solr-search/Dockerfile
)
```

**Count:** 6 path updates

#### `lint-python.yml` (if exists)
Check for working-directory or cache-dependency-glob references.

**Total workflow updates:** ~16-20 lines across 3-4 files

---

### 4. Ruff Configuration: `ruff.toml`

**Lines 11-14:** Per-file ignores with service paths
```toml
"embeddings-server/main.py" = ["S104"]          → "src/embeddings-server/main.py"
"solr-search/main.py" = ["S104"]                → "src/solr-search/main.py"
"solr-search/tests/test_upload.py" = ["S108"]   → "src/solr-search/tests/test_upload.py"
```

**Count:** 3 path updates (ruff.toml is concise)

---

### 5. Documentation Files

#### `.github/copilot-instructions.md`
**Lines with service paths:**
- Service architecture table (lines 9-20): Directory column — 8 updates
- Build/test commands (lines 28-44): `cd` paths — 4 updates
- Command examples: 2-3 inline `cd` commands

**Example:**
```markdown
| **aithena-ui** | React 18 + Vite + TypeScript | `aithena-ui/` | 5173 |
→ | **aithena-ui** | React 18 + Vite + TypeScript | `src/aithena-ui/` | 5173 |
```

**Count:** ~12-15 updates in this file

#### `README.md`
**Impact assessment:** Grep found no direct service path references in first 50 lines.
- Check for inline examples, architecture diagrams, or setup instructions
- Likely minimal updates (1-3)

#### `docs/*.md` (multiple files)
**Found references:**
- `docs/test-report-v0.12.0.md` — Test command examples
  ```bash
  cd /workspaces/aithena/solr-search/...     → cd /workspaces/aithena/src/solr-search/...
  cd /workspaces/aithena/aithena-ui/...      → cd /workspaces/aithena/src/aithena-ui/...
  ```
- `docs/user-manual.md` — References to admin dashboard paths (no changes needed)

**Count:** 4-6 updates across test reports and guides

---

### 6. Test References
#### `solr-search/tests/test_setup_installer.py`
**Import:** `from installer.setup import ...`

**No change needed.** The import path remains `installer.setup` (Python package at root); the import doesn't depend on directory structure. The module will still be importable as long as `sys.path` includes the root (which buildall.sh ensures via `cd` + `uv sync`).

---

## Summary Table: Files to Update

| File | Type | Changes | Complexity |
|------|------|---------|------------|
| `docker-compose.yml` | YAML | 10 path references | Low |
| `buildall.sh` | Shell | 5 list items | Low |
| `.github/workflows/ci.yml` | YAML | 6 working-directory + cache paths | Low |
| `.github/workflows/lint-frontend.yml` | YAML | 4 paths | Low |
| `.github/workflows/version-check.yml` | YAML | 6 dockerfile paths | Low |
| `.github/copilot-instructions.md` | Markdown | 12-15 path references | Low |
| `ruff.toml` | TOML | 3 per-file paths | Low |
| `docs/test-report-*.md` | Markdown | 4-6 command examples | Low |
| `README.md` | Markdown | 0-3 (TBD) | Very Low |
| **Total** | — | **~50-60 line edits** | **All Low** |

---

## Implementation Sequence

### Phase 1: Prepare (no changes to code)
1. ✅ Create `src/` directory (empty)

### Phase 2: Move Directories (git mv or folder operations)
2. ✅ `git mv admin src/admin`
3. ✅ `git mv aithena-ui src/aithena-ui`
4. ✅ `git mv document-indexer src/document-indexer`
5. ✅ `git mv document-lister src/document-lister`
6. ✅ `git mv embeddings-server src/embeddings-server`
7. ✅ `git mv nginx src/nginx`
8. ✅ `git mv rabbitmq src/rabbitmq`
9. ✅ `git mv solr-search src/solr-search`
10. ✅ `git mv solr src/solr`

### Phase 3: Update Path References
11. ✅ Update `docker-compose.yml` (10 paths)
12. ✅ Update `buildall.sh` (5 list items)
13. ✅ Update `.github/workflows/ci.yml` (6 paths)
14. ✅ Update `.github/workflows/lint-frontend.yml` (4 paths)
15. ✅ Update `.github/workflows/version-check.yml` (6 paths)
16. ✅ Update `.github/copilot-instructions.md` (12-15 paths)
17. ✅ Update `ruff.toml` (3 paths)
18. ✅ Update docs (test-report, README) (4-6 paths)

### Phase 4: Testing & Validation
19. **Issue #223:** Validate docker-compose.yml syntax (YAML parsing)
20. **Issue #224:** Validate workflow YAML and shell script syntax
21. **Issue #225:** Smoke test build process with `./buildall.sh` (or unit validation)

### Phase 5: Merge
22. Create PR against `dev` branch
23. Merge once tests pass

---

## Risk Assessment

### Low Risk
- ✅ No code logic changes — only declarative paths
- ✅ `git mv` preserves commit history
- ✅ No runtime sys.path logic changes (buildall.sh uses relative paths)

### Testing Strategy
- **Quick validation:** YAML syntax check on compose files + workflows
- **Build validation:** Run `./buildall.sh` or equivalent (simulated in tests)
- **Shell validation:** `bash -n buildall.sh`

### Rollback Plan
If anything fails:
1. Revert all path edits (they're isolated, low-impact)
2. `git mv src/{service} {service}` to restore original structure
3. No data loss or runtime state affected

---

## Dependencies & Blocking Conditions

None. This is pure restructuring — no code logic, no feature gates, no conditional deployment.

**All related issues (#223-225) are unblocked once #222 is decided.** They become straightforward validation tasks.

---

## Next Steps

1. **Approve this plan:** Lead (Ripley) confirms structure
2. **Assign implementation:** Parker or appropriate engineer picks up #222 with this plan
3. **Validation tasks:** #223, #224, #225 become clear validation steps
4. **Merge:** Single PR with all path updates + directory moves

---

## Appendix: Detailed Line-by-Line Changes

### docker-compose.yml
```yaml
# rabbitmq service
- ./rabbitmq/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
+ - ./src/rabbitmq/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro

# embeddings-server service
- build:
    context: ./embeddings-server
+ build:
    context: ./src/embeddings-server

# (similar for other services: document-lister, document-indexer, solr-search, admin, aithena-ui, nginx, solr)
```

### buildall.sh
```bash
# Line 30-35
- python_service_dirs=(
-   "admin"
-   "document-indexer"
-   "document-lister"
-   "embeddings-server"
-   "solr-search"
- )
+ python_service_dirs=(
+   "src/admin"
+   "src/document-indexer"
+   "src/document-lister"
+   "src/embeddings-server"
+   "src/solr-search"
+ )
```

### .github/copilot-instructions.md (Service Architecture Table)
```markdown
| **aithena-ui** | React 18 + Vite + TypeScript | `aithena-ui/` | 5173 |
→ | **aithena-ui** | React 18 + Vite + TypeScript | `src/aithena-ui/` | 5173 |

(repeated for all 8 service rows)
```

---

## Conclusion

This restructure is **low-risk, high-impact**:
- **Low risk:** 50-60 path references, no logic changes, no runtime dependencies altered
- **High impact:** Repository clarity, scalability (room for additional src/ subdirs in future), professional appearance

**Status:** ✅ **Ready for implementation**

