"""Inventory optimization and decision engine for retail demand forecasting."""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_safety_stock(
    forecast_df: pd.DataFrame,
    service_level: float = 0.95,
) -> float:
    """Calculate safety stock based on forecast uncertainty.

    Args:
        forecast_df: DataFrame with predicted_mean, lower_95, upper_95 columns.
        service_level: Target service level (default 95%).

    Returns:
        Safety stock quantity as float.
    """
    if forecast_df.empty:
        return 0.0

    # Use the standard deviation implied by the confidence interval
    # For 95% CI: upper_95 = mean + 1.96*std, so std = (upper_95 - mean) / 1.96
    std_dev = (forecast_df["upper_95"] - forecast_df["predicted_mean"]) / 1.96
    avg_std = float(std_dev.mean())

    # Z-score for service level (1.65 for 95%)
    z_score = 1.65 if service_level >= 0.95 else 1.28

    safety_stock = z_score * avg_std * np.sqrt(len(forecast_df))
    return max(0.0, float(safety_stock))


def calculate_reorder_point(
    forecast_df: pd.DataFrame,
    lead_time_days: int,
    safety_stock: float,
) -> float:
    """Calculate reorder point based on lead time demand and safety stock.

    Args:
        forecast_df: DataFrame with predicted_mean column.
        lead_time_days: Number of days for supplier lead time.
        safety_stock: Pre-calculated safety stock quantity.

    Returns:
        Reorder point as float.
    """
    if forecast_df.empty or lead_time_days <= 0:
        return safety_stock

    # Average daily demand during lead time
    lead_time_demand = float(
        forecast_df.head(min(lead_time_days, len(forecast_df)))["predicted_mean"].sum()
    )

    reorder_point = lead_time_demand + safety_stock
    return max(0.0, float(reorder_point))


def calculate_order_quantity(
    current_inventory: int,
    reorder_point: float,
    forecast_df: pd.DataFrame,
) -> int:
    """Calculate recommended order quantity.

    Args:
        current_inventory: Current inventory level.
        reorder_point: Pre-calculated reorder point.
        forecast_df: DataFrame with predicted_mean column.

    Returns:
        Order quantity as integer (0 if no order needed).
    """
    if current_inventory >= reorder_point:
        return 0

    # Order enough to cover forecast period demand
    total_forecast_demand = float(forecast_df["predicted_mean"].sum())
    order_qty = max(0, int(np.ceil(total_forecast_demand + reorder_point - current_inventory)))

    return order_qty


def assess_risk_score(
    forecast_df: pd.DataFrame,
    current_inventory: int,
    reorder_point: float,
) -> float:
    """Assess inventory risk score based on uncertainty and stock levels.

    Args:
        forecast_df: DataFrame with predicted_mean, upper_95 columns.
        current_inventory: Current inventory level.
        reorder_point: Pre-calculated reorder point.

    Returns:
        Risk score between 0.0 (low risk) and 1.0 (high risk).
    """
    if forecast_df.empty:
        return 0.0

    # Factor 1: Inventory position relative to reorder point
    inventory_risk = 0.0
    if reorder_point > 0:
        inventory_risk = max(0.0, min(1.0, 1.0 - (current_inventory / reorder_point)))

    # Factor 2: Forecast uncertainty (coefficient of variation)
    mean_demand = float(forecast_df["predicted_mean"].mean())
    std_demand = float((forecast_df["upper_95"] - forecast_df["predicted_mean"]).mean() / 1.96)

    uncertainty_risk = 0.0
    if mean_demand > 0:
        cv = std_demand / mean_demand
        uncertainty_risk = min(1.0, cv)

    # Combined risk score (weighted average)
    risk_score = 0.6 * inventory_risk + 0.4 * uncertainty_risk
    return float(np.clip(risk_score, 0.0, 1.0))


def determine_action(
    order_quantity: int,
    risk_score: float,
) -> str:
    """Determine recommended inventory action.

    Args:
        order_quantity: Calculated order quantity.
        risk_score: Risk score between 0.0 and 1.0.

    Returns:
        Action recommendation string.
    """
    if order_quantity > 0:
        if risk_score >= 0.7:
            return "URGENT_ORDER"
        return "ORDER"

    if risk_score >= 0.5:
        return "MONITOR"

    return "MAINTAIN"


def generate_inventory_decision_summary(
    forecast_df: pd.DataFrame,
    current_inventory: int,
    lead_time_days: int,
    service_level: float = 0.95,
) -> dict[str, float | int | str]:
    """Generate comprehensive inventory decision summary.

    Args:
        forecast_df: DataFrame with date, predicted_mean, lower_95, upper_95.
        current_inventory: Current inventory level.
        lead_time_days: Supplier lead time in days.
        service_level: Target service level (default 95%).

    Returns:
        Dictionary with decision metrics and recommended action.
    """
    if forecast_df.empty:
        return {
            "recommended_action": "INSUFFICIENT_DATA",
            "order_quantity": 0,
            "reorder_point": 0.0,
            "safety_stock": 0.0,
            "risk_score": 0.0,
        }

    safety_stock = calculate_safety_stock(forecast_df, service_level)
    reorder_point = calculate_reorder_point(forecast_df, lead_time_days, safety_stock)
    order_quantity = calculate_order_quantity(current_inventory, reorder_point, forecast_df)
    risk_score = assess_risk_score(forecast_df, current_inventory, reorder_point)
    action = determine_action(order_quantity, risk_score)

    return {
        "recommended_action": action,
        "order_quantity": order_quantity,
        "reorder_point": round(reorder_point, 2),
        "safety_stock": round(safety_stock, 2),
        "risk_score": round(risk_score, 3),
    }
