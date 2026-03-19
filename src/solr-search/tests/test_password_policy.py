"""Unit tests for enhanced password validation policy."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from auth import PasswordPolicyError, validate_password  # noqa: E402


def test_valid_password_passes() -> None:
    validate_password("Str0ngPass")  # should not raise


def test_rejects_too_short() -> None:
    with pytest.raises(PasswordPolicyError, match="at least"):
        validate_password("Ab1")


def test_rejects_too_long() -> None:
    with pytest.raises(PasswordPolicyError, match="at most"):
        validate_password("A1" + "a" * 127)


def test_rejects_no_uppercase() -> None:
    with pytest.raises(PasswordPolicyError, match="uppercase"):
        validate_password("alllower1x")


def test_rejects_no_lowercase() -> None:
    with pytest.raises(PasswordPolicyError, match="lowercase"):
        validate_password("ALLUPPER1X")


def test_rejects_no_digit() -> None:
    with pytest.raises(PasswordPolicyError, match="digit"):
        validate_password("NoDigitsHere")


def test_multiple_violations_reported() -> None:
    with pytest.raises(PasswordPolicyError) as exc_info:
        validate_password("short")
    detail = str(exc_info.value)
    # Should report multiple issues
    assert "at least" in detail
    assert "uppercase" in detail
    assert "digit" in detail


def test_exactly_min_length_valid() -> None:
    validate_password("Abcdef1x")  # 8 chars, has upper, lower, digit


def test_exactly_max_length_valid() -> None:
    password = "A1" + "b" * 126
    assert len(password) == 128
    validate_password(password)
