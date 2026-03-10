"""Comprehensive regression coverage for Shopify route behavior."""

import base64
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlparse

import pytest
import httpx

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


# ---------------------------------------------------------------------------
# Connect page tests
# ---------------------------------------------------------------------------


def test_shopify_connect_page_renders_form_when_no_shop_param(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.get("/shopify/connect", follow_redirects=False)

    assert response.status_code == 200
    html = response.text
    assert "Connect your Shopify store" in html
    assert 'name="shop"' in html
    assert ".myshopify.com" in html
    assert "Continue to Shopify" in html


def test_shopify_connect_page_shows_not_configured_when_creds_missing(client, monkeypatch):
    _configure_shopify_env(monkeypatch, api_key="", api_secret="")

    response = client.get("/shopify/connect", follow_redirects=False)

    assert response.status_code == 503
    html = response.text
    assert "not configured" in html
    assert "SHOPIFY_API_KEY" in html


def test_shopify_connect_redirects_to_oauth_when_shop_provided(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.get(
        "/shopify/connect",
        params={"shop": "marketpulse-ai-2.myshopify.com"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    parsed = urlparse(location)
    assert parsed.scheme == "https"
    assert parsed.netloc == "marketpulse-ai-2.myshopify.com"
    assert parsed.path == "/admin/oauth/authorize"
    params = parse_qs(parsed.query)
    assert params["client_id"] == ["test_shopify_api_key"]
    assert params["redirect_uri"] == ["http://localhost:8000/shopify/callback"]
    assert "state" in params


def test_shopify_connect_auto_appends_myshopify_suffix(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.get(
        "/shopify/connect",
        params={"shop": "marketpulse-ai-2"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    assert "marketpulse-ai-2.myshopify.com" in location


def test_shopify_connect_handles_full_url_with_https(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.get(
        "/shopify/connect",
        params={"shop": "https://marketpulse-ai-2.myshopify.com/"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    assert "marketpulse-ai-2.myshopify.com" in location


def test_shopify_connect_shows_error_for_empty_shop_value(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.get(
        "/shopify/connect",
        params={"shop": "   "},
        follow_redirects=False,
    )

    # Empty/whitespace shop should render the form (not redirect)
    assert response.status_code == 200
    assert "Connect your Shopify store" in response.text


def test_shopify_connect_shows_error_for_redirect_uri_misconfigured(client, monkeypatch):
    _configure_shopify_env(monkeypatch, redirect_uri="")

    response = client.get(
        "/shopify/connect",
        params={"shop": "marketpulse-ai-2"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    html = response.text
    assert "SHOPIFY_REDIRECT_URI" in html


# ---------------------------------------------------------------------------
# POST /shopify/install (programmatic API) tests
# ---------------------------------------------------------------------------


def test_shopify_install_returns_authorization_url_with_signed_state(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.post(
        "/shopify/install",
        json={"shop_domain": "https://marketpulse-ai-2.myshopify.com/"},
    )

    assert response.status_code == 200
    payload = response.json()
    parsed = urlparse(payload["authorization_url"])
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "marketpulse-ai-2.myshopify.com"
    assert parsed.path == "/admin/oauth/authorize"
    assert params["client_id"] == ["test_shopify_api_key"]
    assert params["redirect_uri"] == ["http://localhost:8000/shopify/callback"]
    assert params["scope"] == ["read_products,read_orders,read_inventory"]
    assert "." in params["state"][0]


def test_shopify_install_rejects_invalid_shop_domain(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.post("/shopify/install", json={"shop_domain": "example.com"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid shop domain. Must end with .myshopify.com"


def test_shopify_install_rejects_when_oauth_config_missing(client, monkeypatch):
    _configure_shopify_env(monkeypatch, api_key="", api_secret="")

    response = client.post("/shopify/install", json={"shop_domain": "marketpulse-ai-2.myshopify.com"})

    assert response.status_code == 503
    assert "SHOPIFY_API_KEY" in response.json()["detail"]


def test_shopify_install_rejects_when_redirect_uri_missing(client, monkeypatch):
    _configure_shopify_env(monkeypatch, redirect_uri="")

    response = client.post("/shopify/install", json={"shop_domain": "marketpulse-ai-2.myshopify.com"})

    assert response.status_code == 503
    assert response.json()["detail"] == "SHOPIFY_REDIRECT_URI is not configured."


def test_shopify_install_rejects_local_redirect_port_mismatch(client, monkeypatch):
    _configure_shopify_env(monkeypatch, redirect_uri="http://localhost:8001/shopify/callback")

    response = client.post(
        "http://localhost:8000/shopify/install",
        json={"shop_domain": "marketpulse-ai-2.myshopify.com"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "same backend port" in detail
    assert "8000" in detail
    assert "SHOPIFY_REDIRECT_URI=http://localhost:8000/shopify/callback" in detail


def test_shopify_callback_success_creates_store_and_returns_popup_bridge(client, repo, monkeypatch):
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
            assert json == {
                "client_id": "test_shopify_api_key",
                "client_secret": "test_shopify_api_secret",
                "code": "code_from_shopify",
            }
            return _FakeResponse()

    monkeypatch.setattr(shopify_routes.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient())

    _, state = _install_and_get_state(client, "marketpulse-ai-2.myshopify.com")
    callback_params = {
        "code": "code_from_shopify",
        "host": "YWRtaW4uc2hvcGlmeS5jb20vc3RvcmUvbWFya2V0cHVsc2UtYWktMg",
        "shop": "marketpulse-ai-2.myshopify.com",
        "state": state,
        "timestamp": "1773150232",
    }
    callback_params["hmac"] = _shopify_callback_hmac("test_shopify_api_secret", callback_params)

    callback_response = client.get("/shopify/callback", params=callback_params, follow_redirects=False)

    assert callback_response.status_code == 200
    html = callback_response.text
    assert "window.opener.postMessage" in html
    assert "window.close()" in html
    assert "shopify=connected" in html
    assert "Shopify store connected successfully." in html

    store = repo.get_shopify_store_by_domain("marketpulse-ai-2.myshopify.com")
    assert store is not None
    assert store["access_token"] == "shpat_oauth_token"
    assert store["scope"] == "read_products,read_orders,read_inventory"
    assert store["is_active"] is True


def test_shopify_callback_success_updates_existing_store_token(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "old_token", "read_products")
    repo.deactivate_shopify_store("marketpulse-ai-2.myshopify.com")

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"access_token": "fresh_token", "scope": "read_products,read_orders"}

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url, json):
            return _FakeResponse()

    monkeypatch.setattr(shopify_routes.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient())

    _, state = _install_and_get_state(client, "marketpulse-ai-2.myshopify.com")
    callback_response = client.get(
        "/shopify/callback",
        params={"shop": "marketpulse-ai-2.myshopify.com", "code": "new_code", "state": state},
        follow_redirects=False,
    )

    assert callback_response.status_code == 200
    updated = repo.get_shopify_store_by_domain("marketpulse-ai-2.myshopify.com")
    assert updated["access_token"] == "fresh_token"
    assert updated["scope"] == "read_products,read_orders"
    assert updated["is_active"] is True


def test_shopify_callback_rejects_invalid_state_and_returns_popup_bridge(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    callback_response = client.get(
        "/shopify/callback?shop=marketpulse-ai-2.myshopify.com&code=code_from_shopify&state=wrong_state",
        follow_redirects=False,
    )

    assert callback_response.status_code == 200
    html = callback_response.text
    assert '"status": "error"' in html or '"status":"error"' in html
    assert "invalid_state" in html
    assert "Invalid Shopify OAuth state" in html
    assert "window.opener.postMessage" in html


def test_shopify_callback_rejects_shop_mismatch_in_signed_state(client, monkeypatch):
    _configure_shopify_env(monkeypatch)
    mismatched_state = shopify_routes._encode_oauth_state("other-shop.myshopify.com")

    callback_response = client.get(
        f"/shopify/callback?shop=marketpulse-ai-2.myshopify.com&code=code_from_shopify&state={mismatched_state}",
        follow_redirects=False,
    )

    assert callback_response.status_code == 200
    assert "invalid_state" in callback_response.text


def test_shopify_callback_rejects_expired_signed_state(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    original_time = shopify_routes.time.time
    monkeypatch.setattr(shopify_routes.time, "time", lambda: 1_000_000)
    state = shopify_routes._encode_oauth_state("marketpulse-ai-2.myshopify.com")
    monkeypatch.setattr(shopify_routes.time, "time", lambda: 1_000_000 + shopify_routes._STATE_TTL_SECONDS + 1)

    callback_response = client.get(
        f"/shopify/callback?shop=marketpulse-ai-2.myshopify.com&code=code_from_shopify&state={state}",
        follow_redirects=False,
    )

    assert callback_response.status_code == 200
    assert "invalid_state" in callback_response.text

    monkeypatch.setattr(shopify_routes.time, "time", original_time)


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


def test_shopify_callback_handles_token_exchange_failure(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url, json):
            raise httpx.HTTPError("boom")

    import httpx

    monkeypatch.setattr(shopify_routes.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient())

    _, state = _install_and_get_state(client, "marketpulse-ai-2.myshopify.com")
    response = client.get(
        f"/shopify/callback?shop=marketpulse-ai-2.myshopify.com&code=code_from_shopify&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "token_exchange_failed" in response.text
    assert "Failed to complete Shopify authentication." in response.text


def test_shopify_callback_handles_missing_access_token(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"scope": "read_products"}

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url, json):
            return _FakeResponse()

    monkeypatch.setattr(shopify_routes.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient())

    _, state = _install_and_get_state(client, "marketpulse-ai-2.myshopify.com")
    response = client.get(
        f"/shopify/callback?shop=marketpulse-ai-2.myshopify.com&code=code_from_shopify&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "missing_access_token" in response.text
    assert "Shopify did not return an access token." in response.text


def test_shopify_list_stores_empty(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.get("/shopify/stores")

    assert response.status_code == 200
    assert response.json() == {"stores": [], "total": 0}


def test_shopify_list_stores_returns_connected_store(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")

    response = client.get("/shopify/stores")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["stores"][0]["shop_domain"] == "marketpulse-ai-2.myshopify.com"


def test_shopify_disconnect_store_success(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")

    response = client.delete(f"/shopify/stores/{store['id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"
    assert repo.get_shopify_store_by_domain("marketpulse-ai-2.myshopify.com")["is_active"] is False


def test_shopify_disconnect_store_missing_returns_404(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.delete("/shopify/stores/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Store not found"


def test_shopify_sync_missing_store_returns_404(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.post("/shopify/sync/999", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "Store not found"


def test_shopify_sync_disconnected_store_returns_400(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")
    repo.deactivate_shopify_store("marketpulse-ai-2.myshopify.com")

    response = client.post(f"/shopify/sync/{store['id']}", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Store is disconnected"


def test_shopify_sync_missing_credentials_returns_500(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")
    repo.update_shopify_store_token("marketpulse-ai-2.myshopify.com", "", "read_products")

    response = client.post(f"/shopify/sync/{store['id']}", json={})

    assert response.status_code == 500
    assert response.json()["detail"] == "Store credentials unavailable"


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
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["store_id"] == store["id"]
    assert payload["products_synced"] == 3
    assert payload["orders_synced"] == 4
    assert payload["skus_created"] == 2
    assert payload["sales_records_created"] == 7


def test_shopify_sync_internal_failure_returns_json_error(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")

    def _boom(**kwargs):
        raise RuntimeError("sync failed")

    monkeypatch.setattr(shopify_routes, "run_full_sync", _boom)

    response = client.post(f"/shopify/sync/{store['id']}", json={})

    assert response.status_code == 500
    assert response.json() == {"status": "error", "message": "Sync failed due to an internal error."}


def test_shopify_sync_surfaces_upstream_403_with_actionable_message(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")

    request = httpx.Request("GET", "https://marketpulse-ai-2.myshopify.com/admin/api/2024-10/products.json")
    response = httpx.Response(403, request=request)

    def _boom(**kwargs):
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    monkeypatch.setattr(shopify_routes, "run_full_sync", _boom)

    result = client.post(f"/shopify/sync/{store['id']}", json={})

    assert result.status_code == 502
    payload = result.json()
    assert payload["status"] == "error"
    assert "Shopify rejected the sync request" in payload["message"]
    assert "read_products, read_orders, read_inventory" in payload["message"]


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


def test_shopify_webhook_rejects_missing_headers(client, monkeypatch):
    _configure_shopify_env(monkeypatch)

    response = client.post("/shopify/webhooks", content=b"{}")

    assert response.status_code == 400
    assert response.json()["status"] == "missing headers"


def test_shopify_webhook_rejects_invalid_payload(client, monkeypatch):
    _configure_shopify_env(monkeypatch)
    body = b"{not-json"

    response = client.post(
        "/shopify/webhooks",
        content=body,
        headers={
            "X-Shopify-Hmac-Sha256": _webhook_hmac("test_shopify_api_secret", body),
            "X-Shopify-Topic": "orders/create",
            "X-Shopify-Shop-Domain": "marketpulse-ai-2.myshopify.com",
        },
    )

    assert response.status_code == 400
    assert response.json()["status"] == "invalid payload"


def test_shopify_webhook_returns_already_processed_for_duplicate_event(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    repo.record_webhook_event("webhook-1", "orders/create", "marketpulse-ai-2.myshopify.com")
    body = b'{"id":"order-1"}'

    response = client.post(
        "/shopify/webhooks",
        content=body,
        headers={
            "X-Shopify-Hmac-Sha256": _webhook_hmac("test_shopify_api_secret", body),
            "X-Shopify-Topic": "orders/create",
            "X-Shopify-Shop-Domain": "marketpulse-ai-2.myshopify.com",
            "X-Shopify-Webhook-Id": "webhook-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "already_processed"


def test_shopify_webhook_app_uninstalled_deactivates_store(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")
    body = b"{}"

    response = client.post(
        "/shopify/webhooks",
        content=body,
        headers={
            "X-Shopify-Hmac-Sha256": _webhook_hmac("test_shopify_api_secret", body),
            "X-Shopify-Topic": "app/uninstalled",
            "X-Shopify-Shop-Domain": "marketpulse-ai-2.myshopify.com",
            "X-Shopify-Webhook-Id": "webhook-uninstall",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert repo.get_shopify_store_by_domain("marketpulse-ai-2.myshopify.com")["is_active"] is False
    assert repo.is_webhook_processed("webhook-uninstall") is True


def test_shopify_webhook_orders_create_triggers_sales_sync(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")
    captured: dict[str, object] = {}

    def _fake_sync_orders_to_sales(repo_arg, store_id, payloads):
        captured["repo"] = repo_arg
        captured["store_id"] = store_id
        captured["payloads"] = payloads

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
    assert repo.is_webhook_processed("webhook-order-create") is True


def test_shopify_webhook_products_update_triggers_product_sync(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    store = repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")
    captured: dict[str, object] = {}

    def _fake_sync_products_to_skus(repo_arg, store_id, payloads):
        captured["repo"] = repo_arg
        captured["store_id"] = store_id
        captured["payloads"] = payloads

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
    assert repo.is_webhook_processed("webhook-product-update") is True


def test_shopify_webhook_skips_sync_for_inactive_store_but_records_event(client, repo, monkeypatch):
    _configure_shopify_env(monkeypatch)
    repo.create_shopify_store("marketpulse-ai-2.myshopify.com", "token", "read_products")
    repo.deactivate_shopify_store("marketpulse-ai-2.myshopify.com")

    def _boom(*args, **kwargs):
        raise AssertionError("Sync helper should not be called for inactive stores")

    monkeypatch.setattr(shopify_routes, "sync_orders_to_sales", _boom)
    body = b'{"id":"order-1"}'

    response = client.post(
        "/shopify/webhooks",
        content=body,
        headers={
            "X-Shopify-Hmac-Sha256": _webhook_hmac("test_shopify_api_secret", body),
            "X-Shopify-Topic": "orders/updated",
            "X-Shopify-Shop-Domain": "marketpulse-ai-2.myshopify.com",
            "X-Shopify-Webhook-Id": "webhook-inactive-order",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert repo.is_webhook_processed("webhook-inactive-order") is True
