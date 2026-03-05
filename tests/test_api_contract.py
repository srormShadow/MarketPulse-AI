"""API contract tests for stable response shape and status codes."""

import pandas as pd

from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU


def test_health_endpoint_contract(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["timestamp"], str)


def test_upload_success_response_contract(client, csv_bytes):
    response = client.post(
        "/upload_csv",
        files={"file": ("sku_valid.csv", csv_bytes("sku_valid.csv"), "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"status", "records_inserted", "file_type"}
    assert payload["status"] == "success"


def test_upload_error_response_contract(client, csv_bytes):
    response = client.post(
        "/upload_csv",
        files={"file": ("sku_missing_column.csv", csv_bytes("sku_missing_column.csv"), "text/csv")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["message"] == "Validation failed"
    assert isinstance(payload["errors"], list)
    assert payload["errors"]


def test_discount_simulation_response_contract(client, db_session):
    db_session.add(
        SKU(
            sku_id="SNK_CONTRACT_1",
            product_name="Contract Snack",
            category="Snacks",
            mrp=100.0,
            cost=60.0,
            current_inventory=220,
        )
    )
    dates = pd.date_range("2025-01-01", periods=50, freq="D")
    for idx, dt in enumerate(dates):
        db_session.add(Sales(date=dt.date(), sku_id="SNK_CONTRACT_1", units_sold=28 + (idx % 6)))
    db_session.commit()

    response = client.post(
        "/simulate/discount/Snacks",
        json={
            "n_days": 30,
            "current_inventory": 240,
            "lead_time_days": 7,
            "supplier_pack_size": 1,
            "discount_percent": 15,
            "elasticity_mode": "balanced",
            "include_explanation": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "category",
        "inputs",
        "baseline",
        "simulated",
        "delta",
        "supply_stability_index",
        "explanation",
        "warnings",
    }
