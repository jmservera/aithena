# Decision: Add intel-extension-for-pytorch to OpenVINO extras

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-25
**Status:** Implemented (Issue #1286)
**Context:** User reported Intel GPU detected but inference failing in OpenVINO image

## Problem

The OpenVINO embeddings-server image installed `openvino` and `optimum-intel` but not `intel-extension-for-pytorch` (IPEX). Without IPEX, PyTorch detects Intel XPU hardware but cannot dispatch inference to it — the bridge between PyTorch and Intel's XPU runtime is missing.

## Decision

Add `intel-extension-for-pytorch` to the `[project.optional-dependencies] openvino` group in `src/embeddings-server/pyproject.toml`. This ensures IPEX is installed automatically when the OpenVINO variant is built (`INSTALL_OPENVINO=true`).

## Rationale

- IPEX is the standard PyTorch extension for Intel GPU/XPU support — it's the required bridge
- Adding it to the existing `openvino` extras group keeps the dependency scoped correctly (CPU builds unaffected)
- IPEX 2.8.0 resolves cleanly with torch 2.10.0 — no version pinning needed
- No Dockerfile or application code changes required — the existing `uv sync --extra openvino` picks it up

## Impact

- OpenVINO image size will increase (IPEX adds ~50-100MB of compiled extensions)
- CPU-only builds are completely unaffected
- Existing Intel GPU override (`docker-compose.intel.override.yml`) works without changes
