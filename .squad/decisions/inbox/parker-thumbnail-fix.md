# Decision: Thumbnail URL Prefix in Search API

**Author:** Parker (Backend Dev)
**Date:** 2026-03-25
**Status:** Implemented (PR #1139)
**Context:** Issue #1137

## Problem

Thumbnail URLs stored in Solr are relative paths (e.g., `folder/book.pdf.thumb.jpg`). The search API returned these as-is, but the frontend uses them directly in `<img src>`. Without a `/thumbnails/` prefix, the browser resolved them as relative URLs against the current page, hitting the SPA catch-all instead of the nginx static-file location block.

## Decision

The search API now prefixes relative thumbnail paths with `/thumbnails/` via `_thumbnail_url()` in `search_service.py`. Absolute URLs (http/https) and already-prefixed paths (starting with `/`) are passed through unchanged.

## Rationale

- The backend is the right place to apply URL prefixes because it knows the routing scheme
- The frontend should receive ready-to-use URLs without needing path manipulation
- Preserving absolute URLs ensures backward compatibility with any externally-hosted thumbnails
- The nginx location block `^/thumbnails/(.+\.thumb\.jpg)$` expects this prefix

## Impact

- All search, books, and similar-books responses now return `/thumbnails/`-prefixed URLs
- Frontend components (`BookCard`, `BookDetailView`) work without changes
- nginx correctly routes to `/data/thumbnails/` filesystem path
