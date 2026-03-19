"""Password policy enforcement for aithena user management.

Validates passwords against configurable security rules before hashing.
Returns a list of human-readable violation messages (empty list = valid).

Policy (v1.9.0 defaults — hardcoded, configurable in a future release):
  - Minimum length: 10 characters
  - Maximum length: 128 characters (Argon2 DoS protection)
  - Complexity: at least 3 of 4 categories (uppercase, lowercase, digit, special)
  - Password must not contain the username (case-insensitive)
"""

from __future__ import annotations

import re

MIN_LENGTH = 10
MAX_LENGTH = 128
MIN_COMPLEXITY_CATEGORIES = 3

_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"[0-9]")
_SPECIAL = re.compile(r"[^A-Za-z0-9]")


def validate_password(password: str, username: str) -> list[str]:
    """Validate a password against the security policy.

    Args:
        password: The candidate password (plaintext).
        username: The target username (used for containment check).

    Returns:
        A list of violation messages. An empty list means the password is valid.
    """
    violations: list[str] = []

    if len(password) < MIN_LENGTH:
        violations.append(f"Password must be at least {MIN_LENGTH} characters")

    if len(password) > MAX_LENGTH:
        violations.append(f"Password must be at most {MAX_LENGTH} characters")

    categories = sum([
        bool(_UPPER.search(password)),
        bool(_LOWER.search(password)),
        bool(_DIGIT.search(password)),
        bool(_SPECIAL.search(password)),
    ])
    if categories < MIN_COMPLEXITY_CATEGORIES:
        violations.append(
            f"Password must contain at least {MIN_COMPLEXITY_CATEGORIES} of 4 categories: "
            "uppercase, lowercase, digit, special character"
        )

    if username and username.lower() in password.lower():
        violations.append("Password must not contain the username")

    return violations
