"""Tests for inventory decision engine."""

import numpy as np
import pandas as pd
import pytest

from marketpulse.services.decision_engine import (
    assess_risk_score,
    calculate_order_quantity,
    calculate_reorder_point,
    calculate_safety_stock,
    determine_action,
    generate_inventory_decision_summary,
)


@pytest.fixture
def sample_forecast_df() -> pd.DataFrame:
    """Create sample forecast DataFrame."""
    return pd.DataFrame(
        {
            "date": pd.date_range(start="2024-01-01", periods=30, freq="D"),
            "predicted_mean": np.full(30, 50.0),
            "lower_95": np.full(30, 40.0),
            "upper_95": np.full(30, 60.0),
        }
    )


def test_calculate_safety_stock(sample_forecast_df: pd.DataFrame):
    """Test safety stock calculation."""
    safety_stock = calculate_safety_stock(sample_forecast_df, service_level=0.95)

    assert safety_stock >= 0
    assert isinstance(safety_stock, float)


def test_calculate_safety_stock_empty_df():
    """Test safety stock with empty DataFrame."""
    empty_df = pd.DataFrame(columns=["predicted_mean", "lower_95", "upper_95"])
    safety_stock = calculate_safety_stock(empty_df)

    assert safety_stock == 0.0


def test_calculate_reorder_point(sample_forecast_df: pd.DataFrame):
    """Test reorder point calculation."""
    safety_stock = 20.0
    lead_time_days = 7

    reorder_point = calculate_reorder_point(sample_forecast_df, lead_time_days, safety_stock)

    assert reorder_point >= safety_stock
    assert isinstance(reorder_point, float)


def test_calculate_reorder_point_zero_lead_time(sample_forecast_df: pd.DataFrame):
    """Test reorder point with zero lead time."""
    safety_stock = 20.0
    reorder_point = calculate_reorder_point(sample_forecast_df, 0, safety_stock)

    assert reorder_point == safety_stock


def test_calculate_order_quantity_below_reorder(sample_forecast_df: pd.DataFrame):
    """Test order quantity when inventory is below reorder point."""
    current_inventory = 50
    reorder_point = 200.0

    order_qty = calculate_order_quantity(current_inventory, reorder_point, sample_forecast_df)

    assert order_qty > 0
    assert isinstance(order_qty, int)


def test_calculate_order_quantity_above_reorder(sample_forecast_df: pd.DataFrame):
    """Test order quantity when inventory is above reorder point."""
    current_inventory = 500
    reorder_point = 200.0

    order_qty = calculate_order_quantity(current_inventory, reorder_point, sample_forecast_df)

    assert order_qty == 0


def test_assess_risk_score(sample_forecast_df: pd.DataFrame):
    """Test risk score assessment."""
    current_inventory = 100
    reorder_point = 200.0

    risk_score = assess_risk_score(sample_forecast_df, current_inventory, reorder_point)

    assert 0.0 <= risk_score <= 1.0
    assert isinstance(risk_score, float)


def test_assess_risk_score_low_inventory(sample_forecast_df: pd.DataFrame):
    """Test risk score with low inventory."""
    current_inventory = 10
    reorder_point = 200.0

    risk_score = assess_risk_score(sample_forecast_df, current_inventory, reorder_point)

    assert risk_score > 0.5  # Should be high risk


def test_assess_risk_score_high_inventory(sample_forecast_df: pd.DataFrame):
    """Test risk score with high inventory."""
    current_inventory = 500
    reorder_point = 200.0

    risk_score = assess_risk_score(sample_forecast_df, current_inventory, reorder_point)

    assert risk_score < 0.5  # Should be low risk


def test_assess_risk_score_empty_df():
    """Test risk score with empty DataFrame."""
    empty_df = pd.DataFrame(columns=["predicted_mean", "lower_95", "upper_95"])
    risk_score = assess_risk_score(empty_df, 100, 200.0)

    assert risk_score == 0.0


def test_determine_action_urgent_order():
    """Test action determination for urgent order."""
    action = determine_action(order_quantity=100, risk_score=0.8)
    assert action == "URGENT_ORDER"


def test_determine_action_regular_order():
    """Test action determination for regular order."""
    action = determine_action(order_quantity=100, risk_score=0.4)
    assert action == "ORDER"


def test_determine_action_monitor():
    """Test action determination for monitor."""
    action = determine_action(order_quantity=0, risk_score=0.6)
    assert action == "MONITOR"


