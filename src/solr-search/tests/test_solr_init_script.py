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
import subprocess  # nosec B404
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
COMPOSE_PROD_PATH = REPO_ROOT / "docker" / "compose.prod.yml"
SOLR_INIT_SCRIPT_PATH = REPO_ROOT / "docker" / "solr-init.sh"
SECURITY_JSON_PATH = REPO_ROOT / "src" / "solr" / "security.json"
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


def _load_compose(path: Path) -> dict:
    """Load and parse a docker-compose YAML file."""
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_solr_init_shell_script() -> str:
    """Load docker/solr-init.sh script contents."""
    return SOLR_INIT_SCRIPT_PATH.read_text(encoding="utf-8")


def _load_solr_import_script() -> str:
    """Load scripts/solr-import.sh."""
    with open(SOLR_IMPORT_SCRIPT_PATH, encoding="utf-8") as fh:
        return fh.read()


def _load_compose_prod_init_script() -> str:
    """Extract the inline entrypoint script for the prod solr-init service."""
    compose_prod = _load_compose(COMPOSE_PROD_PATH)
    entrypoint = compose_prod.get("services", {}).get("solr-init", {}).get("entrypoint", [])
    assert len(entrypoint) >= 3, f"Unexpected solr-init entrypoint format in {COMPOSE_PROD_PATH.name}: {entrypoint}"
    return entrypoint[2]


def _extract_cli_helper_functions(script: str) -> str:
    """Extract version-aware solr CLI flag helpers from a shell script."""
    normalized = script.replace("$$", "$")
    match = re.search(
        r"solr_major_version\(\) \{.*?solr_dir_flag\(\) \{\n.*?\n\s*\}",
        normalized,
        re.DOTALL,
    )
    assert match, "solr-init script must define Solr CLI compatibility helper functions"
    return match.group(0)


