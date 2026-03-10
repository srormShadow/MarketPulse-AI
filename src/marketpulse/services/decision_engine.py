"""Inventory optimization and decision engine for retail demand forecasting."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd


def calculate_safety_stock(
    forecast_df: pd.DataFrame,
    service_level: float = 0.95,
) -> tuple[float, bool]:
    """Calculate safety stock based on forecast uncertainty.

    Args:
        forecast_df: DataFrame with predicted_mean, lower_95, upper_95 columns.
        service_level: Target service level (default 95%).

    Returns:
        Tuple of (safety_stock, festival_buffer_applied).
    """
    if forecast_df.empty:
        return 0.0, False

    # Use the standard deviation implied by the confidence interval
    # For 95% CI: upper_95 = mean + 1.96*std, so std = (upper_95 - mean) / 1.96
    std_dev = (forecast_df["upper_95"] - forecast_df["predicted_mean"]) / 1.96
    avg_std = float(std_dev.mean())

    # Z-score for service level (1.65 for 95%)
    z_score = 1.65 if service_level >= 0.95 else 1.28

    safety_stock = z_score * avg_std * np.sqrt(len(forecast_df))

    festival_buffer_applied = False
    if "festival_score" in forecast_df.columns:
        lead_window = forecast_df.head(max(1, min(30, len(forecast_df))))
        if pd.to_numeric(lead_window["festival_score"], errors="coerce").fillna(0.0).gt(0.6).any():
            safety_stock *= 1.3
            festival_buffer_applied = True

    return max(0.0, float(safety_stock)), festival_buffer_applied


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
    supplier_pack_size: int = 1,
) -> int:
    """Calculate recommended order quantity.

    Args:
        current_inventory: Current inventory level.
        reorder_point: Pre-calculated reorder point.
        forecast_df: DataFrame with predicted_mean column.

    Returns:
        Order quantity as integer (0 if no order needed), rounded up
        to nearest supplier pack size.
    """
    if current_inventory >= reorder_point:
        return 0

    # Order enough to cover forecast period demand
    total_forecast_demand = float(forecast_df["predicted_mean"].sum())
    order_qty = max(0, int(np.ceil(total_forecast_demand + reorder_point - current_inventory)))
    if supplier_pack_size > 1 and order_qty > 0:
        order_qty = int(np.ceil(order_qty / supplier_pack_size) * supplier_pack_size)

    return order_qty


def _parse_last_upload_date(last_upload_date: str | date | datetime | None) -> datetime | None:
    if last_upload_date is None:
        return None
    if isinstance(last_upload_date, datetime):
        return last_upload_date.astimezone(timezone.utc) if last_upload_date.tzinfo else last_upload_date.replace(tzinfo=timezone.utc)
    if isinstance(last_upload_date, date):
        return datetime.combine(last_upload_date, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(last_upload_date, str):
        try:
            return datetime.fromisoformat(last_upload_date.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


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
    raw_mean = forecast_df["predicted_mean"].mean()
    raw_std = (forecast_df["upper_95"] - forecast_df["predicted_mean"]).mean() / 1.96
    mean_demand = float(raw_mean) if pd.notna(raw_mean) else 0.0
    std_demand = float(raw_std) if pd.notna(raw_std) else 0.0

    uncertainty_risk = 0.0
    if mean_demand > 0:
        cv = std_demand / mean_demand
        uncertainty_risk = min(1.0, max(0.0, cv))

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
    supplier_pack_size: int = 1,
    last_upload_date: str | date | datetime | None = None,
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
            "festival_buffer_applied": False,
            "data_stale_warning": False,
            "pack_size_applied": False,
        }

    safety_stock, festival_buffer_applied = calculate_safety_stock(forecast_df, service_level)
    reorder_point = calculate_reorder_point(forecast_df, lead_time_days, safety_stock)
    baseline_order_quantity = calculate_order_quantity(
        current_inventory,
        reorder_point,
        forecast_df,
        supplier_pack_size=1,
    )
    order_quantity = calculate_order_quantity(
        current_inventory,
        reorder_point,
        forecast_df,
        supplier_pack_size=max(1, int(supplier_pack_size)),
    )
    pack_size_applied = max(1, int(supplier_pack_size)) > 1 and order_quantity != baseline_order_quantity
    risk_score = assess_risk_score(forecast_df, current_inventory, reorder_point)
    action = determine_action(order_quantity, risk_score)
    parsed_upload = _parse_last_upload_date(last_upload_date)
    data_stale_warning = False
    if parsed_upload is not None:
        data_stale_warning = parsed_upload < (datetime.now(timezone.utc) - timedelta(days=7))

    return {
        "recommended_action": action,
        "order_quantity": order_quantity,
        "reorder_point": round(reorder_point, 2),
        "safety_stock": round(safety_stock, 2),
        "risk_score": round(risk_score, 3),
        "festival_buffer_applied": festival_buffer_applied,
        "data_stale_warning": bool(data_stale_warning),
        "pack_size_applied": pack_size_applied,
    }
