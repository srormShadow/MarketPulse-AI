"""Tests for SQLite repository cache/log parity behavior."""

from __future__ import annotations

from datetime import datetime, timezone

from marketpulse.db.repository import SQLiteRepository


def test_sqlite_recommendation_log_roundtrip(db_session):
    repo = SQLiteRepository(db_session)
    generated_at = datetime.now(timezone.utc)
    repo.log_recommendation(
        category="Snacks",
        risk_score=0.421,
        insight="Test insight",
        generated_at=generated_at,
    )

    cached = repo.get_cached_recommendation("Snacks", risk_score=0.421, max_age_seconds=3600)
    assert cached is not None
    assert cached["insight"] == "Test insight"
    assert cached["category"] == "Snacks"

    recent = repo.list_recent_recommendations(limit=5)
    assert recent
    assert recent[0]["category"] == "Snacks"


def test_sqlite_forecast_cache_roundtrip_with_pack_size(db_session):
    repo = SQLiteRepository(db_session)
    generated_at = datetime.now(timezone.utc)
    payload = {
        "category": "Snacks",
        "forecast": [{"date": "2026-03-10", "predicted_mean": 100, "lower_95": 80, "upper_95": 120}],
        "decision": {
            "recommended_action": "ORDER",
            "order_quantity": 40,
            "reorder_point": 160.0,
            "safety_stock": 20.0,
            "risk_score": 0.3,
            "festival_buffer_applied": False,
            "data_stale_warning": False,
            "pack_size_applied": False,
        },
        "n_days": 1,
        "current_inventory": 50,
        "lead_time_days": 5,
        "supplier_pack_size": 4,
        "warnings": [],
    }
    repo.save_forecast_cache("Snacks", payload, generated_at=generated_at)

    cached = repo.get_cached_forecast(
        category="Snacks",
        n_days=1,
        current_inventory=50,
        lead_time_days=5,
        supplier_pack_size=4,
        max_age_seconds=3600,
    )
    assert cached is not None
    assert cached["category"] == "Snacks"
    assert cached["decision"]["order_quantity"] == 40

