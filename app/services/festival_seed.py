"""Utility functions for seeding festival reference data."""

from datetime import date
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.festival import Festival

logger = logging.getLogger(__name__)


def seed_festivals_if_empty(db: Session) -> None:
    """Seed baseline Indian festival data if the festival table is empty."""

    count = db.scalar(select(func.count()).select_from(Festival))
    if count and count > 0:
        logger.info("Festival seed skipped; existing records found")
        return

    festivals = [
        Festival(festival_name="Diwali", date=date(2024, 11, 1), category="general", historical_uplift=0.30),
        Festival(festival_name="Pongal", date=date(2024, 1, 15), category="grocery", historical_uplift=0.22),
        Festival(festival_name="Christmas", date=date(2024, 12, 25), category="gifting", historical_uplift=0.18),
    ]
    db.add_all(festivals)
    db.commit()
    logger.info("Festival seed complete | records_inserted=%s", len(festivals))
