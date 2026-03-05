"""Service tests for discount simulation transformations."""

from __future__ import annotations

import pandas as pd

from marketpulse.services.discount_simulation import (
    compute_simulation_deltas,
    compute_supply_stability_index,
    simulate_discounted_forecast,
)


def _baseline_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-03-01", periods=10, freq="D"),
            "predicted_mean": [100, 98, 105, 102, 108, 112, 116, 110, 107, 109],
            "lower_95": [80, 79, 84, 83, 87, 90, 93, 89, 86, 88],
            "upper_95": [120, 117, 126, 121, 129, 134, 139, 131, 128, 130],
            "festival_score": [0.1] * 10,
        }
    )


def test_simulated_demand_is_not_lower_for_positive_discount():
    baseline = _baseline_df()
    simulated, _meta = simulate_discounted_forecast(
        baseline_df=baseline,
        category="Snacks",
        discount_percent=20,
        elasticity_mode="balanced",
    )
    assert (simulated["predicted_mean"] >= baseline["predicted_mean"]).all()


def test_simulation_intervals_are_valid_and_non_negative():
    baseline = _baseline_df()
    simulated, _meta = simulate_discounted_forecast(
        baseline_df=baseline,
        category="Staples",
        discount_percent=35,
        elasticity_mode="aggressive",
    )
    assert (simulated["lower_95"] >= 0).all()
    assert (simulated["predicted_mean"] >= simulated["lower_95"]).all()
    assert (simulated["upper_95"] >= simulated["predicted_mean"]).all()


def test_delta_and_stability_calculation_shapes():
    baseline = _baseline_df()
    simulated, meta = simulate_discounted_forecast(
        baseline_df=baseline,
        category="Edible Oil",
        discount_percent=15,
        elasticity_mode="conservative",
    )
    baseline_decision = {"risk_score": 0.35, "order_quantity": 150, "reorder_point": 430.0}
    simulated_decision = {"risk_score": 0.42, "order_quantity": 180, "reorder_point": 462.0}
    delta = compute_simulation_deltas(
        baseline_df=baseline,
        baseline_decision=baseline_decision,
        simulated_df=simulated,
        simulated_decision=simulated_decision,
    )
    assert set(delta.keys()) == {
        "forecast_total_delta",
        "risk_delta",
        "order_quantity_delta",
        "reorder_point_delta",
    }
    stability = compute_supply_stability_index(
        simulated_df=simulated,
        simulated_decision=simulated_decision,
        current_inventory=500,
        interval_scale=float(meta["interval_scale"]),
    )
    assert 0 <= stability <= 100
