# Decision: Screenshot spec expanded to 11 pages

**Author:** Lambert (Tester)  
**Date:** 2026-03-19  
**Status:** IMPLEMENTED  
**PR:** #535 (Closes #530)

## Context

The screenshot spec (`e2e/playwright/tests/screenshots.spec.ts`) captured only 4 pages (login, search results, admin dashboard, upload). The user and admin manuals document 11 distinct pages. Release documentation was incomplete.

## Decision

Expanded the spec to capture all 11 documented pages in a single test run. Data-dependent screenshots (faceted search, PDF viewer, similar books) use `discoverCatalogScenario` for dynamic discovery and skip gracefully when data is unavailable.

## Ordering

- Search empty state is captured **before** any query runs (first after login).
- PDF viewer and similar books are captured **sequentially** (similar books depends on an open PDF).
- Static pages (status, stats, library) are captured last.

## Impact

- All team members: release documentation now gets 11 screenshots automatically.
- CI: the spec remains resilient — missing data or unavailable pages produce annotations, not failures.
