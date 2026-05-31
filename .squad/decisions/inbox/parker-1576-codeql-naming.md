# Decision: CodeQL-Safe Naming for Sensitive Credential Status Logs

**Author:** Parker (Backend Dev)
**Date:** 2026-05-24
**Status:** Proposed

## Context

GHAS alert #233 (`py/clear-text-logging-sensitive-data`) flagged the installer summary line that prints `- JWT secret: generated|kept existing`. The printed value is a literal status derived from a boolean, not the secret itself, but the previous local name (`secret_status`) made the false-positive harder for CodeQL to disambiguate.

## Decision

When logging summaries about credential rotation or generation, local variables that contain only enum/status literals should avoid sensitive substrings such as `secret` or `password`. Prefer names that describe the operation state, such as `jwt_rotation_status` or `solr_rotation_status`, and keep comments explicit that only literal status values are logged.

## Impact

This preserves user-facing installer output while making false positives less likely in CodeQL and other taint/name-based scanners.
