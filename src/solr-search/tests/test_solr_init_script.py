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
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
SECURITY_JSON_PATH = REPO_ROOT / "src" / "solr" / "security.json"


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
