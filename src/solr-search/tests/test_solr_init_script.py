"""Tests for solr-init entrypoint script and security.json (issue #1287).

Parses docker-compose.yml to extract the solr-init inline entrypoint script
and verifies that:
- The admin user gets the "admin" role
- The readonly user gets the "readonly" role (not "search")
- The readonly user is created via /admin/authentication
- security.json references the "readonly" role for read operations
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


def test_init_script_assigns_admin_role():
    """solr-init must assign the admin user-role via /admin/authorization."""
    script = _load_solr_init_script()

    # Look for curl to /admin/authorization with set-user-role for admin
    assert "/solr/admin/authorization" in script, "solr-init script missing /admin/authorization call"

    # The admin role should be assigned via "solr auth enable" which creates
    # the admin user with admin role by default. Verify the solr auth enable command.
    assert "solr auth enable" in script, "solr-init script missing 'solr auth enable' command for admin bootstrap"
    assert "--credentials" in script, "solr-init script missing --credentials flag in solr auth enable"
    assert "SOLR_ADMIN_USER" in script, "solr-init script must reference SOLR_ADMIN_USER"


# ---------- 2. Readonly role assignment ----------


def test_init_script_assigns_readonly_role():
    """The readonly user must be assigned the 'readonly' role (not 'search')."""
    script = _load_solr_init_script()

    # Find all set-user-role JSON payloads for the readonly user
    # Pattern: "set-user-role": {"$SOLR_READONLY_USER": ["readonly"]}
    role_assignments = re.findall(r'"set-user-role":\s*\{[^}]*\}', script)
    assert role_assignments, "No set-user-role calls found in solr-init script"

    # Check that the readonly user gets "readonly" role, not "search"
    readonly_assignment = [r for r in role_assignments if "SOLR_READONLY_USER" in r]
    assert readonly_assignment, "No set-user-role for SOLR_READONLY_USER found"

    for assignment in readonly_assignment:
        assert '"readonly"' in assignment, (
            f"Readonly user should be assigned 'readonly' role, not 'search'. "
            f"Found: {assignment} — #1287 fix may not be applied"
        )
        assert '"search"' not in assignment, f"Readonly user should NOT use 'search' role. Found: {assignment}"


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


# ---------- 4. security.json has readonly role ----------


def test_security_json_has_readonly_role():
    """security.json must define permissions that reference the 'readonly' role."""
    sec = _load_security_json()

    auth = sec.get("authorization", {})
    permissions = auth.get("permissions", [])
    assert permissions, "security.json has no permissions defined"

    # Collect all roles referenced in read-type permissions
    read_permissions = [p for p in permissions if p.get("name") == "read"]
    assert read_permissions, "No 'read' permission found in security.json"

    for perm in read_permissions:
        roles = perm.get("role", [])
        if isinstance(roles, str):
            roles = [roles]
        assert "readonly" in roles, f"'read' permission should include 'readonly' role. Found roles: {roles}"
