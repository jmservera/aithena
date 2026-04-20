# PRD: GPU Acceleration for Embeddings Server (v1.17.0)

| Field | Value |
|---|---|
| **Author** | Ripley (Lead) |
| **Requested by** | Juanma (jmservera) |
| **Status** | Approved |
| **Target release** | v1.17.0 |
| **Milestone** | 40 |
| **Last updated** | 2026-03-25 |

---

## 1. Executive Summary

The `embeddings-server` service currently runs inference on **CPU only**, limiting indexing throughput for users with available GPU hardware (NVIDIA, Intel GPUs/NPUs). Research in issue #1147 confirmed that:

1. **PyTorch + CUDA support is already installed** — the `torch+cu128` wheel is present in the Dockerfile
2. **`SentenceTransformer` natively supports device and backend parameters** — no code changes required
3. **Single image, configurable approach is optimal** — one Docker image with `DEVICE` and `BACKEND` environment variables controls GPU acceleration without image fragmentation

This PRD proposes to **enable GPU acceleration by default when hardware is available**, with fallback to CPU, via two environment variables:

- `DEVICE` (auto/cpu/cuda/xpu) — controls PyTorch device selection
- `BACKEND` (torch/openvino) — controls inference backend (torch for NVIDIA/CPUs, openvino for Intel GPUs/CPUs)

Users enable GPU support by:
1. Setting environment variables (`DEVICE=auto` and `BACKEND=torch` or `openvino`)
2. Using Docker Compose profiles for device passthrough (`--profile nvidia` or `--profile intel`)

**Target outcomes:**
- 2–4× embedding throughput improvement for users with NVIDIA GPUs
- 1.5–2× improvement for Intel GPU users
- CPU inference unchanged; GPU is purely opt-in via environment variables

---

## 2. Background & Problem Statement

### Current State

The `embeddings-server` service is deployed with PyTorch and CUDA support preinstalled, but **GPU acceleration is never activated**:

- The `sentence-transformers` model is loaded with **no device parameter** — defaults to CPU
- The inference backend defaults to PyTorch's CPU mode
- No Docker Compose profiles exist for GPU device passthrough (nvidia-runtime, Intel compute-runtime)

### Why This Matters

**For users with GPUs:**
- Document indexing is bottlenecked by embedding generation
- A 50,000-document index takes **8–12 hours** on CPU; **2–4 hours** with GPU
- Users cannot leverage available hardware

**For the system:**
- Indexing queues back up, degrading user experience
- No fallback mechanism for systems without GPU support

### Problems

1. **Missed hardware utilization** — CUDA drivers + torch wheels are installed but never used
2. **No configuration path** — Users cannot opt into GPU acceleration; no documentation
3. **No device fallback strategy** — `DEVICE=auto` is not implemented; defaults to CPU
4. **Missing infrastructure** — Docker Compose lacks profiles for nvidia-runtime and intel compute-runtime
5. **Documentation gaps** — User manual and admin manual provide no GPU acceleration guidance

---

## 3. Goals & Non-Goals

### Goals (In Scope for v1.17.0)

- **G1**: Implement `DEVICE` environment variable (auto/cpu/cuda/xpu) with auto-fallback to CPU
- **G2**: Implement `BACKEND` environment variable (torch/openvino) for backend selection
- **G3**: Add OpenVINO library (~150 MB) to embeddings-server Dockerfile for Intel GPU/CPU support
- **G4**: Create Docker Compose profiles for GPU device passthrough:
  - `--profile nvidia` for NVIDIA GPUs (nvidia-runtime)
  - `--profile intel` for Intel GPUs (Intel compute-runtime)
- **G5**: Test GPU acceleration with real embeddings on NVIDIA (A100, RTX3090) and Intel (Arc GPU) hardware
- **G6**: Update user manual with GPU acceleration setup instructions (env vars, Compose profiles, prerequisites)
- **G7**: Update admin manual with GPU troubleshooting, prerequisites (CUDA, Intel compute-runtime), WSL2 setup
- **G8**: Ensure CPU-only deployments are unaffected (backward compatible)

### Non-Goals (Deferred)

- **NG1**: AMD GPU support (ROCM) — defer to v1.18.0 (different CUDA variant needed)
- **NG2**: GPU memory optimization (pruning, quantization) — defer; not required for performance target
- **NG3**: Multi-GPU load balancing — defer; single GPU sufficient for v1.17.0
- **NG4**: Real-time GPU monitoring dashboard — defer to v1.18.0
- **NG5**: GPU cost analysis in admin panel — defer (feature request for future)

