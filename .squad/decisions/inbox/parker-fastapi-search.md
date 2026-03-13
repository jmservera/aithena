# Parker — FastAPI Search URL & Language Compatibility

## Context
Phase 2 needs search results that the React UI can consume immediately, including links that open PDFs without exposing raw filesystem paths. At the same time, Solr language data may appear as either `language_detected_s` (Phase 1 field contract) or `language_s` (current langid output), so the API needs a stable client contract before follow-up cleanup work lands.

## Decision
- Expose `document_url` as `/documents/{token}`, where `token` is a URL-safe base64 encoding of `file_path_s`.
- Serve PDFs from that route only after decoding the token and verifying the resolved path stays under `BASE_PATH`.
- Normalize and facet `language` by preferring `language_detected_s` and falling back to `language_s` when needed.

## Impact
- Dallas and later frontend work can open PDFs through a stable API route instead of inventing filesystem-aware links.
- The backend keeps compatibility with already indexed documents while Ash/Parker standardize the long-term language field wiring in later work.
