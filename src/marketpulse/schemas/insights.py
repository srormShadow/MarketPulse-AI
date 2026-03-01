"""Pydantic schemas for GenAI insights endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InsightRequest(BaseModel):
    forecast_data: list[dict[str, Any]] | dict[str, Any] = Field(
        default_factory=list,
        description="Forecast payload for one category",
    )
    decision_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Decision summary payload, includes risk_score",
    )
    festival_context: list[dict[str, Any]] | dict[str, Any] | None = Field(
        default=None,
        description="Optional festival context",
    )


class InsightResponse(BaseModel):
    category: str
    insight: str
    generated_at: str


class BatchInsightItem(BaseModel):
    category: str
    forecast_data: list[dict[str, Any]] | dict[str, Any] = Field(default_factory=list)
    decision_data: dict[str, Any] = Field(default_factory=dict)
    festival_context: list[dict[str, Any]] | dict[str, Any] | None = None


class BatchInsightRequest(BaseModel):
    items: list[BatchInsightItem] = Field(default_factory=list)


class BatchInsightResponse(BaseModel):
    insights: list[InsightResponse]
    generated_at: str

