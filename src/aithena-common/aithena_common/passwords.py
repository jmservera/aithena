"""Password hashing and verification using Argon2id."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_PASSWORD_HASHER = PasswordHasher()
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("aithena-dummy-password")


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password against an Argon2id hash.

    Returns True if the password matches, False otherwise.
    """
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError, VerificationError):
        return False


def check_needs_rehash(password_hash: str) -> bool:
    """Return True if the hash should be regenerated (e.g. algorithm parameters changed)."""
    return _PASSWORD_HASHER.check_needs_rehash(password_hash)
