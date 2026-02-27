"""Pydantic schemas for forecasting and inventory decision API."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    """Request schema for forecast endpoint."""

    n_days: int = Field(gt=0, le=365, description="Number of days to forecast (1-365)")
    current_inventory: int = Field(ge=0, description="Current inventory level")
    lead_time_days: int = Field(gt=0, le=90, description="Supplier lead time in days (1-90)")


class ForecastDataPoint(BaseModel):
    """Single forecast data point with uncertainty bounds."""

    date: str = Field(description="Forecast date in YYYY-MM-DD format")
    predicted_mean: float = Field(ge=0, description="Mean predicted demand")
    lower_95: float = Field(ge=0, description="Lower 95% confidence bound")
    upper_95: float = Field(ge=0, description="Upper 95% confidence bound")


class InventoryDecision(BaseModel):
    """Inventory optimization decision summary."""

    recommended_action: Literal[
        "ORDER",
        "URGENT_ORDER",
        "MONITOR",
        "MAINTAIN",
        "INSUFFICIENT_DATA",
    ] = Field(description="Recommended inventory action")
    order_quantity: int = Field(ge=0, description="Recommended order quantity")
    reorder_point: float = Field(ge=0, description="Calculated reorder point")
    safety_stock: float = Field(ge=0, description="Calculated safety stock")
    risk_score: float = Field(ge=0, le=1, description="Risk score (0=low, 1=high)")


class ForecastResponse(BaseModel):
    """Complete forecast and decision response."""

    category: str = Field(description="Product category")
    forecast: list[ForecastDataPoint] = Field(description="Forecast time series")
    decision: InventoryDecision = Field(description="Inventory decision summary")


class ForecastErrorResponse(BaseModel):
    """Error response for forecast endpoint."""

    status: Literal["error"] = "error"
    message: str = Field(description="Error message")
