"""User model — authentication and role-based access."""

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Index, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from marketpulse.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="retailer")
    token_version: Mapped[int] = mapped_column(nullable=False, default=1)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_org", "organization_id"),
    )
