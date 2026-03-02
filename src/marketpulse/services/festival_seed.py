"""Utility functions for seeding festival reference data."""

from __future__ import annotations

from datetime import date
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

logger = logging.getLogger(__name__)

# 2026 Indian festival calendar with product-category granularity.
# ``category`` is stored as a comma-separated string so that each
# festival is a single row in both SQLite and DynamoDB.
# ``historical_uplift`` holds the demand multiplier (1.45 → +45%).
FESTIVALS_2026: list[dict] = [
    {"festival_name": "Holi", "date": date(2026, 3, 13), "category": "Snacks,Staples", "historical_uplift": 1.45},
    {"festival_name": "Eid ul-Fitr", "date": date(2026, 3, 31), "category": "Staples,Edible Oil", "historical_uplift": 1.35},
    {"festival_name": "Ram Navami", "date": date(2026, 4, 6), "category": "Staples", "historical_uplift": 1.20},
    {"festival_name": "Akshaya Tritiya", "date": date(2026, 4, 29), "category": "Snacks,Staples", "historical_uplift": 1.25},
    {"festival_name": "Eid ul-Adha", "date": date(2026, 6, 7), "category": "Staples,Edible Oil", "historical_uplift": 1.30},
    {"festival_name": "Independence Day", "date": date(2026, 8, 15), "category": "Snacks", "historical_uplift": 1.20},
    {"festival_name": "Raksha Bandhan", "date": date(2026, 8, 9), "category": "Snacks,Staples", "historical_uplift": 1.30},
    {"festival_name": "Janmashtami", "date": date(2026, 8, 16), "category": "Staples,Edible Oil", "historical_uplift": 1.25},
    {"festival_name": "Ganesh Chaturthi", "date": date(2026, 8, 27), "category": "Snacks,Staples", "historical_uplift": 1.40},
    {"festival_name": "Navratri", "date": date(2026, 9, 22), "category": "Staples,Edible Oil", "historical_uplift": 1.35},
    {"festival_name": "Dussehra", "date": date(2026, 10, 2), "category": "Snacks,Staples", "historical_uplift": 1.30},
    {"festival_name": "Dhanteras", "date": date(2026, 10, 20), "category": "Snacks,Staples,Edible Oil", "historical_uplift": 1.50},
    {"festival_name": "Diwali", "date": date(2026, 10, 21), "category": "Snacks,Staples,Edible Oil", "historical_uplift": 1.80},
    {"festival_name": "Bhai Dooj", "date": date(2026, 10, 23), "category": "Snacks", "historical_uplift": 1.20},
    {"festival_name": "Christmas", "date": date(2026, 12, 25), "category": "Snacks", "historical_uplift": 1.25},
]


def seed_festivals_if_empty(repo: DataRepository) -> None:
    """Seed baseline Indian festival data if the festival table is empty."""

    count = repo.count_festivals()
    if count and count > 0:
        logger.info("Festival seed skipped; existing records found")
        return

    repo.seed_festivals(FESTIVALS_2026)
    logger.info("Festival seed complete | records_inserted=%s", len(FESTIVALS_2026))


def reseed_festivals(repo: DataRepository) -> int:
    """Clear all existing festivals and reseed with the 2026 calendar."""
    repo.clear_festivals()
    repo.seed_festivals(FESTIVALS_2026)
    logger.info("Festival reseed complete | records_inserted=%s", len(FESTIVALS_2026))
    return len(FESTIVALS_2026)