---

## 4. User Scenarios

### Scenario 1: NVIDIA User (Consumer GPU)

**User profile:** Data scientist with RTX 3090, wants to index 100K documents locally

**Setup:**
```bash
# Install NVIDIA Container Toolkit on host
curl https://get.docker.com/ | sh
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Enable GPU in docker-compose
export DEVICE=cuda
export BACKEND=torch
docker compose --profile nvidia up
```

**Outcome:** Embeddings generation at ~120 embeddings/sec (vs. ~30 embeddings/sec on CPU).

---

### Scenario 2: Intel Arc GPU User (Enterprise)

**User profile:** Enterprise ops team with Intel Arc GPU in production server, indexing 500K documents

**Setup:**
```bash
# Install Intel compute-runtime on host (oneAPI drivers)
wget -qO - https://repositories.intel.com/graphics/intel-graphics.key | sudo apt-key add -
echo "deb [arch=amd64] https://repositories.intel.com/graphics/ubuntu jammy main" | \
  sudo tee /etc/apt/sources.list.d/intel-graphics.list
sudo apt-get update && sudo apt-get install -y intel-level-zero-loader intel-media-driver

# Enable GPU in docker-compose
export DEVICE=auto
export BACKEND=openvino
docker compose --profile intel up
```

**Outcome:** Embeddings generation at ~80 embeddings/sec. OpenVINO automatically optimizes for Intel GPU.

---

### Scenario 3: Intel CPU Optimization (No GPU)

**User profile:** On-premises server without GPU but with modern Intel Xeon CPU, wants CPU optimization

**Setup:**
```bash
# No GPU device passthrough needed; CPU optimization via OpenVINO
export DEVICE=cpu
export BACKEND=openvino
docker compose up  # no --profile needed
```

**Outcome:** CPU inference optimized via OpenVINO compiler (vectorized operations). ~40–50 embeddings/sec on 16-core Xeon.

---

### Scenario 4: Default CPU Fallback (No Config)

**User profile:** User with no GPU, no special environment variables set

**Setup:**
```bash
# No GPU configuration; defaults to CPU
docker compose up
```

**Outcome:** Embeddings generation on CPU at ~30 embeddings/sec. System operates normally (backward compatible).

---

## 5. Technical Approach

### 5.1 Architecture Decision

**Single image, environment-variable-driven configuration:**

```
embeddings-server Dockerfile
  ├── torch+cu128 (already present)
  ├── openvino (new, ~150 MB)
  └── sentence-transformers
      └── Supports device + backend parameters natively
```

**Configuration flow:**
```
Environment variables (DEVICE, BACKEND)
  ↓
SentenceTransformer initialization
  ├─ device=DEVICE → auto/cpu/cuda/xpu
  ├─ backend=BACKEND → torch/openvino
  └─ Auto-fallback: if DEVICE=auto and CUDA unavailable → CPU
```

### 5.2 Device Variable Semantics

| DEVICE | Behavior | When to Use |
|---|---|---|
| `auto` | Auto-detect: CUDA → GPU; otherwise CPU | **Default (recommended)** |
| `cpu` | Force CPU (no GPU check) | Testing, CPU-only environments |
| `cuda` | NVIDIA GPU (fail if CUDA unavailable) | Known NVIDIA hardware |
| `xpu` | Intel Arc/Xe GPU (fail if unavailable) | Known Intel GPU hardware |

### 5.3 Backend Variable Semantics

| BACKEND | Inference Engine | When to Use |
|---|---|---|
| `torch` | PyTorch native (CUDA/CPU) | NVIDIA GPUs, Intel CPUs (default) |
| `openvino` | OpenVINO IR compiler | Intel GPUs, CPU optimization |

**Note:** `torch` and `openvino` can coexist; the user selects via `BACKEND` env var.

### 5.4 Docker Compose Profiles

**Profile: `nvidia`**
```yaml
services:
  embeddings-server:
    runtime: nvidia
    environment:
      DEVICE: "${DEVICE:-auto}"
      BACKEND: "${BACKEND:-torch}"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

**Profile: `intel`**
```yaml
services:
  embeddings-server:
    devices:
      - /dev/dxg  # Intel GPU device passthrough (WSL2)
    environment:
      DEVICE: "${DEVICE:-auto}"
      BACKEND: "${BACKEND:-openvino}"
