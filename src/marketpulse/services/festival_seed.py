"""Utility functions for seeding festival reference data."""

from __future__ import annotations

from datetime import date
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

logger = logging.getLogger(__name__)

# 2026 Indian festival calendar — one row per festival×category pair
# so each category gets a distinct ``historical_uplift`` value.
# ``historical_uplift`` is the fractional demand increase (0.55 → +55%).
FESTIVALS_2026: list[dict] = [
    # Holi — Snacks dominate (colors, parties), Staples moderate
    {"festival_name": "Holi", "date": date(2026, 3, 13), "category": "Snacks", "historical_uplift": 0.55},
    {"festival_name": "Holi", "date": date(2026, 3, 13), "category": "Staples", "historical_uplift": 0.20},
    # Eid ul-Fitr — Staples & Oil for feasting
    {"festival_name": "Eid ul-Fitr", "date": date(2026, 3, 31), "category": "Staples", "historical_uplift": 0.48},
    {"festival_name": "Eid ul-Fitr", "date": date(2026, 3, 31), "category": "Edible Oil", "historical_uplift": 0.40},
    # Ram Navami — mostly Staples
    {"festival_name": "Ram Navami", "date": date(2026, 4, 6), "category": "Staples", "historical_uplift": 0.22},
    # Akshaya Tritiya — Snacks for gifting, Staples moderate
    {"festival_name": "Akshaya Tritiya", "date": date(2026, 4, 29), "category": "Snacks", "historical_uplift": 0.30},
    {"festival_name": "Akshaya Tritiya", "date": date(2026, 4, 29), "category": "Staples", "historical_uplift": 0.18},
    # Eid ul-Adha — heavy on Staples and Oil
    {"festival_name": "Eid ul-Adha", "date": date(2026, 6, 7), "category": "Staples", "historical_uplift": 0.42},
    {"festival_name": "Eid ul-Adha", "date": date(2026, 6, 7), "category": "Edible Oil", "historical_uplift": 0.35},
    # Independence Day — Snacks for celebrations
    {"festival_name": "Independence Day", "date": date(2026, 8, 15), "category": "Snacks", "historical_uplift": 0.25},
    # Raksha Bandhan — Snacks for gifting, Staples modest
    {"festival_name": "Raksha Bandhan", "date": date(2026, 8, 9), "category": "Snacks", "historical_uplift": 0.40},
    {"festival_name": "Raksha Bandhan", "date": date(2026, 8, 9), "category": "Staples", "historical_uplift": 0.15},
    # Janmashtami — Staples and Oil for prasad
    {"festival_name": "Janmashtami", "date": date(2026, 8, 16), "category": "Staples", "historical_uplift": 0.28},
    {"festival_name": "Janmashtami", "date": date(2026, 8, 16), "category": "Edible Oil", "historical_uplift": 0.20},
    # Ganesh Chaturthi — Snacks dominate (modak, sweets), Staples moderate
    {"festival_name": "Ganesh Chaturthi", "date": date(2026, 8, 27), "category": "Snacks", "historical_uplift": 0.50},
    {"festival_name": "Ganesh Chaturthi", "date": date(2026, 8, 27), "category": "Staples", "historical_uplift": 0.25},
    # Navratri — Staples for fasting, Oil for cooking
    {"festival_name": "Navratri", "date": date(2026, 9, 22), "category": "Staples", "historical_uplift": 0.38},
    {"festival_name": "Navratri", "date": date(2026, 9, 22), "category": "Edible Oil", "historical_uplift": 0.28},
    # Dussehra — Snacks for celebrations, Staples moderate
    {"festival_name": "Dussehra", "date": date(2026, 10, 2), "category": "Snacks", "historical_uplift": 0.35},
    {"festival_name": "Dussehra", "date": date(2026, 10, 2), "category": "Staples", "historical_uplift": 0.22},
    # Dhanteras — all categories spike (shopping season starts)
    {"festival_name": "Dhanteras", "date": date(2026, 10, 20), "category": "Snacks", "historical_uplift": 0.45},
    {"festival_name": "Dhanteras", "date": date(2026, 10, 20), "category": "Staples", "historical_uplift": 0.30},
    {"festival_name": "Dhanteras", "date": date(2026, 10, 20), "category": "Edible Oil", "historical_uplift": 0.35},
    # Diwali — peak festival, all categories, Snacks highest
    {"festival_name": "Diwali", "date": date(2026, 10, 21), "category": "Snacks", "historical_uplift": 0.80},
    {"festival_name": "Diwali", "date": date(2026, 10, 21), "category": "Staples", "historical_uplift": 0.50},
    {"festival_name": "Diwali", "date": date(2026, 10, 21), "category": "Edible Oil", "historical_uplift": 0.60},
    # Bhai Dooj — Snacks for gifting
    {"festival_name": "Bhai Dooj", "date": date(2026, 10, 23), "category": "Snacks", "historical_uplift": 0.22},
    # Christmas — Snacks dominate
    {"festival_name": "Christmas", "date": date(2026, 12, 25), "category": "Snacks", "historical_uplift": 0.30},
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
