"""Debug script to verify recursive forecasting with lag features."""

import sys
from pathlib import Path

import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.models.festival import Festival
from app.models.sales import Sales
from app.models.sku import SKU
from app.services.feature_engineering import prepare_training_data
from app.services.forecasting import forecast_next_n_days


def seed_test_data(session):
    """Seed test data for verification."""
    # Clear existing data
    session.query(Sales).delete()
    session.query(SKU).delete()
    session.query(Festival).delete()

    # Add SKUs
    session.add_all(
        [
            SKU(
                sku_id="TEST_A",
                product_name="Test Product A",
                category="TestCategory",
                mrp=100.0,
                cost=50.0,
                current_inventory=200,
            ),
            SKU(
                sku_id="TEST_B",
                product_name="Test Product B",
                category="TestCategory",
                mrp=120.0,
                cost=60.0,
                current_inventory=150,
            ),
        ]
    )

    # Add sales data (60 days)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    for i, dt in enumerate(dates):
        # Create pattern: base + trend + weekly seasonality
        base = 50
        trend = i * 0.5
        weekly = 10 if dt.dayofweek >= 5 else 0
        units_a = int(base + trend + weekly)
        units_b = int(base * 0.8 + trend * 0.7 + weekly * 0.5)

        session.add(Sales(date=dt.date(), sku_id="TEST_A", units_sold=units_a))
        session.add(Sales(date=dt.date(), sku_id="TEST_B", units_sold=units_b))

    # Add festivals
    session.add_all(
        [
            Festival(
                festival_name="Diwali",
                date=pd.Timestamp("2024-11-01").date(),
                category="general",
                historical_uplift=0.3,
            ),
        ]
    )

    session.commit()
    print("✓ Test data seeded successfully")


def verify_lag_features():
    """Verify lag feature generation."""
    print("\n" + "=" * 70)
    print("VERIFICATION 1: Lag Feature Generation")
    print("=" * 70)

    session = SessionLocal()
    try:
        X_train, y_train, full_df = prepare_training_data(session, "TestCategory")

        print(f"\nTraining data shape: {X_train.shape}")
        print(f"Features: {list(X_train.columns)}")

        print("\n--- First 5 rows of lag features ---")
        lag_cols = ["lag_1", "lag_7", "rolling_mean_7", "rolling_std_7"]
        print(full_df[["date", "units_sold"] + lag_cols].head(5).to_string(index=False))

        print("\n--- Last 5 rows of lag features ---")
        print(full_df[["date", "units_sold"] + lag_cols].tail(5).to_string(index=False))

        # Check for NaN values
        nan_count = X_train[lag_cols].isna().sum()
        print(f"\n--- NaN check in training features ---")
        print(nan_count.to_string())

        if nan_count.sum() == 0:
            print("✓ No NaN values in lag features")
        else:
            print("✗ WARNING: NaN values found in lag features!")

        # Verify lag_1 is actually shifted by 1
        print("\n--- Verifying lag_1 shift ---")
        for i in range(1, min(6, len(full_df))):
            expected = full_df.iloc[i - 1]["units_sold"]
            actual = full_df.iloc[i]["lag_1"]
            match = "✓" if abs(expected - actual) < 0.01 else "✗"
            print(f"Row {i}: lag_1={actual:.2f}, expected={expected:.2f} {match}")

    finally:
        session.close()


