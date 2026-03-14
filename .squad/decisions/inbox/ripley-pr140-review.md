# Ripley — PR #140 Review Decision

**Date:** 2026-03-15
**PR:** #140 — "chore: remove smoke test artifacts from repo root, gitignore future outputs"
**Author:** @copilot
**Issue:** #139
**Verdict:** CHANGES REQUESTED

## Issues Found

1. **Wrong target branch** — PR targets `jmservera/solrstreamlitui` instead of `dev`. The 13 artifact files exist only on `dev`, so merging into the wrong base accomplishes nothing. All PRs must target `dev` per squad rules.

2. **`*.png` too broad** — A bare `*.png` in `.gitignore` ignores all PNG files repo-wide, not just root-level smoke artifacts. Should be `/*.png` or specific patterns.

3. **88 unrelated files in diff** — Branch divergence from the wrong base inflated the diff, making the PR unreviewable for a simple chore.

## Recommendation

Redo as a clean branch off `dev` with only the artifact removals + corrected `.gitignore` patterns.
