"""Unit tests for Bayesian forecasting service."""

from __future__ import annotations

import pandas as pd
import pytest

from marketpulse.models.festival import Festival
from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU
from marketpulse.services.forecasting import forecast_next_n_days


def _seed_forecasting_data(session) -> None:
    """Seed deterministic category data for forecasting tests."""

    session.add_all(
        [
            SKU(sku_id="OIL_A", product_name="Oil A", category="Edible Oil", mrp=180.0, cost=130.0, current_inventory=200),
            SKU(sku_id="OIL_B", product_name="Oil B", category="Edible Oil", mrp=210.0, cost=150.0, current_inventory=180),
            SKU(sku_id="SNK_X", product_name="Snack X", category="Snacks", mrp=40.0, cost=20.0, current_inventory=300),
        ]
    )

    dates = pd.date_range("2024-01-01", periods=180, freq="D")
    sales_rows: list[Sales] = []
    for i, dt in enumerate(dates):
        weekly = 8 if dt.dayofweek >= 5 else 0
        trend = i * 0.08
        pulse = 15 if dt.strftime("%m-%d") in {"01-15", "11-01", "12-25"} else 0
        oil_a = int(round(110 + trend + weekly + pulse))
        oil_b = int(round(95 + (trend * 0.9) + (weekly * 0.6) + (pulse * 0.7)))
        sales_rows.append(Sales(date=dt.date(), sku_id="OIL_A", units_sold=oil_a))
        sales_rows.append(Sales(date=dt.date(), sku_id="OIL_B", units_sold=oil_b))

    session.add_all(sales_rows)
    session.add_all(
        [
            Festival(festival_name="Pongal", date=pd.Timestamp("2024-01-15").date(), category="general", historical_uplift=0.2),
            Festival(festival_name="Diwali", date=pd.Timestamp("2024-11-01").date(), category="general", historical_uplift=0.3),
            Festival(festival_name="Christmas", date=pd.Timestamp("2024-12-25").date(), category="general", historical_uplift=0.18),
        ]
    )
    session.commit()


def test_forecast_returns_correct_length(db_session, repo):
    _seed_forecasting_data(db_session)
    out = forecast_next_n_days(repo, "Edible Oil", n_days=30)
    assert len(out) == 30


def test_forecast_columns_exist(db_session, repo):
    _seed_forecasting_data(db_session)
    out = forecast_next_n_days(repo, "Edible Oil", n_days=30)
    assert list(out.columns) == ["date", "predicted_mean", "lower_95", "upper_95"]


def test_no_negative_predictions(db_session, repo):
    _seed_forecasting_data(db_session)
    out = forecast_next_n_days(repo, "Edible Oil", n_days=30)
    assert (out["predicted_mean"] >= 0).all()
    assert (out["lower_95"] >= 0).all()
    assert (out["upper_95"] >= 0).all()


def test_confidence_interval_order(db_session, repo):
    _seed_forecasting_data(db_session)
    out = forecast_next_n_days(repo, "Edible Oil", n_days=30)
    assert (out["lower_95"] <= out["predicted_mean"]).all()
    assert (out["predicted_mean"] <= out["upper_95"]).all()


def test_dates_are_continuous(db_session, repo):
    _seed_forecasting_data(db_session)
    out = forecast_next_n_days(repo, "Edible Oil", n_days=30)
    deltas = pd.to_datetime(out["date"]).diff().dropna().dt.days
    assert (deltas == 1).all()


def test_uncertainty_is_non_zero(db_session, repo):
    _seed_forecasting_data(db_session)
    out = forecast_next_n_days(repo, "Edible Oil", n_days=30)
    width = out["upper_95"] - out["lower_95"]
    assert (width > 0).mean() >= 0.9


def test_uncertainty_increases_with_horizon(db_session, repo):
    _seed_forecasting_data(db_session)
    out = forecast_next_n_days(repo, "Edible Oil", n_days=30)
    width = out["upper_95"] - out["lower_95"]
    early_mean = float(width.iloc[:10].mean())
    late_mean = float(width.iloc[-10:].mean())
    assert late_mean >= early_mean * 0.95


def test_forecast_not_constant(db_session, repo):
    _seed_forecasting_data(db_session)
    out = forecast_next_n_days(repo, "Edible Oil", n_days=30)
    assert out["predicted_mean"].nunique() > 1


def test_invalid_n_days(db_session, repo):
    _seed_forecasting_data(db_session)
    with pytest.raises(ValueError):
        forecast_next_n_days(repo, "Edible Oil", n_days=0)
    with pytest.raises(ValueError):
        forecast_next_n_days(repo, "Edible Oil", n_days=-7)


def test_invalid_category(db_session, repo):
    _seed_forecasting_data(db_session)
    with pytest.raises(ValueError):
        forecast_next_n_days(repo, "NonExistentCategory", n_days=30)
