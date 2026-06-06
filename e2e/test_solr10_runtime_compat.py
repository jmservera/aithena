"""Gated live E2E checks for Solr 10 runtime compatibility.

These tests are opt-in until the Solr 10 stack is available. Set
E2E_SOLR_EXPECTED_MAJOR=10 when running the E2E suite against a Solr 10 fixture.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import requests

SOLR_SEARCH_TESTS_DIR = Path(__file__).resolve().parents[1] / "src" / "solr-search" / "tests"
sys.path.append(str(SOLR_SEARCH_TESTS_DIR))

from solr10_gates import assert_supported_solr10_scalar_bits  # noqa: E402

EXPECTED_MAJOR_ENV = "E2E_SOLR_EXPECTED_MAJOR"

pytestmark = [pytest.mark.e2e, pytest.mark.solr10]


def _require_expected_solr10() -> None:
    expected = os.environ.get(EXPECTED_MAJOR_ENV)
    if expected != "10":
        pytest.skip(f"Set {EXPECTED_MAJOR_ENV}=10 to enable Solr 10 runtime compatibility checks")


def _solr_admin_url(solr_url: str, path: str) -> str:
    collection_suffix = "/books"
    base = solr_url.rstrip("/").removesuffix(collection_suffix).rstrip("/")
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
    try:
        body = resp.json()
    except ValueError as exc:
        pytest.fail(f"{EXPECTED_MAJOR_ENV}=10 requires Solr to return JSON at {url}: {exc}")
    assert isinstance(body, dict), f"Expected Solr JSON object, got {type(body)}"
    return body


def _request_live_solr10(
    method: str,
    url: str,
    *,
    auth: tuple[str, str] | None = None,
    params: Mapping[str, str] | None = None,
    json: Mapping[str, Any] | None = None,
) -> requests.Response:
    _require_expected_solr10()
    try:
        return requests.request(method, url, auth=auth, params=params, json=json, timeout=10)
    except requests.RequestException as exc:
        pytest.fail(f"{EXPECTED_MAJOR_ENV}=10 requires a reachable Solr 10 fixture at {url}: {exc}")


def _summarize_collection_health(body: Mapping[str, Any]) -> str:
    collection = body.get("cluster", {}).get("collections", {}).get("books", {})
    shards = collection.get("shards", {})
    replica_states = []
    for shard_name, shard in shards.items():
        replicas = shard.get("replicas", {})
        for replica_name, replica in replicas.items():
            replica_states.append(f"{shard_name}/{replica_name}={replica.get('state')}")
    health = collection.get("health", "missing")
    return f"health={health}, replicas={','.join(replica_states) or 'none'}"


@pytest.fixture(scope="session")
def solr_books_collection_ready(solr_url: str, solr_auth: tuple[str, str]) -> dict[str, Any]:
    """Wait until the live books collection is fully active, not merely created."""
    _require_expected_solr10()
    base = solr_url.rstrip("/").removesuffix("/books").rstrip("/")
    url = f"{base}/admin/collections"
    params = {"action": "CLUSTERSTATUS", "collection": "books", "wt": "json"}
    deadline = time.monotonic() + int(os.environ.get("E2E_SOLR_READY_TIMEOUT", "90"))
    last_status = "not checked"

    while time.monotonic() < deadline:
        response = _request_live_solr10("GET", url, params=params, auth=solr_auth)
        if response.status_code == 200:
            try:
                body = response.json()
            except ValueError:
                last_status = f"non-JSON response: {response.text[:200]}"
            else:
                last_status = _summarize_collection_health(body)
                collection = body.get("cluster", {}).get("collections", {}).get("books")
                if collection and collection.get("health") == "GREEN":
                    return body
        else:
            last_status = f"HTTP {response.status_code}: {response.text[:200]}"
        time.sleep(2)

    pytest.fail(f"Solr 10 books collection did not become GREEN before live checks: {last_status}")


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


def test_opt_in_non_json_solr10_fixture_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once opted in, a non-JSON Solr response must fail with endpoint context."""
    monkeypatch.setenv(EXPECTED_MAJOR_ENV, "10")

    class _NonJsonResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            raise ValueError("not json")

    def _get_non_json(*_args: Any, **_kwargs: Any) -> _NonJsonResponse:
        return _NonJsonResponse()

    monkeypatch.setattr(requests, "get", _get_non_json)

    with pytest.raises(pytest.fail.Exception, match="requires Solr to return JSON"):
        _get_live_solr10_json("http://127.0.0.1:8983/solr/books/admin/ping")


