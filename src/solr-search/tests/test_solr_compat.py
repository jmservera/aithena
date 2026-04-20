"""Tests for the Solr 9/10 compatibility layer (solr_compat)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import solr_compat


@pytest.fixture(autouse=True)
def _reset_cache():
    """Clear the cached Solr version before each test."""
    solr_compat.reset_cached_version()
    yield
    solr_compat.reset_cached_version()


# ---------------------------------------------------------------------------
# Version detection
# ---------------------------------------------------------------------------


class TestDetectSolrVersion:
    """Tests for detect_solr_version()."""

    def test_env_var_9(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "9")
        assert solr_compat.detect_solr_version() == 9

    def test_env_var_10(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "10")
        assert solr_compat.detect_solr_version() == 10

    def test_env_var_takes_precedence_over_api(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "10")
        # Even if we pass a URL, env var wins
        assert solr_compat.detect_solr_version(solr_url="http://solr:8983/solr") == 10

    def test_invalid_env_var_falls_through(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "invalid")
        # No URL → default to 9
        assert solr_compat.detect_solr_version() == 9

    def test_empty_env_var_falls_through(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "")
        assert solr_compat.detect_solr_version() == 9

    def test_no_env_no_url_defaults_to_9(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("SOLR_VERSION", raising=False)
        assert solr_compat.detect_solr_version() == 9

    @patch("requests.get")
    def test_api_detection_solr_9(self, mock_get, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("SOLR_VERSION", raising=False)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"lucene": {"solr-spec-version": "9.7.0"}}
        mock_get.return_value = mock_resp
        assert solr_compat.detect_solr_version(solr_url="http://solr:8983/solr") == 9

    @patch("requests.get")
    def test_api_detection_solr_10(self, mock_get, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("SOLR_VERSION", raising=False)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"lucene": {"solr-spec-version": "10.0.0"}}
        mock_get.return_value = mock_resp
        assert solr_compat.detect_solr_version(solr_url="http://solr:8983/solr") == 10

    @patch("requests.get")
    def test_api_failure_defaults_to_9(self, mock_get, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("SOLR_VERSION", raising=False)
        mock_get.side_effect = Exception("Connection refused")
        assert solr_compat.detect_solr_version(solr_url="http://solr:8983/solr") == 9


# ---------------------------------------------------------------------------
# Cached version
# ---------------------------------------------------------------------------


class TestGetSolrVersion:
    """Tests for get_solr_version() caching."""

    def test_caches_result(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "10")
        assert solr_compat.get_solr_version() == 10
        # Change env var — cached value should persist
        monkeypatch.setenv("SOLR_VERSION", "9")
        assert solr_compat.get_solr_version() == 10

    def test_reset_clears_cache(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "10")
        solr_compat.get_solr_version()
        solr_compat.reset_cached_version()
        monkeypatch.setenv("SOLR_VERSION", "9")
        assert solr_compat.get_solr_version() == 9


class TestIsSolr10:
    """Tests for is_solr_10()."""

    def test_is_solr_10_true(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "10")
        assert solr_compat.is_solr_10() is True

    def test_is_solr_10_false(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "9")
        assert solr_compat.is_solr_10() is False


# ---------------------------------------------------------------------------
# HNSW parameters
# ---------------------------------------------------------------------------


class TestHnswParams:
    """Tests for hnsw_params()."""

    def test_solr_9_param_names(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "9")
        result = solr_compat.hnsw_params(max_connections=16, beam_width=100)
        assert result == {"hnswMaxConnections": 16, "hnswBeamWidth": 100}

    def test_solr_10_param_names(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "10")
        result = solr_compat.hnsw_params(max_connections=16, beam_width=100)
        assert result == {"maxConnections": 16, "beamWidth": 100}

    def test_custom_values(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "9")
        result = solr_compat.hnsw_params(max_connections=32, beam_width=200)
        assert result == {"hnswMaxConnections": 32, "hnswBeamWidth": 200}


# ---------------------------------------------------------------------------
# Dense vector field type
# ---------------------------------------------------------------------------


class TestDenseVectorFieldType:
    """Tests for dense_vector_field_type()."""

    def test_defaults_no_hnsw_params(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "9")
        result = solr_compat.dense_vector_field_type()
        assert result == {
            "name": "knn_vector_768",
            "class": "solr.DenseVectorField",
            "vectorDimension": 768,
            "similarityFunction": "cosine",
            "knnAlgorithm": "hnsw",
        }
        # No HNSW params when not specified
        assert "hnswMaxConnections" not in result
        assert "hnswBeamWidth" not in result

    def test_with_hnsw_params_solr_9(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "9")
        result = solr_compat.dense_vector_field_type(
            hnsw_max_connections=32,
            hnsw_beam_width=200,
        )
        assert result["hnswMaxConnections"] == 32
        assert result["hnswBeamWidth"] == 200
        assert "maxConnections" not in result

    def test_with_hnsw_params_solr_10(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "10")
        result = solr_compat.dense_vector_field_type(
            hnsw_max_connections=32,
            hnsw_beam_width=200,
        )
        assert result["maxConnections"] == 32
        assert result["beamWidth"] == 200
        assert "hnswMaxConnections" not in result

    def test_custom_field_name_and_dims(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SOLR_VERSION", "9")
        result = solr_compat.dense_vector_field_type(
            name="custom_vector",
            vector_dimension=384,
            similarity_function="dot_product",
        )
        assert result["name"] == "custom_vector"
        assert result["vectorDimension"] == 384
        assert result["similarityFunction"] == "dot_product"
