"""Tests for lag feature generation and recursive forecasting."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marketpulse.models.festival import Festival
from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU
from marketpulse.services.feature_engineering import add_lag_features, prepare_training_data
from marketpulse.services.forecasting import forecast_next_n_days


def _seed_lag_test_data(session) -> None:
    """Seed deterministic data for lag feature tests."""
    session.add_all(
        [
            SKU(
                sku_id="LAG_A",
                product_name="Lag Test A",
                category="LagTest",
                mrp=100.0,
                cost=50.0,
                current_inventory=200,
            ),
        ]
    )

    # Create 30 days of sales with known pattern
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    for i, dt in enumerate(dates):
        units = 100 + i  # Simple linear pattern
        session.add(Sales(date=dt.date(), sku_id="LAG_A", units_sold=units))

    session.add(
        Festival(
            festival_name="TestFestival",
            date=pd.Timestamp("2024-02-15").date(),
            category="general",
            historical_uplift=0.2,
        )
    )
    session.commit()


def test_add_lag_features_creates_correct_columns(db_session):
    """Test that lag features are created with correct column names."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=20, freq="D"),
            "units_sold": range(100, 120),
        }
    )

    result = add_lag_features(df)

    assert "lag_1" in result.columns
    assert "lag_7" in result.columns
    assert "rolling_mean_7" in result.columns
    assert "rolling_std_7" in result.columns


def test_add_lag_features_drops_insufficient_history(db_session):
    """Test that rows with insufficient lag history are dropped."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "units_sold": range(100, 110),
        }
    )

    result = add_lag_features(df)

    # First 7 rows should be dropped due to insufficient rolling window
    assert len(result) == 3  # 10 - 7 = 3


def test_lag_1_is_previous_day(db_session):
    """Test that lag_1 correctly represents previous day's value."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=15, freq="D"),
            "units_sold": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
        }
    )

    result = add_lag_features(df)

    # Check that lag_1 matches previous day's units_sold
    for i in range(len(result)):
        expected_lag_1 = result.iloc[i]["units_sold"] - 1  # Since we have sequential values
        actual_lag_1 = result.iloc[i]["lag_1"]
        assert abs(actual_lag_1 - expected_lag_1) < 0.01


def test_lag_7_is_seven_days_ago(db_session):
    """Test that lag_7 correctly represents 7 days ago value."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=20, freq="D"),
            "units_sold": range(100, 120),
        }
    )

    result = add_lag_features(df)

    # Check that lag_7 is 7 less than current (since we have sequential values)
    for i in range(len(result)):
        expected_lag_7 = result.iloc[i]["units_sold"] - 7
        actual_lag_7 = result.iloc[i]["lag_7"]
        assert abs(actual_lag_7 - expected_lag_7) < 0.01


def test_rolling_mean_7_is_correct(db_session):
    """Test that rolling_mean_7 is correctly calculated."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=15, freq="D"),
            "units_sold": [100] * 15,  # Constant values
        }
    )

    result = add_lag_features(df)

    # For constant values, rolling mean should equal the value
    assert (result["rolling_mean_7"] == 100.0).all()


def test_rolling_std_7_is_correct(db_session):
    """Test that rolling_std_7 is correctly calculated."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=15, freq="D"),
            "units_sold": [100] * 15,  # Constant values
        }
    )

    result = add_lag_features(df)

    # For constant values, rolling std should be 0
    assert (result["rolling_std_7"] == 0.0).all()


def test_no_nan_in_lag_features(db_session):
    """Test that no NaN values exist in lag features after processing."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=20, freq="D"),
            "units_sold": range(100, 120),
        }
    )

    result = add_lag_features(df)

    # Check no NaN in lag columns
    assert not result["lag_1"].isna().any()
    assert not result["lag_7"].isna().any()
    assert not result["rolling_mean_7"].isna().any()
    assert not result["rolling_std_7"].isna().any()


def test_prepare_training_data_includes_lag_features(db_session):
    """Test that prepare_training_data includes lag features in X."""
    _seed_lag_test_data(db_session)

    X, y, full_df = prepare_training_data(db_session, "LagTest")

    # Check that lag features are in X
    assert "lag_1" in X.columns
    assert "lag_7" in X.columns
    assert "rolling_mean_7" in X.columns
    assert "rolling_std_7" in X.columns

    # Check that original features are still there
    assert "time_index" in X.columns
    assert "weekday" in X.columns
    assert "festival_score" in X.columns


def test_prepare_training_data_no_nan_leakage(db_session):
    """Test that prepare_training_data has no NaN values in features."""
    _seed_lag_test_data(db_session)

    X, y, full_df = prepare_training_data(db_session, "LagTest")

    # Check no NaN in any feature
    assert not X.isna().any().any()
    assert not y.isna().any()


