# Ceremonies

> Team meetings that happen before or after work. Each squad configures their own.

## Design Review

| Field | Value |
|-------|-------|
| **Trigger** | auto |
| **When** | before |
| **Condition** | multi-agent task involving 2+ agents modifying shared systems |
| **Facilitator** | lead |
| **Participants** | all-relevant |
| **Time budget** | focused |
| **Enabled** | ✅ yes |

**Agenda:**
1. Review the task and requirements
2. Agree on interfaces and contracts between components
3. Identify risks and edge cases
4. Assign action items

---

## Milestone Kickoff

| Field | Value |
|-------|-------|
| **Trigger** | auto |
| **When** | before |
| **Condition** | Ralph starts work on a new milestone (first issue picked up from a milestone not previously worked) |
| **Facilitator** | lead |
| **Participants** | all-relevant |
| **Time budget** | focused |
| **Enabled** | ✅ yes |

**Agenda:**
1. Review all issues in the milestone — scope, priorities, dependencies
2. Identify the critical path and blockers
3. Assign work to agents based on routing
4. Flag any issues that need research before implementation
5. Set expectations for the milestone (what "done" means)

**Ralph integration:** Before spawning the first work item for a new milestone, Ralph MUST run this ceremony. The kickoff output feeds into the first work batch.

---

## Release Gate

| Field | Value |
|-------|-------|
| **Trigger** | auto |
| **When** | after |
| **Condition** | all issues in a milestone are closed |
| **Facilitator** | newt |
| **Participants** | lead, newt |
| **Time budget** | focused |
| **Enabled** | ✅ yes |

**Agenda:**
1. Verify all milestone issues are closed (no stragglers)
2. Verify CI is green on dev
3. Verify documentation is complete (upgrade guide, test report, changelog)
4. Bump VERSION file to the milestone version
5. Create PR: dev → main (regular merge commit, NOT squash)
6. After merge: tag the release (vX.Y.Z), push tag to trigger release workflow
7. Close the GitHub milestone

**Ralph integration:** After Ralph detects a milestone is clear (all issues closed, zero open PRs), Ralph MUST trigger this ceremony before moving to the next milestone. No milestone work starts until the release is shipped.

---

## Retrospective

| Field | Value |
|-------|-------|
| **Trigger** | auto |
| **When** | after |
| **Condition** | build failure, test failure, or reviewer rejection |
| **Facilitator** | lead |
| **Participants** | all-involved |
| **Time budget** | focused |
| **Enabled** | ✅ yes |

**Agenda:**
1. What happened? (facts only)
2. Root cause analysis
3. What should change?
4. Action items for next iteration