def test_determine_action_maintain():
    """Test action determination for maintain."""
    action = determine_action(order_quantity=0, risk_score=0.2)
    assert action == "MAINTAIN"


def test_generate_inventory_decision_summary(sample_forecast_df: pd.DataFrame):
    """Test complete decision summary generation."""
    decision = generate_inventory_decision_summary(
        forecast_df=sample_forecast_df,
        current_inventory=100,
        lead_time_days=7,
        service_level=0.95,
    )

    assert "recommended_action" in decision
    assert "order_quantity" in decision
    assert "reorder_point" in decision
    assert "safety_stock" in decision
    assert "risk_score" in decision

    assert isinstance(decision["order_quantity"], int)
    assert isinstance(decision["reorder_point"], float)
    assert isinstance(decision["safety_stock"], float)
    assert isinstance(decision["risk_score"], float)

    assert decision["order_quantity"] >= 0
    assert decision["reorder_point"] >= 0
    assert decision["safety_stock"] >= 0
    assert 0.0 <= decision["risk_score"] <= 1.0


def test_generate_inventory_decision_summary_empty_df():
    """Test decision summary with empty DataFrame."""
    empty_df = pd.DataFrame(columns=["date", "predicted_mean", "lower_95", "upper_95"])

    decision = generate_inventory_decision_summary(
        forecast_df=empty_df,
        current_inventory=100,
        lead_time_days=7,
    )

    assert decision["recommended_action"] == "INSUFFICIENT_DATA"
    assert decision["order_quantity"] == 0
    assert decision["reorder_point"] == 0.0
    assert decision["safety_stock"] == 0.0
    assert decision["risk_score"] == 0.0


def test_generate_inventory_decision_summary_high_uncertainty():
    """Test decision with high forecast uncertainty."""
    high_uncertainty_df = pd.DataFrame(
        {
            "date": pd.date_range(start="2024-01-01", periods=30, freq="D"),
            "predicted_mean": np.full(30, 50.0),
            "lower_95": np.full(30, 10.0),  # Wide confidence interval
            "upper_95": np.full(30, 90.0),
        }
    )

    decision = generate_inventory_decision_summary(
        forecast_df=high_uncertainty_df,
        current_inventory=100,
        lead_time_days=7,
    )

    # High uncertainty should result in higher safety stock
    assert decision["safety_stock"] > 0


def test_generate_inventory_decision_summary_varying_demand():
    """Test decision with varying demand pattern."""
    varying_demand_df = pd.DataFrame(
        {
            "date": pd.date_range(start="2024-01-01", periods=30, freq="D"),
            "predicted_mean": np.linspace(30, 70, 30),  # Increasing trend
            "lower_95": np.linspace(20, 60, 30),
            "upper_95": np.linspace(40, 80, 30),
        }
    )

    decision = generate_inventory_decision_summary(
        forecast_df=varying_demand_df,
        current_inventory=50,
        lead_time_days=7,
    )

    assert decision["order_quantity"] >= 0
    assert decision["recommended_action"] in [
        "ORDER",
        "URGENT_ORDER",
        "MONITOR",
        "MAINTAIN",
    ]


def test_safety_stock_increases_with_uncertainty():
    """Test that safety stock increases with forecast uncertainty."""
    low_uncertainty_df = pd.DataFrame(
        {
            "date": pd.date_range(start="2024-01-01", periods=30, freq="D"),
            "predicted_mean": np.full(30, 50.0),
            "lower_95": np.full(30, 45.0),
            "upper_95": np.full(30, 55.0),
        }
    )

    high_uncertainty_df = pd.DataFrame(
        {
            "date": pd.date_range(start="2024-01-01", periods=30, freq="D"),
            "predicted_mean": np.full(30, 50.0),
            "lower_95": np.full(30, 20.0),
            "upper_95": np.full(30, 80.0),
        }
    )

    low_safety = calculate_safety_stock(low_uncertainty_df)
    high_safety = calculate_safety_stock(high_uncertainty_df)

    assert high_safety > low_safety


def test_reorder_point_increases_with_lead_time(sample_forecast_df: pd.DataFrame):
    """Test that reorder point increases with lead time."""
    safety_stock = 20.0

    short_lead_time = calculate_reorder_point(sample_forecast_df, 3, safety_stock)
    long_lead_time = calculate_reorder_point(sample_forecast_df, 14, safety_stock)

    assert long_lead_time > short_lead_time
