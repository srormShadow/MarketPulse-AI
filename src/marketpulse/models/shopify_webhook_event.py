"""SQLAlchemy model for idempotent Shopify webhook event tracking."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from marketpulse.db.base import Base


class ShopifyWebhookEvent(Base):
    """Tracks processed Shopify webhook events for idempotency."""

    __tablename__ = "shopify_webhook_events"
    __table_args__ = (
        Index("ix_webhook_events_shopify_id", "shopify_webhook_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shopify_webhook_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    shop_domain: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
