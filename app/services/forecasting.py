"""Probabilistic forecasting utilities for category-level retail demand."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.linear_model import BayesianRidge
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from app.services.feature_engineering import (
    compute_festival_proximity,
    prepare_training_data,
)


def train_model(X: pd.DataFrame, y: pd.Series) -> tuple[BayesianRidge, StandardScaler]:
    """Train a Bayesian Ridge model with standardized input features.

    Args:
        X: Feature matrix containing numeric predictors.
        y: Target series (units_sold).

    Returns:
        Trained BayesianRidge model and fitted StandardScaler.
    """

    if X.empty or y.empty:
        raise ValueError("Training data is empty")
    if len(X) != len(y):
        raise ValueError("X and y must have the same number of rows")

    X_numeric = X.astype(float)
    y_numeric = y.astype(float)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_numeric)

    model = BayesianRidge()
    model.fit(X_scaled, y_numeric)
    return model, scaler


def predict_with_uncertainty(
    model: BayesianRidge,
    scaler: StandardScaler,
    X_future: pd.DataFrame,
) -> pd.DataFrame:
    """Predict mean and 95% interval bounds using Bayesian posterior std.

    Args:
        model: Trained BayesianRidge model.
        scaler: Fitted StandardScaler used during training.
        X_future: Future feature matrix.

    Returns:
        DataFrame with `predicted_mean`, `lower_95`, `upper_95`.
    """

    if X_future.empty:
        return pd.DataFrame(columns=["predicted_mean", "lower_95", "upper_95"])

    X_scaled: NDArray[np.float64] = np.asarray(
        scaler.transform(X_future.astype(float)),
        dtype=np.float64,
    )
    prediction = model.predict(X_scaled, return_std=True)
    mean_pred, std_pred = cast(tuple[NDArray[np.float64], NDArray[np.float64]], prediction)

    lower_95 = mean_pred - (1.96 * std_pred)
    upper_95 = mean_pred + (1.96 * std_pred)

    # Demand cannot be negative.
    mean_pred = np.clip(mean_pred, 0, None)
    lower_95 = np.clip(lower_95, 0, None)
    upper_95 = np.clip(upper_95, 0, None)

    return pd.DataFrame(
        {
            "predicted_mean": mean_pred,
            "lower_95": lower_95,
            "upper_95": upper_95,
        }
    )


def forecast_next_n_days(
    session: Session,
    category: str,
    n_days: int = 30,
) -> pd.DataFrame:
    """Forecast next N days with uncertainty using recursive multi-step prediction.

    Pipeline:
    1. Build historical training data with lag features from feature engineering.
    2. Train Bayesian Ridge model on standardized features.
    3. For each future day, recursively:
       a) Build feature row with time/weekday/festival features
       b) For lag features:
          - If lag refers to historical period → use actual data
          - If lag refers to future period → use previous prediction
       c) Predict next day with uncertainty
       d) Append predicted value to temporary series for next iteration
    4. Return forecast with mean and 95% confidence intervals.

    Args:
        session: Active SQLAlchemy session.
        category: Category name passed to feature engineering pipeline.
        n_days: Number of future days to forecast.

    Returns:
        DataFrame with columns: `date`, `predicted_mean`, `lower_95`, `upper_95`.
    """

    if n_days <= 0:
        raise ValueError("n_days must be a positive integer")

    X_train, y_train, full_df = prepare_training_data(session, category)
    if full_df.empty or len(full_df) < 7:
        raise ValueError("Insufficient historical data to train forecasting model")

    model, scaler = train_model(X_train, y_train)

    last_date = pd.to_datetime(full_df["date"].max())
    last_time_index = int(full_df["time_index"].max())

    # Build extended series that includes historical + future predictions
    # This allows us to look back for lag features during recursive forecasting
    historical_units: list[float] = full_df["units_sold"].values.tolist()
    predicted_units: list[float] = []

    # Pre-compute future dates and festival features
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=n_days, freq="D")

    future_df = pd.DataFrame(
        {
            "date": future_dates,
            "time_index": np.arange(last_time_index + 1, last_time_index + 1 + n_days, dtype=int),
            "weekday": future_dates.dayofweek.astype(int),
        }
    )

    festival_features = compute_festival_proximity(
        future_df[["date"]].copy(),
        session,
        category,
    )
    future_df["festival_score"] = festival_features["festival_score"].astype(float)

    # Recursive forecasting: predict one day at a time
    predictions_mean: list[float] = []
    predictions_lower: list[float] = []
    predictions_upper: list[float] = []

    for i in range(n_days):
        # Combined series: historical + predictions so far
        combined_series: list[float] = historical_units + predicted_units

        # Calculate lag features for current prediction step
        # lag_1: previous day (could be historical or predicted)
        lag_1 = float(combined_series[-1]) if len(combined_series) >= 1 else 0.0

        # lag_7: 7 days ago (could be historical or predicted)
        lag_7 = float(combined_series[-7]) if len(combined_series) >= 7 else lag_1

        # rolling_mean_7: average of last 7 days
        if len(combined_series) >= 7:
            rolling_mean_7 = float(np.mean(combined_series[-7:]))
        else:
            rolling_mean_7 = float(np.mean(combined_series))

        # rolling_std_7: std of last 7 days
        if len(combined_series) >= 7:
            rolling_std_7 = float(np.std(combined_series[-7:]))
        else:
            rolling_std_7 = 0.0

        # Build feature row for this prediction
        X_future_row = pd.DataFrame(
            {
                "time_index": [future_df.iloc[i]["time_index"]],
                "weekday": [future_df.iloc[i]["weekday"]],
                "festival_score": [future_df.iloc[i]["festival_score"]],
                "lag_1": [lag_1],
                "lag_7": [lag_7],
                "rolling_mean_7": [rolling_mean_7],
                "rolling_std_7": [rolling_std_7],
            }
        )

        # Predict with uncertainty
        pred = predict_with_uncertainty(model, scaler, X_future_row)

        mean_val = float(pred["predicted_mean"].iloc[0])
        lower_val = float(pred["lower_95"].iloc[0])
        upper_val = float(pred["upper_95"].iloc[0])

        predictions_mean.append(mean_val)
        predictions_lower.append(lower_val)
        predictions_upper.append(upper_val)

        # Add prediction to series for next iteration
        predicted_units.append(mean_val)

    result = pd.DataFrame(
        {
            "date": future_dates,
            "predicted_mean": predictions_mean,
            "lower_95": predictions_lower,
            "upper_95": predictions_upper,
        }
    )

    return result
