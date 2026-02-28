"""Festival model for category-level demand uplift signals."""

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from marketpulse.db.base import Base


class Festival(Base):
    """Represents a festival and its historical category uplift."""

    __tablename__ = "festivals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    festival_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    historical_uplift: Mapped[float] = mapped_column(Float, nullable=False)
