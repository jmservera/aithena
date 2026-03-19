### 2026-03-19T21:20: User directive — MCP servers available
**By:** Juanma (via Copilot)
**What:** Three MCP servers are configured in `.vscode/mcp.json` and available for development:
- **Context7** (`@upstash/context7-mcp`) — library documentation lookup (use for API docs of dependencies like FastAPI, Solr, React, Playwright, etc.)
- **DeepWiki** (`https://mcp.deepwiki.com/mcp`) — deep repository/wiki knowledge (use for understanding external project internals)
- **Playwright MCP** (`@playwright/mcp@latest`) — browser automation via MCP (use for UI testing, screenshots, browser interaction)

Agents should leverage these when available (VS Code sessions) for library docs lookups instead of guessing APIs. In CLI sessions, fall back to web_fetch or documentation files.
**Why:** User request — captured for team memory. Ensures agents use available tools for accurate library/API information.
