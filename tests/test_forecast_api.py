"""Tests for forecast API endpoint."""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU
from marketpulse.services.feature_engineering import prepare_training_data
from marketpulse.services.forecasting import train_model
from marketpulse.db.repository import SQLiteRepository


def _build_model_json(repo, category: str) -> dict:
    """Train a model locally and return its JSON artifact (matching save_model format)."""
    X_train, y_train, _ = prepare_training_data(repo, category)
    model, scaler = train_model(X_train, y_train)
    return {
        "schema_version": "1.0",
        "trained_at": "20260315T000000Z",
        "feature_columns": list(X_train.columns),
        "model": {
            "coef_": model.coef_.tolist(),
            "intercept_": float(model.intercept_),
            "alpha_": float(model.alpha_),
            "lambda_": float(model.lambda_),
            "sigma_": model.sigma_.tolist(),
        },
        "scaler": {
            "scale_": scaler.scale_.tolist(),
            "mean_": scaler.mean_.tolist(),
            "var_": scaler.var_.tolist(),
            "n_samples_seen_": int(scaler.n_samples_seen_),
        },
    }


@pytest.fixture
def sample_category_data(db_session: Session, client: TestClient) -> str:
    """Create sample SKU and sales data for a category, train model with mocked S3."""
    category = "TestCategory"

    # Create SKU
    sku = SKU(
        sku_id="TEST001",
        product_name="Test Product",
        category=category,
        mrp=100.0,
        cost=50.0,
        current_inventory=100,
    )
    db_session.add(sku)
    db_session.flush()

    # Create sales history (30 days)
    dates = pd.date_range(end=pd.Timestamp.now().normalize(), periods=30, freq="D")
    for date in dates:
        sale = Sales(
            sku_id="TEST001",
            date=date.date(),
            units_sold=50 + (date.dayofweek * 5),  # Varying demand
        )
        db_session.add(sale)

    db_session.commit()

    # Train model locally (mock S3 save) and capture the artifact
    repo = SQLiteRepository(db_session)
    model_json = _build_model_json(repo, category)

    # Patch load_model globally so forecast_next_n_days can find the trained model
    patcher = patch("marketpulse.services.forecasting.load_model", return_value=model_json)
    patcher.start()

    yield category

    patcher.stop()


