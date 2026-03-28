# Decision: Local Path Loading for Offline HF Models (Supersedes snapshot_download)

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-28
**Status:** Implemented (base image: main, aithena: PR #1259)
**Context:** OpenVINO offline loading fails even with `snapshot_download()` caching

## Problem

The first fix (calling `snapshot_download()` before `SentenceTransformer()`) didn't work. While `snapshot_download()` caches model files, `optimum-intel`'s OpenVINO loading path makes an API call (`tree/main?recursive=True`) that is NOT covered by the snapshot cache. The offline verification step we added caught this failure at build time.

## Decision

1. **Save models to a known local directory** using `model.save('/models/sentence_transformers/{model_name}')` instead of relying on HF Hub cache.
2. **Load from local path at runtime** — when a directory exists at the expected path, pass it to `SentenceTransformer()` instead of the model name. Loading from a local directory bypasses ALL HF Hub API calls.
3. **Remove `snapshot_download()`** — unnecessary when saving to a local directory.
4. **Keep the offline verification step** — validates the local path loads correctly with `HF_HUB_OFFLINE=1`.

## Rationale

- A local directory path is the ONLY reliable way to get zero HF Hub calls with `optimum-intel` + openvino
- `SentenceTransformer('/path/to/model')` never touches the Hub — no metadata, no tree listings, no API calls
- Backward-compatible: if the local path doesn't exist (no base image), falls back to hub download
- The offline verification step caught the `snapshot_download()` failure, proving its value as a build-time safety net

## Impact

- Base image (`embeddings-server-base`): Dockerfile updated, pushed to main
- Aithena (`src/embeddings-server/main.py`): Checks for local path before hub fallback (PR #1259)
- Pattern applies to any future base image that pre-caches HF models for offline use
