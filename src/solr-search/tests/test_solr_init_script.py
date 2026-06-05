"""Tests for solr-init entrypoint script and security.json (issue #1287, #1332).

Parses docker-compose.yml to extract the solr-init inline entrypoint script
and verifies that:
- The admin user roles are NOT overwritten (solr auth enable assigns all 4 roles)
- The readonly user gets the "search" role (Solr 9.7 built-in role)
- The readonly user is created via /admin/authentication
- security.json matches Solr 9.7 built-in role hierarchy
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
SECURITY_JSON_PATH = REPO_ROOT / "src" / "solr" / "security.json"
SOLR_INIT_SCRIPT_PATH = REPO_ROOT / "docker" / "solr-init.sh"
SOLR_IMPORT_SCRIPT_PATH = REPO_ROOT / "scripts" / "solr-import.sh"


def _load_solr_init_script() -> str:
    """Extract the inline entrypoint script for the solr-init service."""
    with open(COMPOSE_PATH, encoding="utf-8") as fh:
        compose = yaml.safe_load(fh)

    services = compose.get("services", {})
    solr_init = services.get("solr-init")
    assert solr_init is not None, "solr-init service not found in docker-compose.yml"

    entrypoint = solr_init.get("entrypoint", [])
    # entrypoint format: ["/bin/bash", "-ceu", "<script>"]
    assert len(entrypoint) >= 3, f"Unexpected entrypoint format: {entrypoint}"
    return entrypoint[2]


def _load_security_json() -> dict:
    """Load and parse src/solr/security.json."""
    with open(SECURITY_JSON_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _load_shared_solr_init_script() -> str:
    """Load docker/solr-init.sh."""
    with open(SOLR_INIT_SCRIPT_PATH, encoding="utf-8") as fh:
        return fh.read()


def _load_solr_import_script() -> str:
    """Load scripts/solr-import.sh."""
    with open(SOLR_IMPORT_SCRIPT_PATH, encoding="utf-8") as fh:
        return fh.read()


# ---------- 1. Admin role assignment ----------


def test_init_script_does_not_overwrite_admin_roles():
    """solr-init must NOT overwrite admin roles set by solr auth enable (#1332).

    Solr 9.7's `solr auth enable` assigns ["superadmin", "admin", "search", "index"]
    to the created user. A set-user-role call for the admin user would overwrite these.
    """
    script = _load_solr_init_script()

    # Verify solr auth enable is used for admin bootstrap
    assert "solr auth enable" in script, "solr-init script missing 'solr auth enable' command"
    assert "-u" in script, "solr-init script missing -u flag in solr auth enable"
    assert "SOLR_ADMIN_USER" in script, "solr-init script must reference SOLR_ADMIN_USER"

    # Verify there is NO set-user-role call for the admin user
    role_assignments = re.findall(r'"set-user-role":\s*\{[^}]*\}', script)
    admin_assignments = [r for r in role_assignments if "SOLR_ADMIN_USER" in r]
    assert not admin_assignments, (
        f"solr-init must NOT call set-user-role for admin user — solr auth enable "
        f"already assigns all needed roles. Found: {admin_assignments}"
    )


# ---------- 2. Readonly role assignment ----------


def test_init_script_assigns_readonly_search_role():
    """The readonly user must be assigned the 'search' role (Solr 9.7 built-in)."""
    script = _load_solr_init_script()

    # Find all set-user-role JSON payloads for the readonly user
    role_assignments = re.findall(r'"set-user-role":\s*\{[^}]*\}', script)
    assert role_assignments, "No set-user-role calls found in solr-init script"

    readonly_assignment = [r for r in role_assignments if "SOLR_READONLY_USER" in r]
    assert readonly_assignment, "No set-user-role for SOLR_READONLY_USER found"

    for assignment in readonly_assignment:
        assert '"search"' in assignment, (
            f"Readonly user should be assigned 'search' role (Solr 9.7 built-in). Found: {assignment}"
        )


# ---------- 3. Readonly user creation ----------


def test_init_script_creates_readonly_user():
    """solr-init must create the readonly user via /admin/authentication."""
    script = _load_solr_init_script()

    # Look for set-user call to /admin/authentication for the readonly user
    assert "/solr/admin/authentication" in script, "solr-init script missing /admin/authentication call"

    auth_calls = re.findall(r'curl\s[^|]*?/solr/admin/authentication[^|]*?"set-user"', script, re.DOTALL)
    assert auth_calls, "No 'set-user' call to /admin/authentication found — readonly user creation missing"

    # Verify SOLR_READONLY_USER and SOLR_READONLY_PASS are used
    assert "SOLR_READONLY_USER" in script, "Script must reference SOLR_READONLY_USER"
    assert "SOLR_READONLY_PASS" in script, "Script must reference SOLR_READONLY_PASS"


# ---------- 4. security.json matches Solr 9.7 role hierarchy ----------


def test_security_json_matches_solr97_roles():
    """security.json must use Solr 9.7 built-in role hierarchy."""
    sec = _load_security_json()

    auth = sec.get("authorization", {})
    permissions = auth.get("permissions", [])
    assert permissions, "security.json has no permissions defined"

    # Build permission-to-role map
    perm_map = {p["name"]: p.get("role") for p in permissions}

    # Verify Solr 9.7 role hierarchy
    assert perm_map.get("security-edit") == "superadmin", "security-edit must require superadmin role"
    assert perm_map.get("collection-admin-read") == "search", "collection-admin-read must require search role"
    assert perm_map.get("read") == "search", "read must require search role"
    assert perm_map.get("collection-admin-edit") == "admin", "collection-admin-edit must require admin role"
    assert perm_map.get("update") == "index", "update must require index role"


def test_init_scripts_rewrite_solr10_hnsw_params_for_solr9():
    """Solr 9 bootstrap must rewrite source Solr 10 vector schema names."""
    for script in (_load_solr_init_script(), _load_shared_solr_init_script()):
        assert 'SOLR_VERSION:-9}" = "9"' in script
        assert 'hnswM="/hnswMaxConnections="' in script
        assert 'hnswEfConstruction="/hnswBeamWidth="' in script
        assert 'solr.ScalarQuantizedDenseVectorField"/class="solr.DenseVectorField' in script
        assert 'bits="8"/ vectorEncoding="BYTE' in script
        assert 'solr zk upconfig -z "${ZK_HOST}" -n books -d "${CONFIGSET_DIR}"' in script or (
            'solr zk upconfig -z "$$ZK_HOST" -n books -d "$$CONFIGSET_DIR"' in script
        )


def test_solr_import_configset_upload_stages_solr9_hnsw_rewrite():
    """solr-import --configset-dir must not upload Solr 10 HNSW params to Solr 9."""
    script = _load_solr_import_script()
    assert "stage_configset_for_solr9" in script
    assert 'SOLR_MAJOR_VERSION" -eq 9' in script

    scratch = REPO_ROOT / ".pytest-solr-import-configset" / str(os.getpid())
    config_dir = scratch / "source-configset"
    staged_root = scratch / "staged-root"
    shutil.rmtree(scratch, ignore_errors=True)
    config_dir.mkdir(parents=True)
    staged_root.mkdir(parents=True)
    schema = config_dir / "managed-schema.xml"
    schema.write_text(
        '<schema><fieldType name="knn_vector_768_byte" '
        'class="solr.ScalarQuantizedDenseVectorField" bits="8" '
        'hnswM="12" hnswEfConstruction="100"/></schema>',
        encoding="utf-8",
    )

    try:
        bash = f"""
set -euo pipefail
PROJECT_ROOT={staged_root}
LOG_FILE=/dev/null
eval "$(sed '/^main "\\$@"/,$d' scripts/solr-import.sh)"
staged="$(stage_configset_for_solr9 {config_dir} books)"
test -f "${{staged}}/managed-schema.xml"
grep -q 'hnswMaxConnections="12"' "${{staged}}/managed-schema.xml"
grep -q 'hnswBeamWidth="100"' "${{staged}}/managed-schema.xml"
grep -q 'class="solr.DenseVectorField"' "${{staged}}/managed-schema.xml"
grep -q 'vectorEncoding="BYTE"' "${{staged}}/managed-schema.xml"
! grep -q 'hnswM=' "${{staged}}/managed-schema.xml"
! grep -q 'hnswEfConstruction=' "${{staged}}/managed-schema.xml"
! grep -q 'ScalarQuantizedDenseVectorField' "${{staged}}/managed-schema.xml"
! grep -q 'bits="8"' "${{staged}}/managed-schema.xml"
grep -q 'hnswM="12"' {schema}
grep -q 'ScalarQuantizedDenseVectorField' {schema}
cleanup_staged_configset "$staged"
test ! -d "$staged"
"""
        subprocess.run(  # noqa: S603 - script under test and paths are repo-local fixtures
            ["/bin/bash", "-c", bash],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
