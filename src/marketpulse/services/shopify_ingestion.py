"""Shopify data ingestion service.

Maps Shopify products to SKU records and Shopify orders to Sales records,
then persists them through the existing DataRepository interface.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import httpx

from marketpulse.core.config import get_settings

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

logger = logging.getLogger(__name__)


def _shopify_headers(access_token: str) -> dict[str, str]:
    return {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }


def _shopify_api_url(shop_domain: str, endpoint: str) -> str:
    clean_domain = shop_domain.strip().rstrip("/")
    api_version = get_settings().shopify_api_version
    return f"https://{clean_domain}/admin/api/{api_version}/{endpoint}"


def _sanitize_text(value: str) -> str:
    """Clean hidden characters and normalize whitespace."""
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f\u200b-\u200f\ufeff]", "", value)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_next_page_url(link_header: str | None) -> str | None:
    """Extract the next page URL from Shopify's Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


def _generate_sku_id(product: dict, variant: dict) -> str:
    """Generate a deterministic sku_id from Shopify product/variant data."""
    shopify_sku = str(variant.get("sku", "")).strip()
    if shopify_sku:
        return f"SHOP-{shopify_sku}".upper()
    return f"SHOP-{variant.get('id', 'UNKNOWN')}".upper()


def _map_product_type_to_category(product_type: str) -> str:
    """Map Shopify product_type to a normalized category name."""
    normalized = _sanitize_text(product_type).title() if product_type else "General"
    return normalized or "General"


def fetch_products(
    shop_domain: str,
    access_token: str,
) -> list[dict[str, Any]]:
    """Fetch all products from a Shopify store using cursor-based pagination."""
    products: list[dict[str, Any]] = []
    url: str | None = _shopify_api_url(shop_domain, "products.json?limit=250&status=active")

    timeout = get_settings().shopify_api_timeout
    with httpx.Client(timeout=timeout) as client:
        while url:
            response = client.get(url, headers=_shopify_headers(access_token))
            response.raise_for_status()
            data = response.json()
            products.extend(data.get("products", []))
            url = _extract_next_page_url(response.headers.get("Link"))

    logger.info("Fetched %d products from %s", len(products), shop_domain)
    return products


def fetch_orders(
    shop_domain: str,
    access_token: str,
    days_back: int = 90,
) -> list[dict[str, Any]]:
    """Fetch fulfilled orders from a Shopify store."""
    orders: list[dict[str, Any]] = []
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    url: str | None = _shopify_api_url(
        shop_domain,
        f"orders.json?limit=250&status=any&financial_status=paid&created_at_min={since}",
    )

    timeout = get_settings().shopify_api_timeout
    with httpx.Client(timeout=timeout) as client:
        while url:
            response = client.get(url, headers=_shopify_headers(access_token))
            response.raise_for_status()
            data = response.json()
            orders.extend(data.get("orders", []))
            url = _extract_next_page_url(response.headers.get("Link"))

    logger.info("Fetched %d orders from %s (last %d days)", len(orders), shop_domain, days_back)
    return orders


