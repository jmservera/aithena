# Decision: Canonical environment template

Date: 2026-06-07
Issue: #1452
Owner: Parker

## Decision

`.env.example` is the canonical environment template for development, production, and offline deployment. The separate `.env.prod.example` template is removed; release packaging and docs should copy/reference `.env.example` and override values in the generated `.env`/`.env.prod` as needed.

## Rationale

Maintaining separate templates let production-only variables and compose defaults drift. A single template keeps variable coverage reviewable and lets installer/release paths consume the same documented defaults without changing runtime secret generation behavior.
