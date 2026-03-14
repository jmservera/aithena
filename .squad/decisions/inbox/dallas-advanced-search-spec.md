# Dallas — Advanced Search Builder Spec

## Context
The current search page exposes a single free-text query box. Solr already supports richer query syntax, but users should not need to remember field names, fuzzy operators, quoted phrases, negation, or range syntax. This spec adds an opt-in advanced builder while keeping the simple search path as the default experience.

## UX Goals
- Preserve the existing quick-search workflow as the default.
- Let users progressively reveal structured query controls.
- Teach Solr syntax through a live preview instead of forcing users to learn it first.
- Keep the layout compatible with the existing dark UI and Bootstrap form patterns.
- Reserve space for future semantic and hybrid search without redesigning the composer.

## Component Tree
```text
AdvancedSearchBuilder.tsx
├── SearchModeSelector.tsx
├── QueryTermRow.tsx
├── YearRangeFilter.tsx
├── LanguageFilter.tsx
└── QueryPreview.tsx
```

## Search Composer Modes
### 1. Builder toggle
The top-level composer exposes a two-state toggle:
- **Simple** — current single text box + Search button
- **Advanced** — structured query builder

Simple mode remains the default and is the only path users see until they opt into Advanced.

### 2. Search mode selector
Inside Advanced mode, show tabs for:
- **Keyword** — full structured builder
- **Semantic** — natural-language input only
- **Hybrid** — keyword builder + semantic input together

For now, only **Keyword** is enabled in the shipped UI. **Semantic** and **Hybrid** are rendered as disabled “Soon” tabs so the future capability is visible without exposing unfinished backend behavior.

## Advanced Keyword Builder Layout
### Search terms section
Each row includes:
- text input for the word / phrase / wildcard pattern
- boolean operator dropdown: `AND | OR | NOT`
- field dropdown: `All fields | Title | Author | Content | Category`
- `Fuzzy` checkbox (single-token fuzzy suffix)
- `Phrase` checkbox (quoted phrase)
- per-row **Remove** button

Behavior notes:
- the first row keeps the operator visible but disabled because it has no previous clause to join against
- phrase selection disables fuzzy because Solr fuzzy suffixes are only valid for single terms in this UI
- wildcards (`*`, `?`) are typed directly into the term input
- multi-word non-phrase inputs are grouped automatically so the preview stays valid

### Additional filters
Below the term rows:
- **Add term** button
- **Year range** with `from` / `to`
- **Language filter** populated from detected language facet values, with fallback language codes (`ca`, `en`, `es`, `fr`) when facet data is not available yet

### Preview + submit
At the bottom of Advanced mode:
- **Live query preview** card showing the generated Solr query
- **Search** button that submits the generated query string

## Query generation rules
### Field mapping
UI labels map to indexed Solr fields:
- Title → `title_s`
- Author → `author_s`
- Content → `content`
- Category → `category_s`
- All fields → no explicit field prefix

### `buildQuery()` contract
`buildQuery()` takes:
- `terms[]`
- `yearRange { from, to }`
- `language`

and returns a Solr-safe query string.

### Examples
```ts
[{ text: "folklore", field: "all", operator: "AND", fuzzy: true }]
// folklore~

[{ text: "catalan folklore", field: "title", operator: "AND", phrase: true }]
// title_s:"catalan folklore"

yearRange: { from: "1900", to: "1950" }
// year_i:[1900 TO 1950]

language: "ca"
// (language_detected_s:ca OR language_s:ca)
```

### Combination rules
- blank rows are ignored
- first non-empty term is emitted without a leading operator
- subsequent rows prepend `AND`, `OR`, or `NOT`
- year and language filters are appended with `AND`
- empty builders fall back to `*:*`
- invalid year boundaries are ignored instead of generating malformed range clauses

## Future semantic / hybrid behavior
The component is intentionally structured so future enablement is small:
- **Semantic** mode swaps the keyword builder for a natural-language textarea
- **Hybrid** mode shows both the keyword builder and semantic textarea together
- `QueryPreview` already supports dual preview blocks for hybrid mode
- `useSearch()` carries a `mode` field so UI wiring is ready once backend contract is finalized

## Integration plan
- Create `src/Components/AdvancedSearch/`
- Move the page shell into `src/Pages/SearchPage.tsx`
- Replace the existing top search form with `AdvancedSearchBuilder`
- Keep sidebar facets, active filters, pagination, and PDF viewer behavior unchanged
- Import Bootstrap CSS globally so builder controls can use Bootstrap patterns while existing custom styles remain in `App.css`

## Testing
Add unit tests for `buildQuery()` covering:
- fuzzy term output
- field-specific phrase output
- boolean + range + language composition
- open-ended range handling
- match-all fallback
- invalid year boundary sanitization

## Notes for follow-up
When semantic and hybrid endpoints are officially enabled, the current disabled tabs can be turned on without changing the component structure. The main remaining product decision will be how hybrid requests should encode separate keyword and semantic inputs in the backend contract.
