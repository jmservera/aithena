"""Integration tests for the admin auth flow.

Covers the full auth lifecycle: login → JWT generation → token validation →
protected-route gating → logout, plus edge cases (expired tokens, malformed
input, missing env vars, empty credentials).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from auth import (
    JWT_ALGORITHM,
    AuthenticatedUser,
    AuthSettings,
    authenticate_user,
    check_auth,
    create_access_token,
    decode_access_token,
    login,
    logout,
    parse_ttl_to_seconds,
    require_auth,
)

SECRET = "integration-test-secret-key"
SETTINGS = AuthSettings(
    jwt_secret=SECRET,
    jwt_ttl_seconds=3600,
    admin_username="admin",
    admin_password="s3cret!",
)


# ── Full auth flow integration ──


class TestFullAuthFlow:
    """End-to-end flow: login → check_auth → logout → check_auth returns None."""

    @patch("auth.st")
    def test_login_check_logout_cycle(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {}

        # login
        user = login("admin", "s3cret!", SETTINGS)
        assert user is not None
        assert user.username == "admin"
        assert user.role == "admin"
        assert "auth_token" in mock_st.session_state
        assert mock_st.session_state["auth_user"] == "admin"

        # check_auth returns user while token is live
        authed = check_auth(SETTINGS)
        assert authed is not None
        assert authed.username == "admin"

        # logout clears session
        logout()
        assert "auth_token" not in mock_st.session_state
        assert "auth_user" not in mock_st.session_state

        # check_auth returns None after logout
        assert check_auth(SETTINGS) is None

    @patch("auth.st")
    def test_login_failure_leaves_session_clean(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {}
        assert login("admin", "wrong-password", SETTINGS) is None
        assert "auth_token" not in mock_st.session_state
        assert "auth_user" not in mock_st.session_state

    @patch("auth.st")
    def test_multiple_logins_replace_token(self, mock_st: MagicMock) -> None:
        """Second login overwrites the first token; latest token is valid."""
        mock_st.session_state = {}
        login("admin", "s3cret!", SETTINGS)
        first_token = mock_st.session_state["auth_token"]

        # Force a different iat by sleeping past the second boundary
        import time

        time.sleep(1.1)

        login("admin", "s3cret!", SETTINGS)
        second_token = mock_st.session_state["auth_token"]

        assert first_token != second_token
        user = check_auth(SETTINGS)
        assert user is not None


# ── JWT generation and validation ──


class TestJWTIntegration:
    """Token creation → decode round-trips and payload correctness."""

    USER = AuthenticatedUser(username="admin", role="admin")

    def test_token_contains_required_claims(self) -> None:
        now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
        token = create_access_token(self.USER, SECRET, 7200, now=now)
        raw = jwt.decode(token, SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        assert raw["sub"] == "admin"
        assert raw["role"] == "admin"
        assert raw["iat"] == int(now.timestamp())
        assert raw["exp"] == int(now.timestamp()) + 7200

    def test_decode_returns_authenticated_user(self) -> None:
        token = create_access_token(self.USER, SECRET, 3600)
        user = decode_access_token(token, SECRET)
        assert isinstance(user, AuthenticatedUser)
        assert user.username == "admin"
        assert user.role == "admin"

    def test_expired_token_rejected(self) -> None:
        past = datetime(2020, 1, 1, tzinfo=UTC)
        token = create_access_token(self.USER, SECRET, 1, now=past)
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token, SECRET)

    def test_wrong_secret_rejected(self) -> None:
        token = create_access_token(self.USER, SECRET, 3600)
        with pytest.raises(jwt.InvalidSignatureError):
            decode_access_token(token, "not-the-right-secret")

    def test_malformed_token_rejected(self) -> None:
        with pytest.raises(jwt.DecodeError):
            decode_access_token("not.a.jwt", SECRET)

    def test_completely_invalid_string(self) -> None:
        with pytest.raises(jwt.DecodeError):
            decode_access_token("garbage-token-data", SECRET)

    def test_empty_token_rejected(self) -> None:
        with pytest.raises(jwt.DecodeError):
            decode_access_token("", SECRET)

    def test_token_missing_sub_claim(self) -> None:
        payload = {"role": "admin", "exp": int(time.time()) + 3600, "iat": int(time.time())}
        token = jwt.encode(payload, SECRET, algorithm=JWT_ALGORITHM)
        with pytest.raises(jwt.MissingRequiredClaimError):
            decode_access_token(token, SECRET)

    def test_token_missing_role_claim(self) -> None:
        payload = {"sub": "admin", "exp": int(time.time()) + 3600, "iat": int(time.time())}
        token = jwt.encode(payload, SECRET, algorithm=JWT_ALGORITHM)
        with pytest.raises(jwt.MissingRequiredClaimError):
            decode_access_token(token, SECRET)

    def test_token_missing_exp_claim(self) -> None:
        payload = {"sub": "admin", "role": "admin", "iat": int(time.time())}
        token = jwt.encode(payload, SECRET, algorithm=JWT_ALGORITHM)
        with pytest.raises(jwt.MissingRequiredClaimError):
            decode_access_token(token, SECRET)

    def test_token_with_none_algorithm_rejected(self) -> None:
        """Verify 'none' algorithm attack vector is blocked."""
        payload = {
            "sub": "admin",
            "role": "admin",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        # Encode without signing
        token = jwt.encode(payload, "", algorithm="none")
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(token, SECRET)

    def test_very_short_ttl(self) -> None:
        """Token with 1-second TTL expires almost immediately."""
        token = create_access_token(self.USER, SECRET, 1)
        # Should be valid right now
        user = decode_access_token(token, SECRET)
        assert user.username == "admin"

    def test_different_users_get_different_tokens(self) -> None:
        user_a = AuthenticatedUser(username="alice", role="admin")
        user_b = AuthenticatedUser(username="bob", role="admin")
        token_a = create_access_token(user_a, SECRET, 3600)
        token_b = create_access_token(user_b, SECRET, 3600)
        assert token_a != token_b
        assert decode_access_token(token_a, SECRET).username == "alice"
        assert decode_access_token(token_b, SECRET).username == "bob"


# ── Protected route behaviour (check_auth) ──


class TestProtectedRoutes:
    """check_auth gating: valid token passes, invalid/expired/missing blocks."""

    @patch("auth.st")
    def test_valid_token_passes(self, mock_st: MagicMock) -> None:
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, SECRET, 3600)
        mock_st.session_state = {"auth_token": token}
        result = check_auth(SETTINGS)
        assert result is not None
        assert result.username == "admin"

    @patch("auth.st")
    def test_expired_token_clears_session(self, mock_st: MagicMock) -> None:
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, SECRET, 1, now=datetime(2020, 1, 1, tzinfo=UTC))
        mock_st.session_state = {"auth_token": token, "auth_user": "admin"}
        assert check_auth(SETTINGS) is None
        assert "auth_token" not in mock_st.session_state
        assert "auth_user" not in mock_st.session_state

    @patch("auth.st")
    def test_malformed_token_clears_session(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {"auth_token": "not-valid-jwt", "auth_user": "admin"}
        assert check_auth(SETTINGS) is None
        assert "auth_token" not in mock_st.session_state

    @patch("auth.st")
    def test_missing_token_returns_none(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {}
        assert check_auth(SETTINGS) is None

    @patch("auth.st")
    def test_empty_string_token_returns_none(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {"auth_token": ""}
        assert check_auth(SETTINGS) is None

    @patch("auth.st")
    def test_token_signed_with_wrong_secret_clears_session(self, mock_st: MagicMock) -> None:
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, "other-secret", 3600)
        mock_st.session_state = {"auth_token": token, "auth_user": "admin"}
        assert check_auth(SETTINGS) is None
        assert "auth_token" not in mock_st.session_state

    @patch("auth.st")
    def test_token_with_tampered_payload_rejected(self, mock_st: MagicMock) -> None:
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, SECRET, 3600)
        # Tamper with the payload section
        parts = token.split(".")
        parts[1] = parts[1][::-1]  # reverse the payload
        tampered = ".".join(parts)
        mock_st.session_state = {"auth_token": tampered, "auth_user": "admin"}
        assert check_auth(SETTINGS) is None


# ── require_auth integration ──


class TestRequireAuth:
    """require_auth blocks rendering when unauthenticated."""

    @patch("auth.st")
    def test_authenticated_returns_user(self, mock_st: MagicMock) -> None:
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, SECRET, 3600)
        mock_st.session_state = {"auth_token": token}
        result = require_auth(SETTINGS)
        assert result.username == "admin"

    @patch("auth.render_login_page", create=True)
    @patch("auth.st")
    def test_unauthenticated_renders_login_and_stops(self, mock_st: MagicMock, mock_render: MagicMock) -> None:
        mock_st.session_state = {}
        mock_st.stop.side_effect = SystemExit

        with pytest.raises(SystemExit):
            require_auth(SETTINGS)

        mock_st.stop.assert_called_once()


# ── authenticate_user edge cases ──


class TestAuthenticateUserEdgeCases:
    def test_empty_username(self) -> None:
        assert authenticate_user("", "s3cret!", SETTINGS) is None

    def test_empty_password(self) -> None:
        assert authenticate_user("admin", "", SETTINGS) is None

    def test_both_empty(self) -> None:
        assert authenticate_user("", "", SETTINGS) is None

    def test_whitespace_username(self) -> None:
        assert authenticate_user("  admin  ", "s3cret!", SETTINGS) is None

    def test_case_sensitive_username(self) -> None:
        assert authenticate_user("Admin", "s3cret!", SETTINGS) is None

    def test_case_sensitive_password(self) -> None:
        assert authenticate_user("admin", "S3CRET!", SETTINGS) is None

    def test_unicode_credentials_raise(self) -> None:
        """hmac.compare_digest rejects non-ASCII str; verify it surfaces."""
        with pytest.raises(TypeError):
            authenticate_user("admin", "pässwörd", SETTINGS)

    def test_very_long_credentials(self) -> None:
        long_str = "a" * 10000
        assert authenticate_user(long_str, long_str, SETTINGS) is None


# ── AuthSettings.from_env edge cases ──


class TestAuthSettingsEdgeCases:
    def test_empty_string_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_JWT_SECRET", "")
        monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "pass")
        with pytest.raises(ValueError, match="AUTH_JWT_SECRET"):
            AuthSettings.from_env()

    def test_empty_string_password_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
        monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "")
        with pytest.raises(ValueError, match="AUTH_ADMIN_PASSWORD"):
            AuthSettings.from_env()

    def test_invalid_ttl_format_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
        monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "pass")
        monkeypatch.setenv("AUTH_JWT_TTL", "forever")
        with pytest.raises(ValueError, match="Invalid AUTH_JWT_TTL"):
            AuthSettings.from_env()

    def test_zero_ttl_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
        monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "pass")
        monkeypatch.setenv("AUTH_JWT_TTL", "0s")
        with pytest.raises(ValueError, match="greater than zero"):
            AuthSettings.from_env()

    def test_custom_username(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
        monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "pass")
        monkeypatch.setenv("AUTH_ADMIN_USERNAME", "superadmin")
        s = AuthSettings.from_env()
        assert s.admin_username == "superadmin"

    def test_ttl_in_days(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
        monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "pass")
        monkeypatch.setenv("AUTH_JWT_TTL", "7d")
        s = AuthSettings.from_env()
        assert s.jwt_ttl_seconds == 604800


# ── parse_ttl_to_seconds edge cases ──


class TestParseTtlEdgeCases:
    def test_leading_trailing_whitespace(self) -> None:
        assert parse_ttl_to_seconds("  30m  ") == 1800

    def test_uppercase_unit(self) -> None:
        assert parse_ttl_to_seconds("24H") == 86400

    def test_bare_number_treated_as_seconds(self) -> None:
        assert parse_ttl_to_seconds("120") == 120

    def test_negative_pattern_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_ttl_to_seconds("-10s")

    def test_float_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_ttl_to_seconds("1.5h")

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_ttl_to_seconds("")

    def test_only_unit_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_ttl_to_seconds("h")

    def test_zero_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_ttl_to_seconds("0")

    def test_large_value(self) -> None:
        assert parse_ttl_to_seconds("365d") == 365 * 86400
