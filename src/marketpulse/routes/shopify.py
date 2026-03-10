"""Shopify integration routes: OAuth install, store management, sync, and webhooks."""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from marketpulse.core.config import get_settings
from marketpulse.core.rate_limit import limiter
from marketpulse.core.security import verify_api_key
from marketpulse.db.get_repo import get_repo
from marketpulse.schemas.shopify import (
    ShopifyInstallRequest,
    ShopifyInstallResponse,
    ShopifyStoreListResponse,
    ShopifyStoreResponse,
    ShopifySyncRequest,
    ShopifySyncResponse,
)
from marketpulse.services.shopify_ingestion import (
    run_full_sync,
    sync_orders_to_sales,
    sync_products_to_skus,
)

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["shopify"])
_STATE_TTL_SECONDS = 600


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_shopify_configured() -> bool:
    """Return True if Shopify OAuth credentials are present."""
    settings = get_settings()
    return bool(settings.shopify_api_key and settings.shopify_api_secret)


def _validate_shopify_configured() -> None:
    """Raise if Shopify OAuth credentials are not configured."""
    if not _is_shopify_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shopify integration is not configured. Set SHOPIFY_API_KEY and SHOPIFY_API_SECRET.",
        )


def _validate_local_redirect_uri_consistency(request: Request, redirect_uri: str) -> None:
    """Fail fast in local development if OAuth starts on one port and callbacks return to another."""
    request_url = request.url
    request_port = request_url.port or (443 if request_url.scheme == "https" else 80)
    parsed_redirect = urlparse(redirect_uri)
    redirect_port = parsed_redirect.port or (443 if parsed_redirect.scheme == "https" else 80)
    local_hosts = {"127.0.0.1", "localhost"}

    if request_url.hostname in local_hosts and parsed_redirect.hostname in local_hosts and request_port != redirect_port:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Local Shopify OAuth is misconfigured. "
                "SHOPIFY_REDIRECT_URI must point to the same backend port that started the flow. "
                f"Current request uses {request_port}, but redirect URI uses {redirect_port}. "
                f"Set SHOPIFY_REDIRECT_URI=http://localhost:{request_port}/shopify/callback and restart the backend."
            ),
        )


def _frontend_redirect_url(status_value: str, shop: str, *, reason: str = "", message: str = "") -> str:
    settings = get_settings()
    if settings.frontend_url:
        frontend_url = settings.frontend_url.split(",")[0].strip()
    elif settings.shopify_redirect_uri:
        parsed = urlparse(settings.shopify_redirect_uri)
        frontend_url = f"{parsed.scheme}://{parsed.netloc}"
    else:
        frontend_url = "http://localhost:5173"
    params = {"tab": "data", "shopify": status_value, "shop": shop}
    if reason:
        params["reason"] = reason
    if message:
        params["message"] = message
    return f"{frontend_url}?{urlencode(params)}"


def _oauth_callback_response(status_value: str, shop: str, *, reason: str = "", message: str = "") -> HTMLResponse:
    frontend_url = _frontend_redirect_url(status_value, shop, reason=reason, message=message)
    frontend_origin = urlparse(frontend_url).scheme + "://" + urlparse(frontend_url).netloc
    payload = {
        "type": "shopify-oauth-result",
        "status": status_value,
        "shop": shop,
        "reason": reason,
        "message": message,
        "redirectUrl": frontend_url,
    }
    payload_json = json.dumps(payload)
    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Connecting Shopify...</title>
  </head>
  <body>
    <script>
      (function() {{
        const payload = {payload_json};
        const redirectUrl = payload.redirectUrl;
        try {{
          if (window.opener && !window.opener.closed) {{
            window.opener.postMessage(payload, {json.dumps(frontend_origin)});
            window.close();
            return;
          }}
        }} catch (error) {{
          console.error('Failed to notify MarketPulse opener', error);
        }}
        window.location.replace(redirectUrl);
      }})();
    </script>
    <p>Returning to MarketPulse...</p>
    <p><a href="{frontend_url}">Continue</a></p>
  </body>