```

**Profile: default (no GPU)**
```yaml
# No device passthrough; CPU inference
services:
  embeddings-server:
    environment:
      DEVICE: "${DEVICE:-auto}"
      BACKEND: "${BACKEND:-torch}"
```

### 5.5 Fallback & Error Handling

- **If `DEVICE=auto` and GPU unavailable**: Log WARNING, fall back to CPU (no crash)
- **If `DEVICE=cuda` and CUDA unavailable**: Log ERROR, attempt CPU fallback (graceful)
- **If `BACKEND=openvino` and unavailable**: Log ERROR, attempt torch fallback
- **No silent degradation**: User sees log warnings; health check remains green (embeddings still work)

### 5.6 Implementation Details

**Changes to `embeddings-server`:**

1. **Dockerfile**: Add `pip install openvino==2024.1.0` (pinned version)
2. **inference.py** (or equivalent): Modify model initialization:
   ```python
   device = os.getenv("DEVICE", "auto")
   backend = os.getenv("BACKEND", "torch")
   model = SentenceTransformer(
       model_name,
       device=device,
       backend=backend
   )
   ```
3. **Health check**: Verify embeddings generation works (unchanged)

**Changes to `docker-compose.yml`:**

1. Add `profiles: [nvidia]` to embeddings-server service for NVIDIA profile
2. Add `profiles: [intel]` to embeddings-server service for Intel profile
3. Add device passthrough directives per profile
4. Document usage in compose override files

**No changes required to:**
- FastAPI routes (unchanged)
- Document-indexer (unchanged)
- Solr schema (unchanged)

---

## 6. Implementation Plan with Work Items

### Phase 1: Research & Validation (1–2 days)

**WI-1**: Validate SentenceTransformer device/backend parameters on NVIDIA GPU
- Test `device=cuda` and `device=auto` with actual RTX GPU
- Confirm CUDA detection and fallback behavior
- Measure throughput improvement (target: 2–4×)
- Deliverable: Validation report

**WI-2**: Validate SentenceTransformer device/backend parameters on Intel GPU
- Test `device=xpu` and `backend=openvino` with Intel Arc GPU
- Confirm fallback if Intel runtime unavailable
- Measure throughput improvement
- Deliverable: Validation report

**WI-3**: Evaluate OpenVINO integration
- Measure OpenVINO CPU inference vs. torch CPU (target: 1.5–2× speedup)
- Confirm binary size impact (~150 MB)
- Test openvino fallback to torch
- Deliverable: Benchmark report, openvino version pinned

---

### Phase 2: Implementation (3–4 days)

**WI-4**: Update embeddings-server Dockerfile
- Add `pip install openvino==2024.1.0` to requirements
- Verify image builds cleanly
- Confirm image size within budget
- Deliverable: Dockerfile changes, build logs

**WI-5**: Update inference logic in embeddings-server
- Modify model initialization to accept `DEVICE` and `BACKEND` env vars
- Implement auto-fallback logic (if DEVICE=auto and GPU unavailable → CPU)
- Add logging for device selection and fallback
- Deliverable: Python code changes, unit tests

**WI-6**: Update docker-compose.yml with GPU profiles
- Add `profiles: [nvidia]` to embeddings-server
- Add nvidia runtime and device capability directives
- Add `profiles: [intel]` to embeddings-server
- Add device passthrough directives for Intel GPU
- Deliverable: Compose file changes, tested locally

**WI-7**: Create docker/compose.gpu-nvidia.yml (optional reference)
- Provide example override file for NVIDIA users
- Deliverable: Example file in docs/

---

### Phase 3: Testing & Documentation (2–3 days)

**WI-8**: E2E testing on NVIDIA GPU hardware
- Test `docker compose --profile nvidia up`
- Verify embeddings generation on GPU
- Confirm fallback to CPU if GPU unavailable
- Benchmark throughput
- Deliverable: Test report, screenshots

**WI-9**: E2E testing on Intel GPU hardware
- Test `docker compose --profile intel up`
- Verify embeddings generation on Intel GPU
- Benchmark throughput
- Deliverable: Test report

**WI-10**: Update user manual
- Add "GPU Acceleration" section covering:
  - Prerequisites (CUDA for NVIDIA, Intel compute-runtime for Intel)
  - Environment variable setup (`DEVICE`, `BACKEND`)
  - Docker Compose profile usage
  - Troubleshooting common issues (CUDA not detected, OpenVINO fallback)
  - Example setups for NVIDIA, Intel GPU, Intel CPU optimization
- Deliverable: User manual updated

**WI-11**: Update admin manual
- Add "GPU Troubleshooting" section covering:
  - NVIDIA Container Toolkit installation (all OS variants)
  - Intel compute-runtime installation (Ubuntu, RHEL)
  - WSL2 GPU passthrough (for Windows + WSL2 users)
  - GPU health check endpoints
  - Verifying GPU is being used (via logs)
  - Common issues: CUDA version mismatch, driver outdated, device not found
- Deliverable: Admin manual updated

**WI-12**: Create troubleshooting guide
- Document expected log messages for each scenario (GPU found, fallback to CPU, etc.)
- Common issues and solutions
- Performance expectations by hardware
- Deliverable: Standalone troubleshooting document in docs/guides/

---

### Phase 4: Release & Rollout (1–2 days)

**WI-13**: Release v1.17.0
- Ensure all work items from Phases 1–3 are complete
- Run full release gate (security, performance, architecture review)
- Update CHANGELOG with GPU acceleration feature
- Deliverable: Version bump, release notes, GitHub Release

**WI-14**: Post-release validation
- Monitor production deployments for any GPU initialization issues
- Respond to user GPU setup questions
- Iterate on troubleshooting guide based on feedback
- Deliverable: Feedback log, guide updates

---

## 7. Documentation Requirements

### 7.1 User Manual Updates

**Location:** `docs/quickstart.md` or new `docs/guides/gpu-acceleration.md`

**Sections:**

1. **Introduction & Benefits**
   - Performance improvement expectations (2–4× NVIDIA, 1.5–2× Intel GPU)
   - Hardware requirements (NVIDIA: GPU + CUDA compute capability >= 3.5; Intel: Arc GPU or Xe NPU)

2. **NVIDIA GPU Setup**
   ```bash
   # Prerequisites
   - NVIDIA GPU (GeForce RTX, Tesla, A100, etc.)
   - NVIDIA drivers (version >= 530.00)
   - NVIDIA Container Toolkit
   
   # Installation steps (Linux)
   # Ubuntu/Debian
   curl https://get.docker.com/ | sh
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   ...
   sudo apt-get install -y nvidia-docker2
   
   # Docker Compose
   export DEVICE=cuda
   export BACKEND=torch
   docker compose --profile nvidia up
   ```

3. **Intel GPU Setup**
   ```bash
   # Prerequisites
   - Intel Arc GPU or Intel Xe GPU
   - Intel compute-runtime (oneAPI drivers)
   
   # Installation steps (Ubuntu/Debian)
   wget -qO - https://repositories.intel.com/graphics/intel-graphics.key | sudo apt-key add -
   ...
   
   # Docker Compose
   export DEVICE=auto
   export BACKEND=openvino
   docker compose --profile intel up
   ```

4. **Intel CPU Optimization (No GPU)**
   ```bash
   # For modern Intel Xeon CPUs (optional, non-GPU setup)
   export DEVICE=cpu
   export BACKEND=openvino
   docker compose up
   ```

5. **Environment Variables Reference**
   - `DEVICE`: auto (default), cpu, cuda, xpu
   - `BACKEND`: torch (default), openvino

6. **Troubleshooting**
   - "CUDA not detected" → check drivers, check NVIDIA Container Toolkit
   - "OpenVINO unavailable" → fallback to torch
   - Performance slower than expected → verify GPU is being used (check logs)

### 7.2 Admin Manual Updates

**Location:** `docs/admin-manual.md`

**Sections:**

1. **GPU Troubleshooting & Validation**
   - How to verify GPU is being used (log analysis)
   - Common CUDA issues and solutions
   - Intel compute-runtime installation across OS variants

2. **Prerequisites by Platform**
   - **Linux (Ubuntu/Debian):**
     - NVIDIA Container Toolkit: apt install nvidia-docker2
     - Intel compute-runtime: wget + apt setup
   
   - **Linux (RHEL/CentOS):**
     - NVIDIA: nvidia-docker2 from yum repos
     - Intel: setup Intel repos + dnf install
   
   - **WSL2 (Windows):**
     - GPU passthrough requires WSL2 with NVIDIA-CUDA or Intel GPU support
     - Link to Microsoft WSL GPU documentation

3. **Health Check Endpoints**
   - Endpoint to verify embeddings-server is responding
   - How to verify GPU is active (embedding response time)

4. **Monitoring & Performance**
   - Expected throughput by hardware type
   - How to identify bottlenecks (CPU, GPU memory, I/O)
   - GPU memory utilization monitoring

---

## 8. Testing Strategy

### 8.1 Unit Tests

**Test file:** `tests/test_embeddings_gpu.py`

- Test device selection (auto/cpu/cuda/xpu)
- Test backend selection (torch/openvino)
- Test auto-fallback (DEVICE=auto with no CUDA → CPU)
- Test error handling (invalid device, backend fallback)
- Mock GPU availability for CI environments

### 8.2 Integration Tests

**Test file:** `tests/integration_gpu.py`

- Test embeddings generation on CPU (always runs)
- Test embeddings generation on GPU (skipped if GPU unavailable)
- Test API response time comparison (GPU vs. CPU)
- Verify embedding quality is identical (GPU vs. CPU)

### 8.3 E2E Tests (Manual + Automated)

**Hardware scenarios:**

1. **NVIDIA GPU (A100 or RTX):**
   - Docker compose --profile nvidia with DEVICE=auto, BACKEND=torch
   - Verify 2–4× throughput improvement
   - Verify logs show "Using device: cuda"

2. **Intel Arc GPU:**
   - Docker compose --profile intel with DEVICE=auto, BACKEND=openvino
   - Verify 1.5–2× throughput improvement
   - Verify logs show "Using device: xpu" or "Using backend: openvino"

3. **CPU-only (default fallback):**
   - docker compose up (no --profile)
   - Verify DEVICE=auto falls back to CPU
   - Verify system operates normally

4. **WSL2 + NVIDIA GPU (Windows):**
   - Windows 11 WSL2 with NVIDIA GPU support
   - docker compose --profile nvidia up
   - Verify GPU detection and throughput

### 8.4 Performance Benchmarks

**Baseline (v1.16.0, CPU-only):**
- 50,000-document corpus: ~8–12 hours

**Target (v1.17.0, GPU):**
- NVIDIA GPU: 2–4 hours (2–4× improvement)
- Intel GPU: 3–5 hours (1.5–2× improvement)
- CPU-only: unchanged

**Test methodology:**
- Time 50K document indexing end-to-end
- Measure embeddings-server latency per request (p50, p95, p99)
- Measure GPU memory utilization

---

## 9. Acceptance Criteria

### Must-Have (Blocking Release)

1. ✅ `DEVICE=auto` env var implemented; defaults to auto-detect
2. ✅ `BACKEND` env var implemented; torch and openvino supported
3. ✅ OpenVINO library integrated into Dockerfile (binary size <= 300 MB)
4. ✅ Docker Compose `--profile nvidia` activates nvidia-runtime
5. ✅ Docker Compose `--profile intel` activates device passthrough
6. ✅ GPU fallback to CPU works gracefully (no crashes on missing GPU)
7. ✅ E2E test on NVIDIA GPU shows 2–4× throughput improvement
8. ✅ E2E test on Intel GPU shows 1.5–2× throughput improvement
9. ✅ CPU-only deployment (no GPU) unchanged and backward compatible
10. ✅ User manual updated with GPU acceleration setup (NVIDIA, Intel, CPU optimization)
11. ✅ Admin manual updated with GPU troubleshooting and prerequisites

### Should-Have (High Priority)

12. ✅ Admin manual covers WSL2 GPU setup
13. ✅ Troubleshooting guide created in docs/guides/
14. ✅ CHANGELOG entry for v1.17.0 GPU acceleration feature
15. ✅ Performance benchmarks documented (expected throughput by hardware)

### Nice-to-Have (Future Enhancements)

16. GPU monitoring dashboard in admin panel (v1.18.0)
17. Real-time GPU memory tracking (v1.18.0)
18. AMD ROCm support (v1.18.0)
19. GPU cost analysis for cloud deployments (v2.0)

---

## 10. Success Metrics & Rollback Plan

### Success Metrics

- **GPU detection:** 100% of users with `DEVICE=auto` see correct device (cuda/cpu/xpu)
- **Throughput improvement:** NVIDIA users report 2–4× speedup; Intel GPU users 1.5–2×
- **Backward compatibility:** CPU-only deployments unaffected (0 regressions)
- **Adoption:** >= 30% of on-premises deployments enable GPU within 2 weeks of release
- **Support:** < 5% of GPU setup issues unresolved by user manual

### Rollback Plan

**If GPU acceleration causes issues in production:**

1. Set `DEVICE=cpu` and `BACKEND=torch` in environment (forces CPU)
2. Restart embeddings-server container
3. Verify CPU inference works (logs should show "Using device: cpu")
4. File issue against v1.17.0 with logs and hardware details

**Complete rollback (if needed):**
- Downgrade to v1.16.0 (no GPU support attempted)
- Redeploy without `--profile nvidia` or `--profile intel`

---

## 11. Dependencies & Risks

### Dependencies

- **External:** NVIDIA Container Toolkit (user responsibility for NVIDIA GPU support)
- **External:** Intel compute-runtime (user responsibility for Intel GPU support)
- **Internal:** embeddings-server Dockerfile changes (does not impact other services)
- **Internal:** Docker Compose schema (must support `profiles` keyword — requires Docker Compose v1.28+)

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CUDA version mismatch (CUDA 12.x but torch built for 11.8) | Medium | GPU not detected; silent fallback to CPU | Pin torch and cuda versions; document in admin manual |
| OpenVINO conflicts with PyTorch | Low | Import error; backend unavailable | Test openvino + torch coexistence; fallback to torch |
| Intel GPU driver missing on user system | Medium | Device not found; fallback to CPU | Clear error logging; troubleshooting guide |
| GPU out of memory (OOM) on embedding batch | Low | Inference fails; system goes down | Add per-batch OOM handling; fallback to CPU inference |
| WSL2 GPU passthrough unavailable on Windows | Medium | DEVICE=auto doesn't detect GPU | Document WSL2 GPU setup; link to Microsoft docs |

---

## 12. Appendices

### A. SentenceTransformer Device & Backend Parameters

From `sentence_transformers` documentation:

```python
from sentence_transformers import SentenceTransformer

