"""Gated live E2E checks for Solr 10 runtime compatibility.

These tests are opt-in until the Solr 10 stack is available. Set
E2E_SOLR_EXPECTED_MAJOR=10 when running the E2E suite against a Solr 10 fixture.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
import requests

EXPECTED_MAJOR_ENV = "E2E_SOLR_EXPECTED_MAJOR"


def _require_expected_solr10() -> None:
    expected = os.environ.get(EXPECTED_MAJOR_ENV)
    if expected != "10":
        pytest.skip(f"Set {EXPECTED_MAJOR_ENV}=10 to enable Solr 10 runtime compatibility checks")


def _solr_admin_url(solr_url: str, path: str) -> str:
    collection_suffix = "/books"
    base = solr_url.removesuffix(collection_suffix).rstrip("/")
    return f"{base}/{path.lstrip('/')}"


@pytest.fixture(scope="session")
def solr_system_info(solr_url: str, solr_auth: tuple[str, str], solr_available: None) -> dict[str, Any]:
    _require_expected_solr10()
    resp = requests.get(_solr_admin_url(solr_url, "admin/info/system"), auth=solr_auth, timeout=10)
    resp.raise_for_status()
    body = resp.json()
    assert isinstance(body, dict), f"Expected system info object, got {type(body)}"
    return body


def test_live_solr_major_version_is_10(solr_system_info: dict[str, Any]) -> None:
    """The opt-in Solr 10 fixture must actually run Solr 10."""
    version = str(solr_system_info.get("lucene", {}).get("solr-spec-version", ""))
    assert version.startswith("10."), f"Expected Solr 10.x, got {version!r}"


def test_live_solr10_schema_exposes_scalar_quantized_vector(
    solr_url: str,
    solr_auth: tuple[str, str],
    solr_available: None,
) -> None:
    """The live Solr 10 books schema must expose the native int8 vector field type."""
    _require_expected_solr10()
    resp = requests.get(
        f"{solr_url}/schema/fieldtypes/knn_vector_768_byte",
        params={"wt": "json"},
        auth=solr_auth,
        timeout=10,
    )
    resp.raise_for_status()
    field_type = resp.json().get("fieldType", {})
    assert field_type.get("class") == "solr.ScalarQuantizedDenseVectorField"
    assert str(field_type.get("bits")) == "8"
    assert "hnswMaxConnections" not in field_type
    assert "hnswBeamWidth" not in field_type
    assert field_type.get("hnswM") in (12, "12")


def test_live_solr10_security_allows_health_probe(
    solr_url: str,
    solr_auth: tuple[str, str],
    solr_available: None,
) -> None:
    """Solr 10 auth bootstrap must preserve unauthenticated health checks."""
    _require_expected_solr10()
    auth_resp = requests.get(_solr_admin_url(solr_url, "admin/authentication"), auth=solr_auth, timeout=10)
    auth_resp.raise_for_status()
    authentication = auth_resp.json().get("authentication", {})
    assert authentication.get("blockUnknown") is False

    health_resp = requests.get(_solr_admin_url(solr_url, "admin/info/system"), timeout=10)
    assert health_resp.status_code == 200
