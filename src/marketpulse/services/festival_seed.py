"""Utility functions for seeding festival reference data."""

from __future__ import annotations

from datetime import date
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

logger = logging.getLogger(__name__)


def seed_festivals_if_empty(repo: DataRepository) -> None:
    """Seed baseline Indian festival data if the festival table is empty."""

    count = repo.count_festivals()
    if count and count > 0:
        logger.info("Festival seed skipped; existing records found")
        return

    festivals = [
        {"festival_name": "Diwali", "date": date(2024, 11, 1), "category": "general", "historical_uplift": 0.30},
        {"festival_name": "Pongal", "date": date(2024, 1, 15), "category": "grocery", "historical_uplift": 0.22},
        {"festival_name": "Christmas", "date": date(2024, 12, 25), "category": "gifting", "historical_uplift": 0.18},
    ]
    repo.seed_festivals(festivals)
    logger.info("Festival seed complete | records_inserted=%s", len(festivals))
