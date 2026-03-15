### 2026-03-15T09:12: User directive — docs required BEFORE release
**By:** jmservera (via Copilot)
**What:** Documentation (feature guide, updated manuals, test report, screenshots) is a HARD REQUIREMENT before any release. Newt must generate all docs as part of the release validation step, not after. If docs are missing, the release is blocked — same as failing tests.
**Why:** v0.5.0 was released without updated docs. This happened with v0.4.0 too (caught by Juanma). Adding to Newt's charter as a gate condition.