def _evaluate_cli_flags(script: str, solr_version: str) -> list[str]:
    helpers = _extract_cli_helper_functions(script)
    command = f"""
{helpers}
SOLR_VERSION={solr_version}
solr_credentials_flag
solr_zk_host_flag
solr_name_flag
solr_dir_flag
"""
    result = subprocess.run(  # noqa: S603
        ["bash", "-ceu", command],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


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


def test_block_unknown_explicitly_set_to_false_in_init_scripts():
    """All Solr init scripts must explicitly set --block-unknown false."""
    compose_embedded_script = _load_solr_init_script()
    file_script = _load_solr_init_shell_script()
    compose_prod_script = _load_compose_prod_init_script()

    assert "--block-unknown false" in compose_embedded_script, "docker-compose solr-init must set --block-unknown false"
    assert "--block-unknown false" in file_script, "docker/solr-init.sh must set --block-unknown false"
    assert "--block-unknown false" in compose_prod_script, (
        "docker/compose.prod.yml solr-init must set --block-unknown false"
    )


@pytest.mark.parametrize(
    ("script_name", "script"),
    [
        ("docker-compose.yml", _load_solr_init_script()),
        ("docker/compose.prod.yml", _load_compose_prod_init_script()),
        ("docker/solr-init.sh", _load_solr_init_shell_script()),
    ],
)
def test_solr_init_cli_helpers_translate_flags_for_solr_9_and_10(script_name: str, script: str):
    """solr-init must emit Solr 9 flags by default and Solr 10 long flags when requested."""
    assert _evaluate_cli_flags(script, "9") == ["-u", "-z", "-n", "-d"], (
        f"{script_name} must preserve Solr 9 CLI flag compatibility"
    )
    assert _evaluate_cli_flags(script, "10") == ["--credentials", "--zk-host", "--name", "--dir"], (
        f"{script_name} must translate solr CLI flags to Solr 10 double-dash syntax"
    )
    assert _evaluate_cli_flags(script, "10.0.0") == ["--credentials", "--zk-host", "--name", "--dir"], (
        f"{script_name} must accept full Solr 10 version strings"
    )


@pytest.mark.parametrize(
    ("script_name", "script"),
    [
        ("docker-compose.yml", _load_solr_init_script()),
        ("docker/compose.prod.yml", _load_compose_prod_init_script()),
        ("docker/solr-init.sh", _load_solr_init_shell_script()),
    ],
)
def test_solr_init_security_seed_uses_writable_solr_data_path(script_name: str, script: str):
    """Solr 9 init must not seed security.json under unwritable /opt/solr."""
    normalized = script.replace("$$", "$")

    seed_lines = [line for line in normalized.splitlines() if "empty-security.json" in line]

    assert "/opt/solr/empty-security.json" not in normalized, f"{script_name} must not write under /opt/solr"
    assert seed_lines, f"{script_name} must seed security.json before enabling auth"
    assert all("/var/solr/empty-security.json" in line for line in seed_lines), (
        f"{script_name} must only use Solr's writable home directory for the seed security.json"
    )
    assert "echo '{}' > /var/solr/empty-security.json" in normalized, (
        f"{script_name} must create the seed security.json in Solr's writable home directory"
    )
    assert 'solr zk cp file:/var/solr/empty-security.json zk:/security.json "$(solr_zk_host_flag)"' in normalized, (
        f"{script_name} must upload the seed security.json from Solr's writable home directory"
    )


@pytest.mark.parametrize(
    ("script_name", "script"),
    [
        ("docker-compose.yml", _load_solr_init_script()),
        ("docker/compose.prod.yml", _load_compose_prod_init_script()),
        ("docker/solr-init.sh", _load_solr_init_shell_script()),
    ],
)
def test_solr_init_cli_commands_use_compatibility_helpers(script_name: str, script: str):
    """All solr CLI commands affected by Solr 10 must call version-aware flag helpers."""
    normalized = script.replace("$$", "$")

    assert 'solr zk cp file:/var/solr/empty-security.json zk:/security.json "$(solr_zk_host_flag)"' in normalized, (
        f"{script_name} must use the zk-host helper for solr zk cp"
    )
    assert re.search(
        r'"\$\(solr_credentials_flag\)" "\$[{]?SOLR_ADMIN_USER[}]?:\$[{]?SOLR_ADMIN_PASS[}]?"',
        normalized,
    ), f"{script_name} must use the credentials helper for solr auth enable"
    assert re.search(r'solr zk ls /configs "\$\(solr_zk_host_flag\)" "\$[{]?ZK_HOST[}]?"', normalized), (
        f"{script_name} must use the zk-host helper for solr zk ls"
    )
    assert re.search(
        r'solr zk upconfig "\$\(solr_zk_host_flag\)" "\$[{]?ZK_HOST[}]?" '
        r'"\$\(solr_name_flag\)" books "\$\(solr_dir_flag\)" "\$[{]?CONFIGSET_DIR[}]?"',
        normalized,
    ), f"{script_name} must use compatibility helpers for solr zk upconfig"


def test_security_json_explicitly_sets_block_unknown_false():
    """security.json must explicitly keep blockUnknown=false."""
    sec = _load_security_json()
    authentication = sec.get("authentication", {})
    assert "blockUnknown" in authentication, "security.json authentication must include blockUnknown key"
    assert authentication.get("blockUnknown") is False, (
        "security.json authentication.blockUnknown must remain explicitly false"
    )


def test_security_json_allows_unauthenticated_health_and_metrics():
    """Health and metrics endpoints should remain unauthenticated."""
    permissions = _load_security_json().get("authorization", {}).get("permissions", [])
    perm_map = {p["name"]: p.get("role") for p in permissions}

    assert "health" in perm_map, "security.json permissions must include health"
    assert "metrics-read" in perm_map, "security.json permissions must include metrics-read"
    # role: null means unauthenticated access is allowed for these endpoints.
    assert perm_map.get("health") is None, "health permission must allow unauthenticated access (role: null)"
    assert perm_map.get("metrics-read") is None, "metrics-read must allow unauthenticated access (role: null)"


def test_solr_health_checks_use_authenticated_curl():
    """Solr service health checks must authenticate with SOLR_AUTH_USER/PASS.

    Both dev and prod compose variants are expected to define the 3-node Solr
    services using names solr, solr2, solr3.
    """
    for compose_path in (COMPOSE_PATH, COMPOSE_PROD_PATH):
        services = _load_compose(compose_path).get("services", {})
        solr_services = sorted(name for name in services if re.fullmatch(r"solr[0-9]*", name))
        assert solr_services, f"{compose_path.name} has no solr/solr2/solr3 services to validate"

        for service_name in solr_services:
            healthcheck = services.get(service_name, {}).get("healthcheck", {})
            test_cmd = healthcheck.get("test", [])
            healthcheck_command = " ".join(test_cmd) if isinstance(test_cmd, list) else str(test_cmd)
            assert re.search(r"\bcurl\b.*\s-u\s", healthcheck_command), (
                f"{compose_path.name}:{service_name} healthcheck must use curl auth"
            )
            assert "SOLR_AUTH_USER" in healthcheck_command and "SOLR_AUTH_PASS" in healthcheck_command, (
                f"{compose_path.name}:{service_name} healthcheck must use SOLR_AUTH_USER/PASS"
            )
            assert "/solr/admin/info/system" in healthcheck_command, (
                f"{compose_path.name}:{service_name} healthcheck must probe /admin/info/system"
            )
