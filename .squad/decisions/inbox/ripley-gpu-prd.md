# Decision: GPU Acceleration PRD for v1.17.0

**Author:** Ripley (Lead)  
**Date:** 2026-03-25  
**Status:** Proposed  
**Impact:** Architecture, release planning, documentation updates  
**Related Issues:** #1148–#1161 (14 work items), PRD: docs/prd/gpu-acceleration.md

---

## Problem

The embeddings-server runs on **CPU only**, limiting indexing throughput for users with available GPU hardware (NVIDIA, Intel). Indexing 50,000 documents takes 8–12 hours on CPU; with GPU it could take 2–4 hours (2–4× improvement). Research in issue #1147 confirmed that PyTorch+CUDA support is already installed in the Dockerfile, but GPU acceleration is never activated.

---

## Decision

**Implement single-image, environment-variable-driven GPU acceleration:**

1. **Single Dockerfile** — One embeddings-server image with:
   - `torch+cu128` wheel (already present)
   - OpenVINO library (~150 MB, new)
   - `sentence-transformers` with native device/backend support

2. **Environment Variables for Configuration:**
   - `DEVICE` (auto/cpu/cuda/xpu) — controls PyTorch device selection; `auto` is default with fallback to CPU
   - `BACKEND` (torch/openvino) — controls inference engine; `torch` is default for NVIDIA/CPUs, `openvino` for Intel GPUs/CPUs

3. **Docker Compose Profiles for Hardware-Specific Setup:**
   - `--profile nvidia` activates nvidia-runtime and GPU capability directives
   - `--profile intel` activates /dev/dri device passthrough for Intel GPU
   - Default (no profile) = CPU-only, unchanged behavior

4. **Auto-Fallback Strategy:**
   - If `DEVICE=auto` and CUDA unavailable → fall back to CPU (graceful, logged)
   - If `BACKEND=openvino` unavailable → fall back to torch
   - No crashes, no silent failures — all transitions logged at INFO/WARNING level

---

## Rationale

### Why Single Image?

**Alternative considered:** Multi-image approach (separate NVIDIA image, Intel image, CPU image)
- **Rejected because:** Doubles CI complexity, complicates version management, increases troubleshooting surface, requires users to know which image to pull

**Selected approach:** Single image with env var configuration
- **Advantages:**
  - One build, one registry entry, one deployment artifact
  - torch+cu128 is already installed (zero cost addition)
  - openvino adds ~150 MB (acceptable; total image << 5 GB)
  - Environment variables are standard Docker practice
  - SentenceTransformer natively supports device/backend parameters (zero code changes)

### Why Docker Compose Profiles?

**Alternative considered:** YAML duplication (separate compose files for nvidia/intel)
- **Rejected because:** Forces users to manage multiple files, error-prone, diff discipline breaks down

**Selected approach:** Profiles
- **Advantages:**
  - Single compose file, clean semantics
  - `--profile nvidia` is discoverable and idiomatic
  - Device passthrough directives (nvidia runtime, /dev/dri) are profile-specific
  - Backward compatible: `docker compose up` (no profile) = CPU-only, unchanged

### Why Auto-Fallback?

**Alternative considered:** Explicit DEVICE (cuda/cpu/xpu only, no auto)
- **Rejected because:** Users would need to pre-check GPU availability, complicates deployment scripts

**Selected approach:** `DEVICE=auto` with graceful fallback
- **Advantages:**
  - "Just works" — set once, system adapts to hardware
  - Clear logging shows what device was selected
  - No crashes on missing GPU; embeddings still work on CPU
  - Aligns with PyTorch best practices

---

## Impact

### Technical

- **Dockerfile:** Add `pip install openvino==2024.1.0` (pinned version)
- **Python code:** Modify model initialization to accept DEVICE/BACKEND env vars (4–5 line change)
- **Docker Compose:** Add profiles and device passthrough directives (16–20 lines per service definition)
- **Documentation:** Add GPU acceleration section to user manual, admin manual, troubleshooting guide (~8 KB total)

### Team

- **Phase 1 (Research, 1–2 days):** Parker or Dallas validates NVIDIA/Intel GPU support, measures throughput
- **Phase 2 (Implementation, 3–4 days):** Ash or Parker updates inference logic; Brett updates Docker Compose
- **Phase 3 (Testing, 2–3 days):** Lambert runs E2E tests; Ash/Dallas update documentation
- **Phase 4 (Release, 1–2 days):** Ripley runs release gate (security, performance, architecture review)

### Risks

| Risk | Mitigation |
|---|---|
| CUDA version mismatch (e.g., CUDA 12.x but torch built for 11.8) | Document CUDA compatibility; add version notes to Dockerfile comments |
| OpenVINO conflicts with PyTorch | Pre-test coexistence; implement fallback chain (openvino → torch) |
| Intel GPU driver missing on user system | Clear error logging; troubleshooting guide with installation links |
| WSL2 GPU passthrough unavailable | Explicit WSL2 section in admin manual; link to Microsoft docs |

---

## Acceptance Criteria

✅ **Must-Have:**
- [ ] DEVICE env var implemented (auto/cpu/cuda/xpu)
- [ ] BACKEND env var implemented (torch/openvino)
- [ ] OpenVINO integrated (binary size <= 300 MB added)
- [ ] Docker Compose profiles for nvidia and intel
- [ ] E2E test on NVIDIA shows 2–4× throughput improvement
- [ ] E2E test on Intel GPU shows 1.5–2× improvement
- [ ] CPU-only deployment backward compatible (zero regressions)
- [ ] User manual updated with GPU setup instructions
- [ ] Admin manual updated with GPU prerequisites and troubleshooting

✅ **Should-Have:**
- [ ] Troubleshooting guide created
- [ ] CHANGELOG updated
- [ ] Performance benchmarks documented

---

## Next Steps

1. **Kickoff Phase 1:** Assign validation work to team members with GPU access
2. **Parallel implementation:** Phase 2 work can proceed during Phase 1 research
3. **Weekly sync:** Review progress against 4-phase timeline
4. **Release gate:** Architecture review before shipping (ensure fallback logic is sound, no silent failures)

---

## References

- **PRD:** docs/prd/gpu-acceleration.md
- **Work Items:** Issues #1148–#1161
- **SentenceTransformer docs:** https://github.com/UKPLab/sentence-transformers
- **OpenVINO docs:** https://docs.openvino.ai/
