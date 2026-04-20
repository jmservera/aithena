"""Vector quantization utilities for embedding storage optimization.

Supports three modes:
- ``none``:  float32 pass-through (default)
- ``fp16``:  reduced precision (float16 → float32 round-trip)
- ``int8``:  scaled to [-128, 127] for Solr ``ByteEncoding``
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

_VALID_MODES = {"none", "fp16", "int8"}


def quantize_embedding(embedding: np.ndarray, mode: str) -> tuple[np.ndarray, str]:
    """Quantize embedding vector based on *mode*.

    Returns:
        ``(quantized_vector, solr_field_name)`` tuple.

        - ``none``:  float32 pass-through → ``'embedding'``
        - ``fp16``:  float16 reduced precision → ``'embedding'``
        - ``int8``:  scaled to [-128, 127] → ``'embedding_byte'``

    Raises:
        ValueError: If *mode* is not one of the supported values.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"Unknown quantization mode '{mode}'; expected one of {_VALID_MODES}")

    if mode == "none":
        return embedding, "embedding"

    if mode == "fp16":
        quantized = embedding.astype(np.float16).astype(np.float32)
        return quantized, "embedding"

    # int8: scale to [-128, 127]
    quantized = np.clip(np.round(embedding * 127), -128, 127).astype(np.int8)
    return quantized, "embedding_byte"


def validate_quantization_quality(
    original: np.ndarray,
    quantized: np.ndarray,
    *,
    threshold: float = 0.01,
) -> float:
    """Compute cosine similarity between *original* and *quantized*.

    Logs a warning when degradation exceeds *threshold* (i.e. similarity
    drops below ``1 - threshold``).

    Returns:
        The cosine similarity (0.0 – 1.0).
    """
    orig_f = original.astype(np.float64)
    quant_f = quantized.astype(np.float64)

    norm_orig = np.linalg.norm(orig_f)
    norm_quant = np.linalg.norm(quant_f)

    if norm_orig == 0 or norm_quant == 0:
        logger.warning("Zero-norm vector encountered during quantization quality check")
        return 0.0

    similarity = float(np.dot(orig_f, quant_f) / (norm_orig * norm_quant))

    if similarity < 1.0 - threshold:
        logger.warning(
            "Quantization degradation above threshold: cosine_sim=%.6f (threshold=%.4f)",
            similarity,
            threshold,
        )

    return similarity
