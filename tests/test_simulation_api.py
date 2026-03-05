"""API tests for discount simulation route."""

from __future__ import annotations

import pandas as pd

from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU
from marketpulse.routes import simulation as simulation_routes


def _seed_category_data(db_session) -> None:
    db_session.add(
        SKU(
            sku_id="SNK_SIM_1",
            product_name="Snack Sim",
            category="Snacks",
            mrp=100.0,
            cost=60.0,
            current_inventory=250,
        )
    )
    dates = pd.date_range("2025-01-01", periods=60, freq="D")
    for idx, dt in enumerate(dates):
        db_session.add(Sales(date=dt.date(), sku_id="SNK_SIM_1", units_sold=35 + (idx % 9)))
    db_session.commit()


def test_simulation_endpoint_returns_expected_shape(client, db_session):
    _seed_category_data(db_session)
    response = client.post(
        "/simulate/discount/Snacks",
        json={
            "n_days": 30,
            "current_inventory": 300,
            "lead_time_days": 7,
            "supplier_pack_size": 1,
            "discount_percent": 20,
            "elasticity_mode": "balanced",
            "include_explanation": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "Snacks"
    assert "baseline" in payload and "simulated" in payload
    assert "delta" in payload and "supply_stability_index" in payload
    assert payload["explanation"] is None


def test_simulation_endpoint_404_for_unknown_category(client):
    response = client.post(
        "/simulate/discount/UnknownCategory",
        json={
            "n_days": 30,
            "current_inventory": 100,
            "lead_time_days": 7,
            "supplier_pack_size": 1,
            "discount_percent": 10,
            "elasticity_mode": "balanced",
            "include_explanation": False,
        },
    )
    assert response.status_code == 404


def test_simulation_endpoint_rejects_invalid_discount(client, db_session):
    _seed_category_data(db_session)
    response = client.post(
        "/simulate/discount/Snacks",
        json={
            "n_days": 30,
            "current_inventory": 300,
            "lead_time_days": 7,
            "supplier_pack_size": 1,
            "discount_percent": 90,
            "elasticity_mode": "balanced",
            "include_explanation": False,
        },
    )
    assert response.status_code == 422


def test_simulation_endpoint_skips_bedrock_when_explanation_disabled(client, db_session, monkeypatch):
    _seed_category_data(db_session)

    def _should_not_call(*args, **kwargs):
        raise AssertionError("Bedrock explanation helper should not be called")

    monkeypatch.setattr(simulation_routes, "generate_discount_simulation_explanation", _should_not_call)

    response = client.post(
        "/simulate/discount/Snacks",
        json={
            "n_days": 30,
            "current_inventory": 300,
            "lead_time_days": 7,
            "supplier_pack_size": 1,
            "discount_percent": 12,
            "elasticity_mode": "balanced",
            "include_explanation": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["explanation"] is None


def test_simulation_endpoint_returns_explanation_when_enabled(client, db_session, monkeypatch):
    _seed_category_data(db_session)
    monkeypatch.setattr(
        simulation_routes,
        "generate_discount_simulation_explanation",
        lambda *args, **kwargs: "Simulation explanation text",
    )

    response = client.post(
        "/simulate/discount/Snacks",
        json={
            "n_days": 30,
            "current_inventory": 300,
            "lead_time_days": 7,
            "supplier_pack_size": 1,
            "discount_percent": 18,
            "elasticity_mode": "conservative",
            "include_explanation": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["explanation"] == "Simulation explanation text"
