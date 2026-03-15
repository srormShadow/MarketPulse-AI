"""Pydantic schemas for forecasting and inventory decision API."""

from typing import Literal

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    """Request schema for forecast endpoint."""

    n_days: int = Field(gt=0, le=365, description="Number of days to forecast (1-365)")
    current_inventory: int = Field(ge=0, description="Current inventory level")
    lead_time_days: int = Field(gt=0, le=90, description="Supplier lead time in days (1-90)")
    supplier_pack_size: int = Field(default=1, ge=1, description="Order pack size multiple")
    last_upload_date: str | None = Field(default=None, description="Last data upload timestamp in ISO format")


class ForecastDataPoint(BaseModel):
    """Single forecast data point with uncertainty bounds."""

    date: str = Field(description="Forecast date in YYYY-MM-DD format")
    predicted_mean: float = Field(ge=0, description="Mean predicted demand")
    lower_95: float = Field(ge=0, description="Lower 95% confidence bound")
    upper_95: float = Field(ge=0, description="Upper 95% confidence bound")
    confidence_level: Literal["high", "medium", "low"] = Field(description="Rule-based horizon confidence level")


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
    festival_buffer_applied: bool = Field(default=False, description="True if festival safety buffer was applied")
    data_stale_warning: bool = Field(default=False, description="True if source data is older than 7 days")
    pack_size_applied: bool = Field(default=False, description="True if order qty was rounded by pack size")


class ForecastResponse(BaseModel):
    """Complete forecast and decision response."""

    status: str = Field(default="completed", description="Response status (completed, accepted, etc)")
    category: str = Field(description="Product category")
    forecast: list[ForecastDataPoint] = Field(default_factory=list, description="Forecast time series")
    decision: InventoryDecision | None = Field(default=None, description="Inventory decision summary")
    cache_hit: bool = Field(default=False, description="True if served from cache")
    data_stale: bool = Field(default=False, description="True if source data appears stale")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal sanity warnings")
    is_training: bool = Field(default=False, description="True if a model training job was dispatched")


class BatchForecastRequest(BaseModel):
    categories: list[str] = Field(min_length=1, max_length=20, description="Categories to forecast")
    n_days: int = Field(gt=0, le=365, description="Forecast horizon")
    inventory: dict[str, int] = Field(default_factory=dict, description="Category -> current inventory")
    lead_times: dict[str, int] = Field(default_factory=dict, description="Category -> lead time days")
    supplier_pack_sizes: dict[str, int] = Field(default_factory=dict, description="Category -> supplier pack size")
    last_upload_dates: dict[str, str] = Field(default_factory=dict, description="Category -> last upload timestamp ISO")


class BatchForecastResponse(BaseModel):
    results: list[ForecastResponse] = Field(default_factory=list)


class ForecastErrorResponse(BaseModel):
    """Error response for forecast endpoint."""

    status: Literal["error"] = "error"
    message: str = Field(description="Error message")
