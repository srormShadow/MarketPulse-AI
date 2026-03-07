"""Regression coverage for insights endpoints request parsing and behavior."""

from __future__ import annotations

from marketpulse.routes import insights as insights_routes


def test_insight_endpoint_accepts_empty_body(client, monkeypatch):
    captured: dict = {}

    def _fake_generate(category, forecast_data, decision_data, festival_context):
        captured["category"] = category
        captured["forecast_data"] = forecast_data
        captured["decision_data"] = decision_data
        captured["festival_context"] = festival_context
        return "Generated insight"

    monkeypatch.setattr(insights_routes, "generate_category_insight", _fake_generate)

    response = client.post("/insights/Snacks", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "Snacks"
    assert payload["insight"] == "Generated insight"
    assert captured["forecast_data"] == []
    assert captured["decision_data"] == {}


def test_insight_endpoint_accepts_missing_body(client, monkeypatch):
    monkeypatch.setattr(insights_routes, "generate_category_insight", lambda *args, **kwargs: "OK")

    response = client.post("/insights/Snacks")
    assert response.status_code == 200
    assert response.json()["insight"] == "OK"


def test_batch_insights_accepts_missing_body_and_defaults_to_empty(client):
    response = client.post("/insights/batch")
    assert response.status_code == 200
    payload = response.json()
    assert payload["insights"] == []
    assert "generated_at" in payload


def test_batch_insights_generates_for_items(client, monkeypatch):
    monkeypatch.setattr(insights_routes, "generate_category_insight", lambda *args, **kwargs: "Batch OK")

    response = client.post(
        "/insights/batch",
        json={
            "items": [
                {
                    "category": "Snacks",
                    "forecast_data": [{"date": "2026-03-04", "predicted_units": 10}],
                    "decision_data": {"risk_score": 0.5},
                }
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["insights"]) == 1
    assert payload["insights"][0]["category"] == "Snacks"
    assert payload["insights"][0]["insight"] == "Batch OK"

