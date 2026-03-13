"""SKU model for master product data."""

from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from marketpulse.db.base import Base


class SKU(Base):
    """Represents a retail stock-keeping unit (SKU)."""

    __tablename__ = "skus"
    __table_args__ = (
        UniqueConstraint("organization_id", "sku_id", name="uq_skus_org_sku"),
        Index("ix_skus_source", "data_source", "source_store_id"),
        Index("ix_skus_external_id", "external_id"),
        Index("ix_skus_org_category", "organization_id", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    mrp: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    current_inventory: Mapped[int] = mapped_column(Integer, nullable=False)

    # Multi-tenant: every SKU belongs to an organization
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True,
    )

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
