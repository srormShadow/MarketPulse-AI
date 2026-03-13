"""SQLite model for recommendation/audit log entries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from marketpulse.db.base import Base


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"
    __table_args__ = (
        Index("ix_recommendation_logs_org_timestamp", "organization_id", "timestamp"),
        Index("ix_recommendation_logs_category_timestamp", "category", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True,
    )
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    insight: Mapped[str] = mapped_column(Text, nullable=False)

