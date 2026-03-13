from __future__ import annotations

from marketpulse.core.auth import hash_password
from marketpulse.core.config import get_settings


def _create_user(repo):
    org = repo.create_organization("Tenant A", plan="starter")
    return repo.create_user(
        email="owner@example.com",
        password_hash=hash_password("supersecure123"),
        role="retailer",
        organization_id=org["id"],
    )


def _login(client):
    response = client.post("/auth/login", json={"email": "owner@example.com", "password": "supersecure123"})
    assert response.status_code == 200
    csrf_token = response.json()["csrf_token"]
    client.headers["X-CSRF-Token"] = csrf_token
    return response


def test_dashboard_bootstrap_requires_auth(anonymous_client, repo):
    _create_user(repo)
    response = anonymous_client.get("/dashboard/bootstrap")
    assert response.status_code == 401


def test_shopify_connect_requires_auth(anonymous_client, repo, monkeypatch):
    _create_user(repo)
    monkeypatch.setenv("SHOPIFY_API_KEY", "key")
    monkeypatch.setenv("SHOPIFY_API_SECRET", "secret")
    monkeypatch.setenv("SHOPIFY_REDIRECT_URI", "http://localhost:8000/shopify/callback")
    get_settings.cache_clear()
    response = anonymous_client.get("/shopify/connect?shop=test-store", follow_redirects=False)
    assert response.status_code == 401


def test_logout_revokes_existing_bearer_token(client, repo):
    _create_user(repo)
    login_response = _login(client)
    token = login_response.cookies.get("mp_session")
    assert token

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 401
    assert me_response.json()["detail"] == "Session has been revoked"


def test_upload_rejects_invalid_csrf_header(client, repo):
    _create_user(repo)
    _login(client)
    response = client.post(
        "/upload_csv",
        files={"file": ("sample.csv", b"sku_id,product_name,category,mrp,cost,current_inventory\nA1,Item,Snacks,10,5,1\n", "text/csv")},
        headers={"X-CSRF-Token": "wrong-token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token invalid."
