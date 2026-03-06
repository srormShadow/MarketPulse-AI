"""SQLite model for cached forecast payloads."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from marketpulse.db.base import Base


class ForecastCache(Base):
    __tablename__ = "forecast_cache"
    __table_args__ = (
        Index("ix_forecast_cache_category_generated_at", "category", "generated_at"),
        Index("ix_forecast_cache_category_params_hash", "category", "params_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    params_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    n_days: Mapped[int] = mapped_column(Integer, nullable=False)
    current_inventory: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier_pack_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

