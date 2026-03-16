### 2026-03-16T13:38: Copilot CLI flags correction
**By:** Juanma (Product Owner) — corrected by Squad Coordinator
**What:** `--agent <agent>` and `--autopilot` ARE valid Copilot CLI command-line flags. Previous assessment was wrong.
- `--agent <agent>` — Specify a custom agent to use (e.g., `--agent squad` to use the Squad agent)
- `--autopilot` — Enable autopilot continuation in prompt mode (agent keeps working without user confirmation)
**Impact:** Issue #303 (Update Copilot CLI invocation in release-docs.yml) should use these flags. The workflow can invoke `copilot --agent squad --autopilot -p "Newt: generate release docs"` to have Newt produce documentation autonomously.
**Why:** Verified via `copilot --help` output on the installed CLI.
