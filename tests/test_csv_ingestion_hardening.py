"""Tests for hardened ingestion validation and observability behaviors."""

import logging

from sqlalchemy import select

from marketpulse.models.sales import Sales


def test_negative_units_sold_rows_are_dropped(client, db_session):
    sku_payload = (
        "sku_id,product_name,category,mrp,cost,current_inventory\n"
        "SKU_NEG_SALES,Sales Item,Grocery,100,60,10\n"
    ).encode("utf-8")
    sales_payload = (
        "date,sku_id,units_sold\n"
        "2026-03-01,SKU_NEG_SALES,-2\n"
        "2026-03-02,SKU_NEG_SALES,5\n"
    ).encode("utf-8")

    client.post("/upload_csv", files={"file": ("sku.csv", sku_payload, "text/csv")})
    response = client.post("/upload_csv", files={"file": ("sales.csv", sales_payload, "text/csv")})

    assert response.status_code == 200
    assert response.json()["records_inserted"] == 1

    rows = db_session.scalars(select(Sales).where(Sales.sku_id == "SKU_NEG_SALES")).all()
    assert len(rows) == 1
    assert rows[0].units_sold == 5


def test_sales_outlier_is_logged_but_retained(client, db_session, caplog):
    sku_payload = (
        "sku_id,product_name,category,mrp,cost,current_inventory\n"
        "SKU_OUT,Outlier Item,Grocery,100,60,10\n"
    ).encode("utf-8")
    sales_payload = (
        "date,sku_id,units_sold\n"
        "2026-03-01,SKU_OUT,8\n"
        "2026-03-02,SKU_OUT,9\n"
        "2026-03-03,SKU_OUT,10\n"
        "2026-03-04,SKU_OUT,11\n"
        "2026-03-05,SKU_OUT,400\n"
    ).encode("utf-8")

    client.post("/upload_csv", files={"file": ("sku.csv", sku_payload, "text/csv")})

    caplog.set_level(logging.WARNING)
    response = client.post("/upload_csv", files={"file": ("sales.csv", sales_payload, "text/csv")})

    assert response.status_code == 200
    rows = db_session.scalars(select(Sales).where(Sales.sku_id == "SKU_OUT")).all()
    assert len(rows) == 5
    assert "Sales outliers detected via IQR" in caplog.text


def test_invalid_schema_version_is_rejected(client):
    sku_payload = (
        "sku_id,product_name,category,mrp,cost,current_inventory,schema_version\n"
        "SKU_VER,Versioned,Grocery,100,60,10,2.0\n"
    ).encode("utf-8")

    response = client.post("/upload_csv", files={"file": ("sku.csv", sku_payload, "text/csv")})

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["message"] == "Validation failed"
    assert payload["errors"][0]["field"] == "schema_version"


def test_valid_schema_version_is_accepted(client, db_session):
    sku_payload = (
        "sku_id,product_name,category,mrp,cost,current_inventory,schema_version\n"
        "SKU_VER_OK,Versioned,Grocery,100,60,10,1.0\n"
    ).encode("utf-8")

    response = client.post("/upload_csv", files={"file": ("sku.csv", sku_payload, "text/csv")})

    assert response.status_code == 200
    assert response.json()["records_inserted"] == 1
