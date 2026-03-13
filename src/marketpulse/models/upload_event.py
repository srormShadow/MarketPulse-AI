"""SQLite model for category upload timestamps."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from marketpulse.db.base import Base


class UploadEvent(Base):
    __tablename__ = "upload_events"
    __table_args__ = (
        Index("ix_upload_events_org_category_uploaded_at", "organization_id", "category", "uploaded_at"),
        Index("ix_upload_events_category_uploaded_at", "category", "uploaded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True,
    )
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

