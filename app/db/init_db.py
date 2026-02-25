"""Database initialization utilities."""

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.db.base import Base
from app.models import Festival, HealthPing, SKU, Sales
from app.services.festival_seed import seed_festivals_if_empty

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Initialize DB schema and seed baseline reference data."""

    from app.db.session import SessionLocal, engine

    try:
        logger.info("Starting database initialization")
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema ensured via create_all")

        with SessionLocal() as db:
            seed_festivals_if_empty(db)

        logger.info("Database initialization completed")
    except SQLAlchemyError as exc:
        logger.exception("Database initialization failed")
        raise RuntimeError("Database initialization failed") from exc
    except Exception as exc:
        logger.exception("Unexpected error during database initialization")
        raise RuntimeError("Unexpected database startup failure") from exc
