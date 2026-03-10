"""Database initialization utilities."""

from __future__ import annotations

import logging

from marketpulse.core.config import get_settings

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Initialize the active database backend and seed reference data."""
    settings = get_settings()

    if settings.use_dynamo:
        _init_dynamo()
    else:
        _init_sqlite()


def _init_sqlite() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    from marketpulse.db.base import Base
    from marketpulse.db.repository import SQLiteRepository
    from marketpulse.db.session import SessionLocal, _get_engine
    from marketpulse.models import Festival, HealthPing, SKU, Sales, ShopifyStore, ShopifyWebhookEvent  # noqa: F401 — register models
    from marketpulse.services.festival_seed import seed_festivals_if_empty

    try:
        logger.info("Starting SQLite database initialization")
        Base.metadata.create_all(bind=_get_engine())
        logger.info("Database schema ensured via create_all")

        db = SessionLocal()
        try:
            repo = SQLiteRepository(db)
            seed_festivals_if_empty(repo)
        finally:
            db.close()

        logger.info("SQLite database initialization completed")
    except SQLAlchemyError as exc:
        logger.exception("SQLite database initialization failed")
        raise RuntimeError("Database initialization failed") from exc
    except Exception as exc:
        logger.exception("Unexpected error during SQLite initialization")
        raise RuntimeError("Unexpected database startup failure") from exc


def _init_dynamo() -> None:
    from marketpulse.db.dynamo import ensure_tables_exist
    from marketpulse.db.dynamo_repository import DynamoRepository
    from marketpulse.services.festival_seed import seed_festivals_if_empty

    try:
        logger.info("Starting DynamoDB initialization")
        ensure_tables_exist()
        repo = DynamoRepository()
        seed_festivals_if_empty(repo)
        logger.info("DynamoDB initialization completed")
    except Exception as exc:
        logger.exception("DynamoDB initialization failed")
        raise RuntimeError("DynamoDB initialization failed") from exc
