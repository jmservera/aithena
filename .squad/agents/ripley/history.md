# Ripley — History

## Core Context

Ripley is the project lead for architecture, roadmap, sequencing, review quality, release gates, and cross-agent coordination.

**System shape:** on-prem book-library search platform with Solr/SolrCloud, FastAPI services, RabbitMQ workers, React/Vite UI, Redis, nginx, multilingual embeddings, and PDF extraction. No runtime cloud APIs or external auth are part of the core product posture.

**Core search model:** parent/chunk hierarchy, chunk-level embeddings, parent-level UX results, hybrid BM25+kNN fusion, and evolving vector schema/quantization settings that must stay aligned across code, docs, and release evidence.

## Leadership Patterns

- **Phase-gated execution:** research → implementation → validation → merge. Parallelize inside a phase, not across unresolved phase boundaries.
- **Use waves for broad work.** When the board has many issues, group them into foundations/build/integration/polish passes with explicit owners and retrospectives.
- **Prefer incremental delivery over grand rewrites.** Ship the safe first slice, then record Phase 2 follow-up explicitly.
- **Document domain assumptions before coding.** Parent/chunk confusion, queue topology, and schema contracts are architecture risks, not just implementation details.
- **Demand root cause, not symptom patching.** Reproduce, explain, then fix. Mechanical guardrails beat hand-wavy coaching.
- **No silent degradation.** Search paths should not quietly change modes, hide failures, or drop results without explicit product approval.
- **Fresh-branch hygiene matters.** Always start from current `origin/dev`; cross-branch contamination silently reverts good work.
- **Mergeability includes rulesets and conversations.** Green checks alone are insufficient if review threads or rulesets remain unresolved.
- **Release flow is ordered work.** Artifacts land on `dev`, `VERSION` changes there, dev merges to main, then tags/releases happen. Never rewrite shipped tags.
- **Docs are part of the release gate.** Release notes, manuals, changelog, screenshots, and validation evidence are shipping artifacts, not cleanup.
- **Security exceptions need explicit mitigation and follow-up.** “Known issue” is not enough without a compensating-control story.
- **Batch dependency work needs lockfile discipline.** Regenerate locks after stacked merges, close superseded PRs manually, and separate real regressions from infra flakes.
- **Keep skills lean and histories distilled.** Repeated rediscovery should become a skill; history should preserve only durable context.

## Coordination Map

- Parker: backend/services
- Dallas: UI
- Ash: search/schema/relevance
- Brett: infra/Compose/CI
- Kane: security
- Lambert: tests/validation
- Newt: release/docs/manuals
- Copilot: scoped implementation

## Active Architecture Cautions

- Solr version and quantization claims remain evidence-gated.
- Native Solr fusion features are interesting, but current parent/chunk normalization still makes app-side fusion the safe production path.
- Chronic flake fixes should happen centrally, not as one-off PR exceptions.