</html>"""
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)


def _state_signing_secret() -> bytes:
    settings = get_settings()
    return settings.shopify_api_secret.encode("utf-8")


def _encode_oauth_state(shop: str) -> str:
    payload = {
        "shop": shop,
        "iat": int(time.time()),
        "nonce": secrets.token_urlsafe(16),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = hmac.new(_state_signing_secret(), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{payload_b64}.{signature_b64}"


def _decode_oauth_state(state: str, expected_shop: str) -> None:
    try:
        payload_b64, signature_b64 = state.split(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed Shopify OAuth state.") from exc

    expected_signature = hmac.new(
        _state_signing_secret(),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    provided_signature = base64.urlsafe_b64decode(signature_b64 + "=" * (-len(signature_b64) % 4))
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise ValueError("Shopify OAuth state signature is invalid.")

    payload_bytes = base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4))
    payload = json.loads(payload_bytes.decode("utf-8"))
    issued_at = int(payload.get("iat", 0))
    shop = str(payload.get("shop", "")).strip().lower()
    if shop != expected_shop:
        raise ValueError("Shopify OAuth state shop does not match callback shop.")

    if issued_at <= 0 or (time.time() - issued_at) > _STATE_TTL_SECONDS:
        raise ValueError("Shopify OAuth state has expired.")


def _validate_shop_domain(shop: str) -> str:
    """Validate and normalize a Shopify domain. Raises HTTPException on invalid input."""
    clean = shop.strip().lower()
    for prefix in ("https://", "http://"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
    clean = clean.rstrip("/")
    if not clean.endswith(".myshopify.com"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid shop domain. Must end with .myshopify.com",
        )
    return clean


def _normalize_shop_input(raw: str) -> str | None:
    """Normalize freeform shop input to a full myshopify.com domain, or None if empty."""
    clean = raw.strip().lower()
    if not clean:
        return None
    for prefix in ("https://", "http://"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
    clean = clean.rstrip("/")
    if not clean.endswith(".myshopify.com"):
        clean = f"{clean}.myshopify.com"
    return clean


def _build_authorization_url(request: Request, shop: str) -> str:
    """Build the Shopify OAuth authorization URL for a validated shop domain."""
    settings = get_settings()
    redirect_uri = settings.shopify_redirect_uri
    if not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SHOPIFY_REDIRECT_URI is not configured.",
        )
    _validate_local_redirect_uri_consistency(request, redirect_uri)
    state = _encode_oauth_state(shop)
    params = urlencode(
        {
            "client_id": settings.shopify_api_key,
            "scope": settings.shopify_scopes,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"https://{shop}/admin/oauth/authorize?{params}"


# ---------------------------------------------------------------------------
# Connect page HTML templates
# ---------------------------------------------------------------------------


_CONNECT_PAGE_CSS = """\
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background: #0c0f1a; color: #e2e8f0;
      min-height: 100vh; display: flex; align-items: center; justify-content: center;
    }
    .card {
      background: #151928; border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px; padding: 40px 36px; max-width: 420px; width: 100%; text-align: center;
    }
    .logo { display: inline-flex; align-items: center; gap: 10px; margin-bottom: 28px; }
    .logo svg { width: 28px; height: 28px; fill: none; stroke: #96bf48; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .logo span { font-size: 15px; font-weight: 700; letter-spacing: 0.5px; color: #94a3b8; text-transform: uppercase; }
    h1 { font-size: 22px; font-weight: 700; margin-bottom: 8px; color: #f1f5f9; }
    .subtitle { font-size: 14px; color: #94a3b8; margin-bottom: 28px; line-height: 1.5; }
    .field { position: relative; margin-bottom: 16px; }
    .field input {
      width: 100%; background: #0c0f1a; border: 1px solid rgba(255,255,255,0.12);
      border-radius: 12px; padding: 14px 150px 14px 16px; font-size: 15px; color: #e2e8f0;
      outline: none; transition: border-color 0.2s;
    }
    .field input:focus { border-color: #96bf48; box-shadow: 0 0 0 3px rgba(150,191,72,0.15); }
    .field input::placeholder { color: #4a5568; }
    .suffix { position: absolute; right: 16px; top: 50%; transform: translateY(-50%); font-size: 13px; color: #64748b; pointer-events: none; }
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 8px;
      width: 100%; padding: 14px 20px; font-size: 15px; font-weight: 600; color: #fff;
      background: #96bf48; border: none; border-radius: 12px; cursor: pointer;
      transition: background 0.2s, opacity 0.2s;
    }
    .btn:hover { background: #7ea83d; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .help { margin-top: 20px; font-size: 12px; color: #64748b; line-height: 1.5; }
    .error {
      background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.25); color: #fca5a5;
      border-radius: 10px; padding: 12px 16px; font-size: 13px; margin-bottom: 20px;
      text-align: left; line-height: 1.5;
    }
    code {
      display: inline-block; margin-top: 16px; background: #0c0f1a;
      border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 10px 14px;
      font-size: 12px; color: #96bf48; text-align: left; word-break: break-all;
    }"""

_LOGO_SVG = (
    '<svg viewBox="0 0 24 24"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/>'
    '<line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>'
)

_ARROW_SVG = (
    '<svg viewBox="0 0 24 24"><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/>'
    '<polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>'
)


def _render_connect_page(*, error_message: str = "", prefill: str = "") -> HTMLResponse:
    """Render the branded Shopify connect page."""
    error_html = f'<div class="error">{error_message}</div>' if error_message else ""
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Connect Shopify &mdash; MarketPulse</title>
  <style>{_CONNECT_PAGE_CSS}</style>
</head>
<body>
  <div class="card">
    <div class="logo">{_LOGO_SVG}<span>MarketPulse</span></div>
    <h1>Connect your Shopify store</h1>
    <p class="subtitle">
      Enter your store name and we'll take you to Shopify to authorize the connection.
    </p>
    {error_html}
    <form method="get" action="/shopify/connect">
      <div class="field">
        <input
          type="text" name="shop" placeholder="your-store"
          value="{prefill}" required autofocus
          autocomplete="off" autocapitalize="off" spellcheck="false"
        />
        <span class="suffix">.myshopify.com</span>
      </div>
      <button type="submit" class="btn">{_ARROW_SVG} Continue to Shopify</button>
    </form>
    <p class="help">
      You'll be redirected to Shopify to approve access. No passwords are shared with MarketPulse.
    </p>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)


def _render_not_configured_page() -> HTMLResponse:
    """Render a friendly error page when Shopify is not configured."""
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Shopify Not Configured &mdash; MarketPulse</title>
  <style>{_CONNECT_PAGE_CSS}</style>
</head>
<body>
  <div class="card">
    <h1 style="color:#fca5a5">Shopify integration is not configured</h1>
    <p class="subtitle">
      To connect a Shopify store, set the following environment variables and restart the backend:
    </p>
    <code>SHOPIFY_API_KEY=your_key<br/>SHOPIFY_API_SECRET=your_secret<br/>SHOPIFY_REDIRECT_URI=your_callback_url</code>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


# ---------------------------------------------------------------------------
# Connect page — the primary entry point for Shopify OAuth
# ---------------------------------------------------------------------------


@router.get("/shopify/connect", response_model=None)
@limiter.limit("15/minute")
async def connect_page(
    request: Request,
    shop: str = Query(default=""),
) -> HTMLResponse | RedirectResponse:
    """Backend-served connect page that drives the Shopify OAuth flow.

    - No ``shop`` param → render the branded connect form.
    - ``shop`` param provided → validate, build OAuth URL, redirect to Shopify.

    This serves as both the direct-connect entry point (opened from the frontend
    in a popup) and the Shopify App Store install entry point (Shopify sends
    ``?shop=domain.myshopify.com`` automatically).
    """
    if not _is_shopify_configured():
        return _render_not_configured_page()

    raw_shop = shop.strip()
    if not raw_shop:
        return _render_connect_page()

    normalized = _normalize_shop_input(raw_shop)
    if not normalized or not normalized.endswith(".myshopify.com"):
        return _render_connect_page(
            error_message="Please enter a valid Shopify store name.",
            prefill=raw_shop,
        )

    try:
        validated = _validate_shop_domain(normalized)
        authorization_url = _build_authorization_url(request, validated)
    except HTTPException as exc:
        return _render_connect_page(error_message=str(exc.detail), prefill=raw_shop)

    return RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# OAuth endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/shopify/install",
    response_model=ShopifyInstallResponse,
)
@limiter.limit("10/minute")
async def initiate_install(
    request: Request,
    payload: ShopifyInstallRequest = Body(...),
    _api_key: str = Depends(verify_api_key),
) -> ShopifyInstallResponse:
    """Generate a Shopify OAuth authorization URL (programmatic API)."""
    _validate_shopify_configured()
    shop = _validate_shop_domain(payload.shop_domain)
    authorization_url = _build_authorization_url(request, shop)
    return ShopifyInstallResponse(authorization_url=authorization_url)


@router.get("/shopify/callback", response_model=None)
@limiter.limit("10/minute")
async def oauth_callback(
    request: Request,
    shop: str = Query(...),
    code: str = Query(...),
    state: str = Query(...),
    hmac_param: str = Query(default="", alias="hmac"),
    repo: "DataRepository" = Depends(get_repo),
) -> HTMLResponse | JSONResponse:
    """Handle Shopify OAuth callback and persist the returned token."""
    _validate_shopify_configured()
    shop = _validate_shop_domain(shop)
    settings = get_settings()

    if hmac_param:
        query_params = dict(request.query_params)
        query_params.pop("hmac", None)
        sorted_params = "&".join(f"{key}={value}" for key, value in sorted(query_params.items()))
        computed = hmac.new(
            settings.shopify_api_secret.encode("utf-8"),
            sorted_params.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(computed, hmac_param):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"status": "error", "message": "HMAC verification failed."},
            )

    try:
        _decode_oauth_state(state, shop)
    except ValueError:
        logger.warning("Invalid OAuth state received for shop=%s", shop, exc_info=True)
        return _oauth_callback_response(
            "error",
            shop,
            reason="invalid_state",
            message=(
                "Invalid Shopify OAuth state. Restart the connection from MarketPulse and "
                "complete the newest Shopify approval tab only."
            ),
        )

    token_url = f"https://{shop}/admin/oauth/access_token"
    token_payload = {
        "client_id": settings.shopify_api_key,
        "client_secret": settings.shopify_api_secret,
        "code": code,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.shopify_api_timeout) as client:
            token_response = await client.post(token_url, json=token_payload)
            token_response.raise_for_status()
            token_data = token_response.json()
    except (httpx.HTTPError, httpx.TimeoutException):
        logger.exception("Failed to exchange Shopify OAuth code for shop=%s", shop)
        return _oauth_callback_response(
            "error",
            shop,
            reason="token_exchange_failed",
            message="Failed to complete Shopify authentication.",
        )

    access_token = str(token_data.get("access_token", "")).strip()
    scope = str(token_data.get("scope", "")).strip()
    if not access_token:
        return _oauth_callback_response(
            "error",
            shop,
            reason="missing_access_token",
            message="Shopify did not return an access token.",
        )

    existing = repo.get_shopify_store_by_domain(shop)
    if existing:
        repo.update_shopify_store_token(shop, access_token, scope)
        store_id = existing["id"]
    else:
        store = repo.create_shopify_store(shop, access_token, scope)
        store_id = store["id"]

    logger.info("Shopify store connected via OAuth: shop=%s store_id=%d", shop, store_id)
    return _oauth_callback_response(
        "connected",
        shop,
        message="Shopify store connected successfully.",
    )


# ---------------------------------------------------------------------------
# Store management
# ---------------------------------------------------------------------------


@router.get(
    "/shopify/stores",
    response_model=ShopifyStoreListResponse,
)
async def list_stores(
    repo: "DataRepository" = Depends(get_repo),
    _api_key: str = Depends(verify_api_key),
) -> ShopifyStoreListResponse:
    """List connected Shopify stores."""
    stores = repo.list_shopify_stores()
    return ShopifyStoreListResponse(
        stores=[ShopifyStoreResponse(**store) for store in stores],
        total=len(stores),
    )


@router.delete("/shopify/stores/{store_id}")
async def disconnect_store(
    store_id: int,
    repo: "DataRepository" = Depends(get_repo),
    _api_key: str = Depends(verify_api_key),
) -> JSONResponse:
    """Disconnect a Shopify store."""
    store = repo.get_shopify_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    repo.deactivate_shopify_store(store["shop_domain"])
    return JSONResponse(content={"status": "disconnected", "store_id": store_id})


# ---------------------------------------------------------------------------
# Data sync
# ---------------------------------------------------------------------------


@router.post(
    "/shopify/sync/{store_id}",
    response_model=ShopifySyncResponse,
)
@limiter.limit("3/minute")
async def trigger_sync(
    request: Request,
    store_id: int,
    payload: ShopifySyncRequest | None = Body(default=None),
    repo: "DataRepository" = Depends(get_repo),
    _api_key: str = Depends(verify_api_key),
) -> ShopifySyncResponse | JSONResponse:
    """Trigger a manual sync from a connected Shopify store."""
    store_summary = repo.get_shopify_store(store_id)
    if not store_summary:
        raise HTTPException(status_code=404, detail="Store not found")
    if not store_summary.get("is_active"):
        raise HTTPException(status_code=400, detail="Store is disconnected")

    store_full = repo.get_shopify_store_by_domain(store_summary["shop_domain"])
    if not store_full or not store_full.get("access_token"):
        raise HTTPException(status_code=500, detail="Store credentials unavailable")

    access_token = str(store_full["access_token"]).strip()
    sync_params = payload or ShopifySyncRequest()

    try:
        result = run_full_sync(
            repo=repo,
            store_id=store_id,
            shop_domain=store_full["shop_domain"],
            access_token=access_token,
            sync_products=sync_params.sync_products,
            sync_orders=sync_params.sync_orders,
            orders_days_back=sync_params.orders_days_back,
        )
    except httpx.HTTPStatusError as exc:
        logger.exception("Shopify sync rejected by upstream API for store_id=%d", store_id)
        upstream_status = exc.response.status_code
        if upstream_status in {401, 403}:
            detail = (
                "Shopify rejected the sync request. Verify this app is installed on the same store "
                "and has the required Admin API scopes: read_products, read_orders, read_inventory. "
                "If you changed scopes in Shopify, reinstall the app before syncing again."
            )
        else:
            detail = f"Shopify API request failed with status {upstream_status} during sync."
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"status": "error", "message": detail},
        )
    except Exception:
        logger.exception("Shopify sync failed for store_id=%d", store_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Sync failed due to an internal error."},
        )

    return ShopifySyncResponse(
        status="completed",
        store_id=store_id,
        shop_domain=store_full["shop_domain"],
        **result,
    )


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


@router.post("/shopify/webhooks")
async def handle_webhook(
    request: Request,
    repo: "DataRepository" = Depends(get_repo),
) -> JSONResponse:
    """Handle incoming Shopify webhooks for real-time data updates."""
    settings = get_settings()
    body_bytes = await request.body()

    shopify_hmac = request.headers.get("X-Shopify-Hmac-Sha256", "")
    if settings.shopify_api_secret and shopify_hmac:
        computed = hmac.new(
            settings.shopify_api_secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256,
        )
        expected = base64.b64encode(computed.digest()).decode("utf-8")
        if not hmac.compare_digest(expected, shopify_hmac):
            logger.warning("Webhook HMAC verification failed")
            return JSONResponse(status_code=401, content={"status": "unauthorized"})

    topic = request.headers.get("X-Shopify-Topic", "")
    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
    webhook_id = request.headers.get("X-Shopify-Webhook-Id", "")

    if not topic or not shop_domain:
        return JSONResponse(status_code=400, content={"status": "missing headers"})

    if webhook_id and repo.is_webhook_processed(webhook_id):
        return JSONResponse(content={"status": "already_processed"})

    logger.info("Shopify webhook received: topic=%s shop=%s", topic, shop_domain)

    try:
        payload = json.loads(body_bytes) if body_bytes else {}
    except (json.JSONDecodeError, ValueError):
        return JSONResponse(status_code=400, content={"status": "invalid payload"})

    if topic == "app/uninstalled":
        repo.deactivate_shopify_store(shop_domain)
        logger.info("Shopify store uninstalled: %s", shop_domain)
    elif topic in ("orders/create", "orders/updated"):
        store = repo.get_shopify_store_by_domain(shop_domain)
        if store and store.get("is_active"):
            sync_orders_to_sales(repo, store["id"], [payload])
    elif topic == "products/update":
        store = repo.get_shopify_store_by_domain(shop_domain)
        if store and store.get("is_active"):
            sync_products_to_skus(repo, store["id"], [payload])

    if webhook_id:
        repo.record_webhook_event(webhook_id, topic, shop_domain)

    return JSONResponse(content={"status": "ok"})
