"""Pytest shared fixtures for isolated FastAPI + SQLite testing."""

import pathlib
import sys
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from marketpulse.db.base import Base
from marketpulse.db.get_repo import get_repo
from marketpulse.db.repository import SQLiteRepository
from marketpulse.main import app


@pytest.fixture(scope="session")
def test_engine():
    """Create a shared in-memory SQLite engine with FK enforcement enabled."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Provide a fresh transactional session with clean tables per test."""

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def repo(db_session: Session) -> Generator[SQLiteRepository, None, None]:
    """Wrap the test session in a SQLiteRepository for service-level tests."""
    yield SQLiteRepository(db_session)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a TestClient with DB dependency overridden to isolated session."""

    def override_get_repo() -> Generator[SQLiteRepository, None, None]:
        yield SQLiteRepository(db_session)

    app.dependency_overrides[get_repo] = override_get_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def data_dir() -> pathlib.Path:
    """Return path to static CSV fixtures used across tests."""

    return PROJECT_ROOT / "tests" / "data"


@pytest.fixture
def csv_bytes(data_dir: pathlib.Path):
    """Load a CSV fixture file as bytes for multipart upload tests."""

    def _loader(filename: str) -> bytes:
        return (data_dir / filename).read_bytes()

    return _loader