def verify_recursive_forecast():
    """Verify recursive forecasting."""
    print("\n" + "=" * 70)
    print("VERIFICATION 2: Recursive Forecasting")
    print("=" * 70)

    session = SessionLocal()
    try:
        # Generate forecast
        forecast_df = forecast_next_n_days(session, "TestCategory", n_days=14)

        print(f"\nForecast shape: {forecast_df.shape}")
        print(f"Columns: {list(forecast_df.columns)}")

        print("\n--- First 5 forecast rows ---")
        print(forecast_df.head(5).to_string(index=False))

        print("\n--- Last 5 forecast rows ---")
        print(forecast_df.tail(5).to_string(index=False))

        # Check for NaN values
        nan_count = forecast_df.isna().sum()
        print(f"\n--- NaN check in forecast ---")
        print(nan_count.to_string())

        if nan_count.sum() == 0:
            print("✓ No NaN values in forecast")
        else:
            print("✗ WARNING: NaN values found in forecast!")

        # Check confidence intervals
        print("\n--- Confidence interval validation ---")
        lower_valid = (forecast_df["lower_95"] <= forecast_df["predicted_mean"]).all()
        upper_valid = (forecast_df["predicted_mean"] <= forecast_df["upper_95"]).all()
        print(f"lower_95 <= predicted_mean: {lower_valid} {'✓' if lower_valid else '✗'}")
        print(f"predicted_mean <= upper_95: {upper_valid} {'✓' if upper_valid else '✗'}")

        # Check for non-negative values
        print("\n--- Non-negative validation ---")
        all_positive = (
            (forecast_df["predicted_mean"] >= 0).all()
            and (forecast_df["lower_95"] >= 0).all()
            and (forecast_df["upper_95"] >= 0).all()
        )
        print(f"All predictions >= 0: {all_positive} {'✓' if all_positive else '✗'}")

        # Check that predictions vary (not constant)
        print("\n--- Prediction variance ---")
        unique_predictions = forecast_df["predicted_mean"].nunique()
        print(f"Unique prediction values: {unique_predictions}")
        if unique_predictions > 1:
            print("✓ Predictions vary over time (not constant)")
        else:
            print("✗ WARNING: All predictions are the same!")

        # Check uncertainty increases with horizon
        print("\n--- Uncertainty growth ---")
        early_width = (forecast_df["upper_95"] - forecast_df["lower_95"]).iloc[:5].mean()
        late_width = (forecast_df["upper_95"] - forecast_df["lower_95"]).iloc[-5:].mean()
        print(f"Early uncertainty (days 1-5): {early_width:.2f}")
        print(f"Late uncertainty (days 10-14): {late_width:.2f}")
        if late_width >= early_width * 0.9:
            print("✓ Uncertainty grows or stays stable with horizon")
        else:
            print("✗ WARNING: Uncertainty decreases with horizon!")

    finally:
        session.close()


def verify_recursive_consistency():
    """Verify that recursive predictions use previous predictions."""
    print("\n" + "=" * 70)
    print("VERIFICATION 3: Recursive Consistency")
    print("=" * 70)

    session = SessionLocal()
    try:
        # Generate two forecasts with different horizons
        forecast_7 = forecast_next_n_days(session, "TestCategory", n_days=7)
        forecast_14 = forecast_next_n_days(session, "TestCategory", n_days=14)

        print("\n--- Comparing overlapping predictions ---")
        print("First 7 days should be similar (but may differ slightly due to recursion)")

        for i in range(7):
            pred_7 = forecast_7.iloc[i]["predicted_mean"]
            pred_14 = forecast_14.iloc[i]["predicted_mean"]
            diff = abs(pred_7 - pred_14)
            diff_pct = (diff / pred_7 * 100) if pred_7 > 0 else 0
            print(f"Day {i+1}: 7-day={pred_7:.2f}, 14-day={pred_14:.2f}, diff={diff:.2f} ({diff_pct:.1f}%)")

        # They should be reasonably close (within 10% for early days)
        early_diffs = [
            abs(forecast_7.iloc[i]["predicted_mean"] - forecast_14.iloc[i]["predicted_mean"])
            / forecast_7.iloc[i]["predicted_mean"]
            for i in range(3)
        ]
        avg_diff = sum(early_diffs) / len(early_diffs) * 100

        print(f"\nAverage difference in first 3 days: {avg_diff:.2f}%")
        if avg_diff < 15:
            print("✓ Recursive predictions are consistent")
        else:
            print("⚠ Predictions differ more than expected (may be due to recursive nature)")

    finally:
        session.close()


def main():
    """Run all verifications."""
    print("\n" + "=" * 70)
    print("RECURSIVE FORECAST VERIFICATION SCRIPT")
    print("=" * 70)

    session = SessionLocal()
    try:
        seed_test_data(session)
    finally:
        session.close()

    verify_lag_features()
    verify_recursive_forecast()
    verify_recursive_consistency()

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
