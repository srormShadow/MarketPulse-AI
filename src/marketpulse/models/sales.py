"""Sales model for daily SKU sales records."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from marketpulse.db.base import Base


class Sales(Base):
    """Represents daily units sold for a SKU."""

    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("date", "sku_id", name="uq_sales_date_sku"),
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

    sku: Mapped["SKU"] = relationship("SKU", back_populates="sales")
