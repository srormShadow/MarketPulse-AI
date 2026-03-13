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


def _migrate_add_org_columns(engine) -> None:
    """Add organization_id columns to existing tables if they don't have them yet."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    migrations = [
        ("skus", "organization_id", "INTEGER REFERENCES organizations(id)"),
        ("sales", "organization_id", "INTEGER REFERENCES organizations(id)"),
        ("forecast_cache", "organization_id", "INTEGER REFERENCES organizations(id)"),
        ("recommendation_logs", "organization_id", "INTEGER REFERENCES organizations(id)"),
        ("upload_events", "organization_id", "INTEGER REFERENCES organizations(id)"),
        ("users", "token_version", "INTEGER NOT NULL DEFAULT 1"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            if table not in inspector.get_table_names():
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing_cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                logger.info("Migration: added %s.%s", table, column)
        conn.commit()


def _init_sqlite() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    from marketpulse.db.base import Base
    from marketpulse.db.repository import SQLiteRepository
    from marketpulse.db.session import SessionLocal, _get_engine
    from marketpulse.models import Festival, HealthPing, Organization, SKU, Sales, ShopifyStore, ShopifyWebhookEvent, User  # noqa: F401 — register models
    from marketpulse.services.festival_seed import seed_festivals_if_empty

    try:
        logger.info("Starting SQLite database initialization")
        engine = _get_engine()
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema ensured via create_all")
        _migrate_add_org_columns(engine)
        _stamp_alembic_head(engine)

        db = SessionLocal()
        try:
            repo = SQLiteRepository(db)
            seed_festivals_if_empty(repo)
            _seed_default_admin(repo)
        finally:
            db.close()

        logger.info("SQLite database initialization completed")
    except SQLAlchemyError as exc:
        logger.exception("SQLite database initialization failed")
        raise RuntimeError("Database initialization failed") from exc
    except Exception as exc:
        logger.exception("Unexpected error during SQLite initialization")
        raise RuntimeError("Unexpected database startup failure") from exc


def _seed_default_admin(repo) -> None:
    """Create a default admin + demo retailer user if no users exist yet.

    Credentials are configured via environment variables (see Settings) and are
    never logged in plaintext.
    """
    settings = get_settings()
    if repo.count_users() > 0:
        return
    if settings.environment.lower() not in {"development", "dev", "local"} or not settings.enable_dev_seed_users:
        logger.info("Skipping default user seeding outside explicit local-dev bootstrap mode")
        return

    from marketpulse.core.auth import hash_password

    admin_email = settings.seed_admin_email
    admin_password = settings.seed_admin_password
    retailer_email = settings.seed_retailer_email
    retailer_password = settings.seed_retailer_password

    # Create default organization for admin
    org = repo.create_organization(name="MarketPulse Admin", plan="enterprise")

    repo.create_user(
        email=admin_email,
        password_hash=hash_password(admin_password),
        role="admin",
        organization_id=org["id"],
    )

    # Create demo retailer organization + user
    retailer_org = repo.create_organization(name="Demo Retail Store", plan="starter")
    repo.create_user(
        email=retailer_email,
        password_hash=hash_password(retailer_password),
        role="retailer",
        organization_id=retailer_org["id"],
    )

    logger.info("Default admin user created (email=%s)", admin_email)
    logger.info("Default retailer user created (email=%s)", retailer_email)


def _stamp_alembic_head(engine) -> None:
    """Stamp the Alembic version table so ``alembic upgrade head`` is a no-op on fresh DBs."""
    try:
        from alembic import command
        from alembic.config import Config

        cfg = Config()
        cfg.set_main_option("script_location", "migrations")
        cfg.set_main_option("sqlalchemy.url", str(engine.url))
        command.stamp(cfg, "head")
        logger.info("Alembic version table stamped at head")
    except Exception:
        logger.debug("Alembic stamp skipped (alembic not installed or migrations dir absent)")


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
