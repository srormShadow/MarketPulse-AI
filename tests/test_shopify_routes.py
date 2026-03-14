"""Regression coverage for the current Shopify OAuth integration."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from marketpulse.core.config import get_settings
from marketpulse.routes import shopify as shopify_routes


def _configure_shopify_env(
    monkeypatch,
    *,
    redirect_uri: str = "http://localhost:8000/shopify/callback",
    frontend_url: str = "http://localhost:5173",
    api_key: str = "test_shopify_api_key",
    api_secret: str = "test_shopify_api_secret",
) -> None:
    monkeypatch.setenv("SHOPIFY_REDIRECT_URI", redirect_uri)
    monkeypatch.setenv("FRONTEND_URL", frontend_url)
    monkeypatch.setenv("SHOPIFY_API_KEY", api_key)
    monkeypatch.setenv("SHOPIFY_API_SECRET", api_secret)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _install_and_get_state(client, shop_domain: str) -> tuple[str, str]:
    response = client.post("/shopify/install", json={"shop_domain": shop_domain})
    assert response.status_code == 200
    authorization_url = response.json()["authorization_url"]
    state = parse_qs(urlparse(authorization_url).query)["state"][0]
    return authorization_url, state


def _shopify_callback_hmac(secret: str, params: dict[str, str]) -> str:
    sorted_params = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
    return hmac.new(secret.encode("utf-8"), sorted_params.encode("utf-8"), hashlib.sha256).hexdigest()


def _webhook_hmac(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_shopify_connect_requires_auth(anonymous_client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = anonymous_client.get("/shopify/connect", follow_redirects=False)

    assert response.status_code == 401


def test_shopify_connect_page_renders_form_for_authenticated_user(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.get("/shopify/connect", follow_redirects=False)

    assert response.status_code == 200
    assert "Connect your Shopify store" in response.text
    assert 'name="shop"' in response.text


def test_shopify_connect_redirects_to_oauth_for_valid_shop(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.get("/shopify/connect?shop=marketpulse-ai-2", follow_redirects=False)

    assert response.status_code == 302
    parsed = urlparse(response.headers["location"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "marketpulse-ai-2.myshopify.com"
    assert parsed.path == "/admin/oauth/authorize"
    assert params["client_id"] == ["test_shopify_api_key"]
    assert params["scope"] == ["read_products,read_orders,read_inventory"]
    assert params["redirect_uri"] == ["http://localhost:8000/shopify/callback"]
    assert "." in params["state"][0]


def test_shopify_connect_not_configured_page(client, monkeypatch):
    _configure_shopify_env(monkeypatch, api_key="", api_secret="")

    response = client.get("/shopify/connect", follow_redirects=False)

    assert response.status_code == 503
    assert "Shopify integration is not configured" in response.text


def test_shopify_connect_oauth_normalizes_store_name(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.post("/shopify/connect-oauth", json={"shop_domain": "marketpulse-ai-2"})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["shop_domain"] == "marketpulse-ai-2.myshopify.com"


def test_shopify_install_returns_signed_authorization_url(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.post("/shopify/install", json={"shop_domain": "https://marketpulse-ai-2.myshopify.com/"})

    assert response.status_code == 200
    parsed = urlparse(response.json()["authorization_url"])
    params = parse_qs(parsed.query)
    assert parsed.netloc == "marketpulse-ai-2.myshopify.com"
    assert params["client_id"] == ["test_shopify_api_key"]
    assert "." in params["state"][0]


def test_shopify_install_rejects_missing_redirect_uri(client, monkeypatch):
    _configure_shopify_env(monkeypatch, redirect_uri="")

    response = client.post("/shopify/install", json={"shop_domain": "marketpulse-ai-2.myshopify.com"})

    assert response.status_code == 503
    assert response.json()["detail"] == "SHOPIFY_REDIRECT_URI is not configured."


def test_shopify_callback_success_creates_store(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"access_token": "shpat_oauth_token", "scope": "read_products,read_orders,read_inventory"}

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url, json):
            assert url == "https://marketpulse-ai-2.myshopify.com/admin/oauth/access_token"
            assert json["code"] == "code_from_shopify"
            return _FakeResponse()

    monkeypatch.setattr(shopify_routes.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient())

    _, state = _install_and_get_state(client, "marketpulse-ai-2.myshopify.com")
    callback_params = {
        "code": "code_from_shopify",
        "host": "encoded-host",
        "shop": "marketpulse-ai-2.myshopify.com",
        "state": state,
        "timestamp": "1773150232",
    }
    callback_params["hmac"] = _shopify_callback_hmac("test_shopify_api_secret", callback_params)

    callback_response = client.get("/shopify/callback", params=callback_params, follow_redirects=False)

    assert callback_response.status_code == 200
    assert "window.opener.postMessage" in callback_response.text
    assert '"shopify": "connected"' in callback_response.text

    store = repo.get_shopify_store_by_domain("marketpulse-ai-2.myshopify.com")
    assert store is not None
    assert store["access_token"] == "shpat_oauth_token"
    assert store["scope"] == "read_products,read_orders,read_inventory"
    assert store["is_active"] is True


def test_shopify_callback_rejects_invalid_state(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.get(
        "/shopify/callback?shop=marketpulse-ai-2.myshopify.com&code=code_from_shopify&state=wrong_state",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert '"shopify": "error"' in response.text
    assert "invalid_state" in response.text


def test_shopify_callback_rejects_hmac_verification_failure(client, monkeypatch):
    _configure_shopify_env(monkeypatch)
    _, state = _install_and_get_state(client, "marketpulse-ai-2.myshopify.com")

    response = client.get(
        "/shopify/callback",
        params={
            "shop": "marketpulse-ai-2.myshopify.com",
            "code": "code_from_shopify",
            "state": state,
            "host": "encoded-host",
            "timestamp": "1773150232",
            "hmac": "not_valid",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert response.json()["message"] == "HMAC verification failed."


def test_shopify_list_stores_returns_only_active_stores(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    active = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")
    repo.create_shopify_store("old-shop.myshopify.com", "token", "read_products")
    repo.deactivate_shopify_store("old-shop.myshopify.com")

    response = client.get("/shopify/stores")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["stores"][0]["id"] == active["id"]
    assert payload["stores"][0]["shop_domain"] == "marketpulse-ai-2.myshopify.com"


def test_shopify_disconnect_store_success(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")

    response = client.delete(f"/shopify/stores/{store['id']}")

    assert response.status_code == 200
    assert response.json() == {"status": "disconnected", "store_id": store["id"]}
    assert repo.get_shopify_store_by_domain("marketpulse-ai-2.myshopify.com")["is_active"] is False


def test_shopify_sync_success_returns_summary(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")

    monkeypatch.setattr(
        shopify_routes,
        "run_full_sync",
        lambda **kwargs: {
            "products_synced": 3,
            "orders_synced": 4,
            "skus_created": 2,
            "sales_records_created": 7,
        },
    )

    response = client.post(
        f"/shopify/sync/{store['id']}",
        json={"sync_products": True, "sync_orders": False, "orders_days_back": 30},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "store_id": store["id"],
        "shop_domain": "marketpulse-ai-2.myshopify.com",
        "products_synced": 3,
        "orders_synced": 4,
        "skus_created": 2,
        "sales_records_created": 7,
    }


def test_shopify_sync_missing_credentials_returns_500(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")
    repo.update_shopify_store_token("marketpulse-ai-2.myshopify.com", "", "read_products")

    response = client.post(f"/shopify/sync/{store['id']}", json={})

    assert response.status_code == 500
    assert response.json()["detail"] == "Store credentials unavailable"


def test_shopify_sync_surfaces_upstream_403_with_actionable_message(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")

    request = httpx.Request("GET", "https://marketpulse-ai-2.myshopify.com/admin/api/2024-10/products.json")
    response = httpx.Response(403, request=request, text="Forbidden")

    def _boom(**kwargs):
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    monkeypatch.setattr(shopify_routes, "run_full_sync", _boom)

    result = client.post(f"/shopify/sync/{store['id']}", json={})

    assert result.status_code == 502
    payload = result.json()
    assert payload["status"] == "error"
    assert "Shopify rejected the sync request" in payload["message"]
    assert "read_products, read_orders, read_inventory" in payload["message"]


def test_shopify_sync_surfaces_connectivity_errors(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")

    def _boom(**kwargs):
        raise httpx.ConnectError("[WinError 10013] blocked", request=httpx.Request("GET", "https://example.com"))

    monkeypatch.setattr(shopify_routes, "run_full_sync", _boom)

    result = client.post(f"/shopify/sync/{store['id']}", json={})

    assert result.status_code == 502
    payload = result.json()
    assert payload["status"] == "error"
    assert "Unable to reach Shopify from the backend" in payload["message"]
    assert "WinError 10013" in payload["message"]


def test_shopify_webhook_rejects_invalid_hmac(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.post(
        "/shopify/webhooks",
        content=b'{"ok": true}',
        headers={
            "X-Shopify-Hmac-Sha256": "invalid",
            "X-Shopify-Topic": "orders/create",
            "X-Shopify-Shop-Domain": "marketpulse-ai-2.myshopify.com",
        },
    )

    assert response.status_code == 401
    assert response.json()["status"] == "unauthorized"


def test_shopify_webhook_orders_create_triggers_sales_sync(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")
    captured: dict[str, object] = {}

    def _fake_sync_orders_to_sales(repo_arg, store_id, payloads, organization_id=None):
        captured["repo"] = repo_arg
        captured["store_id"] = store_id
        captured["payloads"] = payloads
        captured["organization_id"] = organization_id

    monkeypatch.setattr(shopify_routes, "sync_orders_to_sales", _fake_sync_orders_to_sales)
    body = b'{"id":"order-1","name":"#1001"}'

    response = client.post(
        "/shopify/webhooks",
        content=body,
        headers={
            "X-Shopify-Hmac-Sha256": _webhook_hmac("test_shopify_api_secret", body),
            "X-Shopify-Topic": "orders/create",
            "X-Shopify-Shop-Domain": "marketpulse-ai-2.myshopify.com",
            "X-Shopify-Webhook-Id": "webhook-order-create",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert captured["store_id"] == store["id"]
    assert captured["payloads"] == [{"id": "order-1", "name": "#1001"}]
    assert captured["organization_id"] == store["organization_id"]
    assert repo.is_webhook_processed("webhook-order-create") is True


def test_shopify_webhook_products_update_triggers_product_sync(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")
    captured: dict[str, object] = {}

    def _fake_sync_products_to_skus(repo_arg, store_id, payloads, organization_id=None):
        captured["repo"] = repo_arg
        captured["store_id"] = store_id
        captured["payloads"] = payloads
        captured["organization_id"] = organization_id

    monkeypatch.setattr(shopify_routes, "sync_products_to_skus", _fake_sync_products_to_skus)
    body = b'{"id":"product-1","title":"Soap"}'

    response = client.post(
        "/shopify/webhooks",
        content=body,
        headers={
            "X-Shopify-Hmac-Sha256": _webhook_hmac("test_shopify_api_secret", body),
            "X-Shopify-Topic": "products/update",
            "X-Shopify-Shop-Domain": "marketpulse-ai-2.myshopify.com",
            "X-Shopify-Webhook-Id": "webhook-product-update",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert captured["store_id"] == store["id"]
    assert captured["payloads"] == [{"id": "product-1", "title": "Soap"}]
    assert captured["organization_id"] == store["organization_id"]
    assert repo.is_webhook_processed("webhook-product-update") is True
