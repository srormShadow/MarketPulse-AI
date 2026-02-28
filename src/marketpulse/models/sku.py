"""SKU model for master product data."""

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from marketpulse.db.base import Base


class SKU(Base):
    """Represents a retail stock-keeping unit (SKU)."""

    __tablename__ = "skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    mrp: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    current_inventory: Mapped[int] = mapped_column(Integer, nullable=False)

    sales: Mapped[list["Sales"]] = relationship(
        "Sales",
        back_populates="sku",
        cascade="all, delete-orphan",
    )
