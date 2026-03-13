"""SQLAlchemy engine and session factory.

Engine creation is lazy (deferred to first use) so that importing this module
does not crash when USE_DYNAMO=true and no SQLite database is configured.
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketpulse.core.config import get_settings


@lru_cache
def _get_engine():
    settings = get_settings()
    connect_args: dict = {}
    pool_kwargs: dict = {"pool_pre_ping": True}

    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # SQLite doesn't support real connection pooling; use StaticPool.
        pool_kwargs["poolclass"] = StaticPool
    else:
        # PostgreSQL / MySQL in production: explicit pool tuning.
        pool_kwargs["pool_size"] = 10
        pool_kwargs["max_overflow"] = 20
        pool_kwargs["pool_timeout"] = 30
        pool_kwargs["pool_recycle"] = 1800  # recycle connections every 30 min

    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        **pool_kwargs,
    )

    if settings.database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@lru_cache
def _get_session_factory():
    return sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())


def SessionLocal() -> Session:
    """Create a new SQLAlchemy Session."""
    return _get_session_factory()()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — kept for backward compatibility with tests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
