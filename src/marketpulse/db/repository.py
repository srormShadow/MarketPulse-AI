"""Repository protocol and SQLite implementation.

All database access across services and routes goes through DataRepository.
Service code never imports SQLAlchemy or boto3 directly.
"""

from __future__ import annotations

from datetime import date as date_type, datetime
from typing import Any, Protocol, runtime_checkable

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from marketpulse.models.festival import Festival
from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU


@runtime_checkable
class DataRepository(Protocol):
    """Abstract interface every backend must satisfy."""

    # --- SKU / Inventory ---
    def upsert_skus(self, records: list[dict]) -> int: ...
    def get_skus_for_category(self, category: str) -> list[dict]: ...
    def list_skus(self, limit: int, offset: int) -> tuple[int, list[dict]]: ...
    def sku_ids_exist(self, sku_ids: list[str]) -> set[str]: ...

    # --- Sales ---
    def upsert_sales(self, records: list[dict]) -> int: ...
    def count_sales(self) -> int: ...
    def get_category_daily_sales(self, category: str) -> pd.DataFrame: ...

    # --- Festivals ---
    def count_festivals(self) -> int: ...
    def clear_festivals(self) -> None: ...
    def seed_festivals(self, festivals: list[dict]) -> None: ...
    def get_all_festival_dates(self) -> list[tuple[str, Any]]: ...
    def list_all_festivals(self) -> list[dict]: ...

    # --- Insights / Recommendations ---
    def log_recommendation(self, category: str, risk_score: float, insight: str, generated_at: datetime) -> None: ...
    def get_cached_recommendation(self, category: str, risk_score: float, max_age_seconds: int = 3600) -> dict[str, Any] | None: ...
    def list_recent_recommendations(self, limit: int = 10) -> list[dict[str, Any]]: ...

    # --- Forecast Cache ---
    def save_forecast_cache(self, category: str, payload: dict[str, Any], generated_at: datetime) -> None: ...
    def get_cached_forecast(self, category: str, n_days: int, current_inventory: int, lead_time_days: int, max_age_seconds: int = 3600) -> dict[str, Any] | None: ...
    def get_category_last_upload_timestamp(self, category: str) -> datetime | None: ...

    # --- Transaction control ---
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


# -----------------------------------------------------------------------
# SQLite implementation — wraps a SQLAlchemy Session
# -----------------------------------------------------------------------