def test_recursive_forecast_no_nan(db_session):
    """Test that recursive forecasting produces no NaN values."""
    _seed_lag_test_data(db_session)

    forecast = forecast_next_n_days(db_session, "LagTest", n_days=14)

    # Check no NaN in forecast
    assert not forecast.isna().any().any()


def test_recursive_forecast_predictions_vary(db_session):
    """Test that recursive predictions are not constant."""
    _seed_lag_test_data(db_session)

    forecast = forecast_next_n_days(db_session, "LagTest", n_days=14)

    # Predictions should vary
    assert forecast["predicted_mean"].nunique() > 1


def test_recursive_forecast_uses_previous_predictions(db_session):
    """Test that recursive forecasting uses previous predictions for lag features."""
    _seed_lag_test_data(db_session)

    # Generate two forecasts with different horizons
    forecast_7 = forecast_next_n_days(db_session, "LagTest", n_days=7)
    forecast_14 = forecast_next_n_days(db_session, "LagTest", n_days=14)

    # First 7 predictions should be identical (same recursive path)
    for i in range(7):
        assert abs(forecast_7.iloc[i]["predicted_mean"] - forecast_14.iloc[i]["predicted_mean"]) < 0.01


def test_recursive_forecast_uncertainty_grows(db_session):
    """Test that uncertainty grows with forecast horizon."""
    _seed_lag_test_data(db_session)

    forecast = forecast_next_n_days(db_session, "LagTest", n_days=30)

    # Calculate uncertainty width
    width = forecast["upper_95"] - forecast["lower_95"]

    # Early uncertainty
    early_width = width.iloc[:5].mean()
    # Late uncertainty
    late_width = width.iloc[-5:].mean()

    # Late uncertainty should be >= early uncertainty (or very close)
    assert late_width >= early_width * 0.9


def test_recursive_forecast_with_varying_pattern(db_session):
    """Test recursive forecasting with more complex pattern."""
    session = db_session

    # Create data with weekly pattern
    session.add(
        SKU(
            sku_id="PATTERN_A",
            product_name="Pattern Test",
            category="PatternTest",
            mrp=100.0,
            cost=50.0,
            current_inventory=200,
        )
    )

    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    for i, dt in enumerate(dates):
        # Weekly pattern: higher on weekends
        base = 100
        weekly = 20 if dt.dayofweek >= 5 else 0
        trend = i * 0.5
        units = int(base + weekly + trend)
        session.add(Sales(date=dt.date(), sku_id="PATTERN_A", units_sold=units))

    session.commit()

    forecast = forecast_next_n_days(session, "PatternTest", n_days=14)

    # Should capture weekly pattern (predictions should vary)
    assert forecast["predicted_mean"].std() > 1.0


def test_lag_features_with_minimum_data(db_session):
    """Test that lag features work with minimum required data."""
    session = db_session

    session.add(
        SKU(
            sku_id="MIN_A",
            product_name="Min Test",
            category="MinTest",
            mrp=100.0,
            cost=50.0,
            current_inventory=200,
        )
    )

    # Create exactly 10 days of data (minimum for lag features)
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    for i, dt in enumerate(dates):
        session.add(Sales(date=dt.date(), sku_id="MIN_A", units_sold=100 + i))

    session.commit()

    X, y, full_df = prepare_training_data(session, "MinTest")

    # Should have 3 rows after dropping first 7 for lag features
    assert len(X) == 3
    assert len(y) == 3


def test_recursive_forecast_confidence_intervals_valid(db_session):
    """Test that confidence intervals are valid throughout recursive forecast."""
    _seed_lag_test_data(db_session)

    forecast = forecast_next_n_days(db_session, "LagTest", n_days=30)

    # Check all confidence intervals are valid
    assert (forecast["lower_95"] <= forecast["predicted_mean"]).all()
    assert (forecast["predicted_mean"] <= forecast["upper_95"]).all()
    assert (forecast["lower_95"] >= 0).all()  # No negative predictions


def test_lag_features_preserve_order(db_session):
    """Test that lag features preserve temporal order."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=20, freq="D"),
            "units_sold": range(100, 120),
        }
    )

    result = add_lag_features(df)

    # Dates should still be in order
    assert (result["date"].diff().dropna().dt.days == 1).all()


def test_recursive_forecast_dates_sequential(db_session):
    """Test that forecast dates are sequential."""
    _seed_lag_test_data(db_session)

    forecast = forecast_next_n_days(db_session, "LagTest", n_days=20)

    # Check dates are sequential
    date_diffs = pd.to_datetime(forecast["date"]).diff().dropna().dt.days
    assert (date_diffs == 1).all()
