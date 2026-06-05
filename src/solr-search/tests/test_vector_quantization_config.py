from __future__ import annotations

import importlib

import pytest


def _reload_config(monkeypatch: pytest.MonkeyPatch, **env: str):
    import config

    for key in ("VECTOR_QUANTIZATION", "KNN_FIELD", "BOOK_EMBEDDING_FIELD"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(config)


def test_default_vector_fields_use_float_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _reload_config(monkeypatch)

    assert config.settings.vector_quantization == "none"
    assert config.settings.knn_field == "embedding_v"
    assert config.settings.book_embedding_field == "embedding_v"


def test_int8_quantization_defaults_to_byte_vector_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _reload_config(monkeypatch, VECTOR_QUANTIZATION="int8")

    assert config.settings.vector_quantization == "int8"
    assert config.settings.knn_field == "embedding_byte_v"
    assert config.settings.book_embedding_field == "embedding_byte_v"


def test_explicit_vector_fields_override_quantization_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _reload_config(
        monkeypatch,
        VECTOR_QUANTIZATION="int8",
        KNN_FIELD="custom_knn_v",
        BOOK_EMBEDDING_FIELD="custom_book_v",
    )

    assert config.settings.knn_field == "custom_knn_v"
    assert config.settings.book_embedding_field == "custom_book_v"


def test_invalid_vector_quantization_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit, match="Invalid VECTOR_QUANTIZATION"):
        _reload_config(monkeypatch, VECTOR_QUANTIZATION="int4")
