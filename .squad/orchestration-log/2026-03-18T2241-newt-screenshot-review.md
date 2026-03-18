# Orchestration Log: Newt (Product Manager) — Screenshot Strategy Review

**Timestamp:** 2026-03-18T22:41Z  
**Agent:** Newt  
**Role:** Product Manager  
**Task:** Review screenshot needs for release documentation  
**Mode:** Background  
**Status:** Completed ✅

---

## Outcome

**Decision filed:** `.squad/decisions/inbox/newt-screenshot-strategy.md`

### Complete Screenshot Inventory (3 Tiers)

#### Tier 1: REQUIRED FOR EVERY RELEASE (4 pages)
- Login page (`login-page.png`)
- Search results page (`search-results-page.png`)
- Admin dashboard (`admin-dashboard.png`)
- Upload page (`upload-page.png`)

#### Tier 2: RECOMMENDED FOR SPECIFIC FEATURES (6+ pages)
- Status tab (`status-tab.png`)
- Stats tab (`stats-tab.png`)
- Filtered search results (`search-results-filtered.png`)
- PDF viewer + similar books (`pdf-viewer-with-recommendations.png`)
- Search error state (`search-error-no-results.png`)
- Responsive mobile layout (`search-page-mobile.png`)

#### Tier 3: ADMIN/OPERATIONAL DOCUMENTATION (4+ pages)
- Healthy Solr admin UI (`admin-solr-healthy.png`)
- RabbitMQ management UI (`admin-rabbitmq-queues.png`)
- Redis commander (`admin-redis-inspector.png`)
- System health check API response (`admin-health-api-response.png`)

---

## 4-Phase Rollout Plan

### Phase 1: Formalize Tier 1 Canonical Set (v1.8.0)
- Owner: Lambert (testing)
- Organize screenshots in `docs/screenshots/`
- Update screenshot spec
- Move existing 7 images to Tier 2

### Phase 2: Integrate into Release-Docs (v1.8.0+)
- Owner: Newt + Automation
- Enhance release-docs.yml workflow with artifact download/validation
- Create release-notes template with screenshot sections
- Update manual templates

### Phase 3: Expand Tier 2 & Tier 3 (v1.8.0–v1.10.0)
- Owner: Lambert + Newt
- Capture screenshots on-demand as features ship

### Phase 4: Before/After Comparisons (v1.9.0+)
- Owner: Newt
- Add side-by-side comparisons in release notes for major features

---

## Decision: APPROVED APPROACH

✅ **Phase 1 & 2 approved for v1.8.0** — Formalize Tier 1, integrate into release docs  
✅ **Phase 3 planned ongoing** — Tier 2/3 as features ship  
⏸️ **Mobile screenshots deferred to v1.9.0** — Not critical for v1.8.0

---

## Success Metrics

- Every release notes (v1.8.0+) includes 4 Tier 1 screenshots
- User/admin manual screenshots auto-updated
- Zero manual screenshot extraction in release workflow
- Release PR includes screenshot commit + release docs commit

---

## References

- Full decision: `newt-screenshot-strategy.md`
- Related: Brett's pipeline decision (`brett-screenshot-pipeline.md`)
