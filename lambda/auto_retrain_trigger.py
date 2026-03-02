"""
Lambda: auto_retrain_trigger

Triggers automatic model retraining when new CSV sales data is uploaded to S3.
Part of the MarketPulse AI event-driven ML retraining pipeline.

Trigger : S3 PUT event on 'marketpulse-data-uploads' bucket
Runtime : Python 3.11
Memory  : 128 MB
Timeout : 30 seconds
Region  : ap-south-1
"""

import json
import logging
import os
import urllib.parse

import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# API Gateway endpoint — set via Lambda environment variable
API_BASE_URL = os.environ.get("API_BASE_URL", "https://your-api-gateway-id.execute-api.ap-south-1.amazonaws.com")

# Mapping: lowercase filename prefix → canonical category name
CATEGORY_MAP = {
    "snacks": "Snacks",
    "staples": "Staples",
    "edible_oil": "Edible Oil",
    "edibleoil": "Edible Oil",
    "edible-oil": "Edible Oil",
}


def _extract_category(filename: str) -> str | None:
    """Derive the product category from the uploaded filename.

    Supports patterns like:
        snacks_sales.csv        → Snacks
        Staples_daily.csv       → Staples
        edible_oil_2024.csv     → Edible Oil
        edible-oil_upload.csv   → Edible Oil

    Returns None if no known category prefix is matched.
    """
    base = filename.rsplit("/", 1)[-1]          # strip any S3 key prefix
    base = base.lower().replace(".csv", "")     # normalize

    # Try longest prefixes first so "edible_oil" matches before "edible"
    for prefix in sorted(CATEGORY_MAP, key=len, reverse=True):
        if base.startswith(prefix):
            return CATEGORY_MAP[prefix]

    return None


def handler(event, context):
    """AWS Lambda entry point — invoked by S3 PUT event notification."""

    logger.info("Event received: %s", json.dumps(event, default=str))

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        size = record["s3"]["object"].get("size", 0)

        logger.info("New upload  bucket=%s  key=%s  size=%d bytes", bucket, key, size)

        # Skip non-CSV or zero-byte files
        if not key.lower().endswith(".csv"):
            logger.info("Skipping non-CSV file: %s", key)
            continue
        if size == 0:
            logger.info("Skipping zero-byte file: %s", key)
            continue

        # Extract category from filename
        category = _extract_category(key)
        if category is None:
            logger.warning(
                "Could not determine category from filename '%s'. "
                "Expected prefix: %s",
                key,
                ", ".join(sorted(CATEGORY_MAP)),
            )
            continue

        # Trigger retrain via API Gateway
        retrain_url = f"{API_BASE_URL.rstrip('/')}/retrain/{category}"
        logger.info("Triggering retrain  POST %s", retrain_url)

        try:
            resp = requests.post(retrain_url, timeout=25, json={
                "source_bucket": bucket,
                "source_key": key,
                "triggered_by": "s3_event",
            })
            resp.raise_for_status()

            logger.info(
                "Retrain succeeded  category=%s  status=%d  response=%s",
                category, resp.status_code, resp.text[:500],
            )

        except requests.exceptions.RequestException as exc:
            logger.error(
                "Retrain request failed  category=%s  url=%s  error=%s",
                category, retrain_url, exc,
            )

    return {"statusCode": 200, "body": "Processed"}
