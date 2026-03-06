"""Regression tests for simulation baseline cache path."""

from __future__ import annotations

from datetime import datetime, timezone

from marketpulse.db.repository import SQLiteRepository
from marketpulse.models.sku import SKU
from marketpulse.routes import simulation as simulation_routes


def test_simulation_uses_cached_baseline_forecast(client, db_session, monkeypatch):
    db_session.add(
        SKU(
            sku_id="SNK_CACHE_1",
            product_name="Snack Cache",
            category="Snacks",
            mrp=100.0,
            cost=60.0,
            current_inventory=250,
        )
    )
    db_session.commit()

    repo = SQLiteRepository(db_session)
    payload = {
        "category": "Snacks",
        "forecast": [
            {
                "date": "2026-03-10",
                "predicted_mean": 120.0,
                "lower_95": 100.0,
                "upper_95": 140.0,
                "festival_score": 0.1,
                "confidence_level": "high",
            },
            {
                "date": "2026-03-11",
                "predicted_mean": 125.0,
                "lower_95": 104.0,
                "upper_95": 146.0,
                "festival_score": 0.1,
                "confidence_level": "high",
            },
        ],
        "decision": {
            "recommended_action": "ORDER",
            "order_quantity": 80,
            "reorder_point": 220.0,
            "safety_stock": 30.0,
            "risk_score": 0.34,
            "festival_buffer_applied": False,
            "data_stale_warning": False,
            "pack_size_applied": False,
        },
        "warnings": [],
        "n_days": 2,
        "current_inventory": 300,
        "lead_time_days": 7,
        "supplier_pack_size": 1,
    }
    repo.save_forecast_cache(
        category="Snacks",
        payload=payload,
        generated_at=datetime.now(timezone.utc),
    )

    def _should_not_recompute(*args, **kwargs):
        raise AssertionError("forecast_next_n_days should not run when fresh cache exists")

    monkeypatch.setattr(simulation_routes, "forecast_next_n_days", _should_not_recompute)

    response = client.post(
        "/simulate/discount/Snacks",
        json={
            "n_days": 2,
            "current_inventory": 300,
            "lead_time_days": 7,
            "supplier_pack_size": 1,
            "discount_percent": 10,
            "elasticity_mode": "balanced",
            "include_explanation": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["baseline"]["forecast"][0]["predicted_mean"] == 120.0

