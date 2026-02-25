import io

from sqlalchemy import select

from app.models.sales import Sales
from app.models.sku import SKU


def _csv_bytes(content: str) -> bytes:
    return content.encode("utf-8")


def test_upload_sku_csv_success(client, db_session):
    sku_csv = _csv_bytes(
        "sku_id,product_name,category,mrp,cost,current_inventory\n"
        "SKU100,Face Wash,Personal Care,120.5,80.0,50\n"
    )

    response = client.post(
        "/upload_csv",
        files={"file": ("sku.csv", io.BytesIO(sku_csv), "text/csv")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "records_inserted": 1,
        "file_type": "sku",
    }

    stored = db_session.scalar(select(SKU).where(SKU.sku_id == "SKU100"))
    assert stored is not None
    assert stored.product_name == "Face Wash"


def test_upload_sales_csv_success(client, db_session):
    sku_csv = _csv_bytes(
        "sku_id,product_name,category,mrp,cost,current_inventory\n"
        "SKU200,Biscuit,Grocery,30,20,100\n"
    )
    sales_csv = _csv_bytes(
        "date,sku_id,units_sold\n"
        "2026-02-20,SKU200,25\n"
    )

    client.post(
        "/upload_csv",
        files={"file": ("sku.csv", io.BytesIO(sku_csv), "text/csv")},
    )
    response = client.post(
        "/upload_csv",
        files={"file": ("sales.csv", io.BytesIO(sales_csv), "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["file_type"] == "sales"
    assert response.json()["records_inserted"] == 1

    stored_sale = db_session.scalar(select(Sales).where(Sales.sku_id == "SKU200"))
    assert stored_sale is not None
    assert stored_sale.units_sold == 25


def test_upload_csv_missing_columns_returns_validation_error(client):
    bad_csv = _csv_bytes("sku_id,product_name\nSKU1,Soap\n")

    response = client.post(
        "/upload_csv",
        files={"file": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["message"] == "Validation failed"
    assert payload["errors"][0]["field"] == "columns"


def test_upload_csv_invalid_data_types_returns_validation_error(client):
    bad_sales_csv = _csv_bytes(
        "date,sku_id,units_sold\n"
        "not-a-date,SKU404,not-an-int\n"
    )

    response = client.post(
        "/upload_csv",
        files={"file": ("sales.csv", io.BytesIO(bad_sales_csv), "text/csv")},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["message"] == "Validation failed"


def test_upload_empty_file_returns_error(client):
    response = client.post(
        "/upload_csv",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Uploaded file is empty"


def test_upload_corrupted_csv_returns_error(client):
    response = client.post(
        "/upload_csv",
        files={"file": ("corrupted.csv", io.BytesIO(b"\xff\xfe\x00\x00\x81"), "text/csv")},
    )

    assert response.status_code == 400
    assert "corrupted" in response.json()["message"].lower()


def test_sku_duplicate_upsert_updates_existing_row(client, db_session):
    first_csv = _csv_bytes(
        "sku_id,product_name,category,mrp,cost,current_inventory\n"
        "SKU300,Shampoo,Personal Care,200,120,10\n"
    )
    second_csv = _csv_bytes(
        "sku_id,product_name,category,mrp,cost,current_inventory\n"
        "SKU300,Shampoo XL,Personal Care,250,150,15\n"
    )

    client.post(
        "/upload_csv",
        files={"file": ("sku.csv", io.BytesIO(first_csv), "text/csv")},
    )
    response = client.post(
        "/upload_csv",
        files={"file": ("sku.csv", io.BytesIO(second_csv), "text/csv")},
    )

    assert response.status_code == 200
    sku_rows = db_session.scalars(select(SKU).where(SKU.sku_id == "SKU300")).all()
    assert len(sku_rows) == 1
    assert sku_rows[0].product_name == "Shampoo XL"
    assert sku_rows[0].mrp == 250


def test_sales_duplicate_upsert_updates_units_sold(client, db_session):
    sku_csv = _csv_bytes(
        "sku_id,product_name,category,mrp,cost,current_inventory\n"
        "SKU400,Juice,Beverages,90,55,80\n"
    )
    first_sales = _csv_bytes("date,sku_id,units_sold\n2026-02-21,SKU400,12\n")
    second_sales = _csv_bytes("date,sku_id,units_sold\n2026-02-21,SKU400,30\n")

    client.post(
        "/upload_csv",
        files={"file": ("sku.csv", io.BytesIO(sku_csv), "text/csv")},
    )
    client.post(
        "/upload_csv",
        files={"file": ("sales.csv", io.BytesIO(first_sales), "text/csv")},
    )
    response = client.post(
        "/upload_csv",
        files={"file": ("sales.csv", io.BytesIO(second_sales), "text/csv")},
    )

    assert response.status_code == 200
    sales_rows = db_session.scalars(select(Sales).where(Sales.sku_id == "SKU400")).all()
    assert len(sales_rows) == 1
    assert sales_rows[0].units_sold == 30
