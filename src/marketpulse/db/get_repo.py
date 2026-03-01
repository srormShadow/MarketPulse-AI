"""FastAPI dependency that yields the active DataRepository backend."""

from __future__ import annotations

from collections.abc import Generator

from marketpulse.core.config import get_settings
from marketpulse.db.repository import DataRepository


def get_repo() -> Generator[DataRepository, None, None]:
    """Yield a DataRepository wired to the active backend.

    USE_DYNAMO=true  → DynamoRepository  (stateless, no teardown)
    USE_DYNAMO=false → SQLiteRepository  (wraps a SQLAlchemy Session)
    """
    settings = get_settings()

    if settings.use_dynamo:
        from marketpulse.db.dynamo_repository import DynamoRepository

        yield DynamoRepository()
    else:
        from marketpulse.db.session import SessionLocal

        db = SessionLocal()
        try:
            from marketpulse.db.repository import SQLiteRepository

            yield SQLiteRepository(db)
        finally:
            db.close()