class SQLiteRepository:
    """Implements DataRepository by delegating to a SQLAlchemy Session."""

    def __init__(self, session: Session) -> None:
        self._db = session

    # --- SKU / Inventory -------------------------------------------------

    def upsert_skus(self, records: list[dict]) -> int:
        stmt = sqlite_insert(SKU).values(records)
        upsert = stmt.on_conflict_do_update(
            index_elements=[SKU.sku_id],
            set_={
                "product_name": stmt.excluded.product_name,
                "category": stmt.excluded.category,
                "mrp": stmt.excluded.mrp,
                "cost": stmt.excluded.cost,
                "current_inventory": stmt.excluded.current_inventory,
            },
        )
        self._db.execute(upsert)
        return len(records)

    def get_skus_for_category(self, category: str) -> list[dict]:
        rows = self._db.scalars(
            select(SKU).where(SKU.category == category)
        ).all()
        return [
            {
                "sku_id": r.sku_id,
                "product_name": r.product_name,
                "category": r.category,
                "mrp": r.mrp,
                "cost": r.cost,
                "current_inventory": r.current_inventory,
            }
            for r in rows
        ]

    def list_skus(self, limit: int, offset: int) -> tuple[int, list[dict]]:
        total = self._db.scalar(select(func.count()).select_from(SKU)) or 0
        rows = self._db.scalars(
            select(SKU).order_by(SKU.sku_id.asc()).offset(offset).limit(limit)
        ).all()
        items = [
            {
                "sku_id": r.sku_id,
                "product_name": r.product_name,
                "category": r.category,
                "mrp": r.mrp,
                "cost": r.cost,
                "current_inventory": r.current_inventory,
            }
            for r in rows
        ]
        return total, items

    def sku_ids_exist(self, sku_ids: list[str]) -> set[str]:
        rows = self._db.execute(
            select(SKU.sku_id).where(SKU.sku_id.in_(sku_ids))
        )
        return {row[0] for row in rows}

    # --- Sales -----------------------------------------------------------

    def upsert_sales(self, records: list[dict]) -> int:
        stmt = sqlite_insert(Sales).values(records)
        upsert = stmt.on_conflict_do_update(
            index_elements=[Sales.date, Sales.sku_id],
            set_={"units_sold": stmt.excluded.units_sold},
        )
        self._db.execute(upsert)
        return len(records)

    def count_sales(self) -> int:
        return self._db.scalar(select(func.count()).select_from(Sales)) or 0

    def get_category_daily_sales(self, category: str) -> pd.DataFrame:
        stmt = (
            select(Sales.date, func.sum(Sales.units_sold).label("units_sold"))
            .join(SKU, Sales.sku_id == SKU.sku_id)
            .where(SKU.category == category)
            .group_by(Sales.date)
            .order_by(Sales.date.asc())
        )
        rows = self._db.execute(stmt).all()
        frame = pd.DataFrame(rows, columns=["date", "units_sold"])
        if frame.empty:
            return pd.DataFrame(columns=["date", "units_sold"])
        frame["date"] = pd.to_datetime(frame["date"])
        frame["units_sold"] = pd.to_numeric(frame["units_sold"], errors="coerce")
        return frame.sort_values("date").reset_index(drop=True)

    # --- Festivals -------------------------------------------------------

    def count_festivals(self) -> int:
        return self._db.scalar(select(func.count()).select_from(Festival)) or 0

    def clear_festivals(self) -> None:
        self._db.query(Festival).delete()
        self._db.commit()

    def seed_festivals(self, festivals: list[dict]) -> None:
        objs = [Festival(**f) for f in festivals]
        self._db.add_all(objs)
        self._db.commit()

    def get_all_festival_dates(self) -> list[tuple[str, Any]]:
        rows = self._db.execute(
            select(Festival.festival_name, Festival.date)
        ).all()
        return [(str(r[0]), r[1]) for r in rows]

    def list_all_festivals(self) -> list[dict]:
        rows = self._db.scalars(
            select(Festival).order_by(Festival.date.asc())
        ).all()
        return [
            {
                "festival_name": r.festival_name,
                "date": r.date,
                "category": r.category,
                "historical_uplift": r.historical_uplift,
            }
            for r in rows
        ]

    # --- Insights / Recommendations ------------------------------------

    def log_recommendation(self, category: str, risk_score: float, insight: str, generated_at: datetime) -> None:
        # SQLite path currently does not persist recommendation logs.
        return None

    def get_cached_recommendation(
        self,
        category: str,
        risk_score: float,
        max_age_seconds: int = 3600,
    ) -> dict[str, Any] | None:
        # SQLite path currently does not persist recommendation logs.
        return None

    def list_recent_recommendations(self, limit: int = 10) -> list[dict[str, Any]]:
        # SQLite path currently does not persist recommendation logs.
        return []

    # --- Forecast Cache -------------------------------------------------

    def save_forecast_cache(self, category: str, payload: dict[str, Any], generated_at: datetime) -> None:
        # SQLite path currently does not persist forecast cache.
        return None

    def get_cached_forecast(
        self,
        category: str,
        n_days: int,
        current_inventory: int,
        lead_time_days: int,
        max_age_seconds: int = 3600,
    ) -> dict[str, Any] | None:
        # SQLite path currently does not persist forecast cache.
        return None

    def get_category_last_upload_timestamp(self, category: str) -> datetime | None:
        # SQLite path does not track last upload timestamp.
        return None

    # --- Transaction control ---------------------------------------------

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