# Supported devices: "auto", "cpu", "cuda", "xpu", "mps"
# Supported backends: "torch", "openvino"

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device="auto",        # or "cpu", "cuda", "xpu"
    backend="torch"       # or "openvino"
)

embeddings = model.encode(["Hello, world!", "How are you?"])
```

### B. OpenVINO Compatibility Matrix

| Framework | OpenVINO Version | CPU Optimization | GPU Support |
|---|---|---|---|
| PyTorch | 2024.1.0 | ✅ (via torch->ONNX->IR) | ✅ (Intel Arc/Xe) |
| TensorFlow | 2024.1.0 | ✅ | ✅ |
| ONNX | 2024.1.0 | ✅ | ✅ |

**For sentence-transformers:** PyTorch models are automatically optimized by OpenVINO when `backend="openvino"` is set.

### C. Example docker/compose.gpu-nvidia.yml

```yaml
version: '3.8'
services:
  embeddings-server:
    runtime: nvidia
    environment:
      DEVICE: "auto"
      BACKEND: "torch"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

**Usage:**
```bash
docker compose -f docker-compose.yml -f docker/compose.gpu-nvidia.yml up
```

### D. NVIDIA Container Toolkit Installation

**Ubuntu/Debian:**
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
      && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
      && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

**RHEL/CentOS:**
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.repo | \
  sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
sudo yum clean expire-cache
sudo yum install -y nvidia-docker2
sudo systemctl restart docker
```

### E. Intel compute-runtime Installation

**Ubuntu/Debian:**
```bash
wget -qO - https://repositories.intel.com/graphics/intel-graphics.key | sudo apt-key add -
echo "deb [arch=amd64] https://repositories.intel.com/graphics/ubuntu jammy main" | \
  sudo tee /etc/apt/sources.list.d/intel-graphics.list
sudo apt-get update
sudo apt-get install -y intel-level-zero-loader intel-media-driver intel-metrics-discoverer
```

**RHEL/CentOS:**
```bash
sudo dnf install https://repositories.intel.com/graphics/rhel/8/intel-graphics-rhel-8-latest.x86_64.rpm
sudo dnf install -y intel-level-zero intel-metrics-discoverer
```

---

## 13. References

- SentenceTransformer GitHub: https://github.com/UKPLab/sentence-transformers
- OpenVINO Docs: https://docs.openvino.ai/
- NVIDIA Container Toolkit: https://github.com/NVIDIA/nvidia-docker
- Intel Graphics Installation: https://dgpu-docs.intel.com/
- PyTorch Device Selection: https://pytorch.org/docs/stable/tensor_attributes.html#torch.device
