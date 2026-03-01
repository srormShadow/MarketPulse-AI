"""Initialize local MarketPulse stack (DynamoDB Local + LocalStack S3)."""

from __future__ import annotations

import pathlib
import sys

import boto3
import pandas as pd

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from marketpulse.core.config import get_settings
from marketpulse.db.dynamo import ensure_tables_exist
from marketpulse.db.dynamo_repository import DynamoRepository
from marketpulse.services.festival_seed import seed_festivals_if_empty


def _ensure_s3_buckets() -> None:
    settings = get_settings()
    kwargs = {
        "region_name": settings.aws_region,
        "aws_access_key_id": settings.aws_access_key_id or "fake",
        "aws_secret_access_key": settings.aws_secret_access_key or "fake",
    }
    endpoint = settings.s3_endpoint_url or settings.s3_endpoint
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    client = boto3.client("s3", **kwargs)

    for bucket_name in (settings.s3_data_bucket, settings.s3_model_bucket):
        try:
            client.head_bucket(Bucket=bucket_name)
            print(f"[ok] S3 bucket already exists: {bucket_name}")
        except Exception:
            client.create_bucket(Bucket=bucket_name)
            print(f"[ok] Created S3 bucket: {bucket_name}")


def _load_demo_csvs(repo: DynamoRepository) -> None:
    sku_csv = PROJECT_ROOT / "data" / "demo_sku_master.csv"
    sales_csv = PROJECT_ROOT / "data" / "demo_sales_365.csv"

    sku_df = pd.read_csv(sku_csv)
    sku_df.columns = [c.strip().lower() for c in sku_df.columns]
    sku_records = sku_df[
        ["sku_id", "product_name", "category", "mrp", "cost", "current_inventory"]
    ].to_dict(orient="records")
    sku_inserted = repo.upsert_skus(sku_records)
    print(f"[ok] Upserted SKU records: {sku_inserted}")

    sales_df = pd.read_csv(sales_csv)
    sales_df.columns = [c.strip().lower() for c in sales_df.columns]
    sales_df["date"] = pd.to_datetime(sales_df["date"], errors="coerce").dt.date
    sales_df = sales_df.dropna(subset=["date", "sku_id", "units_sold"]).copy()
    sales_df["units_sold"] = pd.to_numeric(sales_df["units_sold"], errors="coerce").fillna(0).astype(int)
    sales_records = sales_df[["date", "sku_id", "units_sold"]].to_dict(orient="records")
    sales_inserted = repo.upsert_sales(sales_records)
    print(f"[ok] Upserted Sales records: {sales_inserted}")


def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    if not settings.use_dynamo:
        raise RuntimeError("USE_DYNAMO must be true for local AWS-like initialization.")

    print("[init] Ensuring DynamoDB tables...")
    ensure_tables_exist()
    repo = DynamoRepository()

    print("[init] Seeding festival reference data...")
    seed_festivals_if_empty(repo)

    print("[init] Creating local S3 buckets...")
    _ensure_s3_buckets()

    print("[init] Loading demo CSV data...")
    _load_demo_csvs(repo)

    print("[done] Local stack initialized successfully.")


if __name__ == "__main__":
    main()