def sync_products_to_skus(
    repo: DataRepository,
    store_id: int,
    products: list[dict[str, Any]],
) -> int:
    """Convert Shopify products into SKU records and upsert them.

    Each Shopify product variant becomes a separate SKU record.
    """
    records: list[dict[str, Any]] = []

    for product in products:
        product_type = str(product.get("product_type", "") or "")
        category = _map_product_type_to_category(product_type)
        product_title = _sanitize_text(str(product.get("title", "Unknown Product")))

        settings = get_settings()
        for variant in product.get("variants", []):
            sku_id = _generate_sku_id(product, variant)
            price = float(variant.get("price", 0) or 0)
            compare_at_price = float(variant.get("compare_at_price") or price or 0)
            mrp = max(price, compare_at_price) if compare_at_price else price
            cost = float(variant.get("cost", 0) or 0) or price * settings.shopify_default_cost_ratio

            variant_title = str(variant.get("title", "")).strip()
            full_name = f"{product_title} - {variant_title}" if variant_title and variant_title != "Default Title" else product_title

            inventory_quantity = max(0, int(variant.get("inventory_quantity", 0) or 0))

            records.append({
                "sku_id": sku_id,
                "product_name": full_name[:255],
                "category": category[:100],
                "mrp": round(mrp, 2),
                "cost": round(min(cost, mrp * settings.shopify_max_cost_ratio), 2),
                "current_inventory": inventory_quantity,
                "data_source": "shopify",
                "source_store_id": store_id,
                "external_id": str(variant.get("id", "")),
            })

    if not records:
        return 0

    # Deduplicate by sku_id, keeping last occurrence
    seen: dict[str, int] = {}
    for idx, rec in enumerate(records):
        seen[rec["sku_id"]] = idx
    deduped = [records[i] for i in sorted(seen.values())]

    repo.upsert_skus(deduped)
    repo.commit()
    logger.info("Synced %d SKUs from Shopify store_id=%d", len(deduped), store_id)
    return len(deduped)


def sync_orders_to_sales(
    repo: DataRepository,
    store_id: int,
    orders: list[dict[str, Any]],
) -> int:
    """Convert Shopify orders into daily Sales records and upsert them.

    Each order line item contributes to a (date, sku_id) sales aggregate.
    """
    # Aggregate sales by (date, sku_id)
    aggregated: dict[tuple[str, str], int] = {}

    for order in orders:
        created_at = str(order.get("created_at", ""))
        if not created_at:
            continue
        try:
            order_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
        except ValueError:
            continue

        date_str = order_date.isoformat()

        for item in order.get("line_items", []):
            variant_id = str(item.get("variant_id", ""))
            shopify_sku = str(item.get("sku", "")).strip()
            quantity = int(item.get("quantity", 0) or 0)

            if quantity <= 0:
                continue

            # Generate the same sku_id used during product sync
            if shopify_sku:
                sku_id = f"SHOP-{shopify_sku}".upper()
            elif variant_id:
                sku_id = f"SHOP-{variant_id}".upper()
            else:
                continue

            key = (date_str, sku_id)
            aggregated[key] = aggregated.get(key, 0) + quantity

    if not aggregated:
        return 0

    # Filter to only SKUs that exist in the database
    all_sku_ids = list({sku_id for _, sku_id in aggregated})
    existing_skus = repo.sku_ids_exist(all_sku_ids)

    records: list[dict[str, Any]] = []
    for (date_str, sku_id), units in aggregated.items():
        if sku_id not in existing_skus:
            continue
        records.append({
            "date": date_str,
            "sku_id": sku_id,
            "units_sold": units,
            "data_source": "shopify",
            "source_store_id": store_id,
            "external_id": f"{date_str}#{sku_id}",
        })

    if not records:
        logger.warning("No matching SKUs found for Shopify orders (store_id=%d)", store_id)
        return 0

    repo.upsert_sales(records)
    repo.commit()
    logger.info("Synced %d sales records from Shopify orders (store_id=%d)", len(records), store_id)
    return len(records)


def run_full_sync(
    repo: DataRepository,
    store_id: int,
    shop_domain: str,
    access_token: str,
    sync_products: bool = True,
    sync_orders: bool = True,
    orders_days_back: int = 90,
) -> dict[str, int]:
    """Run a full sync of products and orders from a Shopify store."""
    result = {
        "products_synced": 0,
        "orders_synced": 0,
        "skus_created": 0,
        "sales_records_created": 0,
    }

    if sync_products:
        products = fetch_products(shop_domain, access_token)
        result["products_synced"] = len(products)
        result["skus_created"] = sync_products_to_skus(repo, store_id, products)

    if sync_orders:
        orders = fetch_orders(shop_domain, access_token, days_back=orders_days_back)
        result["orders_synced"] = len(orders)
        result["sales_records_created"] = sync_orders_to_sales(repo, store_id, orders)

    repo.update_shopify_last_synced(store_id)
    return result
