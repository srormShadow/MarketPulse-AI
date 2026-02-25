"""CSV ingestion endpoint tests for SKU and Sales files."""

from sqlalchemy import select

from app.models.sales import Sales
from app.models.sku import SKU


def test_upload_valid_sku_csv(client, db_session, csv_bytes):
    response = client.post(
        "/upload_csv",
        files={"file": ("sku_valid.csv", csv_bytes("sku_valid.csv"), "text/csv")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "records_inserted": 1,
        "file_type": "sku",
    }

    row = db_session.scalar(select(SKU).where(SKU.sku_id == "SKU100"))
    assert row is not None


def test_upload_sku_missing_required_column_returns_400(client, csv_bytes):
    response = client.post(
        "/upload_csv",
        files={"file": ("sku_missing_column.csv", csv_bytes("sku_missing_column.csv"), "text/csv")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["message"] == "Validation failed"


def test_upload_sku_wrong_datatype_returns_400(client, csv_bytes):
    response = client.post(
        "/upload_csv",
        files={"file": ("sku_wrong_datatype.csv", csv_bytes("sku_wrong_datatype.csv"), "text/csv")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["message"] == "Validation failed"


def test_upload_empty_file_returns_clean_error(client, csv_bytes):
    response = client.post(
        "/upload_csv",
        files={"file": ("empty.csv", csv_bytes("empty.csv"), "text/csv")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["errors"][0]["issue"] == "Uploaded file is empty"


def test_upload_valid_sales_csv(client, db_session, csv_bytes):
    client.post(
        "/upload_csv",
        files={"file": ("sku_valid.csv", csv_bytes("sku_valid.csv"), "text/csv")},
    )

    response = client.post(
        "/upload_csv",
        files={"file": ("sales_valid.csv", csv_bytes("sales_valid.csv"), "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["file_type"] == "sales"

    rows = db_session.scalars(select(Sales).where(Sales.sku_id == "SKU100")).all()
    assert len(rows) == 1


def test_upload_sales_missing_sku_id_returns_400(client, csv_bytes):
    response = client.post(
        "/upload_csv",
        files={"file": ("sales_missing_sku_id.csv", csv_bytes("sales_missing_sku_id.csv"), "text/csv")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"


def test_upload_sales_invalid_date_returns_400(client, csv_bytes):
    client.post(
        "/upload_csv",
        files={"file": ("sku_valid.csv", csv_bytes("sku_valid.csv"), "text/csv")},
    )

    response = client.post(
        "/upload_csv",
        files={"file": ("sales_invalid_date.csv", csv_bytes("sales_invalid_date.csv"), "text/csv")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"


def test_upload_sales_duplicate_date_entries_are_upserted(client, db_session, csv_bytes):
    client.post(
        "/upload_csv",
        files={"file": ("sku_valid.csv", csv_bytes("sku_valid.csv"), "text/csv")},
    )

    response = client.post(
        "/upload_csv",
        files={"file": ("sales_duplicate_dates.csv", csv_bytes("sales_duplicate_dates.csv"), "text/csv")},
    )

    assert response.status_code == 200

    rows = db_session.scalars(select(Sales).where(Sales.sku_id == "SKU100")).all()
    assert len(rows) == 1
    assert rows[0].units_sold == 12