def test_live_solr_major_version_is_10(solr_system_info: dict[str, Any]) -> None:
    """The opt-in Solr 10 fixture must actually run Solr 10."""
    version = str(solr_system_info.get("lucene", {}).get("solr-spec-version", ""))
    assert version.startswith("10."), f"Expected Solr 10.x, got {version!r}"


def test_live_solr10_schema_exposes_scalar_quantized_vector(
    solr_url: str,
    solr_auth: tuple[str, str],
    solr_books_collection_ready: dict[str, Any],
) -> None:
    """The live Solr 10 books schema must expose the native int8 vector field type."""
    field_url = f"{solr_url}/schema/fieldtypes/knn_vector_768_byte"
    field_resp = _request_live_solr10("GET", field_url, params={"wt": "json"}, auth=solr_auth)
    if field_resp.status_code == 404 and os.environ.get("VECTOR_QUANTIZATION", "none") != "int8":
        pytest.skip("VECTOR_QUANTIZATION=none removes the scalar-quantized byte vector field from the live schema")
    field_resp.raise_for_status()
    body = _get_live_solr10_json(
        field_url,
        params={"wt": "json"},
        auth=solr_auth,
    )
    field_type = body.get("fieldType", {})
    assert field_type.get("class") == "solr.ScalarQuantizedDenseVectorField"
    assert_supported_solr10_scalar_bits(field_type.get("bits"))
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

    _get_live_solr10_json(_solr_admin_url(solr_url, "admin/info/health"))


def test_live_solr10_security_enforces_rbac(
    solr_url: str,
    solr_auth: tuple[str, str],
    solr_books_collection_ready: dict[str, Any],
) -> None:
    """The final Solr 10 candidate must block unauth/admin mutations while preserving health/metrics."""
    base = solr_url.rstrip("/").removesuffix("/books").rstrip("/")
    probe_suffix = f"{int(time.time())}_{os.getpid()}"
    probe_collection = f"audit_probe_{probe_suffix}"
    probe_user = f"audit_probe_{probe_suffix}"
    readonly_auth = (
        os.environ.get("SOLR_READONLY_USER", "solr_read"),
        os.environ.get("SOLR_READONLY_PASS", "SolrRead_dev2024!"),
    )

    unauth_admin = _request_live_solr10("GET", f"{base}/admin/info/system", params={"wt": "json"})
    assert unauth_admin.status_code in (401, 403)

    health = _request_live_solr10("GET", f"{base}/admin/info/health")
    assert health.status_code == 200

    metrics = _request_live_solr10("GET", f"{base}/admin/metrics", params={"wt": "prometheus"})
    assert metrics.status_code == 200

    readonly_query = _request_live_solr10(
        "GET",
        f"{solr_url}/select",
        auth=readonly_auth,
        params={"q": "*:*", "rows": "0", "wt": "json"},
    )
    assert readonly_query.status_code == 200

    readonly_collection_create = None
    try:
        readonly_collection_create = _request_live_solr10(
            "GET",
            f"{base}/admin/collections",
            auth=readonly_auth,
            params={
                "action": "CREATE",
                "name": probe_collection,
                "collection.configName": "books",
                "numShards": "1",
                "replicationFactor": "1",
                "wt": "json",
            },
        )
    finally:
        _request_live_solr10(
            "GET",
            f"{base}/admin/collections",
            auth=solr_auth,
            params={"action": "DELETE", "name": probe_collection, "wt": "json"},
        )
    assert readonly_collection_create is not None
    assert readonly_collection_create.status_code in (401, 403), readonly_collection_create.text

    readonly_security_edit = None
    try:
        readonly_security_edit = _request_live_solr10(
            "POST",
            f"{base}/admin/authentication",
            auth=readonly_auth,
            params={"wt": "json"},
            json={"set-user": {probe_user: "blocked"}},
        )
    finally:
        _request_live_solr10(
            "POST",
            f"{base}/admin/authentication",
            auth=solr_auth,
            params={"wt": "json"},
            json={"delete-user": [probe_user]},
        )
    assert readonly_security_edit is not None
    assert readonly_security_edit.status_code in (401, 403), readonly_security_edit.text

    create_probe = _request_live_solr10(
        "POST",
        f"{base}/admin/authentication",
        auth=solr_auth,
        params={"wt": "json"},
        json={"set-user": {probe_user: "AuditProbe_test_2026!"}},
    )
    try:
        assert create_probe.status_code == 200, create_probe.text
    finally:
        delete_probe = _request_live_solr10(
            "POST",
            f"{base}/admin/authentication",
            auth=solr_auth,
            params={"wt": "json"},
            json={"delete-user": [probe_user]},
        )
        if create_probe.status_code == 200:
            assert delete_probe.status_code == 200, delete_probe.text
