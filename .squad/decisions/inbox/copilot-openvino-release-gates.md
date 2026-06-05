# Brett decision: OpenVINO release gates for base-image drift

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-06-05T17:02:51.834+00:00  
**Status:** Proposed for Scribe merge  
**Related:** #1662

## Decision

Keep Docker `uv sync --inexact` for the OpenVINO embeddings image, but treat it as
safe only when the built image proves the installed runtime packages satisfy the
OpenVINO extra constraints in `src/embeddings-server/pyproject.toml`.

The release gate now has two enforcement points:

1. The Docker build fails immediately after `uv sync --inexact` if installed
   `openvino`, `openvino-tokenizers`, or `optimum-intel` drift outside the
   configured constraints.
2. A PR/manual/weekly `OpenVINO Release Gate` workflow rebuilds the image with
   the latest base image and runs runtime smoke diagnostics.

## Rationale

The post-mortem for #1662 showed that lockfile validation in a clean environment
does not catch skew introduced by preserving base-image packages. Verifying inside
the built image checks the actual runtime that will be released while preserving
the build-time optimization.

## Coordination notes for Parker

Application/runtime tests can rely on `/v1/embeddings/model` for the expected
embedding dimension instead of hardcoding `768`. If Parker changes model-loading
behavior or OpenVINO dependencies, the Docker verifier and smoke script are the
infra-owned gates that should be updated with the new source-of-truth constraints.
