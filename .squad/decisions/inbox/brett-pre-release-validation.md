# Decision: Narrow pre-release auth failure classification

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-06-06T09:36:46.687+00:00  
**Status:** Proposed for Scribe merge  
**Related:** #1686

## Context

Pre-release validation run 27053636169 reported a release-blocking `security` error for `document-indexer-1`. The underlying log line was a benign thumbnail warning for a corrupt fixture PDF under a `TestAuthor` path:

`TestAuthor ... Thumbnail generation failed ... Failed to open file`

The analyzer classified it as security because the shell glob `auth*fail` matched `Author` followed later by `failed`.

## Decision

Pre-release security classification should use phrase-level authentication failure patterns, not broad substring globs. The analyzer now matches explicit phrases such as `auth failed`, `auth failure`, `auth error`, `authentication failed`, and `authorization failed/failure`.

## Rationale

This keeps real authentication and authorization failures release-blocking while preventing benign author names, filenames, or log fields from tripping the security gate. The fix is narrower than adding an allowlist for the corrupt PDF fixture because it addresses the classifier bug without hiding future file-open or thumbnail problems.
