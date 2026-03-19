# Ralph Dependency Check

**Confidence:** medium
**Domain:** orchestration, ralph, work-monitor
**Last validated:** 2026-03-19

## Pattern

When Ralph finds assigned-but-unstarted issues, the coordinator MUST check whether each issue is actually blocked before skipping it.

## Algorithm

```
for each open issue with squad:{member} label:
  blockers = extract "Blocked by #N" from issue body
  if no blockers:
    → ACTIONABLE — spawn agent immediately
  else:
    for each blocker #N:
      check if #N is still open (gh issue view N --json state)
    if all blockers are closed:
      → ACTIONABLE — spawn agent immediately
    else:
      → BLOCKED — skip, note which blocker is pending
```

## Anti-pattern (what went wrong)

The coordinator treated a dependency chain of 4 issues (#530→#531→#532→#533) as "all blocked" and reported the board as idle. In reality, #530 (the chain head) had zero blockers and was immediately actionable.

**Wrong:** "Board is blocked on dependency chain — Ralph is idling."
**Right:** "#530 has no blockers — spawning Lambert now. #531-#533 remain blocked."

## Key rule

Ralph NEVER asks "want me to start this?" — Ralph starts it. The protocol says: "Do NOT ask for permission. Just act."
