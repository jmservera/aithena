# Decision: Charter Reskill — Extract Procedures to Skills

**Author:** Ripley  
**Date:** 2026-07-14  
**Status:** Implemented

## What Changed

Extracted duplicated procedural content from 7 agent charters into shared skills, reducing total charter size from 13.4KB to 9.2KB (31% reduction).

## Decisions Made

1. **Project Context sections removed from all charters** — Agents get project context from `decisions.md`, `team.md`, and the `project-conventions` skill at spawn time. Duplicating it in every charter wastes ~2.5KB.

2. **Tech Stack sections removed from 6 charters** — Consolidated into `project-conventions` skill. Agent-specific tool knowledge stays in responsibilities (e.g., "Configure multilingual text analyzers" implies Solr expertise).

3. **`project-conventions` skill rewritten** — Replaced the empty template with actual project context, service inventory, tech stack, testing conventions, and anti-patterns.

4. **`squad-pr-workflow` skill created** — Extracted branch naming, PR conventions, commit trailers, and stale PR detection patterns from copilot charter and Ripley's history.

5. **Copilot Capability Profile preserved** — This is functional config (self-assessment matrix), not procedure. Kept in charter.

6. **Scribe charter untouched** — Already under 1KB (936B).

## Impact

All charters now under 1.5KB target except copilot (2.2KB — contains required capability profile matrix that can't be externalized without breaking auto-assign logic).
