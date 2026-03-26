---
name: "prd-writing-aithena"
description: "Product requirement document structure and approval process for Aithena initiatives"
domain: "product-management, planning"
confidence: "high"
source: "earned from pre-release-containers.md (v1.16.0, 5 issues) and admin-react-migration.md (v2.0, 12 issues)"
author: "Newt"
created: "2026-03-25"
last_validated: "2026-03-25"
---

## Context

Major Aithena initiatives (v1.16.0+, v2.0, v3.0) require PRDs to clarify scope, acceptance criteria, and risks before kickoff. PRDs live in `docs/prd/` and serve as the reference for team coordination, milestone breakdown, and release gating.

**Two PRDs In Progress:**
- **Pre-Release Container Testing** (v1.16.0): 5 issues, 1–2 week initiative
- **Admin Portal React Migration** (v2.0): 12 issues, multi-month, wave-based execution

---

## PRD Structure

Every Aithena PRD includes these sections:

### 1. Header Metadata
```yaml
Status: Proposed | In Progress | Complete
Author: [Newt or assigned PM]
Target Release: [vX.Y.Z or vX.0]
Last Updated: [YYYY-MM-DD]
```

### 2. Problem Statement

**Format:** 3–5 paragraphs that establish:
- Current state (what exists now, how it's used)
- Problems with current state (gaps, risks, inefficiencies)
- Impact (who is affected, severity, business case)

**Example (Pre-Release Containers):**
- Current: Images built only post-merge; no local smoke test with production artifacts
- Problems: No rollback window, parity gap (docker build vs. docker pull), Dockerfiles not exercised pre-release
- Impact: Release risk increases, operator confidence decreases

**Example (Admin React Migration):**
- Current: Split admin experience (Streamlit + React) with separate auth systems
- Problems: Docker socket security concern, duplicate tech stacks, accessibility gaps, tight infrastructure coupling
- Impact: Deployment complexity, maintenance burden, security surface area

### 3. Proposed Solution

**Format:** Clear architectural decision with:
- What changes (new workflow, new components, removals)
- Why this approach (rationale, trade-offs considered)
- Scope boundaries (what's in vs. out)

**Example (Pre-Release Containers):**
- **What:** Add pre-release.yml workflow that builds 6 images with `-rc.N` tags before merging to main
- **Why:** Enables local validation with production artifacts; fast feedback loop before commit
- **Trade-off:** Additional registry storage for RC images (minimal, layers shared with final release)

**Example (Admin React Migration):**
- **What:** Phase 1–4 migration; unify auth system; remove Streamlit service
- **Why:** Single tech stack (React), shared components, proper auth abstraction, eliminated docker.sock dependency
- **Phase Plan:** Phase 1 (API foundation), Phase 2 (React pages), Phase 3 (testing), Phase 4 (Streamlit removal)

### 4. Acceptance Criteria (AC)

**Format:** Numbered checklist of testable conditions. Must answer "how do we know it's done?"

**Example (Pre-Release Containers):**
1. Manual trigger works — `gh workflow run pre-release.yml --ref dev` pushes 6 images with `-rc.N` tags
2. Auto-trigger on release PR — opening PR to main triggers RC build automatically
3. Local pull works — `VERSION=X.Y.Z-rc.N docker compose -f docker-compose.prod.yml pull` succeeds
4. Smoke tests pass — per-container health checks run against RC images in CI
5. No latest overwrite — RC builds never tag as `latest`, `{major}`, or `{major}.{minor}`
6. Parity with release — RC uses identical Dockerfiles, build args, base images as release.yml
7. RC number auto-increment — if no RC number specified, finds highest existing RC and increments

**Anti-Pattern:** AC should NOT be vague (e.g., "system is better" or "infrastructure is improved"). Must be objective.

### 5. Current Feature/Implementation Inventory (for migrations)

For large migrations (admin React), catalog what exists today:

**Format:** Table with current implementation + data sources + gaps

**Example (Admin React Migration section 4.1–4.8):**
| Feature | Current Implementation | Data Source | Required for v2.0? |
|---------|---|---|---|
| Dashboard metrics | Streamlit st.metric cards | Direct Redis | ✅ Yes (move to React) |
| Document queues | st.dataframe | Redis keys | ✅ Yes (move to React) |
| Log viewer | Docker socket mount | docker.sock:ro | ✅ Yes (replace with API) |
| RabbitMQ metrics | HTTP management API | management-api | ✅ Yes (via solr-search API) |

This inventory **directly informs** milestone issue decomposition.

### 6. Goals & Non-Goals

**Format:** Explicit lists

**Goals:**
- What this initiative WILL deliver
- Numbered (G1, G2, G3...)
- Specific, measurable where possible

**Non-Goals:**
- What this initiative does NOT cover (deferred, out-of-scope, future work)
- Numbered (NG1, NG2, NG3...)

**Example (Admin React Migration):**
- G1: Migrate all 7 Streamlit pages to React routes
- G2: Eliminate direct Redis/RabbitMQ/Docker access from frontend
- G3: Remove Streamlit service from docker-compose.yml
- G4: Unify auth via existing React auth context
- G5: Replace Docker socket log viewer with API-based streaming
- NG1: Real-time WebSocket log streaming (v2.0 uses polling; WebSocket in v2.1)
- NG2: Advanced RBAC beyond admin/user/viewer

### 7. Phase Plan (for multi-milestone initiatives)

**Format:** Phase breakdown with deliverables, duration, dependencies

**Example (Admin React Migration — Phase 1–4):**
```
Phase 1: API Foundation (Weeks 1–2)
- 4 new solr-search endpoints (queue-status, indexing-status, logs/{service}, infrastructure)
- Docker socket removed from admin service in docker-compose.yml
- Deliverable: v1.16.0 (these endpoints are backward-compatible; Streamlit still uses them)

Phase 2: React Pages (Weeks 3–4)
- Implement 7 React admin routes (reuse existing /admin framework)
- Dashboard, Document Manager, Reindex, Indexing Status, System Status, Log Viewer, Infrastructure
- Deliverable: v2.0 alpha (admin routes exist; Streamlit still served)

Phase 3: Testing & Migration (Week 5)
- E2E tests for all 7 admin routes
- Migration guide for operators
- Deliverable: v2.0 RC (feature parity achieved)

Phase 4: Cleanup (Week 6)
- Remove Streamlit admin service from docker-compose.yml
- Remove src/admin/ from build
- Deliverable: v2.0 final
```

### 8. Risks & Mitigations

**Format:** Risk table with Impact/Likelihood/Mitigation

**Example (Pre-Release Containers):**
| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|-----------|
| RC images consume registry storage | Low | Medium | Cleanup job post-release (optional; layers shared) |
| RC auto-trigger on every PR push | Medium | High | Only auto-trigger on PRs to main (release PRs) |
| Build parity drift | High | Low | Extract shared reusable workflow; lint for drift in CI |
| HF_TOKEN exposure in PR-triggered | Medium | Low | Restrict auto-trigger to non-fork PRs; manual is primary |

### 9. Out of Scope

**Format:** Explicit deferral list with rationale (not "we're not doing this"; instead "we're doing this in vX.Y.Z because...")

**Example (Pre-Release Containers):**
- **Staging environment deployment** — This PRD covers image building only, not automated deployment to staging cluster (future: v1.17.0)
- **Automated E2E in CI against RC images** — Existing integration test workflow covers E2E from source; E2E against pulled RC images is a future enhancement
- **Container signing/attestation** — Separate security initiative (cosign/sigstore) deferred to v2.0

**Example (Admin React Migration):**
- **Real-time WebSocket log streaming** — v2.0 uses polling; WebSocket upgraded in v2.1
- **Advanced RBAC beyond admin/user/viewer** — Current role model sufficient; advanced RBAC deferred to v3.0
- **Multi-tenant admin** — Single-tenant on-premises; not applicable
- **Admin page i18n** — Framework exists; English-only in v2.0; translations in v2.1+

### 10. Implementation Notes (Technical Constraints & Dependencies)

**Format:** Bullets addressing architecture, dependencies, team coordination

**Example (Pre-Release Containers):**
- The workflow should share as much as possible with `release.yml` (same matrix, Dockerfile paths, build args)
- Consider extracting a reusable workflow (`.github/workflows/build-containers.yml`) called by both `release.yml` and `pre-release.yml`
- `HF_TOKEN` secret is needed for embeddings-server; pre-release workflow needs same secret access
- Build caching (`type=gha`) should be shared between RC and release builds to avoid redundant layer rebuilds

**Example (Admin React Migration):**
- Phase 1 API endpoints are backward-compatible; existing Streamlit continues to work
- Phase 2 React routes depend on Phase 1 endpoints being live (can't start Phase 2 until Phase 1 merges to main)
- Docker socket dependency is the primary blocker for production deployment until Streamlit is removed (Phase 4)
- Auth migration: React uses SQLite-backed users + JWT; Streamlit uses env-var credentials + JWT. Phase 1–2 run in parallel with old auth; Phase 4 removes env-var fallback

### 11. See Also / Related Documents

**Format:** Links to related PRDs, decisions, skills

**Example:**
- Related PRD: `docs/prd/admin-react-migration.md` (Phase 1 API endpoints support pre-release validation)
- Skill: `phase-gated-execution` (Admin React migration will use 4-phase model)
- Skill: `milestone-wave-execution` (12-issue Admin React migration will use waves)
- Decision: `.squad/decisions.md` (Pre-release containers approved 2026-03-25)

---

## PRD Approval Process

### Before Writing

1. **Check if PRD-worthy:** Is this 5+ issues? Does it require multi-team coordination? Does it have architectural decisions?
   - **Yes → PRD required**
   - **No → Use issue description + comments instead**

2. **Discuss with Ripley or Tech Lead:**
   - Problem statement validated
   - Solution approach reviewed (technical feasibility)
   - Phase plan sketched
   - Risks identified

### During Writing

3. **Use PRD template above** — Don't skip sections
4. **Get internal review** — Share draft with Parker (backend), Dallas (frontend), or Brett (infra) based on domain
5. **Validate AC are testable** — Each criterion must be objectively verifiable at release time

### Before Merge

6. **Ripley final review** — Architecture, phase decomposition, dependencies
7. **Create issue for kickoff** — Tag with v1.16.0 or v2.0 milestone, PRD-type label
8. **Announce to team** — Link in weekly standup or Slack
9. **Commit to `docs/prd/`** — PR against dev, merge with feature branch

---

## Anti-Patterns

❌ **Don't:**
- Write PRD after work starts (use issue descriptions for small work)
- Leave AC vague ("it should be better"; instead: "AC1: metric X improves by Y%")
- Skip risk section (risks always exist; document them)
- Forget about phase dependencies (Admin React Phase 2 can't start until Phase 1 merges)
- Defer "important but small" items to NG without rationale (explain why)
- Skip "See Also" links (helps team find related work)

✅ **Do:**
- Start with problem statement, not solution
- Validate AC with team before writing implementation
- Call out which team members are involved in each phase
- Use PRD as release gate checklist (all AC must pass before v1.16.0/v2.0 approved)
- Update PRD if scope changes mid-project (track decisions in `.squad/decisions/`)

---

## When PRDs Feed Release Gates

At release time (e.g., v1.16.0 release):
1. **All AC must pass** — If AC#3 says "local pull works," test it locally before approval
2. **Risks must be mitigated** — If risk says "build parity," verify RC build matches release.yml
3. **Phase plan must be complete** — For multi-phase PRDs, all phases must finish before release tag

**Example:** Pre-Release Containers PRD has 7 AC; v1.16.0 release checklist includes verification of all 7.

---

## References

- **Pre-Release Containers PRD:** `docs/prd/pre-release-containers.md` (v1.16.0, 5 issues)
- **Admin React Migration PRD:** `docs/prd/admin-react-migration.md` (v2.0, 12 issues)
- **Related skills:** phase-gated-execution, milestone-wave-execution, release-gate
- **Decision tracker:** `.squad/decisions.md` (all approved PRDs logged here)
