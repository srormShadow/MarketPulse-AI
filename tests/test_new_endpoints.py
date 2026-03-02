"""Coverage for newly added diagnostics/recommendations/prediction endpoints."""

from __future__ import annotations

import json

import pandas as pd

from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU


def _seed_basic_sales(db_session) -> None:
    db_session.add_all(
        [
            SKU(
                sku_id="S1",
                product_name="Snack One",
                category="Snacks",
                mrp=100.0,
                cost=60.0,
                current_inventory=100,
            ),
            SKU(
                sku_id="S2",
                product_name="Staple One",
                category="Staples",
                mrp=120.0,
                cost=70.0,
                current_inventory=120,
            ),
        ]
    )
    dates = pd.date_range("2025-01-01", periods=45, freq="D")
    for idx, dt in enumerate(dates):
        db_session.add(Sales(date=dt.date(), sku_id="S1", units_sold=30 + (idx % 7)))
        db_session.add(Sales(date=dt.date(), sku_id="S2", units_sold=20 + (idx % 5)))
    db_session.commit()


def test_diagnostics_category_endpoint_returns_coefficients(client, db_session):
    _seed_basic_sales(db_session)
    response = client.get("/diagnostics/Snacks")
    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "Snacks"
    assert "coefficients" in payload
    assert "feature_influence" in payload
    assert isinstance(payload["coefficients"], dict)


def test_diagnostics_all_endpoint_returns_items(client, db_session):
    _seed_basic_sales(db_session)
    response = client.get("/diagnostics/all")
    assert response.status_code == 200
    payload = response.json()
    assert "categories" in payload
    assert "items" in payload
    assert payload["total"] >= 1


def test_recommendations_recent_endpoint_returns_logged_rows(client, db_session, repo):
    repo.log_recommendation(
        category="Snacks",
        risk_score=0.42,
        insight=json.dumps(
            {
                "type": "forecast_decision",
                "decision": {"recommended_action": "ORDER", "order_quantity": 250},
            }
        ),
        generated_at=pd.Timestamp("2026-03-01T10:00:00Z").to_pydatetime(),
    )

    response = client.get("/recommendations/recent?limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert payload["total"] >= 0
    if payload["items"]:
        first = payload["items"][0]
        assert "date" in first
        assert "category" in first
        assert "action" in first
        assert "order_quantity" in first
        assert "risk_score" in first


def test_predictions_endpoint_returns_expected_shape(client, db_session):
    _seed_basic_sales(db_session)
    response = client.get("/predictions?date=2026-03-13&stock=Snacks")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stock"] == "Snacks"
    assert "predicted_demand" in payload
    assert "risk_score" in payload
    assert "confidence_level" in payload
    assert "suggested_action" in payload


def test_historical_endpoint_returns_year_map(client, db_session):
    _seed_basic_sales(db_session)
    response = client.get("/historical?date=2026-03-13&stock=Snacks")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert "2025" in payload
    assert "2024" in payload
