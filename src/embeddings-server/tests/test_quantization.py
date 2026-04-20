"""Tests for the vector quantization module."""

from __future__ import annotations

import logging

import numpy as np
import pytest
from quantization import (
    quantize_embedding,
    validate_quantization_quality,
)


@pytest.fixture()
def random_embedding():
    """A random 512-d float32 embedding roughly unit-norm."""
    rng = np.random.default_rng(42)
    vec = rng.standard_normal(512).astype(np.float32)
    vec /= np.linalg.norm(vec)
    return vec


# ---------------------------------------------------------------------------
# Mode: none
# ---------------------------------------------------------------------------


class TestNoneMode:
    def test_identity(self, random_embedding):
        result, field = quantize_embedding(random_embedding, "none")
        np.testing.assert_array_equal(result, random_embedding)

    def test_field_name(self, random_embedding):
        _, field = quantize_embedding(random_embedding, "none")
        assert field == "embedding"

    def test_dtype_unchanged(self, random_embedding):
        result, _ = quantize_embedding(random_embedding, "none")
        assert result.dtype == random_embedding.dtype


# ---------------------------------------------------------------------------
# Mode: fp16
# ---------------------------------------------------------------------------


class TestFp16Mode:
    def test_field_name(self, random_embedding):
        _, field = quantize_embedding(random_embedding, "fp16")
        assert field == "embedding"

    def test_output_dtype_is_float32(self, random_embedding):
        result, _ = quantize_embedding(random_embedding, "fp16")
        assert result.dtype == np.float32

    def test_high_similarity(self, random_embedding):
        result, _ = quantize_embedding(random_embedding, "fp16")
        sim = validate_quantization_quality(random_embedding, result)
        assert sim > 0.99

    def test_some_precision_lost(self, random_embedding):
        """fp16 should not be bit-for-bit identical to the original."""
        result, _ = quantize_embedding(random_embedding, "fp16")
        assert not np.array_equal(result, random_embedding)


# ---------------------------------------------------------------------------
# Mode: int8
# ---------------------------------------------------------------------------


class TestInt8Mode:
    def test_field_name(self, random_embedding):
        _, field = quantize_embedding(random_embedding, "int8")
        assert field == "embedding_byte"

    def test_output_dtype(self, random_embedding):
        result, _ = quantize_embedding(random_embedding, "int8")
        assert result.dtype == np.int8

    def test_values_in_range(self, random_embedding):
        result, _ = quantize_embedding(random_embedding, "int8")
        assert result.min() >= -128
        assert result.max() <= 127

    def test_shape_preserved(self, random_embedding):
        result, _ = quantize_embedding(random_embedding, "int8")
        assert result.shape == random_embedding.shape


# ---------------------------------------------------------------------------
# Invalid mode
# ---------------------------------------------------------------------------


class TestInvalidMode:
    def test_raises_value_error(self, random_embedding):
        with pytest.raises(ValueError, match="Unknown quantization mode"):
            quantize_embedding(random_embedding, "bfloat16")


# ---------------------------------------------------------------------------
# Quality validation
# ---------------------------------------------------------------------------


class TestQualityValidation:
    def test_identical_vectors(self, random_embedding):
        sim = validate_quantization_quality(random_embedding, random_embedding)
        assert sim == pytest.approx(1.0)

    def test_warns_on_degradation(self, random_embedding, caplog):
        """When quantized vector is very different, a warning is logged."""
        bad = np.zeros_like(random_embedding)
        bad[0] = 1.0
        with caplog.at_level(logging.WARNING):
            sim = validate_quantization_quality(random_embedding, bad, threshold=0.01)
        assert sim < 0.99
        assert "degradation" in caplog.text.lower()

    def test_zero_norm_returns_zero(self):
        zero = np.zeros(10, dtype=np.float32)
        sim = validate_quantization_quality(zero, zero)
        assert sim == 0.0
