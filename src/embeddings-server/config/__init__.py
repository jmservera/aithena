import os

EMBEDDINGS_HOST = os.environ.get("EMBEDDINGS_HOST", "localhost")
EMBEDDINGS_PORT = os.environ.get("EMBEDDINGS_PORT", 8000)
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = os.environ.get("QDRANT_PORT", 6333)
STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
STORAGE_CONTAINER = os.environ.get("STORAGE_CONTAINER")
EMBEDDINGS_TIMEOUT = os.environ.get("EMBEDDINGS_TIMEOUT", 30 * 60)  # 30 minutes
CHAT_HOST = os.environ.get("CHAT_HOST", "localhost")
CHAT_PORT = os.environ.get("CHAT_PORT", 8001)
PORT = int(os.environ.get("PORT", 8080))
VERSION = os.environ.get("VERSION", "dev")
GIT_COMMIT = os.environ.get("GIT_COMMIT", "unknown")
BUILD_DATE = os.environ.get("BUILD_DATE", "unknown")
# ADR-004 → updated: multilingual-e5-base replaces distiluse (benchmark #926)
MODEL_NAME = os.environ.get("MODEL_NAME", "intfloat/multilingual-e5-base")

# GPU acceleration config (v1.17.0)
# DEVICE: auto|cpu|cuda|xpu — controls PyTorch device selection
# BACKEND: torch|openvino — controls inference backend
DEVICE = os.environ.get("DEVICE", "cpu")
BACKEND = os.environ.get("BACKEND", "torch")

# Vector quantization mode: none | fp16 | int8
# Controls precision/size trade-off for stored embeddings.
VECTOR_QUANTIZATION = os.environ.get("VECTOR_QUANTIZATION", "none").lower()
