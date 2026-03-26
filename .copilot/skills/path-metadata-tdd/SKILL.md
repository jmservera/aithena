---
name: "path-metadata-tdd"
description: "Write pytest coverage for filesystem-path metadata extractors using real corpus examples plus portable temp fixtures"
domain: "testing, metadata"
confidence: "high"
source: "earned — Lambert metadata extraction work in aithena"
---

## Pattern

When a metadata parser is driven by folder and filename heuristics:

1. Scan the real corpus first to capture true naming conventions.
2. Split tests into:
   - **portable temp-path fixtures** for canonical patterns and edge cases
   - **real-library cases** guarded with `skipif` so local knowledge is preserved without breaking CI
3. Assert path fields (`file_path`, `folder_path`) relative to the parser's `base_path`.
4. Keep fallback tests strict: unknown patterns should not silently normalize or invent metadata.
5. Use a fixture that fails clearly when the target module/function does not exist yet, so the suite works for TDD while implementation is still landing.

## Good targets for this pattern

- book/document library indexers
- media catalog importers
- archive ingestion pipelines
- any parser that infers metadata from directory layout instead of embedded file tags
