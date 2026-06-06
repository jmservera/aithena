"""Shared Solr 10 test gates."""

from __future__ import annotations

import pytest

SUPPORTED_SOLR10_SCALAR_BITS = {"4", "7"}
SOLR10_BITS_1344_GATE = "GATED: #1344 must keep Solr 10 scalar quantization bits at supported bits 4 or 7"


def assert_supported_solr10_scalar_bits(bits: object) -> None:
    actual = str(bits)
    if actual == "8":
        pytest.skip(SOLR10_BITS_1344_GATE)
    assert actual in SUPPORTED_SOLR10_SCALAR_BITS, (
        "Solr 10 ScalarQuantizedDenseVectorField bits must be one of "
        f"{sorted(SUPPORTED_SOLR10_SCALAR_BITS)}, got {actual!r}"
    )
