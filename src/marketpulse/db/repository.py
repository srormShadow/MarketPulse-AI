"""Repository protocol and SQLite implementation.

All database access across services and routes goes through DataRepository.
Service code never imports SQLAlchemy or boto3 directly.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date as date_type, datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from marketpulse.models.forecast_cache import ForecastCache
from marketpulse.models.festival import Festival
from marketpulse.models.recommendation_log import RecommendationLog
from marketpulse.models.sales import Sales
from marketpulse.models.shopify_store import ShopifyStore
from marketpulse.models.shopify_webhook_event import ShopifyWebhookEvent
from marketpulse.models.sku import SKU
from marketpulse.models.upload_event import UploadEvent


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
    def get_cached_forecast(
        self,
        category: str,
        n_days: int,
        current_inventory: int,
        lead_time_days: int,
        supplier_pack_size: int = 1,
        max_age_seconds: int = 3600,
    ) -> dict[str, Any] | None: ...
    def get_category_last_upload_timestamp(self, category: str) -> datetime | None: ...

    # --- Shopify Stores ---
    def create_shopify_store(self, shop_domain: str, access_token: str, scope: str) -> dict[str, Any]: ...
    def get_shopify_store(self, store_id: int) -> dict[str, Any] | None: ...
    def get_shopify_store_by_domain(self, shop_domain: str) -> dict[str, Any] | None: ...
    def list_shopify_stores(self) -> list[dict[str, Any]]: ...
    def update_shopify_store_token(self, shop_domain: str, access_token: str, scope: str) -> None: ...
    def deactivate_shopify_store(self, shop_domain: str) -> None: ...
    def update_shopify_last_synced(self, store_id: int) -> None: ...
    def is_webhook_processed(self, shopify_webhook_id: str) -> bool: ...
    def record_webhook_event(self, shopify_webhook_id: str, topic: str, shop_domain: str) -> None: ...

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

    @staticmethod
    def _forecast_signature(
        n_days: int,
        current_inventory: int,
        lead_time_days: int,
        supplier_pack_size: int,
    ) -> str:
        raw = f"{n_days}|{current_inventory}|{lead_time_days}|{supplier_pack_size}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _legacy_forecast_signature(
        n_days: int,
        current_inventory: int,
        lead_time_days: int,
    ) -> str:
        raw = f"{n_days}|{current_inventory}|{lead_time_days}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # --- SKU / Inventory -------------------------------------------------

    def upsert_skus(self, records: list[dict]) -> int:
        stmt = sqlite_insert(SKU).values(records)
        update_set: dict[str, Any] = {
            "product_name": stmt.excluded.product_name,
            "category": stmt.excluded.category,
            "mrp": stmt.excluded.mrp,
            "cost": stmt.excluded.cost,
            "current_inventory": stmt.excluded.current_inventory,
            "data_source": stmt.excluded.data_source,
            "source_store_id": stmt.excluded.source_store_id,
            "external_id": stmt.excluded.external_id,
        }
        upsert = stmt.on_conflict_do_update(
            index_elements=[SKU.sku_id],
            set_=update_set,
        )
        self._db.execute(upsert)
        now_utc = datetime.now(timezone.utc)
        categories = {str(rec.get("category", "")).strip() for rec in records if rec.get("category")}
        if categories:
            self._db.add_all([UploadEvent(category=category, uploaded_at=now_utc) for category in categories])
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
            set_={
                "units_sold": stmt.excluded.units_sold,
                "data_source": stmt.excluded.data_source,
                "source_store_id": stmt.excluded.source_store_id,
                "external_id": stmt.excluded.external_id,
            },
        )
        self._db.execute(upsert)
        sku_ids = list({str(rec.get("sku_id", "")) for rec in records if rec.get("sku_id")})
        if sku_ids:
            categories = self._db.scalars(
                select(SKU.category).where(SKU.sku_id.in_(sku_ids)).distinct()
            ).all()
            now_utc = datetime.now(timezone.utc)
            self._db.add_all([UploadEvent(category=category, uploaded_at=now_utc) for category in categories])
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
        generated = generated_at.astimezone(timezone.utc) if generated_at.tzinfo else generated_at.replace(tzinfo=timezone.utc)
        self._db.add(
            RecommendationLog(
                category=category,
                timestamp=generated,
                risk_score=round(float(risk_score), 3),
                insight=insight,
            )
        )
        self._db.commit()

    def get_cached_recommendation(
        self,
        category: str,
        risk_score: float,
        max_age_seconds: int = 3600,
    ) -> dict[str, Any] | None:
        threshold = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        rounded_risk = round(float(risk_score), 3)
        row = self._db.scalars(
            select(RecommendationLog)
            .where(RecommendationLog.category == category)
            .where(RecommendationLog.risk_score == rounded_risk)
            .where(RecommendationLog.timestamp >= threshold)
            .order_by(RecommendationLog.timestamp.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        return {
            "category": row.category,
            "insight": row.insight,
            "generated_at": row.timestamp.astimezone(timezone.utc).isoformat(),
            "risk_score": float(row.risk_score),
        }

    def list_recent_recommendations(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._db.scalars(
            select(RecommendationLog)
            .order_by(RecommendationLog.timestamp.desc())
            .limit(max(1, int(limit)))
        ).all()
        return [
            {
                "category": row.category,
                "timestamp": row.timestamp.astimezone(timezone.utc).isoformat(),
                "risk_score": float(row.risk_score),
                "insight": row.insight,
            }
            for row in rows
        ]

    # --- Forecast Cache -------------------------------------------------

    def save_forecast_cache(self, category: str, payload: dict[str, Any], generated_at: datetime) -> None:
        generated = generated_at.astimezone(timezone.utc) if generated_at.tzinfo else generated_at.replace(tzinfo=timezone.utc)
        n_days = int(payload.get("n_days", 0))
        current_inventory = int(payload.get("current_inventory", 0))
        lead_time_days = int(payload.get("lead_time_days", 0))
        supplier_pack_size = int(payload.get("supplier_pack_size", 1))
        params_hash = self._forecast_signature(
            n_days=n_days,
            current_inventory=current_inventory,
            lead_time_days=lead_time_days,
            supplier_pack_size=supplier_pack_size,
        )
        self._db.add(
            ForecastCache(
                category=category,
                generated_at=generated,
                params_hash=params_hash,
                n_days=n_days,
                current_inventory=current_inventory,
                lead_time_days=lead_time_days,
                supplier_pack_size=supplier_pack_size,
                payload_json=json.dumps(payload, default=str),
            )
        )
        self._db.commit()

    def get_cached_forecast(
        self,
        category: str,
        n_days: int,
        current_inventory: int,
        lead_time_days: int,
        supplier_pack_size: int = 1,
        max_age_seconds: int = 3600,
    ) -> dict[str, Any] | None:
        threshold = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        params_hash = self._forecast_signature(
            n_days=n_days,
            current_inventory=current_inventory,
            lead_time_days=lead_time_days,
            supplier_pack_size=max(1, int(supplier_pack_size)),
        )
        acceptable_hashes = [params_hash]
        if max(1, int(supplier_pack_size)) == 1:
            acceptable_hashes.append(
                self._legacy_forecast_signature(
                    n_days=n_days,
                    current_inventory=current_inventory,
                    lead_time_days=lead_time_days,
                )
            )
        rows = self._db.scalars(
            select(ForecastCache)
            .where(ForecastCache.category == category)
            .where(ForecastCache.generated_at >= threshold)
            .where(ForecastCache.params_hash.in_(acceptable_hashes))
            .order_by(ForecastCache.generated_at.desc())
            .limit(25)
        ).all()
        for row in rows:
            try:
                payload = json.loads(row.payload_json)
            except json.JSONDecodeError:
                continue
            payload["generated_at"] = row.generated_at.astimezone(timezone.utc).isoformat()
            return payload
        return None

    def get_category_last_upload_timestamp(self, category: str) -> datetime | None:
        latest = self._db.scalar(
            select(func.max(UploadEvent.uploaded_at)).where(UploadEvent.category == category)
        )
        if latest is None:
            return None
        if latest.tzinfo:
            return latest.astimezone(timezone.utc)
        return latest.replace(tzinfo=timezone.utc)

    # --- Shopify Stores ---------------------------------------------------

    def _shopify_store_to_dict(self, store: ShopifyStore) -> dict[str, Any]:
        return {
            "id": store.id,
            "shop_domain": store.shop_domain,
            "scope": store.scope,
            "is_active": store.is_active,
            "installed_at": store.installed_at.astimezone(timezone.utc).isoformat() if store.installed_at else None,
            "last_synced_at": store.last_synced_at.astimezone(timezone.utc).isoformat() if store.last_synced_at else None,
        }

    def create_shopify_store(self, shop_domain: str, access_token: str, scope: str) -> dict[str, Any]:
        store = ShopifyStore(
            shop_domain=shop_domain,
            access_token=access_token,
            scope=scope,
            is_active=True,
            installed_at=datetime.now(timezone.utc),
        )
        self._db.add(store)
        self._db.commit()
        self._db.refresh(store)
        return self._shopify_store_to_dict(store)

    def get_shopify_store(self, store_id: int) -> dict[str, Any] | None:
        store = self._db.scalars(
            select(ShopifyStore).where(ShopifyStore.id == store_id)
        ).first()
        if store is None:
            return None
        return self._shopify_store_to_dict(store)

    def get_shopify_store_by_domain(self, shop_domain: str) -> dict[str, Any] | None:
        store = self._db.scalars(
            select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain)
        ).first()
        if store is None:
            return None
        result = self._shopify_store_to_dict(store)
        result["access_token"] = store.access_token
        return result

    def list_shopify_stores(self) -> list[dict[str, Any]]:
        stores = self._db.scalars(
            select(ShopifyStore).where(ShopifyStore.is_active == True).order_by(ShopifyStore.installed_at.desc())
        ).all()
        return [self._shopify_store_to_dict(s) for s in stores]

    def update_shopify_store_token(self, shop_domain: str, access_token: str, scope: str) -> None:
        store = self._db.scalars(
            select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain)
        ).first()
        if store:
            store.access_token = access_token
            store.scope = scope
            store.is_active = True
            store.uninstalled_at = None
            self._db.commit()

    def deactivate_shopify_store(self, shop_domain: str) -> None:
        store = self._db.scalars(
            select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain)
        ).first()
        if store:
            store.is_active = False
            store.uninstalled_at = datetime.now(timezone.utc)
            self._db.commit()

    def update_shopify_last_synced(self, store_id: int) -> None:
        store = self._db.scalars(
            select(ShopifyStore).where(ShopifyStore.id == store_id)
        ).first()
        if store:
            store.last_synced_at = datetime.now(timezone.utc)
            self._db.commit()

    def is_webhook_processed(self, shopify_webhook_id: str) -> bool:
        count = self._db.scalar(
            select(func.count())
            .select_from(ShopifyWebhookEvent)
            .where(ShopifyWebhookEvent.shopify_webhook_id == shopify_webhook_id)
        )
        return (count or 0) > 0

    def record_webhook_event(self, shopify_webhook_id: str, topic: str, shop_domain: str) -> None:
        self._db.add(
            ShopifyWebhookEvent(
                shopify_webhook_id=shopify_webhook_id,
                topic=topic,
                shop_domain=shop_domain,
                processed_at=datetime.now(timezone.utc),
            )
        )
        self._db.commit()

    # --- Transaction control ---------------------------------------------

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
