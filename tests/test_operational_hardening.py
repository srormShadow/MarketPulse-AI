from __future__ import annotations

import pandas as pd
from sqlalchemy import select

from marketpulse.core.config import get_settings
from marketpulse.models.festival import Festival
from marketpulse.models.recommendation_log import RecommendationLog
from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU


def test_settings_cache_isolation():
    get_settings.cache_clear()


def test_cached_forecast_does_not_duplicate_recommendation_logs(client, db_session):
    db_session.add(
        SKU(
            sku_id="SNK_LOG_1",
            product_name="Snack Log Test",
            category="Snacks",
            mrp=100.0,
            cost=60.0,
            current_inventory=250,
        )
    )
    for idx, dt in enumerate(pd.date_range("2025-01-01", periods=45, freq="D")):
        db_session.add(Sales(date=dt.date(), sku_id="SNK_LOG_1", units_sold=20 + (idx % 5)))
    db_session.commit()

    payload = {
        "n_days": 14,
        "current_inventory": 220,
        "lead_time_days": 7,
        "supplier_pack_size": 1,
    }

    first = client.post("/forecast/Snacks", json=payload)
    second = client.post("/forecast/Snacks", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["cache_hit"] is True

    logs = db_session.scalars(
        select(RecommendationLog).where(RecommendationLog.category == "Snacks")
    ).all()
    assert len(logs) == 1


def test_metrics_requires_api_key_when_configured(anonymous_client, monkeypatch):
    monkeypatch.setenv("API_KEY", "metrics-secret")
    get_settings.cache_clear()

    unauthorized = anonymous_client.get("/metrics")
    assert unauthorized.status_code == 401

    authorized = anonymous_client.get("/metrics", headers={"X-API-Key": "metrics-secret"})
    assert authorized.status_code == 200
    assert "http_request_duration_seconds" in authorized.text or "marketpulse" in authorized.text.lower()
    get_settings.cache_clear()


def test_logout_requires_csrf(client):
    client.headers.pop("X-CSRF-Token", None)

    response = client.post("/auth/logout")

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token missing."


def test_reseed_festivals_requires_admin(anonymous_client):
    response = anonymous_client.post("/reseed_festivals")
    assert response.status_code == 401


def test_reseed_festivals_disabled_in_production(admin_client, monkeypatch, db_session):
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    db_session.query(Festival).delete()
    db_session.commit()

    response = admin_client.post("/reseed_festivals")

    assert response.status_code == 403
    assert response.json()["message"] == "Festival reseeding is disabled in production."
