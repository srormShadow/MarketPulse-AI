"""DynamoDB client setup and table management."""

from __future__ import annotations

import logging

import boto3

from marketpulse.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table schemas — PAY_PER_REQUEST (on-demand) billing, no provisioned capacity.
# ---------------------------------------------------------------------------

TABLES: dict[str, dict] = {
    "marketpulse_inventory": {
        "KeySchema": [
            {"AttributeName": "category", "KeyType": "HASH"},
            {"AttributeName": "sku_id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "category", "AttributeType": "S"},
            {"AttributeName": "sku_id", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    "marketpulse_sales": {
        "KeySchema": [
            {"AttributeName": "category", "KeyType": "HASH"},
            {"AttributeName": "date_sku", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "category", "AttributeType": "S"},
            {"AttributeName": "date_sku", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    "marketpulse_festivals": {
        "KeySchema": [
            {"AttributeName": "festival_name", "KeyType": "HASH"},
            {"AttributeName": "date", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "festival_name", "AttributeType": "S"},
            {"AttributeName": "date", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    "marketpulse_forecasts": {
        "KeySchema": [
            {"AttributeName": "category", "KeyType": "HASH"},
            {"AttributeName": "generated_at", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "category", "AttributeType": "S"},
            {"AttributeName": "generated_at", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    "marketpulse_recommendations_log": {
        "KeySchema": [
            {"AttributeName": "category", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "category", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
}


def _boto_kwargs() -> dict:
    """Build common boto3 keyword args from settings."""
    settings = get_settings()
    kwargs: dict = {"region_name": settings.aws_region}
    endpoint = settings.dynamo_endpoint_url or settings.dynamo_endpoint
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    if settings.aws_session_token:
        kwargs["aws_session_token"] = settings.aws_session_token
    return kwargs


def get_dynamo_resource():
    """Return a boto3 DynamoDB resource."""
    return boto3.resource("dynamodb", **_boto_kwargs())


def get_dynamo_client():
    """Return a boto3 DynamoDB low-level client."""
    return boto3.client("dynamodb", **_boto_kwargs())


def ensure_tables_exist() -> None:
    """Idempotently create all DynamoDB tables (skip if already existing)."""
    client = get_dynamo_client()
    existing = set(client.list_tables().get("TableNames", []))
    for table_name, schema in TABLES.items():
        if table_name in existing:
            logger.info("DynamoDB table already exists: %s", table_name)
            continue
        client.create_table(TableName=table_name, **schema)
        logger.info("DynamoDB table created: %s", table_name)
