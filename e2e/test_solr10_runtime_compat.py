"""Gated live E2E checks for Solr 10 runtime compatibility.

These tests are opt-in until the Solr 10 stack is available. Set
E2E_SOLR_EXPECTED_MAJOR=10 when running the E2E suite against a Solr 10 fixture.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import pytest
import requests

EXPECTED_MAJOR_ENV = "E2E_SOLR_EXPECTED_MAJOR"

pytestmark = [pytest.mark.e2e, pytest.mark.solr10]


def _require_expected_solr10() -> None:
    expected = os.environ.get(EXPECTED_MAJOR_ENV)
    if expected != "10":
        pytest.skip(f"Set {EXPECTED_MAJOR_ENV}=10 to enable Solr 10 runtime compatibility checks")


def _solr_admin_url(solr_url: str, path: str) -> str:
    collection_suffix = "/books"
    base = solr_url.removesuffix(collection_suffix).rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def _get_live_solr10_json(
    url: str,
    *,
    auth: tuple[str, str] | None = None,
    params: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    _require_expected_solr10()
    try:
        resp = requests.get(url, auth=auth, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        pytest.fail(f"{EXPECTED_MAJOR_ENV}=10 requires a reachable Solr 10 fixture at {url}: {exc}")
    body = resp.json()
    assert isinstance(body, dict), f"Expected Solr JSON object, got {type(body)}"
    return body


@pytest.fixture(scope="session")
def solr_system_info(solr_url: str, solr_auth: tuple[str, str]) -> dict[str, Any]:
    return _get_live_solr10_json(_solr_admin_url(solr_url, "admin/info/system"), auth=solr_auth)


def test_opt_in_unreachable_solr10_fixture_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once opted in, a missing live Solr 10 fixture must fail instead of skipping."""
    monkeypatch.setenv(EXPECTED_MAJOR_ENV, "10")

    def _raise_connection_error(*_args: Any, **_kwargs: Any) -> requests.Response:
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "get", _raise_connection_error)

    with pytest.raises(pytest.fail.Exception, match="requires a reachable Solr 10 fixture"):
        _get_live_solr10_json("http://127.0.0.1:1/solr/books/admin/ping")


def test_live_solr_major_version_is_10(solr_system_info: dict[str, Any]) -> None:
    """The opt-in Solr 10 fixture must actually run Solr 10."""
    version = str(solr_system_info.get("lucene", {}).get("solr-spec-version", ""))
    assert version.startswith("10."), f"Expected Solr 10.x, got {version!r}"


def test_live_solr10_schema_exposes_scalar_quantized_vector(
    solr_url: str,
    solr_auth: tuple[str, str],
) -> None:
    """The live Solr 10 books schema must expose the native int8 vector field type."""
    body = _get_live_solr10_json(
        f"{solr_url}/schema/fieldtypes/knn_vector_768_byte",
        params={"wt": "json"},
        auth=solr_auth,
    )
    field_type = body.get("fieldType", {})
    assert field_type.get("class") == "solr.ScalarQuantizedDenseVectorField"
    assert str(field_type.get("bits")) == "8"
    assert "hnswMaxConnections" not in field_type
    assert "hnswBeamWidth" not in field_type
    assert field_type.get("hnswM") in (12, "12")


def test_live_solr10_security_allows_health_probe(
    solr_url: str,
    solr_auth: tuple[str, str],
) -> None:
    """Solr 10 auth bootstrap must preserve unauthenticated health checks."""
    auth_body = _get_live_solr10_json(_solr_admin_url(solr_url, "admin/authentication"), auth=solr_auth)
    authentication = auth_body.get("authentication", {})
    assert authentication.get("blockUnknown") is False

    _get_live_solr10_json(_solr_admin_url(solr_url, "admin/info/system"))
