---
name: "path-metadata-heuristics"
description: "Heuristics for extracting book metadata from aithena library paths"
domain: "backend, indexing"
confidence: "high"
source: "earned — Parker Phase 1 Solr indexer rewrite, validated during lister/indexer bugfixes and 169-file real library indexing (Sessions 2–3)"
---

## Context
Use this when deriving `title`, `author`, `year`, and `category` from book paths before indexing into Solr.

## Patterns

1. **Honor explicit filename structure first**
   - `Author - Title (Year).pdf` → author/title/year from the filename
   - `Category/Author - Title (Year).pdf` → category from folder, author/title/year from filename

2. **Use folder depth to separate category vs author**
   - `Category/Author/Title.pdf` → first folder is category, second folder is author
   - `Author/Title.pdf` → parent folder is author when the filename does not look like a series/journal issue

3. **Handle real aithena library cases**
   - `amades/Auca ... amades.pdf` → treat `amades` as author and strip the repeated author suffix from the title
   - `balearics/ESTUDIS_BALEARICS_01.pdf` → treat `balearics` as category, keep the filename as title text, and use `author="Unknown"`
   - `bsal/Bolletí ... 1885 - 1886.pdf` → treat `bsal` as category; year ranges are metadata, not `Author - Title` separators

4. **Always provide fallbacks**
   - Default `title` to the filename stem with underscores normalized to spaces
   - Default `author` to `Unknown`
   - Return `file_path`, `folder_path`, and `file_size` alongside parsed metadata

## Anti-Patterns
- **Do not split on every ` - ` blindly** — periodicals with year ranges will be misparsed as `Author - Title`
- **Do not assume a single top-level folder is always an author** — some library folders are categories or journal series
