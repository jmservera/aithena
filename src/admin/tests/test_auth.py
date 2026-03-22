"""Tests for the auth module."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import jwt
import pytest

from auth import (
    AUTH_COOKIE_NAME_DEFAULT,
    JWT_ALGORITHM,
    AuthenticatedUser,
    AuthSettings,
    _check_cookie_auth,
    authenticate_user,
    check_auth,
    create_access_token,
    decode_access_token,
    login,
    logout,
    parse_ttl_to_seconds,
)

SECRET = "test-secret-key-for-jwt"


# \u2500\u2500 parse_ttl_to_seconds \u2500\u2500


class TestParseTtl:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("3600", 3600),
            ("3600s", 3600),
            ("60m", 3600),
            ("24h", 86400),
            ("7d", 604800),
            ("1s", 1),
            ("  24H  ", 86400),
        ],
    )
    def test_valid(self, raw: str, expected: int) -> None:
        assert parse_ttl_to_seconds(raw) == expected

    @pytest.mark.parametrize("raw", ["", "abc", "10x", "-1h", "0h"])
    def test_invalid(self, raw: str) -> None:
        with pytest.raises(ValueError):
            parse_ttl_to_seconds(raw)


# \u2500\u2500 AuthSettings.from_env \u2500\u2500


class TestAuthSettings:
    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
        monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "pass")
        s = AuthSettings.from_env()
        assert s.jwt_ttl_seconds == 86400
        assert s.admin_username == "admin"
        assert s.auth_cookie_name == AUTH_COOKIE_NAME_DEFAULT

    def test_missing_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)
        monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "pass")
        with pytest.raises(ValueError, match="AUTH_JWT_SECRET"):
            AuthSettings.from_env()

    def test_missing_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
        monkeypatch.delenv("AUTH_ADMIN_PASSWORD", raising=False)
        with pytest.raises(ValueError, match="AUTH_ADMIN_PASSWORD"):
            AuthSettings.from_env()

    def test_custom_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
        monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "pass")
        monkeypatch.setenv("AUTH_JWT_TTL", "30m")
        assert AuthSettings.from_env().jwt_ttl_seconds == 1800

    def test_custom_cookie_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
        monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "pass")
        monkeypatch.setenv("AUTH_COOKIE_NAME", "my_cookie")
        assert AuthSettings.from_env().auth_cookie_name == "my_cookie"


# \u2500\u2500 authenticate_user \u2500\u2500


class TestAuthenticateUser:
    SETTINGS = AuthSettings(jwt_secret=SECRET, jwt_ttl_seconds=3600, admin_username="admin", admin_password="secret")

    def test_valid(self) -> None:
        user = authenticate_user("admin", "secret", self.SETTINGS)
        assert user is not None and user.username == "admin" and user.role == "admin"

    def test_bad_password(self) -> None:
        assert authenticate_user("admin", "wrong", self.SETTINGS) is None

    def test_bad_username(self) -> None:
        assert authenticate_user("root", "secret", self.SETTINGS) is None

    def test_both_wrong(self) -> None:
        assert authenticate_user("root", "wrong", self.SETTINGS) is None


# \u2500\u2500 Token round-trip \u2500\u2500


class TestTokens:
    USER = AuthenticatedUser(username="admin", role="admin")

    def test_roundtrip(self) -> None:
        token = create_access_token(self.USER, SECRET, 3600)
        decoded = decode_access_token(token, SECRET)
        assert decoded.username == "admin" and decoded.role == "admin"

    def test_expired(self) -> None:
        token = create_access_token(self.USER, SECRET, 1, now=datetime(2020, 1, 1, tzinfo=UTC))
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token, SECRET)

    def test_bad_secret(self) -> None:
        token = create_access_token(self.USER, SECRET, 3600)
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(token, "wrong-secret")

    def test_missing_claims(self) -> None:
        payload = {"sub": "admin", "exp": int(time.time()) + 3600}
        token = jwt.encode(payload, SECRET, algorithm=JWT_ALGORITHM)
        with pytest.raises(jwt.MissingRequiredClaimError):
            decode_access_token(token, SECRET)

    def test_payload_fields(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=UTC)
        token = create_access_token(self.USER, SECRET, 3600, now=now)
        raw = jwt.decode(token, SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        assert raw["sub"] == "admin" and raw["role"] == "admin"
        assert raw["exp"] - raw["iat"] == 3600

    def test_iat_set(self) -> None:
        token = create_access_token(self.USER, SECRET, 60)
        raw = jwt.decode(token, SECRET, algorithms=[JWT_ALGORITHM])
        assert abs(raw["iat"] - int(time.time())) < 5

    def test_custom_now(self) -> None:
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        token = create_access_token(self.USER, SECRET, 7200, now=now)
        raw = jwt.decode(token, SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        assert raw["iat"] == int(now.timestamp())


# \u2500\u2500 Session management \u2500\u2500


class TestSession:
    SETTINGS = AuthSettings(jwt_secret=SECRET, jwt_ttl_seconds=3600, admin_username="admin", admin_password="secret")

    @patch("auth.st")
    def test_check_auth_no_token(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {}
        mock_st.context.cookies = {}
        assert check_auth(self.SETTINGS) is None

    @patch("auth.st")
    def test_check_auth_valid(self, mock_st: MagicMock) -> None:
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, SECRET, 3600)
        mock_st.session_state = {"auth_token": token}
        result = check_auth(self.SETTINGS)
        assert result is not None and result.username == "admin"

    @patch("auth.st")
    def test_check_auth_expired(self, mock_st: MagicMock) -> None:
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, SECRET, 1, now=datetime(2020, 1, 1, tzinfo=UTC))
        mock_st.session_state = {"auth_token": token}
        mock_st.context.cookies = {}
        assert check_auth(self.SETTINGS) is None

    @patch("auth.st")
    def test_login_success(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {}
        user = login("admin", "secret", self.SETTINGS)
        assert user is not None and "auth_token" in mock_st.session_state

    @patch("auth.st")
    def test_login_failure(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {}
        assert login("admin", "wrong", self.SETTINGS) is None
        assert "auth_token" not in mock_st.session_state

    @patch("auth.st")
    def test_logout(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {"auth_token": "tok", "auth_user": "admin"}
        logout()
        assert "auth_token" not in mock_st.session_state


# ── Cookie-based SSO auth ──


class TestCookieAuth:
    """Tests for _check_cookie_auth and the SSO cookie fallback in check_auth."""

    SETTINGS = AuthSettings(jwt_secret=SECRET, jwt_ttl_seconds=3600, admin_username="admin", admin_password="secret")

    @patch("auth.st")
    def test_cookie_auth_valid_token(self, mock_st: MagicMock) -> None:
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, SECRET, 3600)
        mock_st.session_state = {}
        mock_st.context.cookies = {"aithena_auth": token}
        result = _check_cookie_auth(self.SETTINGS)
        assert result is not None
        assert result.username == "admin"
        assert result.role == "admin"
        assert mock_st.session_state["auth_token"] == token
        assert mock_st.session_state["auth_user"] == "admin"

    @patch("auth.st")
    def test_cookie_auth_expired_token(self, mock_st: MagicMock) -> None:
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, SECRET, 1, now=datetime(2020, 1, 1, tzinfo=UTC))
        mock_st.session_state = {}
        mock_st.context.cookies = {"aithena_auth": token}
        assert _check_cookie_auth(self.SETTINGS) is None
        assert "auth_token" not in mock_st.session_state

    @patch("auth.st")
    def test_cookie_auth_wrong_secret(self, mock_st: MagicMock) -> None:
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, "wrong-secret", 3600)
        mock_st.session_state = {}
        mock_st.context.cookies = {"aithena_auth": token}
        assert _check_cookie_auth(self.SETTINGS) is None

    @patch("auth.st")
    def test_cookie_auth_no_cookie(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {}
        mock_st.context.cookies = {}
        assert _check_cookie_auth(self.SETTINGS) is None

    @patch("auth.st")
    def test_cookie_auth_malformed_token(self, mock_st: MagicMock) -> None:
        mock_st.session_state = {}
        mock_st.context.cookies = {"aithena_auth": "not-a-jwt"}
        assert _check_cookie_auth(self.SETTINGS) is None

    @patch("auth.st")
    def test_cookie_auth_context_not_available(self, mock_st: MagicMock) -> None:
        """When st.context is unavailable (old Streamlit), returns None."""

        class _NoContext:
            session_state: dict = {}  # noqa: RUF012

            @property
            def context(self):
                raise AttributeError("no context")

        with patch("auth.st", _NoContext()):
            assert _check_cookie_auth(self.SETTINGS) is None

    @patch("auth.st")
    def test_cookie_auth_rejects_non_admin_role(self, mock_st: MagicMock) -> None:
        """A valid JWT with a non-admin role must be rejected by cookie SSO."""
        viewer = AuthenticatedUser(username="viewer-user", role="viewer")
        token = create_access_token(viewer, SECRET, 3600)
        mock_st.session_state = {}
        mock_st.context.cookies = {"aithena_auth": token}
        assert _check_cookie_auth(self.SETTINGS) is None
        assert "auth_token" not in mock_st.session_state

    @patch("auth.st")
    def test_check_auth_cookie_fallback_rejects_non_admin(self, mock_st: MagicMock) -> None:
        """check_auth rejects a non-admin cookie even when session state is empty."""
        editor = AuthenticatedUser(username="editor-user", role="editor")
        token = create_access_token(editor, SECRET, 3600)
        mock_st.session_state = {}
        mock_st.context.cookies = {"aithena_auth": token}
        assert check_auth(self.SETTINGS) is None
        assert "auth_token" not in mock_st.session_state

    @patch("auth.st")
    def test_cookie_auth_custom_cookie_name(self, mock_st: MagicMock) -> None:
        settings = AuthSettings(
            jwt_secret=SECRET, jwt_ttl_seconds=3600,
            admin_username="admin", admin_password="secret",
            auth_cookie_name="custom_auth",
        )
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, SECRET, 3600)
        mock_st.session_state = {}
        mock_st.context.cookies = {"custom_auth": token}
        result = _check_cookie_auth(settings)
        assert result is not None and result.username == "admin"

    @patch("auth.st")
    def test_check_auth_falls_back_to_cookie(self, mock_st: MagicMock) -> None:
        """check_auth uses cookie when session state is empty."""
        user = AuthenticatedUser(username="admin", role="admin")
        token = create_access_token(user, SECRET, 3600)
        mock_st.session_state = {}
        mock_st.context.cookies = {"aithena_auth": token}
        result = check_auth(self.SETTINGS)
        assert result is not None
        assert result.username == "admin"
        # Token should be persisted in session state for future reruns
        assert mock_st.session_state["auth_token"] == token

    @patch("auth.st")
    def test_check_auth_session_state_takes_priority(self, mock_st: MagicMock) -> None:
        """Session state token is used even if a different cookie is present."""
        session_user = AuthenticatedUser(username="session-admin", role="admin")
        session_token = create_access_token(session_user, SECRET, 3600)
        cookie_user = AuthenticatedUser(username="cookie-admin", role="admin")
        cookie_token = create_access_token(cookie_user, SECRET, 3600)
        mock_st.session_state = {"auth_token": session_token}
        mock_st.context.cookies = {"aithena_auth": cookie_token}
        result = check_auth(self.SETTINGS)
        assert result is not None
        assert result.username == "session-admin"

    @patch("auth.st")
    def test_check_auth_expired_session_falls_back_to_cookie(self, mock_st: MagicMock) -> None:
        """When session token expires, falls back to valid cookie."""
        expired_token = create_access_token(
            AuthenticatedUser(username="admin", role="admin"), SECRET, 1,
            now=datetime(2020, 1, 1, tzinfo=UTC),
        )
        valid_token = create_access_token(
            AuthenticatedUser(username="cookie-admin", role="admin"), SECRET, 3600,
        )
        mock_st.session_state = {"auth_token": expired_token, "auth_user": "admin"}
        mock_st.context.cookies = {"aithena_auth": valid_token}
        result = check_auth(self.SETTINGS)
        assert result is not None
        assert result.username == "cookie-admin"
        assert mock_st.session_state["auth_token"] == valid_token

    @patch("auth.st")
    def test_solr_search_jwt_compatible(self, mock_st: MagicMock) -> None:
        """JWTs created by solr-search (with user_id claim) are accepted."""
        payload = {
            "sub": "admin",
            "user_id": 1,
            "role": "admin",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int(datetime.now(UTC).timestamp()) + 3600,
        }
        token = jwt.encode(payload, SECRET, algorithm=JWT_ALGORITHM)
        mock_st.session_state = {}
        mock_st.context.cookies = {"aithena_auth": token}
        result = check_auth(self.SETTINGS)
        assert result is not None
        assert result.username == "admin"
        assert result.role == "admin"