def test_forecast_endpoint_success(client: TestClient, sample_category_data: str):
    """Test successful forecast generation."""

    response = client.post(
        f"/forecast/{sample_category_data}",
        json={
            "n_days": 7,
            "current_inventory": 200,
            "lead_time_days": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Validate response structure
    assert "category" in data
    assert "forecast" in data
    assert "decision" in data

    assert data["category"] == sample_category_data
    assert len(data["forecast"]) == 7

    # Validate forecast data points
    for point in data["forecast"]:
        assert "date" in point
        assert "predicted_mean" in point
        assert "lower_95" in point
        assert "upper_95" in point
        assert point["predicted_mean"] >= 0
        assert point["lower_95"] >= 0
        assert point["upper_95"] >= point["predicted_mean"]

    # Validate decision structure
    decision = data["decision"]
    assert "recommended_action" in decision
    assert "order_quantity" in decision
    assert "reorder_point" in decision
    assert "safety_stock" in decision
    assert "risk_score" in decision

    assert decision["recommended_action"] in [
        "ORDER",
        "URGENT_ORDER",
        "MONITOR",
        "MAINTAIN",
        "INSUFFICIENT_DATA",
    ]
    assert decision["order_quantity"] >= 0
    assert decision["reorder_point"] >= 0
    assert decision["safety_stock"] >= 0
    assert 0 <= decision["risk_score"] <= 1


def test_forecast_category_not_found(client: TestClient):
    """Test forecast for non-existent category returns 404."""

    response = client.post(
        "/forecast/NonExistentCategory",
        json={
            "n_days": 7,
            "current_inventory": 100,
            "lead_time_days": 5,
        },
    )

    assert response.status_code == 404
    data = response.json()
    assert data["status"] == "error"
    assert "not found" in data["message"].lower()


def test_forecast_invalid_n_days(client: TestClient, sample_category_data: str):
    """Test forecast with invalid n_days parameter."""

    # Test n_days = 0
    response = client.post(
        f"/forecast/{sample_category_data}",
        json={
            "n_days": 0,
            "current_inventory": 100,
            "lead_time_days": 5,
        },
    )
    assert response.status_code == 422  # Validation error

    # Test n_days > 365
    response = client.post(
        f"/forecast/{sample_category_data}",
        json={
            "n_days": 400,
            "current_inventory": 100,
            "lead_time_days": 5,
        },
    )
    assert response.status_code == 422


def test_forecast_invalid_inventory(client: TestClient, sample_category_data: str):
    """Test forecast with invalid inventory parameter."""

    response = client.post(
        f"/forecast/{sample_category_data}",
        json={
            "n_days": 7,
            "current_inventory": -10,
            "lead_time_days": 5,
        },
    )
    assert response.status_code == 422


def test_forecast_invalid_lead_time(client: TestClient, sample_category_data: str):
    """Test forecast with invalid lead_time parameter."""

    # Test lead_time = 0
    response = client.post(
        f"/forecast/{sample_category_data}",
        json={
            "n_days": 7,
            "current_inventory": 100,
            "lead_time_days": 0,
        },
    )
    assert response.status_code == 422

    # Test lead_time > 90
    response = client.post(
        f"/forecast/{sample_category_data}",
        json={
            "n_days": 7,
            "current_inventory": 100,
            "lead_time_days": 100,
        },
    )
    assert response.status_code == 422


def test_forecast_different_horizons(client: TestClient, sample_category_data: str):
    """Test forecast with different time horizons."""

    for n_days in [1, 7, 30, 90]:
        response = client.post(
            f"/forecast/{sample_category_data}",
            json={
                "n_days": n_days,
                "current_inventory": 100,
                "lead_time_days": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["forecast"]) == n_days


def test_forecast_low_inventory_triggers_order(client: TestClient, sample_category_data: str):
    """Test that low inventory triggers order recommendation."""

    response = client.post(
        f"/forecast/{sample_category_data}",
        json={
            "n_days": 30,
            "current_inventory": 10,  # Very low inventory
            "lead_time_days": 7,
        },
    )

    assert response.status_code == 200
    data = response.json()

    decision = data["decision"]
    # With low inventory, should recommend ordering
    assert decision["recommended_action"] in ["ORDER", "URGENT_ORDER"]
    assert decision["order_quantity"] > 0


def test_forecast_high_inventory_no_order(client: TestClient, sample_category_data: str):
    """Test that high inventory doesn't trigger order."""

    response = client.post(
        f"/forecast/{sample_category_data}",
        json={
            "n_days": 7,
            "current_inventory": 10000,  # Very high inventory
            "lead_time_days": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()

    decision = data["decision"]
    # With high inventory, should not order
    assert decision["order_quantity"] == 0
    assert decision["recommended_action"] in ["MAINTAIN", "MONITOR"]


def test_forecast_date_format(client: TestClient, sample_category_data: str):
    """Test that forecast dates are in correct format."""

    response = client.post(
        f"/forecast/{sample_category_data}",
        json={
            "n_days": 7,
            "current_inventory": 100,
            "lead_time_days": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()

    import re

    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    for point in data["forecast"]:
        assert date_pattern.match(point["date"]), f"Invalid date format: {point['date']}"


def test_forecast_dates_are_sequential(client: TestClient, sample_category_data: str):
    """Test that forecast dates are sequential and in the future."""

    response = client.post(
        f"/forecast/{sample_category_data}",
        json={
            "n_days": 7,
            "current_inventory": 100,
            "lead_time_days": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()

    from datetime import datetime, timedelta

    dates = [datetime.strptime(point["date"], "%Y-%m-%d") for point in data["forecast"]]

    # Check dates are sequential
    for i in range(len(dates) - 1):
        assert dates[i + 1] - dates[i] == timedelta(days=1)
