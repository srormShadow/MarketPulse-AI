"""Discount simulation utilities built on top of forecast outputs."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

ElasticityMode = Literal["conservative", "balanced", "aggressive"]

ELASTICITY_MULTIPLIERS: dict[ElasticityMode, float] = {
    "conservative": 0.8,
    "balanced": 1.2,
    "aggressive": 1.6,
}

CATEGORY_TUNING: dict[str, float] = {
    "snacks": 1.10,
    "staples": 0.95,
    "edible oil": 0.90,
}


def _seasonal_factor_for_row(row: pd.Series) -> float:
    weekday = int(row.get("date").dayofweek)
    weekend_boost = 1.05 if weekday >= 5 else 1.0

    festival_score = float(row.get("festival_score", 0.0))
    festival_boost = 1.0 + min(0.2, festival_score * 0.2)
    return weekend_boost * festival_boost


def simulate_discounted_forecast(
    baseline_df: pd.DataFrame,
    category: str,
    discount_percent: float,
    elasticity_mode: ElasticityMode,
    uplift_cap: float = 1.2,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Transform a baseline forecast into a discount-adjusted forecast."""
    if baseline_df.empty:
        return baseline_df.copy(), {"avg_uplift": 0.0, "interval_scale": 1.0}

    mode_multiplier = ELASTICITY_MULTIPLIERS.get(elasticity_mode, ELASTICITY_MULTIPLIERS["balanced"])
    category_tuning = CATEGORY_TUNING.get(category.strip().lower(), 1.0)
    discount_ratio = max(0.0, float(discount_percent)) / 100.0

    simulated = baseline_df.copy()
    for col in ("predicted_mean", "lower_95", "upper_95"):
        simulated[col] = pd.to_numeric(simulated[col], errors="coerce").astype(float)
    uplifts: list[float] = []
    for idx, row in simulated.iterrows():
        seasonal_factor = _seasonal_factor_for_row(row)
        uplift = min(uplift_cap, discount_ratio * mode_multiplier * category_tuning * seasonal_factor)
        uplifts.append(float(uplift))

        base_mean = float(row["predicted_mean"])
        base_lower = float(row["lower_95"])
        base_upper = float(row["upper_95"])

        sim_mean = max(0.0, base_mean * (1.0 + uplift))
        base_width = max(0.0, base_upper - base_lower)
        interval_scale = 1.0 + min(0.35, discount_ratio / 2.0)
        sim_width = base_width * interval_scale

        sim_lower = max(0.0, sim_mean - (sim_width / 2.0))
        sim_upper = max(sim_mean, sim_mean + (sim_width / 2.0))
        if sim_lower > sim_mean:
            sim_lower = sim_mean

        simulated.at[idx, "predicted_mean"] = float(sim_mean)
        simulated.at[idx, "lower_95"] = float(sim_lower)
        simulated.at[idx, "upper_95"] = float(sim_upper)

    interval_scale = 1.0 + min(0.35, discount_ratio / 2.0)
    return simulated, {
        "avg_uplift": float(np.mean(uplifts)) if uplifts else 0.0,
        "interval_scale": float(interval_scale),
    }


def compute_simulation_deltas(
    baseline_df: pd.DataFrame,
    baseline_decision: dict,
    simulated_df: pd.DataFrame,
    simulated_decision: dict,
) -> dict[str, float | int]:
    baseline_total = float(pd.to_numeric(baseline_df["predicted_mean"], errors="coerce").fillna(0.0).sum())
    simulated_total = float(pd.to_numeric(simulated_df["predicted_mean"], errors="coerce").fillna(0.0).sum())
    return {
        "forecast_total_delta": round(simulated_total - baseline_total, 2),
        "risk_delta": round(float(simulated_decision.get("risk_score", 0.0)) - float(baseline_decision.get("risk_score", 0.0)), 3),
        "order_quantity_delta": int(simulated_decision.get("order_quantity", 0)) - int(baseline_decision.get("order_quantity", 0)),
        "reorder_point_delta": round(float(simulated_decision.get("reorder_point", 0.0)) - float(baseline_decision.get("reorder_point", 0.0)), 2),
    }


def compute_supply_stability_index(
    simulated_df: pd.DataFrame,
    simulated_decision: dict,
    current_inventory: int,
    interval_scale: float,
) -> float:
    """Compute a simple 0-100 stability score (higher is better)."""
    risk = float(simulated_decision.get("risk_score", 0.0))
    mean_daily = float(pd.to_numeric(simulated_df["predicted_mean"], errors="coerce").fillna(0.0).mean())
    days_of_cover = (float(current_inventory) / mean_daily) if mean_daily > 0 else 999.0

    risk_penalty = min(100.0, risk * 65.0)
    cover_penalty = 0.0 if days_of_cover >= 14 else (14.0 - max(0.0, days_of_cover)) * 2.0
    uncertainty_penalty = max(0.0, (interval_scale - 1.0) * 80.0)

    stability = 100.0 - risk_penalty - cover_penalty - uncertainty_penalty
    return round(float(np.clip(stability, 0.0, 100.0)), 2)
