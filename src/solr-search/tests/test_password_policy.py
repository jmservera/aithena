"""Comprehensive tests for password_policy module.

Covers: min/max length, all complexity category combinations, username-in-password,
unicode characters, empty/whitespace edge cases, and boundary conditions.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from password_policy import MAX_LENGTH, MIN_COMPLEXITY_CATEGORIES, MIN_LENGTH, validate_password  # noqa: E402, I001


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _is_valid(password: str, username: str = "testuser") -> bool:
    return validate_password(password, username) == []


# ---------------------------------------------------------------------------
# Length enforcement
# ---------------------------------------------------------------------------

class TestMinLength:
    def test_too_short_returns_violation(self) -> None:
        violations = validate_password("Ab1!", "user")
        assert any("at least" in v for v in violations)

    def test_exactly_min_length_passes_length_check(self) -> None:
        password = "Abcdefg1!@"  # 10 chars, 4 categories
        assert len(password) == MIN_LENGTH
        violations = validate_password(password, "other")
        assert not any("at least" in v for v in violations)

    def test_one_below_min_fails(self) -> None:
        password = "Abcdef1!@"  # 9 chars
        assert len(password) == MIN_LENGTH - 1
        violations = validate_password(password, "other")
        assert any("at least" in v for v in violations)

    def test_empty_password_fails(self) -> None:
        violations = validate_password("", "user")
        assert any("at least" in v for v in violations)


class TestMaxLength:
    def test_exactly_max_length_passes_length_check(self) -> None:
        password = "A" * 126 + "1!"  # 128 chars, 3 categories
        assert len(password) == MAX_LENGTH
        violations = validate_password(password, "other")
        assert not any("at most" in v for v in violations)

    def test_one_above_max_fails(self) -> None:
        password = "A" * 127 + "1!"  # 129 chars
        assert len(password) == MAX_LENGTH + 1
        violations = validate_password(password, "other")
        assert any("at most" in v for v in violations)

    def test_way_over_max_fails(self) -> None:
        password = "Aa1!" * 100  # 400 chars
        violations = validate_password(password, "other")
        assert any("at most" in v for v in violations)


# ---------------------------------------------------------------------------
# Complexity (3 of 4 categories required)
# ---------------------------------------------------------------------------

class TestComplexity:
    """Tests for the 3-of-4 complexity rule: uppercase, lowercase, digit, special."""

    # --- All 4 categories (should pass) ---
    def test_all_four_categories(self) -> None:
        assert _is_valid("Abcdefgh1!")

    # --- Exactly 3 categories (should pass) ---
    def test_upper_lower_digit(self) -> None:
        assert _is_valid("Abcdefghi1")

    def test_upper_lower_special(self) -> None:
        assert _is_valid("Abcdefghi!")

    def test_upper_digit_special(self) -> None:
        assert _is_valid("ABCDEFGH1!", "other")

    def test_lower_digit_special(self) -> None:
        assert _is_valid("abcdefgh1!", "other")

    # --- Exactly 2 categories (should fail complexity) ---
    def test_upper_lower_only(self) -> None:
        password = "Abcdefghij"  # 10 chars, upper+lower only
        violations = validate_password(password, "other")
        assert any("categories" in v for v in violations)

    def test_upper_digit_only(self) -> None:
        password = "ABCDEFGHI1"
        violations = validate_password(password, "other")
        assert any("categories" in v for v in violations)

    def test_lower_digit_only(self) -> None:
        password = "abcdefghi1"
        violations = validate_password(password, "other")
        assert any("categories" in v for v in violations)

    def test_upper_special_only(self) -> None:
        password = "ABCDEFGHI!"
        violations = validate_password(password, "other")
        assert any("categories" in v for v in violations)

    def test_lower_special_only(self) -> None:
        password = "abcdefghi!"
        violations = validate_password(password, "other")
        assert any("categories" in v for v in violations)

    def test_digit_special_only(self) -> None:
        password = "123456789!"
        violations = validate_password(password, "other")
        assert any("categories" in v for v in violations)

    # --- Only 1 category (should fail) ---
    def test_only_lowercase(self) -> None:
        violations = validate_password("abcdefghij", "other")
        assert any("categories" in v for v in violations)

    def test_only_uppercase(self) -> None:
        violations = validate_password("ABCDEFGHIJ", "other")
        assert any("categories" in v for v in violations)

    def test_only_digits(self) -> None:
        violations = validate_password("1234567890", "other")
        assert any("categories" in v for v in violations)

    def test_only_special(self) -> None:
        violations = validate_password("!@#$%^&*()", "other")
        assert any("categories" in v for v in violations)


# ---------------------------------------------------------------------------
# Username-in-password (case-insensitive)
# ---------------------------------------------------------------------------

class TestUsernameInPassword:
    def test_exact_username_in_password(self) -> None:
        violations = validate_password("myParkEr123!", "parker")
        assert any("username" in v for v in violations)

    def test_case_insensitive_match(self) -> None:
        violations = validate_password("myPARKER123!", "parker")
        assert any("username" in v for v in violations)

    def test_username_at_start(self) -> None:
        violations = validate_password("Parker12345!", "parker")
        assert any("username" in v for v in violations)

    def test_username_at_end(self) -> None:
        violations = validate_password("Secret1!parker", "parker")
        assert any("username" in v for v in violations)

    def test_no_username_match(self) -> None:
        violations = validate_password("Abcdefgh1!", "other")
        assert not any("username" in v for v in violations)

    def test_empty_username_skips_check(self) -> None:
        violations = validate_password("Abcdefgh1!", "")
        assert not any("username" in v for v in violations)

    def test_single_char_username(self) -> None:
        violations = validate_password("aAbcdefg1!", "a")
        assert any("username" in v for v in violations)


# ---------------------------------------------------------------------------
# Unicode / international characters
# ---------------------------------------------------------------------------

class TestUnicode:
    def test_unicode_special_chars_count_as_special(self) -> None:
        # ñ is not in [A-Za-z0-9], so it counts as special
        password = "Abcdefgh1ñ"  # upper + lower + digit + special
        assert _is_valid(password, "other")

    def test_emoji_counts_as_special(self) -> None:
        password = "Abcdefg1🔒"
        violations = validate_password(password, "other")
        assert not any("categories" in v for v in violations)

    def test_cjk_characters_count_as_special(self) -> None:
        password = "Abcdefg1密码"
        violations = validate_password(password, "other")
        assert not any("categories" in v for v in violations)

    def test_unicode_username_match(self) -> None:
        violations = validate_password("Secret1!jüan", "jüan")
        assert any("username" in v for v in violations)


# ---------------------------------------------------------------------------
# Multiple violations
# ---------------------------------------------------------------------------

class TestMultipleViolations:
    def test_short_and_low_complexity(self) -> None:
        violations = validate_password("abc", "other")
        assert len(violations) >= 2
        assert any("at least" in v for v in violations)
        assert any("categories" in v for v in violations)

    def test_short_and_contains_username(self) -> None:
        violations = validate_password("abc", "abc")
        assert any("at least" in v for v in violations)
        assert any("username" in v for v in violations)

    def test_all_violations_at_once(self) -> None:
        violations = validate_password("user", "user")
        assert len(violations) == 3  # too short + low complexity + contains username


# ---------------------------------------------------------------------------
# Fully valid passwords
# ---------------------------------------------------------------------------

class TestValidPasswords:
    def test_strong_password(self) -> None:
        assert _is_valid("C0rrect-Horse!", "other")

    def test_passphrase_style(self) -> None:
        # Upper + lower + special (space) = 3 categories
        assert _is_valid("Correct Horse Battery!", "other")

    def test_exactly_10_chars_all_categories(self) -> None:
        assert _is_valid("Abcdefg1!@", "other")

    def test_long_valid_password(self) -> None:
        password = "Aa1!" + "x" * 96  # 100 chars
        assert _is_valid(password, "other")


# ---------------------------------------------------------------------------
# Return type contract
# ---------------------------------------------------------------------------

class TestReturnContract:
    def test_returns_list_on_valid(self) -> None:
        result = validate_password("Abcdefgh1!", "other")
        assert isinstance(result, list)
        assert result == []

    def test_returns_list_of_strings_on_invalid(self) -> None:
        result = validate_password("bad", "other")
        assert isinstance(result, list)
        assert all(isinstance(v, str) for v in result)

    def test_violation_messages_are_human_readable(self) -> None:
        result = validate_password("short", "other")
        for v in result:
            assert len(v) > 10  # not just a code


# ---------------------------------------------------------------------------
# Constants are sane
# ---------------------------------------------------------------------------

class TestConstants:
    def test_min_length_value(self) -> None:
        assert MIN_LENGTH == 10

    def test_max_length_value(self) -> None:
        assert MAX_LENGTH == 128

    def test_complexity_categories_value(self) -> None:
        assert MIN_COMPLEXITY_CATEGORIES == 3


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_whitespace_only_password(self) -> None:
        violations = validate_password("          ", "other")  # 10 spaces
        # Spaces are special chars, so only 1 category
        assert any("categories" in v for v in violations)

    def test_password_is_exactly_username(self) -> None:
        violations = validate_password("ParkerAdmin", "ParkerAdmin")
        assert any("username" in v for v in violations)

    def test_newlines_in_password(self) -> None:
        password = "Abc\n12345!"
        violations = validate_password(password, "other")
        assert not any("categories" in v for v in violations)

    def test_tab_characters(self) -> None:
        password = "Abc\t12345!"
        violations = validate_password(password, "other")
        assert not any("categories" in v for v in violations)
