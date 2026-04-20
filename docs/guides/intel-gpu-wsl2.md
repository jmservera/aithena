# Running Aithena with Intel GPU Acceleration on WSL2

This guide walks through setting up Aithena to use Intel Xe/Arc GPU acceleration inside Windows Subsystem for Linux 2 (WSL2). WSL2's GPU passthrough differs significantly from native Linux; this document covers those specific requirements and troubleshooting.

**Estimated setup time:** 20–30 minutes (most spent on driver installation and WSL2 updates).

## Quick Start

If you have an Intel GPU on Windows and WSL2 already configured:

```bash
# On Windows: Install latest Intel GPU driver
# (v30.0.100.9684 or newer recommended)

# In WSL2 Ubuntu:
sudo apt update && sudo apt upgrade -y
sudo wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | \
  sudo gpg --dearmor --output /usr/share/keyrings/intel-graphics.gpg
echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] \
  https://repositories.intel.com/gpu/ubuntu noble unified" | \
  sudo tee /etc/apt/sources.list.d/intel-gpu-noble.list
sudo apt update
sudo apt install -y libze-intel-gpu1 intel-opencl-icd clinfo

# Verify GPU is visible
clinfo | head -20

# Start aithena with Intel GPU
VERSION=1.17.1 docker compose \
  -f docker/compose.prod.yml \
  -f docker/compose.gpu-intel.yml \
  up -d

# Verify GPU is active
curl -s http://localhost:8080/health | python3 -m json.tool | grep -E '"device"|"backend"'
```

---

## Prerequisites

### Windows 11 System

- **OS:** Windows 11 (or Windows 10 21H2+)
- **WSL2:** Latest version (`wsl --update` to upgrade kernel)
- **Intel GPU:** Xe or Arc GPU (Alder Lake or newer)
  - Check Device Manager → Display adapters for "Intel Xe" or "Intel Arc"
