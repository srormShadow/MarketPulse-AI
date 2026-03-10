"""Sales model for daily SKU sales records."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from marketpulse.db.base import Base


class Sales(Base):
    """Represents daily units sold for a SKU."""

    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("date", "sku_id", name="uq_sales_date_sku"),
        Index("ix_sales_source", "data_source", "source_store_id"),
        Index("ix_sales_external_id", "external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    sku_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("skus.sku_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False)

    # Data provenance: "csv" (default) or "shopify"
    data_source: Mapped[str] = mapped_column(String(32), nullable=False, default="csv", server_default="csv")
    # Foreign key to shopify_stores.id (NULL for CSV uploads)
    source_store_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # External platform identifier for deduplication (e.g., Shopify order line item ID)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)

    sku: Mapped["SKU"] = relationship("SKU", back_populates="sales")
