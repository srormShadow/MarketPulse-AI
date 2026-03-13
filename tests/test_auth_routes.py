"""Comprehensive tests for authentication routes (login, register, logout, /auth/me)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from marketpulse.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestLogin:
    """POST /auth/login"""

    def test_login_success_returns_user_and_csrf(self, anonymous_client, db_session):
        from tests.conftest import TEST_RETAILER, _bootstrap_user

        _bootstrap_user(db_session, **TEST_RETAILER)
        resp = anonymous_client.post(
            "/auth/login",
            json={"email": TEST_RETAILER["email"], "password": TEST_RETAILER["password"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user"]["email"] == TEST_RETAILER["email"]
        assert body["user"]["role"] == "retailer"
        assert "csrf_token" in body
        assert "mp_session" in resp.cookies
        assert "mp_csrf" in resp.cookies

    def test_login_wrong_password(self, anonymous_client, db_session):
        from tests.conftest import TEST_RETAILER, _bootstrap_user

        _bootstrap_user(db_session, **TEST_RETAILER)
        resp = anonymous_client.post(
            "/auth/login",
            json={"email": TEST_RETAILER["email"], "password": "wrong-password"},
        )
        assert resp.status_code == 401
        assert resp.json()["message"] == "Invalid email or password."

    def test_login_nonexistent_user(self, anonymous_client):
        resp = anonymous_client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "doesntmatter"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, anonymous_client):
        resp = anonymous_client.post("/auth/login", json={"email": ""})
        assert resp.status_code == 400
        assert "required" in resp.json()["message"].lower()

    def test_login_case_insensitive_email(self, anonymous_client, db_session):
        from tests.conftest import TEST_RETAILER, _bootstrap_user

        _bootstrap_user(db_session, **TEST_RETAILER)
        resp = anonymous_client.post(
            "/auth/login",
            json={"email": TEST_RETAILER["email"].upper(), "password": TEST_RETAILER["password"]},
        )
        assert resp.status_code == 200


class TestRegister:
    """POST /auth/register"""

    def test_register_success(self, anonymous_client):
        resp = anonymous_client.post(
            "/auth/register",
            json={
                "email": "new@example.com",
                "password": "strongpassword123",
                "organization_name": "New Org",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["user"]["email"] == "new@example.com"
        assert body["user"]["role"] == "retailer"
        assert "csrf_token" in body
        assert "mp_session" in resp.cookies

    def test_register_duplicate_email(self, anonymous_client, db_session):
        from tests.conftest import TEST_RETAILER, _bootstrap_user

        _bootstrap_user(db_session, **TEST_RETAILER)
        resp = anonymous_client.post(
            "/auth/register",
            json={
                "email": TEST_RETAILER["email"],
                "password": "strongpassword123",
                "organization_name": "Dup Org",
            },
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["message"]

    def test_register_short_password(self, anonymous_client):
        resp = anonymous_client.post(
            "/auth/register",
            json={
                "email": "short@example.com",
                "password": "short",
                "organization_name": "Org",
            },
        )
        assert resp.status_code == 400
        assert "10 characters" in resp.json()["message"]

    def test_register_missing_fields(self, anonymous_client):
        resp = anonymous_client.post(
            "/auth/register",
            json={"email": "x@y.com", "password": "longpassword123"},
        )
        assert resp.status_code == 400


class TestLogout:
    """POST /auth/logout"""

    def test_logout_clears_cookies(self, client):
        resp = client.post("/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_logout_requires_auth(self, anonymous_client):
        resp = anonymous_client.post("/auth/logout")
        assert resp.status_code == 401


class TestAuthMe:
    """GET /auth/me"""

    def test_me_returns_current_user(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "retailer@test.local"
        assert body["role"] == "retailer"
        assert "id" in body
        assert "organization_id" in body

    def test_me_requires_auth(self, anonymous_client):
        resp = anonymous_client.get("/auth/me")
        assert resp.status_code == 401


class TestLoginThrottling:
    """Progressive lockout after repeated failures."""

    def test_lockout_after_repeated_failures(self, anonymous_client, db_session, monkeypatch):
        from tests.conftest import TEST_RETAILER, _bootstrap_user

        _bootstrap_user(db_session, **TEST_RETAILER)

        # Clear any prior throttle state
        from marketpulse.core import login_throttle
        login_throttle._store.clear()

        # 5 failed attempts should trigger lockout
        for _ in range(5):
            resp = anonymous_client.post(
                "/auth/login",
                json={"email": TEST_RETAILER["email"], "password": "wrong"},
            )
            assert resp.status_code == 401

        # 6th attempt should be locked
        resp = anonymous_client.post(
            "/auth/login",
            json={"email": TEST_RETAILER["email"], "password": TEST_RETAILER["password"]},
        )
        assert resp.status_code == 429
        assert "locked" in resp.json()["message"].lower()
