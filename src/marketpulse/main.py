import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from marketpulse.core.secrets import load_secrets

# Load secrets from AWS Secrets Manager BEFORE Settings reads env vars.
load_secrets()

from marketpulse.api.router import api_router  # noqa: E402
from marketpulse.core.config import get_settings  # noqa: E402
from marketpulse.core.logging import configure_logging
from marketpulse.core.metrics import REQUEST_COUNT, REQUEST_LATENCY, metrics_response
from marketpulse.core.rate_limit import limiter
from marketpulse.core.security import verify_api_key
from marketpulse.db.init_db import init_db
from marketpulse.routes.router import router as ingestion_router

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)


def ensure_startup_security() -> None:
    env = settings.environment.lower()
    if env in {"production", "prod"} and not settings.api_key.strip():
        raise RuntimeError("API_KEY must be configured when ENVIRONMENT=production.")

    if env in {"production", "prod"}:
        if not settings.frontend_url.strip():
            raise RuntimeError("FRONTEND_URL must be configured explicitly in production.")
        jwt_secret = settings.jwt_secret.strip()
        # Reject weak or default JWT secrets in non-dev environments.
        if not jwt_secret or jwt_secret == "change-me-in-production" or len(jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET must be configured to a strong, non-default value when ENVIRONMENT=production.")
        if not settings.session_cookie_secure:
            raise RuntimeError("SESSION_COOKIE_SECURE must remain enabled in production.")
        if settings.seed_admin_password or settings.seed_retailer_password or settings.enable_dev_seed_users:
            raise RuntimeError("Default/dev user seeding must be disabled in production.")
        if settings.shopify_api_key and not settings.shopify_token_encryption_key.strip():
            raise RuntimeError("SHOPIFY_TOKEN_ENCRYPTION_KEY must be configured when Shopify integration is enabled.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_startup_security()
    try:
        init_db()
    except Exception:
        logger.exception("Application startup aborted: database initialization failed")
        raise
    yield


app = FastAPI(
    title=settings.app_name,
    debug=False,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"status": "error", "message": "Rate limit exceeded. Please try again later."},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"},
    )


_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

_extra = [u.strip() for u in settings.frontend_url.split(",") if u.strip()]

if settings.environment == "production":
    origins = _extra
else:
    origins = _extra + _DEV_ORIGINS if _extra else _DEV_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization", "X-CSRF-Token"],
)

app.include_router(api_router)
app.include_router(ingestion_router)


# --- Prometheus metrics ---

@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics(_api_key: str = Depends(verify_api_key)):
    from fastapi.responses import Response

    return Response(content=metrics_response(), media_type="text/plain; version=0.0.4; charset=utf-8")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    import time

    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    endpoint = request.url.path
    REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
    REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)
    return response
