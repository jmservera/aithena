# Decision: Skills Database Pruning (49 → 34)

**Author:** Ripley (Lead)  
**Date:** 2026-03-21  
**Status:** IMPLEMENTED  
**Commit:** e66feff (chore: prune skills database from 49 to 34 high-value skills)

## Context

The skills database had grown to 49 entries across v1.0–v1.11 releases. Many skills were:
- **Unvalidated:** "confidence: medium, not yet validated" (e.g., milestone-branching-strategy)
- **One-time processes:** Process docs that won't recur (e.g., i18n-extraction-workflow for v1.6.0–v1.7.0)
- **Deprecated:** Refer to removed systems (e.g., ci-coverage-setup referenced removed admin service)
- **Too generic:** Software engineering first principles, not aithena-specific (e.g., tdd-clean-code, project-conventions)
- **Overlapping:** Duplicate/near-duplicate patterns (e.g., 2 hybrid-search skills vs. 1 definitive pattern)

Skills database had become a burden for onboarding: which 49 skills matter?

**Request:** Prune aggressively to keep only high-value, battle-tested patterns. Target: ~20–25 skills.

## Decision

**Prune from 49 → 34 skills. Aggressive strategy: if a skill is marginal, remove it.**

### Skills Removed (15 total)

**Unvalidated strategies (3):**
- `milestone-branching-strategy` — planned for v1.11.0 but never executed; team still uses dev branch
- `smoke-testing` — low-confidence local dev pattern; rarely used
- `ci-coverage-setup` — config reference table is stale (references removed admin service)

**One-time process docs (4):**
- `i18n-extraction-workflow` — v1.6.0–v1.7.0 specific; i18n now mature, won't recur
- `lead-retrospective` — Ripley-only procedural skill; belongs in charter, not team skills
- `copilot-review-to-issues` — v1.10.1 triage process for Copilot PRs; one-time issue conversion
- `reskill` — meta-skill about reskilling itself; too self-referential

**Too generic (2):**
- `project-conventions` — belongs in team.md/README, not a skill
- `tdd-clean-code` — generic software engineering, not aithena-specific

**Removed system references (2):**
- `dependabot-triage-routing` — operational routing for Brett alone; belongs in Brett's charter
- `ralph-dependency-check` — trivial coordinator rule; belongs in Ralph's charter

**Generic conventions (1):**
- `squad-pr-workflow` — squad branching conventions belong in squad root docs or team.md

**Consolidated skills (3):**
- `docker-health-checks` — subsumed by docker-compose-operations and solrcloud-docker-operations
- `hybrid-search-parent-chunk` — merged into solr-parent-chunk-model
- `hybrid-search-patterns` → merged into solr-parent-chunk-model

### Consolidation Details

**solr-parent-chunk-model** (expanded):
- Now includes parent-chunk data model (existing)
- PLUS hybrid search implementation (RRF fusion, kNN rules, embedding integration, timeout alignment)
- PLUS fallback degradation patterns
- Unified skill: "Parent/chunk document architecture and hybrid search implementation"
- Authors: Ash (model) + Ash (implementation patterns)

**Result: 34 remaining skills**

## Impact

### Team (onboarding perspective)
- **Clearer signal:** 34 battlefield-proven skills vs. 49 mixed-confidence patterns
- **Faster onboarding:** Agents read the 34 skills that matter, not 49 with unclear status
- **Ownership clarity:** Every remaining skill has clear ownership (Parker, Dallas, Lambert, Ash, Brett, Kane, Ripley)

### Removed content ownership
- Skills removed from team-wide docs → migrated to agent charters (Ripley, Ralph, Brett, Kane)
- No knowledge loss; more appropriate home

## Final Skill Inventory (34)

**Core architecture & patterns (6):**
- phase-gated-execution
- solr-parent-chunk-model (hybrid search + parent-chunk)
- solr-pdf-indexing
- http-wrapper-services
- api-contract-alignment
- pdf-extraction-dual-tool

**Search & embeddings (1):**
- solr-parent-chunk-model (covers all)

**Testing (4):**
- pytest-aithena-patterns
- vitest-testing-patterns
- playwright-e2e-aithena
- path-metadata-tdd

**Backend APIs & infrastructure (5):**
- fastapi-auth-patterns
- fastapi-query-params
- redis-connection-patterns
- pika-rabbitmq-fastapi
- logging-security

**Frontend (2):**
- react-frontend-patterns
- accessibility-wcag-react

**Docker & infrastructure (3):**
- docker-compose-operations
- solrcloud-docker-operations
- bind-mount-permissions

**Git & release (6):**
- branch-protection-strict-mode
- release-gate
- release-tagging-process
- multi-release-orchestration
- pr-integration-gate
- ci-gate-pattern

**Quality & process (3):**
- milestone-gate-review
- milestone-wave-execution
- agent-debugging-discipline

**Security & scanning (2):**
- security-scanning-baseline
- workflow-secrets-security
- ci-workflow-security

**Metadata extraction (2):**
- path-metadata-heuristics
- solr-pdf-indexing

**Infrastructure (1):**
- nginx-reverse-proxy

## Acceptance Criteria

- [x] Identified 15 skills for removal with clear justification
- [x] Consolidated overlapping patterns into unified skills
- [x] Removed all skills; consolidated solr-parent-chunk-model
- [x] Committed changes (commit e66feff)
- [x] Updated Ripley history.md with session learnings
- [x] Final count: 34 high-confidence, team-wide skills

## Rationale

Aggressive pruning is better than slow accumulation. A 49-skill database created decision fatigue on onboarding. The 34 remaining skills are:
- **Validated:** Every skill has been proven in at least one release cycle
- **Owned:** Each skill has a clear author/maintainer
- **Actionable:** Every skill answers "how do we do this in aithena?" not "what's a general best practice?"
- **Distinct:** No overlaps; consolidated patterns into single, authoritative skills

## References

- `.squad/skills/` — 34 remaining skill directories
- `.squad/agents/ripley/history.md` — Full session notes

## Follow-Up Actions

- Squad members should review the 34 skills in context of their charters
- Onboarding guide should link to the 34-skill set, not the full directory
- Next reskill cycle: apply same aggressive pruning (remove any skill that hasn't been cited in 2+ releases)
