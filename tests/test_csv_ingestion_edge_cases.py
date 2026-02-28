"""Advanced edge-case tests for CSV ingestion behavior."""

from datetime import date

from sqlalchemy import func, select

from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU
from tests.utils.csv_factory import build_sales_csv, build_sku_csv


def test_sku_csv_with_unexpected_extra_columns_is_accepted(client, db_session):
    csv_payload = (
        "sku_id,product_name,category,mrp,cost,current_inventory,unexpected_col\n"
        "SKU_X1,Soap,Grocery,50,30,100,ignore_me\n"
    ).encode("utf-8")

    response = client.post("/upload_csv", files={"file": ("sku_extra.csv", csv_payload, "text/csv")})

    assert response.status_code == 200
    stored = db_session.scalar(select(SKU).where(SKU.sku_id == "SKU_X1"))
    assert stored is not None


def test_sku_csv_headers_with_whitespace_are_normalized(client, db_session):
    csv_payload = (
        "  sku_id  , product_name , category , mrp , cost , current_inventory  \n"
        "SKU_WS,  conditioner  ,personal care,220,140,20\n"
    ).encode("utf-8")

    response = client.post("/upload_csv", files={"file": ("sku_ws.csv", csv_payload, "text/csv")})

    assert response.status_code == 200
    row = db_session.scalar(select(SKU).where(SKU.sku_id == "SKU_WS"))
    assert row is not None
    assert row.product_name == "conditioner"
    assert row.category == "Personal Care"


def test_mixed_case_sku_id_is_normalized_to_uppercase(client, db_session):
    sku_payload = build_sku_csv([
        {
            "sku_id": "SkU_CaSe_1",
            "product_name": "Body Wash",
            "category": "Personal Care",
            "mrp": 180,
            "cost": 110,
            "current_inventory": 30,
        }
    ])
    sales_payload = build_sales_csv([
        {"date": "2026-02-20", "sku_id": "SkU_CaSe_1", "units_sold": 7}
    ])

    sku_resp = client.post("/upload_csv", files={"file": ("sku_mixed.csv", sku_payload, "text/csv")})
    sales_resp = client.post("/upload_csv", files={"file": ("sales_mixed.csv", sales_payload, "text/csv")})

    assert sku_resp.status_code == 200
    assert sales_resp.status_code == 200
    assert db_session.scalar(select(SKU).where(SKU.sku_id == "SKU_CASE_1")) is not None
    assert db_session.scalar(select(Sales).where(Sales.sku_id == "SKU_CASE_1")) is not None


def test_negative_inventory_row_is_dropped(client, db_session):
    sku_payload = build_sku_csv([
        {
            "sku_id": "SKU_NEG",
            "product_name": "Inventory Drift",
            "category": "Ops",
            "mrp": 10,
            "cost": 5,
            "current_inventory": -4,
        },
        {
            "sku_id": "SKU_OK",
            "product_name": "Inventory Fine",
            "category": "Ops",
            "mrp": 10,
            "cost": 5,
            "current_inventory": 4,
        },
    ])

    response = client.post("/upload_csv", files={"file": ("sku_negative.csv", sku_payload, "text/csv")})

    assert response.status_code == 200
    assert response.json()["records_inserted"] == 1
    assert db_session.scalar(select(SKU).where(SKU.sku_id == "SKU_NEG")) is None
    assert db_session.scalar(select(SKU).where(SKU.sku_id == "SKU_OK")) is not None


def test_large_sku_csv_5000_rows_ingests_successfully(client, db_session):
    rows = [
        {
            "sku_id": f"SKU_{index}",
            "product_name": f"Product {index}",
            "category": "Bulk",
            "mrp": 100 + index,
            "cost": 60 + index,
            "current_inventory": index,
        }
        for index in range(5000)
    ]
    payload = build_sku_csv(rows)

    response = client.post("/upload_csv", files={"file": ("sku_5000.csv", payload, "text/csv")})

    assert response.status_code == 200
    assert response.json()["records_inserted"] == 5000
    count = db_session.scalar(select(func.count()).select_from(SKU))
    assert count == 5000


def test_future_dated_sales_records_are_ingested(client, db_session):
    sku_payload = build_sku_csv([
        {
            "sku_id": "SKU_FUT",
            "product_name": "Future Item",
            "category": "General",
            "mrp": 100,
            "cost": 60,
            "current_inventory": 10,
        }
    ])
    future_date = date(2035, 1, 1).isoformat()
    sales_payload = build_sales_csv([
        {"date": future_date, "sku_id": "SKU_FUT", "units_sold": 1}
    ])

    client.post("/upload_csv", files={"file": ("sku_future.csv", sku_payload, "text/csv")})
    response = client.post("/upload_csv", files={"file": ("sales_future.csv", sales_payload, "text/csv")})

    assert response.status_code == 200
    row = db_session.scalar(select(Sales).where(Sales.sku_id == "SKU_FUT"))
    assert row is not None
    assert row.date == date(2035, 1, 1)


def test_corrupted_binary_csv_returns_validation_error(client):
    response = client.post(
        "/upload_csv",
        files={"file": ("corrupted.csv", b"\x00\xff\x81\xaa\xbb", "text/csv")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["message"] == "Validation failed"


def test_duplicate_upload_keeps_row_count_constant(client, db_session, csv_bytes):
    payload = csv_bytes("sku_valid.csv")

    first = client.post("/upload_csv", files={"file": ("sku_valid.csv", payload, "text/csv")})
    before = db_session.scalar(select(func.count()).select_from(SKU))
    second = client.post("/upload_csv", files={"file": ("sku_valid.csv", payload, "text/csv")})
    after = db_session.scalar(select(func.count()).select_from(SKU))

    assert first.status_code == 200
    assert second.status_code == 200
    assert before == 1
    assert after == 1


def test_partial_row_failures_insert_only_valid_rows(client, db_session):
    payload = (
        "sku_id,product_name,category,mrp,cost,current_inventory\n"
        "SKU_OK,Valid Item,Grocery,100,70,40\n"
        "SKU_BAD,Bad Item,Grocery,not-a-number,50,20\n"
    ).encode("utf-8")

    response = client.post("/upload_csv", files={"file": ("sku_partial.csv", payload, "text/csv")})

    assert response.status_code == 200
    assert response.json()["records_inserted"] == 1
    assert db_session.scalar(select(SKU).where(SKU.sku_id == "SKU_OK")) is not None
    assert db_session.scalar(select(SKU).where(SKU.sku_id == "SKU_BAD")) is None


def test_logical_duplicate_sales_case_insensitive_keeps_latest(client, db_session):
    sku_payload = build_sku_csv([
        {
            "sku_id": "SKU_DUP",
            "product_name": "Dupe Item",
            "category": "General",
            "mrp": 50,
            "cost": 20,
            "current_inventory": 10,
        }
    ])
    sales_payload = (
        "date,sku_id,units_sold\n"
        "2026-01-01,sku_dup,4\n"
        "2026-01-01,SKU_DUP,9\n"
    ).encode("utf-8")

    client.post("/upload_csv", files={"file": ("sku_dup.csv", sku_payload, "text/csv")})
    response = client.post("/upload_csv", files={"file": ("sales_dup.csv", sales_payload, "text/csv")})

    assert response.status_code == 200
    rows = db_session.scalars(select(Sales).where(Sales.sku_id == "SKU_DUP")).all()
    assert len(rows) == 1
    assert rows[0].units_sold == 9