- **Intel GPU Driver:** v30.0.100.9684 or newer from [Intel Support](https://www.intel.com/content/www/us/en/support/products/80939/graphics.html)

### Docker Desktop

- **Docker Desktop 4.0+** with WSL2 backend
- GPU resources enabled in Docker Desktop settings:
  - Settings → Resources → WSL integration → Enable GPU support (or equivalent)
  - Restart Docker Desktop after enabling

### WSL2 Linux Environment

- **Ubuntu 24.04 LTS** (recommended; Ubuntu 22.04 LTS also works)
- At least 4 GB RAM allocated to WSL2
- 10 GB free disk space in `/` for GPU driver libraries

---

## Step 1: Install Intel GPU Driver on Windows

Intel GPU acceleration in WSL2 depends on the **Windows host** having the latest driver.

1. Go to [Intel Support — Download Center](https://www.intel.com/content/www/us/en/support/products/80939/graphics.html)
2. Download the **Latest** driver for your GPU model
3. Extract and run the installer on the Windows host
4. **Reboot after installation** — driver must load before WSL2 can access it
5. Verify: Open Device Manager → Display adapters → Should show "Intel Xe" or "Intel Arc" without warnings

---

## Step 2: Update WSL2 Kernel

WSL2's kernel must be recent enough to expose `/dev/dxg` (the GPU device).

```bash
# On Windows (PowerShell, run as Administrator):
wsl --update
wsl --shutdown
```

Restart WSL2 by opening a new Ubuntu terminal or running:

```bash
# In WSL2 (PowerShell or Windows Terminal):
wsl
```

---

## Step 3: Configure Intel GPU Repositories in WSL2

Inside your WSL2 Ubuntu terminal:

```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Add Intel GPU repository key
sudo wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | \
  sudo gpg --dearmor --output /usr/share/keyrings/intel-graphics.gpg

# Add Intel GPU repository (for Ubuntu 24.04 "noble")
echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] \
  https://repositories.intel.com/gpu/ubuntu noble unified" | \
  sudo tee /etc/apt/sources.list.d/intel-gpu-noble.list

# Refresh package lists
sudo apt update
```

**Note:** If you're on Ubuntu 22.04 (Jammy), replace `noble` with `jammy` in the repository line.

---

## Step 4: Install Intel GPU Runtime Packages

```bash
# Install Intel Level Zero GPU driver + OpenCL support
sudo apt install -y libze-intel-gpu1 intel-opencl-icd

# Optional: Install clinfo to verify GPU recognition
sudo apt install -y clinfo

# Optional: Install intel-gpu-tools to monitor GPU (works better on native Linux)
sudo apt install -y intel-gpu-tools
```

---

## Step 5: Verify GPU is Recognized

```bash
clinfo | head -20
```

Expected output (first 20 lines):

```
Number of platforms: 1
  Platform Name                          Intel(R) Graphics Compute Runtime
  ...
  Device 0
    Device Type: GPU
    Max compute units: 32  (or similar)
```

If `clinfo` shows no devices:
- Check that `/dev/dxg` exists: `ls -la /dev/dxg/`
- If missing, the Windows driver isn't loaded or WSL2 isn't seeing it
- Re-run `wsl --update` and `wsl --shutdown`, then restart

---

## Step 6: Start Aithena with Intel GPU

### Option A: Using the Intel Override (Recommended)

The repository includes `docker/compose.gpu-intel.yml` which configures:
- GPU device passthrough (`/dev/dxg`)
- WSL2 GPU library mounting (`/usr/lib/wsl`)
- Environment variables for Intel GPU (`DEVICE=xpu`, `BACKEND=openvino`)

```bash
# Set version (or leave VERSION unset for default)
export VERSION=1.17.1

# Start the stack with Intel GPU enabled
docker compose \
  -f docker/compose.prod.yml \
  -f docker/compose.gpu-intel.yml \
  up -d
```

### Option B: Manual Configuration (If Override Doesn't Work)

If the override isn't available, manually configure in `docker-compose.yml` under `embeddings-server`:

```yaml
embeddings-server:
  image: ghcr.io/aithena-ai/embeddings-server:${VERSION:-latest}
  environment:
    DEVICE: xpu
    BACKEND: openvino
  devices:
    - /dev/dxg  # WSL2 GPU device (NOT /dev/dri)
  volumes:
    - /usr/lib/wsl:/usr/lib/wsl:ro  # WSL2 GPU libraries
```

**Critical differences for WSL2:**
- Device: `/dev/dxg` (not `/dev/dri` — that's native Linux)
- No `render` group needed (WSL2 doesn't use Linux group permissions)
- Must mount `/usr/lib/wsl` (WSL2's GPU runtime libraries)

---

## Step 7: Verify GPU is Active

### Check Health Endpoint

```bash
curl -s http://localhost:8080/health | python3 -m json.tool
```

Look for:

```json
{
  "device": "xpu",
  "backend": "openvino",
  ...
}
```

If showing `"device": "cpu"`, GPU isn't being used. See [Troubleshooting](#troubleshooting).

### Check Container Logs

```bash
docker compose logs embeddings-server --tail 30 | grep -E "Loading|device|backend"
```

Expected:

```
Loading embedding model: bge-small-en-v1.5 (device=xpu, backend=openvino)
```

### Monitor During Initial Run

The first embedding computation will be slow (10–60 seconds) because the model is compiled and cached on the GPU. Subsequent runs are fast.

---

## WSL2 Intel GPU Architecture Overview

Understanding how GPU passthrough works in WSL2 helps with troubleshooting:

1. **Windows GPU Driver** (on the Windows host)
   - Manages the physical Intel GPU
   - Exposed to WSL2 via `/dev/dxg` device

2. **WSL2 Kernel** (Linux side)
   - Presents `/dev/dxg` as a character device
   - Contains stub drivers for GPU communication

3. **WSL2 GPU Libraries** (`/usr/lib/wsl`)
   - User-space GPU runtime libraries
   - Bridge between container processes and Windows GPU driver
   - These MUST be accessible inside the container

4. **Container Runtime** (OpenVINO + compute-runtime)
   - Links against GPU libraries
   - Offloads computation to the GPU via `/dev/dxg`

**Key insight:** Unlike native Linux where `/dev/dri` is the DRM interface, WSL2 uses DirectX internally, and `/dev/dxg` is the abstraction layer. Containers need both the device AND the supporting libraries to communicate with Windows GPU hardware.

---

## Troubleshooting

### `/dev/dxg` Not Found

**Symptoms:**
- Docker fails to start or logs show "Device not found"
- `ls -la /dev/dxg` returns "No such file or directory"

**Fixes (in order):**

1. Update WSL2 kernel:
   ```bash
   # On Windows (PowerShell as Admin):
   wsl --update
   wsl --shutdown
   ```

2. Verify Windows driver is installed and loaded:
   - Open Device Manager on Windows
   - Check Display adapters for Intel GPU (no yellow warning triangle)
   - If missing/warning, reinstall Intel GPU driver and reboot Windows

3. Restart WSL2:
   ```bash
   # On Windows:
   wsl --shutdown
   # Then open a new WSL terminal
   ```

4. If using a workaround (older WSL2), enable GPU support in Windows:
   - Settings → System → For developers → Developer mode (ON)

### GPU Not Detected Inside Container

**Symptoms:**
- Health endpoint shows `"device": "cpu"` despite `DEVICE=xpu`
- Logs show "No Intel GPU found"

**Diagnosis:**

```bash
# Verify GPU is visible on the host
clinfo | grep -i "device\|platform"

# Verify /dev/dxg is mounted in the container
docker exec embeddings-server ls -la /dev/dxg

# Verify GPU libraries are mounted
docker exec embeddings-server ls -la /usr/lib/wsl | head -10
```

**Fixes:**

| Check | Fix |
|-------|-----|
| `clinfo` shows no devices | Run steps 3–4 above (install GPU repositories and runtime) |
| `/dev/dxg` not in container | Verify docker-compose override is being used: `docker compose -f docker/compose.prod.yml -f docker/compose.gpu-intel.yml config \| grep -A5 devices` |
| `/usr/lib/wsl` is empty or missing | Mount is not present; check override file has `volumes: - /usr/lib/wsl:/usr/lib/wsl:ro` |
| Permission denied on `/dev/dxg` | Run Docker daemon as root or configure group access (complex in WSL2; normally not required) |

### Container Crashes on Startup

**Symptoms:**
- embeddings-server restarts in a loop
- Logs show cryptic OpenVINO errors

**Diagnosis:**

```bash
docker compose logs embeddings-server --tail 100 | grep -i "error\|fail\|openvino"
```

**Common errors and fixes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `ImportError: cannot import name 'openvino'` | OpenVINO not installed in image | Use image with OpenVINO pre-installed (check Dockerfile `INSTALL_OPENVINO` build arg) |
| `RuntimeError: Cannot compile model on xpu device` | GPU driver version mismatch | Update Windows Intel driver to v30.0.100.9684+ and `wsl --update` |
| `Segmentation fault` | GPU libraries incompatible | Ensure `/usr/lib/wsl` is from the same WSL2 kernel version |
| `No such device` | `/dev/dxg` not available | Restart WSL: `wsl --shutdown` |

### Model Loading Very Slow

**Symptoms:**
- First embedding request takes 60+ seconds
- Subsequent requests are fast

**This is expected behavior** for Intel GPU + OpenVINO on WSL2:
1. Model is downloaded (~300 MB)
2. Model is converted to OpenVINO IR format
3. IR is compiled for the GPU
4. Compiled cache is stored on disk

**This only happens once per deployment.** Subsequent runs use the cached model.

**If it's stuck longer than 2 minutes:**

```bash
# Check logs for errors
docker compose logs embeddings-server --tail 50

# Check if disk is full
docker exec embeddings-server df -h /tmp

# Restart embeddings-server
docker compose restart embeddings-server
```

### GPU Utilized but Embedding Still Slow

**Symptoms:**
- Health shows GPU is active, but document indexing is slow

**This usually indicates the bottleneck is elsewhere:**
- PDF extraction (CPU-bound)
- Solr indexing (disk I/O)
- Network latency
- Document size/count

**Verify the GPU is actually being used:**

1. During indexing, check GPU load:
   ```bash
   # On Windows, open Task Manager → Performance tab → GPU
   # Should show non-zero utilization during indexing
   ```

   (Note: `intel_gpu_top` inside WSL2 may not work reliably; use Windows Task Manager instead.)

2. Check OpenVINO batch size:
   ```bash
   # Inside embeddings-server container
   env | grep -i batch
   ```

   Larger batches (16–32) use GPU more efficiently than tiny batches (1–4).

3. Profile the indexing pipeline:
   ```bash
   docker compose logs document-indexer --tail 50 | grep -i "time\|batch"
   ```

### `DEVICE=cpu` Despite Setting `DEVICE=xpu`

**Symptoms:**
- Override file specified but GPU still not active
- Health shows CPU

**Fixes (in order):**

1. Verify override file is in the command:
   ```bash
   docker compose config | grep -A10 'embeddings-server:' | grep -i device
   # Should show DEVICE: xpu
   ```

2. Verify devices section is present:
   ```bash
   docker compose config | grep -A20 'embeddings-server:' | grep -A5 devices
   # Should show /dev/dxg
   ```

3. If not present, ensure the command includes the override:
   ```bash
   docker compose -f docker/compose.prod.yml -f docker/compose.gpu-intel.yml config | ...
   ```

4. Alternatively, set environment explicitly:
   ```bash
   DEVICE=xpu BACKEND=openvino docker compose up -d
   ```

### Permissions or Permission Denied Errors

**Symptoms:**
- `Permission denied: /dev/dxg`
- `Cannot open /usr/lib/wsl: Permission denied`

**Context:** WSL2 GPU passthrough is generally permissive (unlike native Linux). Errors here usually indicate:

1. Docker daemon not running: `sudo systemctl start docker`
2. User not in docker group:
   ```bash
   sudo usermod -aG docker $USER
   # Log out and back in
   ```

3. File ownership issue in `/usr/lib/wsl`:
   ```bash
   sudo chmod -R 755 /usr/lib/wsl
   ```

### Model Quantization / Performance Optimization

Intel GPU + OpenVINO benefits from model quantization. If embeddings are still slow even on GPU:

1. Ensure you're using a quantized model:
   ```bash
   # Check embedding model config
   docker exec embeddings-server curl -s http://localhost:8080/health | grep model
   ```

2. For advanced optimization, rebuild the image with OpenVINO quantization:
   - See `src/embeddings-server/Dockerfile` for `INSTALL_OPENVINO` build arg
   - Rebuild with `docker build --build-arg INSTALL_OPENVINO=true ...`

---

## Performance Expectations

On typical Intel Xe/Arc hardware in WSL2:

| Task | CPU (Baseline) | Intel GPU | Speedup |
|------|---|---|---|
| First embedding (1 doc) | 8–15s | 10–60s (model compile + embed) | 1× (slower first time) |
| Batch embedding (100 docs, 32-dim) | 45–90s | 8–15s | 5–10× |
| Index 500 PDFs (avg 50 pages) | 12–18 min | 2–4 min | 4–6× |

**Note:** WSL2 overhead adds ~10–15% latency vs. native Linux GPU.

---

## Disabling GPU (Fallback to CPU)

If GPU issues become blocking:

```bash
# Remove the override — runs on CPU
docker compose -f docker/compose.prod.yml up -d

# Or explicitly:
DEVICE=cpu docker compose -f docker/compose.prod.yml up -d
```

CPU mode is always stable and requires no GPU driver setup.

---

## References

- [Intel oneAPI Installation Guide — WSL2 Configuration](https://www.intel.com/content/www/us/en/docs/oneapi/installation-guide-linux/2023-0/configure-wsl-2-for-gpu-workflows.html)
- [Intel GPU Drivers — Download Center](https://www.intel.com/content/www/us/en/support/products/80939/graphics.html)
- [OpenVINO Docker Setup](https://docs.openvino.ai/2025/get-started/install-openvino/install-openvino-docker-linux.html)
- [OpenVINO Intel GPU Configuration](https://docs.openvino.ai/2024/get-started/configurations/configurations-intel-gpu.html)
- [Intel compute-runtime WSL2 Guide](https://github.com/intel/compute-runtime/blob/master/WSL.md)
- [Aithena Admin Manual — GPU Acceleration](../admin-manual.md#gpu-acceleration-setup-v1170)
- [Aithena GPU Troubleshooting Guide](./gpu-troubleshooting.md)

---

## Getting Help

If you encounter issues not covered here:

1. Check the [GPU Troubleshooting Guide](./gpu-troubleshooting.md) first
2. Review the Admin Manual's [GPU Acceleration Setup](../admin-manual.md#gpu-acceleration-setup-v1170)
3. File an issue with:
   - Output of `clinfo | head -30`
   - Output of `docker compose logs embeddings-server --tail 100`
   - Windows Device Manager screenshot showing GPU
   - Your WSL2 version (`wsl --version`)
   - Docker Desktop version
   - Intel GPU model
