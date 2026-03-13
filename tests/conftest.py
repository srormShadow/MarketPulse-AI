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
SRC_ROOT = PROJECT_ROOT / "src"
for candidate in (PROJECT_ROOT, SRC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from marketpulse.core.auth import hash_password
from marketpulse.core.config import get_settings
from marketpulse.core.login_throttle import _store as _throttle_store
from marketpulse.db.base import Base
from marketpulse.db.get_repo import get_repo
from marketpulse.db.repository import SQLiteRepository
from marketpulse.main import app
from marketpulse.models.organization import Organization


TEST_RETAILER = {
    "email": "retailer@test.local",
    "password": "supersecure123",
    "role": "retailer",
}
TEST_ADMIN = {
    "email": "admin@test.local",
    "password": "supersecure123",
    "role": "admin",
}


@pytest.fixture(autouse=True)
def _clear_login_throttle():
    """Reset login throttle state between tests to prevent cross-test lockouts."""
    _throttle_store.clear()
    yield
    _throttle_store.clear()


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Reset cached settings between tests so env overrides do not leak."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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

    default_org = Organization(name="Default Test Org", plan="starter")
    session.add(default_org)
    session.flush()
    session.info["default_org_id"] = int(default_org.id)

    @event.listens_for(session, "before_flush")
    def _assign_default_org(current_session, flush_context, instances) -> None:  # noqa: ARG001
        default_org_id = current_session.info.get("default_org_id")
        for instance in list(current_session.new):
            if isinstance(instance, Organization):
                continue
            if hasattr(instance, "organization_id") and getattr(instance, "organization_id", None) is None:
                setattr(instance, "organization_id", default_org_id)

    try:
        yield session
    finally:
        event.remove(session, "before_flush", _assign_default_org)
        session.close()


@pytest.fixture(scope="function")
def repo(db_session: Session) -> Generator[SQLiteRepository, None, None]:
    """Wrap the test session in a SQLiteRepository for service-level tests."""
    yield SQLiteRepository(db_session)


def _install_repo_override(db_session: Session) -> None:
    def override_get_repo() -> Generator[SQLiteRepository, None, None]:
        yield SQLiteRepository(db_session)

    app.dependency_overrides[get_repo] = override_get_repo


def _bootstrap_user(db_session: Session, *, role: str, email: str, password: str) -> dict[str, str | int]:
    repository = SQLiteRepository(db_session)
    organization_id = int(db_session.info["default_org_id"])
    user = repository.create_user(
        email=email,
        password_hash=hash_password(password),
        role=role,
        organization_id=organization_id,
    )
    return {
        "email": user["email"],
        "password": password,
        "organization_id": organization_id,
        "user_id": user["id"],
    }


def _login_test_client(test_client: TestClient, *, email: str, password: str) -> None:
    response = test_client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    csrf_token = response.json()["csrf_token"]
    test_client.headers.update({"X-CSRF-Token": csrf_token})


@pytest.fixture(scope="function")
def anonymous_client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a TestClient with DB dependency overridden but without auth."""

    _install_repo_override(db_session)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a retailer-authenticated TestClient with CSRF header configured."""

    _install_repo_override(db_session)
    _bootstrap_user(db_session, **TEST_RETAILER)
    with TestClient(app) as test_client:
        _login_test_client(test_client, email=TEST_RETAILER["email"], password=TEST_RETAILER["password"])
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create an admin-authenticated TestClient with CSRF header configured."""

    _install_repo_override(db_session)
    _bootstrap_user(db_session, **TEST_ADMIN)
    with TestClient(app) as test_client:
        _login_test_client(test_client, email=TEST_ADMIN["email"], password=TEST_ADMIN["password"])
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
