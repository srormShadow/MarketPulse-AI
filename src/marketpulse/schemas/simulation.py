"""Pydantic schemas for discount simulation API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from marketpulse.schemas.forecast import ForecastDataPoint, InventoryDecision


ElasticityMode = Literal["conservative", "balanced", "aggressive"]


class DiscountSimulationRequest(BaseModel):
    n_days: int = Field(default=30, gt=0, le=90, description="Forecast horizon for simulation")
    current_inventory: int = Field(ge=0, description="Current inventory level")
    lead_time_days: int = Field(gt=0, le=90, description="Supplier lead time in days")
    supplier_pack_size: int = Field(default=1, ge=1, description="Order pack size multiple")
    discount_percent: float = Field(ge=0, le=70, description="Promotional discount percentage")
    elasticity_mode: ElasticityMode = Field(default="balanced", description="Demand elasticity sensitivity mode")
    include_explanation: bool = Field(default=False, description="Whether to request optional Bedrock explanation")


class DiscountSimulationInputs(BaseModel):
    n_days: int
    current_inventory: int
    lead_time_days: int
    supplier_pack_size: int
    discount_percent: float
    elasticity_mode: ElasticityMode


class SimulationBlock(BaseModel):
    forecast: list[ForecastDataPoint]
    decision: InventoryDecision


class SimulationDelta(BaseModel):
    forecast_total_delta: float
    risk_delta: float
    order_quantity_delta: int
    reorder_point_delta: float


class DiscountSimulationResponse(BaseModel):
    category: str
    inputs: DiscountSimulationInputs
    baseline: SimulationBlock
    simulated: SimulationBlock
    delta: SimulationDelta
    supply_stability_index: float = Field(ge=0, le=100)
    explanation: str | None = None
    warnings: list[str] = Field(default_factory=list)
