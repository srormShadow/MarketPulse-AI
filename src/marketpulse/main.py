import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from marketpulse.api.router import api_router
from marketpulse.core.config import get_settings
from marketpulse.core.logging import configure_logging
from marketpulse.db.init_db import init_db
from marketpulse.routes.router import router as ingestion_router

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)


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
    debug=settings.debug,
    lifespan=lifespan,
)

# ── Configure CORS for React Frontend ─────────────────────────────────────
# This allows the React SPA running on port 5173 (or production domain) 
# to make requests to this FastAPI backend.
origins = [
    "http://localhost:3000",      # React dev server via docker-compose
    "http://127.0.0.1:3000",      # React dev server via docker-compose (IP)
    "http://localhost:5173",      # React Vite dev server
    "http://127.0.0.1:5173",      # React Vite dev server (IP)
    # NOTE: In production, add the FRONTEND_URL from env vars here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ingestion_router)
