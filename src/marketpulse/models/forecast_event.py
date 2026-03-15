"""SQLite model for forecast execution events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from marketpulse.db.base import Base


class ForecastEvent(Base):
    __tablename__ = "forecast_events"
    __table_args__ = (
        Index("ix_forecast_events_org_timestamp", "organization_id", "timestamp"),
        Index("ix_forecast_events_category_timestamp", "category", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True,
    )
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    
    n_days: Mapped[int] = mapped_column(Integer, nullable=False)
    current_inventory: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier_pack_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    recommended_action: Mapped[str] = mapped_column(String(50), nullable=False)
    order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
