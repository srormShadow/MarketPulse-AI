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

from marketpulse.core.token_crypto import decrypt_token, encrypt_token
from marketpulse.models.forecast_cache import ForecastCache
from marketpulse.models.festival import Festival
from marketpulse.models.organization import Organization
from marketpulse.models.recommendation_log import RecommendationLog
from marketpulse.models.sales import Sales
from marketpulse.models.shopify_store import ShopifyStore
from marketpulse.models.shopify_webhook_event import ShopifyWebhookEvent
from marketpulse.models.sku import SKU
from marketpulse.models.upload_event import UploadEvent
from marketpulse.models.user import User


@runtime_checkable
class DataRepository(Protocol):
    """Abstract interface every backend must satisfy."""

    # --- Tenant scoping ---
    def with_organization(self, organization_id: int | None) -> "DataRepository": ...

    # --- SKU / Inventory ---
    def upsert_skus(self, records: list[dict]) -> int: ...
    def get_skus_for_category(self, category: str, organization_id: int | None = None) -> list[dict]: ...
    def list_skus(self, limit: int, offset: int, organization_id: int | None = None) -> tuple[int, list[dict]]: ...
    def sku_ids_exist(self, sku_ids: list[str]) -> set[str]: ...
    def list_categories(self, organization_id: int) -> list[dict]: ...
    def get_inventory_summary(self, organization_id: int) -> dict[str, Any]: ...

    # --- Sales ---
    def upsert_sales(self, records: list[dict]) -> int: ...
    def count_sales(self) -> int: ...
    def get_category_daily_sales(self, category: str, organization_id: int | None = None) -> pd.DataFrame: ...

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
    def save_forecast_cache(self, category: str, payload: dict[str, Any], generated_at: datetime, organization_id: int | None = None) -> None: ...
    def get_cached_forecast(
        self,
        category: str,
        n_days: int,
        current_inventory: int,
        lead_time_days: int,
        supplier_pack_size: int = 1,
        max_age_seconds: int = 3600,
        organization_id: int | None = None,
    ) -> dict[str, Any] | None: ...
    def get_category_last_upload_timestamp(self, category: str) -> datetime | None: ...

    # --- Shopify Stores ---
    def create_shopify_store(self, shop_domain: str, access_token: str, scope: str, organization_id: int | None = None) -> dict[str, Any]: ...
    def get_shopify_store(self, store_id: int) -> dict[str, Any] | None: ...
    def get_shopify_store_by_domain(self, shop_domain: str) -> dict[str, Any] | None: ...
    def list_shopify_stores(self, organization_id: int | None = None) -> list[dict[str, Any]]: ...
    def update_shopify_store_token(self, shop_domain: str, access_token: str, scope: str) -> None: ...
    def deactivate_shopify_store(self, shop_domain: str) -> None: ...
    def update_shopify_last_synced(self, store_id: int) -> None: ...
    def is_webhook_processed(self, shopify_webhook_id: str) -> bool: ...
    def record_webhook_event(self, shopify_webhook_id: str, topic: str, shop_domain: str) -> None: ...

    # --- Users ---
    def get_user_by_email(self, email: str) -> dict[str, Any] | None: ...
    def create_user(self, email: str, password_hash: str, role: str, organization_id: int | None = None) -> dict[str, Any]: ...
    def bump_user_token_version(self, user_id: int) -> int: ...
    def list_users(self) -> list[dict[str, Any]]: ...
    def count_users(self) -> int: ...

    # --- Organizations ---
    def create_organization(self, name: str, plan: str = "free") -> dict[str, Any]: ...
    def list_organizations(self) -> list[dict[str, Any]]: ...
    def count_organizations(self) -> int: ...

    # --- Transaction control ---
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


# -----------------------------------------------------------------------
# SQLite implementation — wraps a SQLAlchemy Session
# -----------------------------------------------------------------------


