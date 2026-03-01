"""Database-focused tests for schema and integrity guarantees."""

from datetime import date

from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from marketpulse.db.repository import SQLiteRepository
from marketpulse.models.festival import Festival
from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU
from marketpulse.services.festival_seed import seed_festivals_if_empty


def test_expected_tables_are_created(test_engine):
    inspector = inspect(test_engine)
    table_names = set(inspector.get_table_names())

    assert "skus" in table_names
    assert "sales" in table_names
    assert "festivals" in table_names


def test_sales_fk_integrity_rejects_unknown_sku(db_session):
    db_session.add(Sales(date=date(2026, 2, 20), sku_id="UNKNOWN", units_sold=10))

    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
    else:
        raise AssertionError("Expected foreign key violation was not raised")


def test_duplicate_sku_upsert_does_not_create_multiple_rows(client, db_session, csv_bytes):
    first = client.post(
        "/upload_csv",
        files={"file": ("sku_valid.csv", csv_bytes("sku_valid.csv"), "text/csv")},
    )
    second = client.post(
        "/upload_csv",
        files={"file": ("sku_duplicate_update.csv", csv_bytes("sku_duplicate_update.csv"), "text/csv")},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    rows = db_session.scalars(select(SKU).where(SKU.sku_id == "SKU100")).all()
    assert len(rows) == 1
    assert rows[0].product_name == "Face Wash Pro"
    assert rows[0].current_inventory == 70


def test_festival_seed_is_idempotent(db_session):
    repo = SQLiteRepository(db_session)
    seed_festivals_if_empty(repo)
    seed_festivals_if_empty(repo)

    rows = db_session.scalars(select(Festival)).all()
    assert len(rows) == 3
