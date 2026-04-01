"""Tests for Solr credential management in the installer (issue #1287).

These tests verify that build_env_values(), write_env_file(), and load_env_file()
properly handle SOLR_ADMIN_USER, SOLR_ADMIN_PASS, SOLR_READONLY_USER, and
SOLR_READONLY_PASS. If the fix for #1287 has not been applied yet, some tests
will fail with clear messages indicating what's missing.
"""

from __future__ import annotations

from pathlib import Path

from setup import (
    build_env_values,
    load_env_file,
    write_env_file,
)

INSECURE_SOLR_ADMIN_PASS = "SolrAdmin_dev2024!"
INSECURE_SOLR_READONLY_PASS = "SolrRead_dev2024!"


# ---------- 1. Generation of Solr passwords from scratch ----------


def test_build_env_values_generates_solr_passwords(minimal_env_args):
    """build_env_values must generate SOLR_ADMIN_PASS and SOLR_READONLY_PASS
    when no existing values are provided."""
    env, _, _ = build_env_values(**minimal_env_args)

    assert "SOLR_ADMIN_PASS" in env, "SOLR_ADMIN_PASS not generated — #1287 fix may not be applied"
    assert env["SOLR_ADMIN_PASS"] != "", "SOLR_ADMIN_PASS must not be empty"
    assert env["SOLR_ADMIN_PASS"] == "generated_32", "Expected deterministic factory output for SOLR_ADMIN_PASS"

    assert "SOLR_READONLY_PASS" in env, "SOLR_READONLY_PASS not generated — #1287 fix may not be applied"
    assert env["SOLR_READONLY_PASS"] != "", "SOLR_READONLY_PASS must not be empty"
    assert env["SOLR_READONLY_PASS"] == "generated_32", "Expected deterministic factory output for SOLR_READONLY_PASS"


# ---------- 2. Preserving existing secure Solr passwords ----------


def test_build_env_values_preserves_existing_solr_passwords(minimal_env_args):
    """Existing secure Solr passwords must be preserved (not regenerated)."""
    minimal_env_args["existing_env"] = {
        "SOLR_ADMIN_PASS": "my_secure_admin_pass_42",
        "SOLR_READONLY_PASS": "my_secure_readonly_pass_99",
        "SOLR_ADMIN_USER": "custom_admin",
        "SOLR_READONLY_USER": "custom_reader",
    }

    env, _, _ = build_env_values(**minimal_env_args)

    assert env.get("SOLR_ADMIN_PASS") == "my_secure_admin_pass_42", (
        "Existing secure SOLR_ADMIN_PASS should be preserved"
    )
    assert env.get("SOLR_READONLY_PASS") == "my_secure_readonly_pass_99", (
        "Existing secure SOLR_READONLY_PASS should be preserved"
    )


# ---------- 3. Rotating insecure Solr passwords ----------


def test_build_env_values_rotates_insecure_solr_passwords(minimal_env_args):
    """Insecure default passwords must be replaced with generated ones."""
    minimal_env_args["existing_env"] = {
        "SOLR_ADMIN_PASS": INSECURE_SOLR_ADMIN_PASS,
        "SOLR_READONLY_PASS": INSECURE_SOLR_READONLY_PASS,
    }

    env, _, _ = build_env_values(**minimal_env_args)

    assert env.get("SOLR_ADMIN_PASS") != INSECURE_SOLR_ADMIN_PASS, (
        f"Insecure SOLR_ADMIN_PASS '{INSECURE_SOLR_ADMIN_PASS}' should be rotated"
    )
    assert env.get("SOLR_READONLY_PASS") != INSECURE_SOLR_READONLY_PASS, (
        f"Insecure SOLR_READONLY_PASS '{INSECURE_SOLR_READONLY_PASS}' should be rotated"
    )
    assert env["SOLR_ADMIN_PASS"] == "generated_32"
    assert env["SOLR_READONLY_PASS"] == "generated_32"


# ---------- 4. Reset forces regeneration ----------


def test_build_env_values_resets_solr_passwords(minimal_env_args):
    """reset=True must regenerate passwords even if existing ones are secure."""
    minimal_env_args["existing_env"] = {
        "SOLR_ADMIN_PASS": "perfectly_secure_admin_pass",
        "SOLR_READONLY_PASS": "perfectly_secure_read_pass",
    }
    minimal_env_args["reset"] = True

    env, _, _ = build_env_values(**minimal_env_args)

    assert env.get("SOLR_ADMIN_PASS") == "generated_32", "SOLR_ADMIN_PASS should be regenerated on reset"
    assert env.get("SOLR_READONLY_PASS") == "generated_32", "SOLR_READONLY_PASS should be regenerated on reset"


# ---------- 5. Round-trip through env file ----------


def test_env_file_contains_solr_credentials(minimal_env_args, tmp_path: Path):
    """Solr credentials must survive write_env_file → load_env_file round-trip."""
    env, _, _ = build_env_values(**minimal_env_args)
    env_path = tmp_path / ".env"

    write_env_file(env_path, env)
    loaded = load_env_file(env_path)

    for key in ("SOLR_ADMIN_USER", "SOLR_ADMIN_PASS", "SOLR_READONLY_USER", "SOLR_READONLY_PASS"):
        assert key in loaded, f"{key} missing from env file — #1287 fix may not be applied"
        assert loaded[key] == env[key], f"{key} value mismatch after round-trip"


# ---------- 6. Default usernames ----------


def test_solr_usernames_have_defaults(minimal_env_args):
    """Default Solr usernames should be 'solr_admin' and 'solr_read'."""
    env, _, _ = build_env_values(**minimal_env_args)

    assert env.get("SOLR_ADMIN_USER") == "solr_admin", "Default SOLR_ADMIN_USER should be 'solr_admin'"
    assert env.get("SOLR_READONLY_USER") == "solr_read", "Default SOLR_READONLY_USER should be 'solr_read'"
