---
name: "path-metadata"
description: "Extracting book metadata from filesystem paths and TDD patterns for metadata parsers"
domain: "backend, indexing, testing"
confidence: "high"
source: "consolidated from path-metadata-heuristics, path-metadata-tdd"
author: "Ripley"
created: "2026-07-25"
last_validated: "2026-07-25"
---

## Context

Use when deriving `title`, `author`, `year`, and `category` from book paths before indexing into Solr, or when writing tests for path-based metadata extraction.

## Patterns

### Extraction Heuristics

1. **Honor explicit filename structure first**
   - `Author - Title (Year).pdf` → author/title/year from filename
   - `Category/Author - Title (Year).pdf` → category from folder

2. **Use folder depth to separate category vs author**
   - `Category/Author/Title.pdf` → first folder = category, second = author
   - `Author/Title.pdf` → parent folder = author (when filename doesn't look like a series/journal)

3. **Handle real aithena library cases**
   - `amades/Auca ... amades.pdf` → `amades` as author, strip repeated suffix
   - `balearics/ESTUDIS_BALEARICS_01.pdf` → `balearics` as category, `author="Unknown"`
   - `bsal/Bolletí ... 1885 - 1886.pdf` → `bsal` as category; year ranges are metadata, not `Author - Title` separators

4. **Always provide fallbacks**
   - Default `title` to filename stem with underscores → spaces
   - Default `author` to `Unknown`
   - Return `file_path`, `folder_path`, `file_size` alongside parsed metadata

### TDD for Metadata Parsers

1. Scan the real corpus first to capture true naming conventions
2. Split tests into:
   - **Portable temp-path fixtures** for canonical patterns and edge cases
   - **Real-library cases** guarded with `skipif` (preserves local knowledge without breaking CI)
3. Assert path fields (`file_path`, `folder_path`) relative to the parser's `base_path`
4. Keep fallback tests strict: unknown patterns must not silently normalize or invent metadata
5. Use a fixture that fails clearly when the target function doesn't exist yet (TDD-friendly)

### Good targets for this pattern
- Book/document library indexers
- Media catalog importers
- Archive ingestion pipelines
- Any parser inferring metadata from directory layout

## Anti-Patterns

- **Do not split on every ` - ` blindly** — periodicals with year ranges will be misparsed
- **Do not assume a single top-level folder is always an author** — some are categories or journal series
- **Do not rely on integration tests alone** — portable temp fixtures catch edge cases faster