MAX_PAGE_SIZE = 1000
SQLITE_BULK_CHUNK_SIZE = 200


class SQLiteRepository:
    """Implements DataRepository by delegating to a SQLAlchemy Session."""

    def __init__(self, session: Session, organization_id: int | None = None) -> None:
        self._db = session
        self._organization_id = organization_id

    def with_organization(self, organization_id: int | None) -> "SQLiteRepository":
        return SQLiteRepository(self._db, organization_id=organization_id)

    def _effective_org_id(self, organization_id: int | None = None) -> int | None:
        return organization_id if organization_id is not None else self._organization_id

    def _apply_org_to_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        org_id = self._effective_org_id()
        if org_id is None:
            return records
        return [{**record, "organization_id": record.get("organization_id", org_id)} for record in records]

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

    @staticmethod
    def _chunk_records(records: list[dict[str, Any]], size: int = SQLITE_BULK_CHUNK_SIZE) -> list[list[dict[str, Any]]]:
        return [records[i:i + size] for i in range(0, len(records), size)]

    # --- SKU / Inventory -------------------------------------------------

    def upsert_skus(self, records: list[dict]) -> int:
        records = self._apply_org_to_records(records)
        for chunk in self._chunk_records(records):
            stmt = sqlite_insert(SKU).values(chunk)
            update_set: dict[str, Any] = {
                "product_name": stmt.excluded.product_name,
                "category": stmt.excluded.category,
                "mrp": stmt.excluded.mrp,
                "cost": stmt.excluded.cost,
                "current_inventory": stmt.excluded.current_inventory,
                "data_source": stmt.excluded.data_source,
                "source_store_id": stmt.excluded.source_store_id,
                "external_id": stmt.excluded.external_id,
                "organization_id": stmt.excluded.organization_id,
            }
            upsert = stmt.on_conflict_do_update(
                index_elements=[SKU.organization_id, SKU.sku_id],
                set_=update_set,
            )
            self._db.execute(upsert)
        now_utc = datetime.now(timezone.utc)
        org_id = self._effective_org_id(records[0].get("organization_id") if records else None)
        categories = {str(rec.get("category", "")).strip() for rec in records if rec.get("category")}
        if categories:
            self._db.add_all([
                UploadEvent(category=category, uploaded_at=now_utc, organization_id=org_id)
                for category in categories
            ])
        return len(records)

    def get_skus_for_category(self, category: str, organization_id: int | None = None) -> list[dict]:
        organization_id = self._effective_org_id(organization_id)
        stmt = select(SKU).where(SKU.category == category)
        if organization_id is not None:
            stmt = stmt.where(SKU.organization_id == organization_id)
        rows = self._db.scalars(stmt).all()
        return [
            {
                "sku_id": r.sku_id,
                "product_name": r.product_name,
                "category": r.category,
                "mrp": r.mrp,
                "cost": r.cost,
                "current_inventory": r.current_inventory,
                "organization_id": r.organization_id,
            }
            for r in rows
        ]

    def list_skus(self, limit: int, offset: int, organization_id: int | None = None) -> tuple[int, list[dict]]:
        organization_id = self._effective_org_id(organization_id)
        safe_limit = max(1, min(int(limit), MAX_PAGE_SIZE))
        safe_offset = max(0, int(offset))
        count_stmt = select(func.count()).select_from(SKU)
        list_stmt = select(SKU).order_by(SKU.sku_id.asc())
        if organization_id is not None:
            count_stmt = count_stmt.where(SKU.organization_id == organization_id)
            list_stmt = list_stmt.where(SKU.organization_id == organization_id)
        total = self._db.scalar(count_stmt) or 0
        rows = self._db.scalars(list_stmt.offset(safe_offset).limit(safe_limit)).all()
        items = [
            {
                "sku_id": r.sku_id,
                "product_name": r.product_name,
                "category": r.category,
                "mrp": r.mrp,
                "cost": r.cost,
                "current_inventory": r.current_inventory,
                "organization_id": r.organization_id,
            }
            for r in rows
        ]
        return total, items

    def sku_ids_exist(self, sku_ids: list[str]) -> set[str]:
        stmt = select(SKU.sku_id).where(SKU.sku_id.in_(sku_ids))
        if self._organization_id is not None:
            stmt = stmt.where(SKU.organization_id == self._organization_id)
        rows = self._db.execute(stmt)
        return {row[0] for row in rows}

    def list_categories(self, organization_id: int) -> list[dict]:
        """Return distinct categories with summary stats for an organization."""
        stmt = (
            select(
                SKU.category,
                func.count(SKU.id).label("sku_count"),
                func.sum(SKU.current_inventory).label("total_inventory"),
            )
            .where(SKU.organization_id == organization_id)
            .group_by(SKU.category)
            .order_by(SKU.category.asc())
        )
        rows = self._db.execute(stmt).all()
        return [
            {
                "category": row[0],
                "sku_count": int(row[1] or 0),
                "total_inventory": int(row[2] or 0),
            }
            for row in rows
        ]

    def get_inventory_summary(self, organization_id: int) -> dict[str, Any]:
        """Return per-category inventory and lead time defaults for an organization."""
        categories = self.list_categories(organization_id)
        inventory: dict[str, int] = {}
        lead_times: dict[str, int] = {}
        for cat in categories:
            name = cat["category"]
            inventory[name] = cat["total_inventory"]
            lead_times[name] = 7  # default; will be user-configurable later
        return {
            "categories": [c["category"] for c in categories],
            "inventory": inventory,
            "lead_times": lead_times,
        }

    # --- Sales -----------------------------------------------------------

    def upsert_sales(self, records: list[dict]) -> int:
        records = self._apply_org_to_records(records)
        for chunk in self._chunk_records(records):
            stmt = sqlite_insert(Sales).values(chunk)
            upsert = stmt.on_conflict_do_update(
                index_elements=[Sales.organization_id, Sales.date, Sales.sku_id],
                set_={
                    "units_sold": stmt.excluded.units_sold,
                    "data_source": stmt.excluded.data_source,
                    "source_store_id": stmt.excluded.source_store_id,
                    "external_id": stmt.excluded.external_id,
                    "organization_id": stmt.excluded.organization_id,
                },
            )
            self._db.execute(upsert)
        org_id = self._effective_org_id(records[0].get("organization_id") if records else None)
        sku_ids = list({str(rec.get("sku_id", "")) for rec in records if rec.get("sku_id")})
        if sku_ids:
            stmt = select(SKU.category).where(SKU.sku_id.in_(sku_ids)).distinct()
            if org_id is not None:
                stmt = stmt.where(SKU.organization_id == org_id)
            categories = self._db.scalars(stmt).all()
            now_utc = datetime.now(timezone.utc)
            self._db.add_all([
                UploadEvent(category=category, uploaded_at=now_utc, organization_id=org_id)
                for category in categories
            ])
        return len(records)

    def count_sales(self) -> int:
        stmt = select(func.count()).select_from(Sales)
        if self._organization_id is not None:
            stmt = stmt.where(Sales.organization_id == self._organization_id)
        return self._db.scalar(stmt) or 0

    def get_category_daily_sales(self, category: str, organization_id: int | None = None) -> pd.DataFrame:
        organization_id = self._effective_org_id(organization_id)
        stmt = (
            select(Sales.date, func.sum(Sales.units_sold).label("units_sold"))
            .join(
                SKU,
                (Sales.sku_id == SKU.sku_id)
                & (
                    (Sales.organization_id == SKU.organization_id)
                    | ((Sales.organization_id.is_(None)) & (SKU.organization_id.is_(None)))
                ),
            )
            .where(SKU.category == category)
        )
        if organization_id is not None:
            stmt = stmt.where(SKU.organization_id == organization_id)
        stmt = stmt.group_by(Sales.date).order_by(Sales.date.asc())
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
                organization_id=self._organization_id,
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
        stmt = (
            select(RecommendationLog)
            .where(RecommendationLog.category == category)
            .where(RecommendationLog.risk_score == rounded_risk)
            .where(RecommendationLog.timestamp >= threshold)
        )
        if self._organization_id is not None:
            stmt = stmt.where(RecommendationLog.organization_id == self._organization_id)
        row = self._db.scalars(stmt.order_by(RecommendationLog.timestamp.desc()).limit(1)).first()
        if row is None:
            return None
        return {
            "category": row.category,
            "insight": row.insight,
            "generated_at": row.timestamp.astimezone(timezone.utc).isoformat(),
            "risk_score": float(row.risk_score),
        }

    def list_recent_recommendations(self, limit: int = 10) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), MAX_PAGE_SIZE))
        stmt = select(RecommendationLog)
        if self._organization_id is not None:
            stmt = stmt.where(RecommendationLog.organization_id == self._organization_id)
        rows = self._db.scalars(stmt.order_by(RecommendationLog.timestamp.desc()).limit(safe_limit)).all()
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

    def save_forecast_cache(self, category: str, payload: dict[str, Any], generated_at: datetime, organization_id: int | None = None) -> None:
        organization_id = self._effective_org_id(organization_id)
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
                organization_id=organization_id,
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
        organization_id: int | None = None,
    ) -> dict[str, Any] | None:
        organization_id = self._effective_org_id(organization_id)
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
        stmt = (
            select(ForecastCache)
            .where(ForecastCache.category == category)
            .where(ForecastCache.generated_at >= threshold)
            .where(ForecastCache.params_hash.in_(acceptable_hashes))
        )
        if organization_id is not None:
            stmt = stmt.where(ForecastCache.organization_id == organization_id)
        rows = self._db.scalars(
            stmt.order_by(ForecastCache.generated_at.desc()).limit(25)
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
        stmt = select(func.max(UploadEvent.uploaded_at)).where(UploadEvent.category == category)
        if self._organization_id is not None:
            stmt = stmt.where(UploadEvent.organization_id == self._organization_id)
        latest = self._db.scalar(stmt)
        if latest is None:
            return None
        if latest.tzinfo:
            return latest.astimezone(timezone.utc)
        return latest.replace(tzinfo=timezone.utc)

    # --- Shopify Stores ---------------------------------------------------

    def _shopify_store_to_dict(self, store: ShopifyStore) -> dict[str, Any]:
        return {
            "id": store.id,
            "organization_id": store.organization_id,
            "shop_domain": store.shop_domain,
            "scope": store.scope,
            "is_active": store.is_active,
            "installed_at": store.installed_at.astimezone(timezone.utc).isoformat() if store.installed_at else None,
            "last_synced_at": store.last_synced_at.astimezone(timezone.utc).isoformat() if store.last_synced_at else None,
        }

    def create_shopify_store(self, shop_domain: str, access_token: str, scope: str, organization_id: int | None = None) -> dict[str, Any]:
        store = ShopifyStore(
            shop_domain=shop_domain,
            access_token=encrypt_token(access_token),
            scope=scope,
            is_active=True,
            installed_at=datetime.now(timezone.utc),
            organization_id=organization_id,
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
        result["access_token"] = decrypt_token(store.access_token)
        return result

    def list_shopify_stores(self, organization_id: int | None = None) -> list[dict[str, Any]]:
        stmt = select(ShopifyStore).where(ShopifyStore.is_active == True)
        if organization_id is not None:
            stmt = stmt.where(ShopifyStore.organization_id == organization_id)
        stores = self._db.scalars(stmt.order_by(ShopifyStore.installed_at.desc())).all()
        return [self._shopify_store_to_dict(s) for s in stores]

    def update_shopify_store_token(self, shop_domain: str, access_token: str, scope: str) -> None:
        store = self._db.scalars(
            select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain)
        ).first()
        if store:
            store.access_token = encrypt_token(access_token)
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
        stmt = sqlite_insert(ShopifyWebhookEvent).values(
            shopify_webhook_id=shopify_webhook_id,
            topic=topic,
            shop_domain=shop_domain,
            processed_at=datetime.now(timezone.utc),
        )
        upsert = stmt.on_conflict_do_nothing(index_elements=[ShopifyWebhookEvent.shopify_webhook_id])
        self._db.execute(upsert)
        self._db.commit()

    def upsert_shopify_store(self, shop_domain: str, access_token: str, scope: str, organization_id: int | None = None) -> dict[str, Any]:
        """Atomically create or update a Shopify store record by domain."""
        stmt = sqlite_insert(ShopifyStore).values(
            shop_domain=shop_domain,
            access_token=encrypt_token(access_token),
            scope=scope,
            is_active=True,
            installed_at=datetime.now(timezone.utc),
            organization_id=organization_id,
        )
        update_set: dict[str, Any] = {
            "access_token": stmt.excluded.access_token,
            "scope": stmt.excluded.scope,
            "is_active": True,
            "uninstalled_at": None,
        }
        if organization_id is not None:
            update_set["organization_id"] = organization_id
        upsert = stmt.on_conflict_do_update(
            index_elements=[ShopifyStore.shop_domain],
            set_=update_set,
        )
        self._db.execute(upsert)
        self._db.commit()
        store = self._db.scalars(
            select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain)
        ).first()
        if not store:
            return {"shop_domain": shop_domain}
        return self._shopify_store_to_dict(store)

    # --- Users ------------------------------------------------------------

    @staticmethod
    def _user_to_dict(user: User) -> dict[str, Any]:
        return {
            "id": user.id,
            "email": user.email,
            "password_hash": user.password_hash,
            "role": user.role,
            "token_version": user.token_version,
            "organization_id": user.organization_id,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        row = self._db.scalars(
            select(User).where(User.email == email)
        ).first()
        return self._user_to_dict(row) if row else None

    def create_user(self, email: str, password_hash: str, role: str, organization_id: int | None = None) -> dict[str, Any]:
        user = User(
            email=email,
            password_hash=password_hash,
            role=role,
            organization_id=organization_id,
        )
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return self._user_to_dict(user)

    def bump_user_token_version(self, user_id: int) -> int:
        user = self._db.scalars(select(User).where(User.id == user_id)).first()
        if not user:
            return 0
        user.token_version = int(user.token_version or 0) + 1
        self._db.commit()
        return int(user.token_version)

    def list_users(self) -> list[dict[str, Any]]:
        rows = self._db.scalars(select(User).order_by(User.id.asc())).all()
        return [self._user_to_dict(u) for u in rows]

    def count_users(self) -> int:
        return self._db.scalar(select(func.count()).select_from(User)) or 0

    # --- Organizations ----------------------------------------------------

    @staticmethod
    def _org_to_dict(org: Organization) -> dict[str, Any]:
        return {
            "id": org.id,
            "name": org.name,
            "plan": org.plan,
            "created_at": org.created_at.isoformat() if org.created_at else None,
        }

    def create_organization(self, name: str, plan: str = "free") -> dict[str, Any]:
        org = Organization(name=name, plan=plan)
        self._db.add(org)
        self._db.commit()
        self._db.refresh(org)
        return self._org_to_dict(org)

    def list_organizations(self) -> list[dict[str, Any]]:
        rows = self._db.scalars(select(Organization).order_by(Organization.id.asc())).all()
        return [self._org_to_dict(o) for o in rows]

    def count_organizations(self) -> int:
        return self._db.scalar(select(func.count()).select_from(Organization)) or 0

    # --- Transaction control ---------------------------------------------

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
