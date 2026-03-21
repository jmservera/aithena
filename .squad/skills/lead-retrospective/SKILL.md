---
name: "lead-retrospective"
description: "How to run effective team retrospectives for multi-agent milestones"
domain: "leadership, process-improvement"
confidence: "high"
source: "earned from v1.10.0 Wave 0/1 retrospective — graded C+ → B+ improvement"
author: "Ripley"
created: "2026-03-20"
last_validated: "2026-03-20"
---

## Context

Run a retrospective after each wave in milestones with 15+ issues, or after any incident (PR rejection, near-miss, PO intervention). The retrospective is the primary mechanism for team learning velocity.

**Trigger conditions:**
- Wave boundary in a large milestone
- PR rejected by reviewer or PO
- Critical bug caught in review that should have been prevented
- Process failure (cross-branch contamination, stale PRs, scope violations)

---

## Patterns

### 1. Structure: Findings → Decisions → Action Items → Grade

**Findings** — What happened, with specific PR/issue numbers. No generalizations.
- Bad: "Some PRs had issues"
- Good: "PR #700 silently degraded semantic search to keyword search, masking two real bugs"

**Decisions** — Concrete rules, not aspirations. Each decision is enforceable.
- Bad: "We should be more careful with branches"
- Good: "All agents must branch from `origin/dev`. Branching from local state is prohibited."

**Action Items** — Assigned to specific people, with gate conditions.
- Template: `R{N} — {Title}: {Owner}. {Deliverable}. Must complete before {gate}.`
- Example: `R1 — Branch Hygiene Rule: Ripley. Create decision doc. Must complete before Wave 2.`

**Grade** — Letter grade per wave (A/B/C/D/F with +/-). Compare across waves to show improvement trajectory.

### 2. Root Cause Categories

Classify every finding into one of:
1. **Process gap** — No rule existed (fix: create rule/template/checklist)
2. **Knowledge gap** — Information existed but wasn't accessible (fix: document it)
3. **Tooling gap** — Manual discipline required where automation could help (fix: automate)
4. **Skill gap** — Agent didn't know how to do the task correctly (fix: pair review, skill doc)

### 3. Action Item Gating

Action items from the retro MUST complete before the next wave starts. This is non-negotiable.
- Track in PR (single PR for all retro items is fine)
- Self-review each item against the retro intent — "Is this actionable?"
- Keep items concise: working documents, not policy papers

### 4. Incident-Driven Learning

The best retro content comes from specific incidents:
- **PR rejections** reveal gaps in pre-submission quality
- **Near-misses** (caught in review) reveal gaps in domain knowledge
- **Process failures** reveal systemic issues vs. individual mistakes

---

## Examples

**v1.10.0 Wave 0/1 Retrospective:**
- 4 key findings (PR rejection, near-miss, cross-branch contamination, Wave 1 improvement)
- 5 decisions (branch hygiene, reproduction evidence, no silent degradation, self-review, data model docs)
- 8 action items (R1–R8), with R1–R6 gated before Wave 2
- Grade: C+ (Wave 0), B+ (Wave 1)

---

## Anti-Patterns

- **Retro without specific incidents.** Generic "what went well/badly" produces vague learnings. Anchor every finding to a specific PR, issue, or event.
- **Aspirational decisions.** "We should try to..." is not a decision. "All agents must..." is.
- **Ungated action items.** If retro items don't gate the next phase, they get deprioritized and forgotten.
- **Blaming individuals.** "Cross-branch contamination is a workflow bug, not a people bug." Identify systemic causes, not personal failures.
- **Skipping the grade.** Without a grade, there's no baseline to measure improvement against.
