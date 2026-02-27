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
    """Forecast next N days with uncertainty for a retail category.

    Pipeline:
    1. Build historical training data from existing feature engineering.
    2. Train Bayesian Ridge model on standardized features.
    3. Generate future time/weekday/festival features.
    4. Predict mean and 95% confidence interval.

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
    if full_df.empty or len(full_df) < 5:
        raise ValueError("Insufficient historical data to train forecasting model")

    model, scaler = train_model(X_train, y_train)

    last_date = pd.to_datetime(full_df["date"].max())
    last_time_index = int(full_df["time_index"].max())

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

    X_future = future_df[["time_index", "weekday", "festival_score"]]
    preds = predict_with_uncertainty(model, scaler, X_future)

    result = pd.DataFrame({"date": future_dates})
    result = pd.concat([result, preds], axis=1)
    return result
