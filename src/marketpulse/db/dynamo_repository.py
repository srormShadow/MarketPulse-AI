"""DynamoDB implementation of the DataRepository protocol."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pandas as pd
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from marketpulse.db.dynamo import get_dynamo_resource

logger = logging.getLogger(__name__)


def _to_decimal(value: float | int) -> Decimal:
    """Convert a numeric value to Decimal for DynamoDB storage."""
    return Decimal(str(value))


def _forecast_signature(
    n_days: int,
    current_inventory: int,
    lead_time_days: int,
    supplier_pack_size: int = 1,
) -> str:
    raw = f"{n_days}|{current_inventory}|{lead_time_days}|{supplier_pack_size}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _legacy_forecast_signature(n_days: int, current_inventory: int, lead_time_days: int) -> str:
    raw = f"{n_days}|{current_inventory}|{lead_time_days}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DynamoRepository:
    """Implements DataRepository using boto3 DynamoDB Table operations."""

    def __init__(self) -> None:
        self._dynamo = get_dynamo_resource()

    def _table(self, name: str):
        return self._dynamo.Table(name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _scan_all(self, table_name: str, **kwargs) -> list[dict]:
        """Paginated scan that returns all items."""
        table = self._table(table_name)
        items: list[dict] = []
        response = table.scan(**kwargs)
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"], **kwargs
            )
            items.extend(response.get("Items", []))
        return items

    def _query_all(self, table_name: str, **kwargs) -> list[dict]:
        """Paginated query that returns all matching items."""
        table = self._table(table_name)
        items: list[dict] = []
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = table.query(
                ExclusiveStartKey=response["LastEvaluatedKey"], **kwargs
            )
            items.extend(response.get("Items", []))
        return items

    def _inventory_by_sku_ids(self, sku_ids: list[str], projection_expression: str | None = None) -> list[dict]:
        """Fetch inventory rows by sku_id using GSI when available."""
        if not sku_ids:
            return []
        table = self._table("marketpulse_inventory")
        rows: list[dict] = []
        for sku_id in set(sku_ids):
            kwargs: dict[str, Any] = {
                "IndexName": "sku_id-index",
                "KeyConditionExpression": Key("sku_id").eq(sku_id),
            }
            if projection_expression:
                kwargs["ProjectionExpression"] = projection_expression
            use_scan_fallback = False
            try:
                response = table.query(**kwargs)
            except ClientError as exc:
                error_code = str(exc.response.get("Error", {}).get("Code", ""))
                if error_code not in {"ValidationException", "ResourceNotFoundException"}:
                    raise
                # Fallback for environments where the GSI is not present yet.
                use_scan_fallback = True
                scan_kwargs: dict[str, Any] = {
                    "FilterExpression": Attr("sku_id").eq(sku_id),
                }
                if projection_expression:
                    scan_kwargs["ProjectionExpression"] = projection_expression
                response = table.scan(**scan_kwargs)
            rows.extend(response.get("Items", []))
            while "LastEvaluatedKey" in response:
                if use_scan_fallback:
                    scan_page_kwargs = {
                        "FilterExpression": Attr("sku_id").eq(sku_id),
                        "ExclusiveStartKey": response["LastEvaluatedKey"],
                    }
                    if projection_expression:
                        scan_page_kwargs["ProjectionExpression"] = projection_expression
                    response = table.scan(**scan_page_kwargs)
                else:
                    page_kwargs = dict(kwargs)
                    page_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                    response = table.query(**page_kwargs)
                rows.extend(response.get("Items", []))
        return rows

    # ------------------------------------------------------------------
    # SKU / Inventory
    # ------------------------------------------------------------------

    def upsert_skus(self, records: list[dict]) -> int:
        table = self._table("marketpulse_inventory")
        upload_ts = datetime.now(timezone.utc).isoformat()
        with table.batch_writer() as batch:
            for rec in records:
                batch.put_item(Item={
                    "category": rec["category"],
                    "sku_id": rec["sku_id"],
                    "product_name": rec["product_name"],
                    "mrp": _to_decimal(rec["mrp"]),
                    "cost": _to_decimal(rec["cost"]),
                    "current_inventory": int(rec["current_inventory"]),
                    "last_upload_timestamp": upload_ts,
                })
        return len(records)

    def get_skus_for_category(self, category: str) -> list[dict]:
        items = self._query_all(
            "marketpulse_inventory",
            KeyConditionExpression=Key("category").eq(category),
        )
        return [
            {
                "sku_id": it["sku_id"],
                "product_name": it["product_name"],
                "category": it["category"],
                "mrp": float(it["mrp"]),
                "cost": float(it["cost"]),
                "current_inventory": int(it["current_inventory"]),
            }
            for it in items
        ]

    def list_skus(self, limit: int, offset: int) -> tuple[int, list[dict]]:
        all_items = self._scan_all("marketpulse_inventory")
        all_items.sort(key=lambda x: x.get("sku_id", ""))
        total = len(all_items)
        page = all_items[offset: offset + limit]
        return total, [
            {
                "sku_id": it["sku_id"],
                "product_name": it["product_name"],
                "category": it["category"],
                "mrp": float(it["mrp"]),
                "cost": float(it["cost"]),
                "current_inventory": int(it["current_inventory"]),
            }
            for it in page
        ]

    def sku_ids_exist(self, sku_ids: list[str]) -> set[str]:
        rows = self._inventory_by_sku_ids(sku_ids, projection_expression="sku_id")
        return {str(row["sku_id"]) for row in rows if row.get("sku_id")}

    # ------------------------------------------------------------------
    # Sales
    # ------------------------------------------------------------------

    def upsert_sales(self, records: list[dict]) -> int:
        # Enrich records with category from inventory table
        sku_ids = list({r["sku_id"] for r in records})
        category_map = self._category_for_skus(sku_ids)

        table = self._table("marketpulse_sales")
        written = 0
        with table.batch_writer() as batch:
            for rec in records:
                cat = category_map.get(rec["sku_id"])
                if cat is None:
                    continue
                date_str = str(rec["date"])
                batch.put_item(Item={
                    "category": cat,
                    "date_sku": f"{date_str}#{rec['sku_id']}",
                    "date": date_str,
                    "sku_id": rec["sku_id"],
                    "units_sold": int(rec["units_sold"]),
                })
                written += 1
        if written > 0:
            affected_inventory_keys = {
                (cat, sku_id)
                for sku_id, cat in category_map.items()
            }
            self._touch_inventory_upload_timestamp(affected_inventory_keys)
        return written

    def _touch_inventory_upload_timestamp(self, inventory_keys: set[tuple[str, str]]) -> None:
        if not inventory_keys:
            return
        upload_ts = datetime.now(timezone.utc).isoformat()
        table = self._table("marketpulse_inventory")
        for category, sku_id in inventory_keys:
            table.update_item(
                Key={
                    "category": category,
                    "sku_id": sku_id,
                },
                UpdateExpression="SET last_upload_timestamp = :ts",
                ExpressionAttributeValues={":ts": upload_ts},
            )

    def _category_for_skus(self, sku_ids: list[str]) -> dict[str, str]:
        rows = self._inventory_by_sku_ids(sku_ids, projection_expression="sku_id, category")
        mapping: dict[str, str] = {}
        for row in rows:
            sku_id = str(row.get("sku_id", ""))
            category = str(row.get("category", ""))
            if sku_id and category:
                mapping[sku_id] = category
        return mapping

    def count_sales(self) -> int:
        table = self._table("marketpulse_sales")
        response = table.scan(Select="COUNT")
        count = response.get("Count", 0)
        while "LastEvaluatedKey" in response:
            response = table.scan(
                Select="COUNT",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            count += response.get("Count", 0)
        return count

    def get_category_daily_sales(self, category: str) -> pd.DataFrame:
        items = self._query_all(
            "marketpulse_sales",
            KeyConditionExpression=Key("category").eq(category),
        )
        if not items:
            return pd.DataFrame(columns=["date", "units_sold"])

        frame = pd.DataFrame(items)
        frame["units_sold"] = pd.to_numeric(frame["units_sold"], errors="coerce")
        frame["date"] = pd.to_datetime(frame["date"])
        aggregated = (
            frame.groupby("date", as_index=False)["units_sold"]
            .sum()
            .sort_values("date")
            .reset_index(drop=True)
        )
        return aggregated

    # ------------------------------------------------------------------
    # Festivals
    # ------------------------------------------------------------------

    def count_festivals(self) -> int:
        table = self._table("marketpulse_festivals")
        response = table.scan(Select="COUNT")
        count = response.get("Count", 0)
        while "LastEvaluatedKey" in response:
            response = table.scan(
                Select="COUNT",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            count += response.get("Count", 0)
        return count

    def clear_festivals(self) -> None:
        table = self._table("marketpulse_festivals")
        items = self._scan_all("marketpulse_festivals")
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={
                    "festival_name": item["festival_name"],
                    "date": item["date"],
                })

    def seed_festivals(self, festivals: list[dict]) -> None:
        # Merge per-category rows into one DynamoDB item per (festival_name, date)
        # because the table key is (festival_name HASH, date RANGE).
        merged: dict[tuple[str, str], dict] = {}
        for f in festivals:
            key = (f["festival_name"], str(f["date"]))
            if key not in merged:
                merged[key] = {
                    "festival_name": f["festival_name"],
                    "date": str(f["date"]),
                    "categories": [],
                    "category_uplifts": {},
                    "historical_uplift": 0.0,
                }
            entry = merged[key]
            cat = f["category"]
            uplift = float(f["historical_uplift"])
            if cat not in entry["category_uplifts"]:
                entry["categories"].append(cat)
            entry["category_uplifts"][cat] = uplift
            entry["historical_uplift"] = max(entry["historical_uplift"], uplift)

        table = self._table("marketpulse_festivals")
        with table.batch_writer() as batch:
            for item in merged.values():
                batch.put_item(Item={
                    "festival_name": item["festival_name"],
                    "date": item["date"],
                    "category": ",".join(item["categories"]),
                    "categories": item["categories"],
                    "category_uplifts": {k: _to_decimal(v) for k, v in item["category_uplifts"].items()},
                    "historical_uplift": _to_decimal(item["historical_uplift"]),
                })

    def get_all_festival_dates(self) -> list[tuple[str, Any]]:
        items = self._scan_all("marketpulse_festivals")
        return [
            (it["festival_name"], date_type.fromisoformat(it["date"]))
            for it in items
        ]

    def list_all_festivals(self) -> list[dict]:
        items = self._scan_all("marketpulse_festivals")
        items.sort(key=lambda x: x.get("date", ""))
        rows: list[dict] = []
        for it in items:
            cat_uplifts = it.get("category_uplifts")
            if cat_uplifts and isinstance(cat_uplifts, dict):
                # New format: one DynamoDB item with per-category uplift map.
                # Expand into one row per category for the route grouping logic.
                for cat, uplift in cat_uplifts.items():
                    rows.append({
                        "festival_name": it["festival_name"],
                        "date": date_type.fromisoformat(it["date"]),
                        "category": cat,
                        "historical_uplift": float(uplift),
                    })
            else:
                # Legacy format: comma-separated category, single uplift.
                rows.append({
                    "festival_name": it["festival_name"],
                    "date": date_type.fromisoformat(it["date"]),
                    "category": it.get("category", ""),
                    "historical_uplift": float(it.get("historical_uplift", 0)),
                })
        return rows

    # ------------------------------------------------------------------
    # Insights / Recommendations
    # ------------------------------------------------------------------

    def log_recommendation(self, category: str, risk_score: float, insight: str, generated_at: datetime) -> None:
        table = self._table("marketpulse_recommendations_log")
        timestamp = generated_at.astimezone(timezone.utc).isoformat()
        table.put_item(
            Item={
                "category": category,
                "timestamp": timestamp,
                "risk_score": _to_decimal(round(float(risk_score), 3)),
                "insight": insight,
            }
        )

    def get_cached_recommendation(
        self,
        category: str,
        risk_score: float,
        max_age_seconds: int = 3600,
    ) -> dict[str, Any] | None:
        table = self._table("marketpulse_recommendations_log")
        response = table.query(
            KeyConditionExpression=Key("category").eq(category),
            ScanIndexForward=False,
            Limit=25,
        )
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(seconds=max_age_seconds)
        target_risk = round(float(risk_score), 3)

        for item in response.get("Items", []):
            raw_timestamp = str(item.get("timestamp", ""))
            try:
                generated_at = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            if generated_at < threshold:
                continue

            stored_risk = round(float(item.get("risk_score", 0.0)), 3)
            if stored_risk != target_risk:
                continue

            return {
                "category": category,
                "insight": str(item.get("insight", "")),
                "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
                "risk_score": stored_risk,
            }

        return None

    def list_recent_recommendations(self, limit: int = 10) -> list[dict[str, Any]]:
        items = self._scan_all("marketpulse_recommendations_log")
        normalized: list[dict[str, Any]] = []
        for item in items:
            ts = str(item.get("timestamp", ""))
            category = str(item.get("category", "unknown"))
            insight = str(item.get("insight", ""))
            risk_score = float(item.get("risk_score", 0.0))
            normalized.append(
                {
                    "category": category,
                    "timestamp": ts,
                    "risk_score": risk_score,
                    "insight": insight,
                }
            )

        normalized.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return normalized[: max(1, int(limit))]

    # ------------------------------------------------------------------
    # Forecast Cache
    # ------------------------------------------------------------------

    def save_forecast_cache(self, category: str, payload: dict[str, Any], generated_at: datetime) -> None:
        table = self._table("marketpulse_forecasts")
        timestamp = generated_at.astimezone(timezone.utc).isoformat()
        n_days = int(payload.get("n_days", 0))
        current_inventory = int(payload.get("current_inventory", 0))
        lead_time_days = int(payload.get("lead_time_days", 0))
        supplier_pack_size = int(payload.get("supplier_pack_size", 1))

        table.put_item(
            Item={
                "category": category,
                "generated_at": timestamp,
                "params_hash": _forecast_signature(
                    n_days=n_days,
                    current_inventory=current_inventory,
                    lead_time_days=lead_time_days,
                    supplier_pack_size=supplier_pack_size,
                ),
                "n_days": n_days,
                "current_inventory": current_inventory,
                "lead_time_days": lead_time_days,
                "supplier_pack_size": supplier_pack_size,
                "payload_json": json.dumps(payload, default=str),
            }
        )

    def get_cached_forecast(
        self,
        category: str,
        n_days: int,
        current_inventory: int,
        lead_time_days: int,
        supplier_pack_size: int = 1,
        max_age_seconds: int = 3600,
    ) -> dict[str, Any] | None:
        table = self._table("marketpulse_forecasts")
        response = table.query(
            KeyConditionExpression=Key("category").eq(category),
            ScanIndexForward=False,
            Limit=25,
        )

        target_hash = _forecast_signature(
            n_days=n_days,
            current_inventory=current_inventory,
            lead_time_days=lead_time_days,
            supplier_pack_size=max(1, int(supplier_pack_size)),
        )
        acceptable_hashes = {target_hash}
        if max(1, int(supplier_pack_size)) == 1:
            acceptable_hashes.add(
                _legacy_forecast_signature(
                    n_days=n_days,
                    current_inventory=current_inventory,
                    lead_time_days=lead_time_days,
                )
            )
        threshold = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)

        for item in response.get("Items", []):
            params_hash = str(item.get("params_hash", ""))
            if params_hash not in acceptable_hashes:
                continue
            raw_ts = str(item.get("generated_at", ""))
            try:
                generated_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            if generated_at < threshold:
                continue
            payload_raw = item.get("payload_json")
            if payload_raw is None:
                continue
            try:
                payload = json.loads(str(payload_raw))
            except json.JSONDecodeError:
                continue
            payload["generated_at"] = generated_at.astimezone(timezone.utc).isoformat()
            return payload

        return None

    def get_category_last_upload_timestamp(self, category: str) -> datetime | None:
        items = self._query_all(
            "marketpulse_inventory",
            KeyConditionExpression=Key("category").eq(category),
            ProjectionExpression="last_upload_timestamp",
        )
        timestamps: list[datetime] = []
        for it in items:
            raw = it.get("last_upload_timestamp")
            if not raw:
                continue
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            timestamps.append(dt.astimezone(timezone.utc))

        if not timestamps:
            return None
        return max(timestamps)

    # ------------------------------------------------------------------
    # Transaction control (no-ops for DynamoDB)
    # ------------------------------------------------------------------

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass
