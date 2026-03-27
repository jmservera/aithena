# GPU Acceleration Troubleshooting Guide

This guide helps diagnose and resolve GPU acceleration issues in Aithena's embeddings server. For setup instructions, see the [Admin Manual](../admin-manual.md#gpu-acceleration-setup-v1170).

## Quick Diagnostics

### 1. Check current GPU status

```bash
# Check what device the embeddings server is using
curl -s http://localhost:8080/health | python3 -m json.tool
```

Expected fields:
- `"device": "cuda"` (NVIDIA) or `"device": "xpu"` (Intel) — GPU active
- `"device": "cpu"` — running in CPU mode (fallback or default)
- `"backend": "torch"` (NVIDIA/CPU) or `"backend": "openvino"` (Intel)

### 2. Check container logs

```bash
docker compose logs embeddings-server --tail 50
```

Look for:
- `Loading embedding model: ... (device=cuda, backend=torch)` — GPU config applied
- `Loading embedding model: ... (device=cpu, backend=torch)` — CPU fallback
- `CUDA not available` — NVIDIA driver issue
- `Failed to load embedding model` — critical error

## Common Issues

### NVIDIA GPU Not Detected

**Symptoms:** Health endpoint shows `device: cpu` despite `DEVICE=cuda` in override.

**Diagnosis:**
```bash
# 1. Check host GPU
nvidia-smi

# 2. Check Docker GPU access
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi

# 3. Check override file is loaded
docker compose -f docker-compose.yml -f docker-compose.nvidia.override.yml config | grep -A5 DEVICE
```

**Solutions:**

| Check | Fix |
|-------|-----|
| `nvidia-smi` fails on host | Install/update NVIDIA drivers |
| Docker test fails | Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) |
| Override not in config output | Verify `-f docker-compose.nvidia.override.yml` in your command |
| CUDA version mismatch | Ensure driver supports CUDA 12.x (driver 525.60+) |

### Intel GPU Not Detected

**Symptoms:** Health endpoint shows `device: cpu` despite `DEVICE=xpu`.

**Diagnosis:**
```bash
# 1. Check /dev/dri exists
ls -la /dev/dri/

# 2. Check Intel GPU is recognized
clinfo | head -20

# 3. Check user has video/render group access
groups
```

**Solutions:**

| Check | Fix |
|-------|-----|
| `/dev/dri` missing | Install Intel compute-runtime drivers |
| `clinfo` shows no devices | Install `intel-opencl-icd` and `intel-level-zero-gpu` |
| Permission denied on `/dev/dri` | Add user to `video` and `render` groups |
| WSL2: `/dev/dri` missing | Install Intel GPU drivers on **Windows** host, restart WSL |

### WSL2-Specific Issues

**`/dev/dri` not available in WSL2:**
1. Ensure GPU drivers are installed on the **Windows host** (not inside WSL)
2. Run `wsl --update` to get the latest WSL2 kernel
3. Restart WSL: `wsl --shutdown` then reopen

**NVIDIA: `nvidia-smi` works on host but not in Docker:**
1. Install NVIDIA Container Toolkit inside WSL
2. Configure Docker runtime: `sudo nvidia-ctk runtime configure --runtime=docker`
3. Restart Docker: `sudo systemctl restart docker`

**Intel: `/dev/dri/renderD128` missing:**
1. This requires recent Intel GPU drivers on Windows
2. Check Windows Device Manager → Display adapters for Intel GPU
3. Update Intel driver from [Intel Download Center](https://www.intel.com/content/www/us/en/download-center/home.html)

### Container Crashes on Startup

**Symptoms:** embeddings-server restarts repeatedly with GPU enabled.

**Diagnosis:**
```bash
docker compose logs embeddings-server --tail 100 | grep -i "error\|fail\|cuda\|xpu"
```

**Common causes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `CUDA out of memory` | GPU VRAM insufficient | Model needs ~1.5GB VRAM. Close other GPU apps. |
| `RuntimeError: No CUDA GPUs are available` | Docker can't see GPU | Reinstall NVIDIA Container Toolkit |
| `ImportError: openvino` | OpenVINO runtime broken | Rebuild the image or check Python environment |
| `xpu` device errors | Intel compute-runtime version mismatch | Update to latest compute-runtime |

### Performance Not Improved

**Symptoms:** GPU is active but indexing isn't faster.

**Checks:**
1. Verify GPU is actually being used: `nvidia-smi` during indexing should show GPU utilization
2. Check bottleneck isn't elsewhere: Solr indexing, PDF extraction, or network I/O
3. Ensure batch sizes are reasonable: the document indexer batches embeddings (check `BATCH_SIZE`)
4. For Intel + OpenVINO: first run may be slow due to model compilation/caching

### Falling Back to CPU

If GPU issues persist and you need the system running:

```bash
# Remove the GPU override — back to CPU mode
docker compose up -d
# Or explicitly set CPU:
DEVICE=cpu docker compose up -d
```

CPU mode is always stable. GPU acceleration is purely opt-in.

## Environment Variable Reference

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `DEVICE` | `auto`, `cpu`, `cuda`, `xpu` | `cpu` | Compute device for embeddings |
| `BACKEND` | `torch`, `openvino` | `torch` | Inference backend |

## Log Messages Reference

| Log message | Meaning |
|-------------|---------|
| `Loading embedding model: X (device=cuda, backend=torch)` | NVIDIA GPU active |
| `Loading embedding model: X (device=xpu, backend=openvino)` | Intel GPU active |
| `Loading embedding model: X (device=cpu, backend=torch)` | CPU mode (default) |
| `Model loaded successfully: X (embedding_dim=768)` | Model ready |
| `Failed to load embedding model` | Critical — check drivers |

## Getting Help

1. Check this guide first
2. Review container logs: `docker compose logs embeddings-server`
3. File an issue at the project repository with:
   - Output of `docker compose logs embeddings-server --tail 100`
   - Output of `nvidia-smi` or `ls -la /dev/dri/`
   - Your Docker Compose command
   - Host OS and GPU model
