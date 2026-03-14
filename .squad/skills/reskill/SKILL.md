# Skill: reskill
**Confidence:** medium
**Author:** Ripley (Lead)
**Created:** 2026-03-14
**Last validated:** 2026-03-14

## Pattern
Periodically audit agent charters and extract procedural knowledge into shared skills. Keeps charters lean (identity-focused) and skills reusable (procedure-focused). Reduces context tokens at spawn time.

## When to Apply
- When charters exceed ~1.5KB
- When procedural content is duplicated across 2+ charters
- When new agents are added (check if existing skills cover their domain)
- Quarterly maintenance or when the team feels "sluggish" (context overhead)

## Process

### Step 1: Audit
Read all charters. For each, measure bytes and identify:
- Step-by-step procedures (>3 lines of "how to do X")
- Checklists and patterns
- Tech stack details that are project-wide (not agent-specific)
- Project Context blocks (duplicated everywhere — agents get this from decisions.md)

### Step 2: Identify Overlaps
Find content that appears in 2+ charters. Common offenders:
- `## Project Context` — repeated in every charter
- `## Tech Stack` — project-wide, not agent-specific
- PR/branch conventions — procedural, belongs in a skill
- Testing patterns — procedural, belongs in a skill

### Step 3: Extract to Skills
For each identified procedure:
- Create `.squad/skills/{name}/SKILL.md` with standard format
- Or update an existing skill if one covers the domain
- Set confidence to `low` if first extraction, `medium` if validated

### Step 4: Slim Charters
For each charter, keep ONLY:
- **Identity:** Name, role (1-2 lines)
- **Ownership:** What this agent owns (3-5 bullet points)
- **Behavioral rules:** Core rules that define how they work (3-5 max)
- **Boundaries:** What they do NOT do (delegates to whom)
- **Model preference:** If overridden from default

Remove:
- Project Context (read from decisions.md + team.md at spawn)
- Tech Stack lists (move to project-conventions skill)
- Step-by-step procedures (move to domain skills)
- Responsibility lists >5 items (distill to ownership bullets)

### Step 5: Report Metrics
```
| Agent | Before | After | Saved | Skills extracted |
|-------|--------|-------|-------|-----------------|
```
Plus: total bytes saved, skills created/updated, estimated tokens saved (bytes / 4).

## Anti-Patterns
- Don't extract identity or boundaries — those are charter-only
- Don't create skills with <3 lines of content — too thin to be useful
- Don't remove functional config from copilot charter (capability profiles, auto-assign)
- Don't slim scribe if already under 1KB — it's already minimal
- Don't duplicate content between a skill and a charter — reference only

## Target Metrics
- Most charters: <1.5KB after reskill
- Copilot charter: <2.5KB (has functional config that can't be externalized)
- Scribe charter: untouched if <1KB
- Token savings: typically 800-1200 tokens per full reskill cycle

## References
- `.squad/agents/*/charter.md` — source files
- `.squad/skills/*/SKILL.md` — extraction targets
- `.squad/decisions.md` — project context source of truth
