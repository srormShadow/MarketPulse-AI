"""SKU model for master product data."""

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from marketpulse.db.base import Base


class SKU(Base):
    """Represents a retail stock-keeping unit (SKU)."""

    __tablename__ = "skus"
    __table_args__ = (
        Index("ix_skus_source", "data_source", "source_store_id"),
        Index("ix_skus_external_id", "external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    mrp: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    current_inventory: Mapped[int] = mapped_column(Integer, nullable=False)

    # Data provenance: "csv" (default) or "shopify"
    data_source: Mapped[str] = mapped_column(String(32), nullable=False, default="csv", server_default="csv")
    # Foreign key to shopify_stores.id (NULL for CSV uploads)
    source_store_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # External platform identifier for deduplication (e.g., Shopify product ID)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)

    sales: Mapped[list["Sales"]] = relationship(
        "Sales",
        back_populates="sku",
        cascade="all, delete-orphan",
    )
