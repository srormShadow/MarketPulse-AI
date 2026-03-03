import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from marketpulse.api.router import api_router
from marketpulse.core.config import get_settings
from marketpulse.core.logging import configure_logging
from marketpulse.db.init_db import init_db
from marketpulse.routes.router import router as ingestion_router

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)

# ── Rate limiter (shared instance) ────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
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

# Attach rate limiter state
app.state.limiter = limiter


# ── Global exception handlers ─────────────────────────────────────────────
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


# ── Configure CORS for React Frontend ─────────────────────────────────────
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

_extra = [u.strip() for u in settings.frontend_url.split(",") if u.strip()]

if settings.environment == "production" and _extra:
    origins = _extra
else:
    origins = _extra + _DEV_ORIGINS if _extra else _DEV_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

app.include_router(api_router)
app.include_router(ingestion_router)
