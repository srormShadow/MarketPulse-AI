"""Helper utilities for generating CSV payloads in tests."""

from __future__ import annotations


def build_sku_csv(rows: list[dict[str, object]], *, headers: list[str] | None = None) -> bytes:
    base_headers = headers or [
        "sku_id",
        "product_name",
        "category",
        "mrp",
        "cost",
        "current_inventory",
    ]
    lines = [",".join(base_headers)]
    for row in rows:
        values = [str(row.get(header.strip().lower(), row.get(header, ""))) for header in base_headers]
        lines.append(",".join(values))
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_sales_csv(rows: list[dict[str, object]], *, headers: list[str] | None = None) -> bytes:
    base_headers = headers or ["date", "sku_id", "units_sold"]
    lines = [",".join(base_headers)]
    for row in rows:
        values = [str(row.get(header.strip().lower(), row.get(header, ""))) for header in base_headers]
        lines.append(",".join(values))
    return ("\n".join(lines) + "\n").encode("utf-8")
