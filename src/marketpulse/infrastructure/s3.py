"""S3 utilities for CSV archival and model persistence."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

try:
    import boto3
    from botocore.exceptions import ClientError
except ModuleNotFoundError:  # pragma: no cover - exercised in lean test envs
    boto3 = None

    class ClientError(Exception):
        """Fallback ClientError type when botocore is unavailable."""

        def __init__(self, response: dict | None = None, operation_name: str = "") -> None:
            super().__init__(f"S3 client unavailable for operation '{operation_name}'")
            self.response = response or {"Error": {"Code": "Unavailable"}}
            self.operation_name = operation_name

import joblib

from marketpulse.core.config import get_settings

logger = logging.getLogger(__name__)


def _boto_kwargs() -> dict[str, str]:
    """Build boto3 kwargs from configured environment settings."""
    settings = get_settings()
    kwargs: dict[str, str] = {"region_name": settings.aws_region}

    endpoint = settings.s3_endpoint_url or settings.s3_endpoint
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
    if settings.aws_secret_access_key:
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    if settings.aws_session_token:
        kwargs["aws_session_token"] = settings.aws_session_token
    return kwargs


def _s3_client():
    if boto3 is None:
        raise RuntimeError("boto3 is not installed. Install boto3 to enable S3 features.")
    return boto3.client("s3", **_boto_kwargs())


def _slugify(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    return safe.strip("-") or "unknown"


def _signature_for_payload(payload: bytes, signing_key: str) -> tuple[str, str]:
    key = (signing_key or "").strip()
    if key:
        digest = hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return "hmac-sha256", digest
    return "sha256", hashlib.sha256(payload).hexdigest()


def upload_csv(file: bytes, category: str, filename: str | None = None) -> str:
    """Upload CSV bytes to s3://<data-bucket>/uploads/<category>/..."""
    settings = get_settings()
    bucket = settings.s3_data_bucket
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    safe_category = _slugify(category)
    safe_filename = _slugify(filename or "upload") + ".csv"
    key = f"uploads/{safe_category}/{stamp}_{safe_filename}"

    _s3_client().put_object(
        Bucket=bucket,
        Key=key,
        Body=file,
        ContentType="text/csv",
        ServerSideEncryption="AES256",
    )
    return f"s3://{bucket}/{key}"


def save_model(model_object: Any, category: str) -> str:
    """Serialize and store model object in S3 under category/latest.pkl."""
    settings = get_settings()
    bucket = settings.s3_model_bucket
    safe_category = _slugify(category)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    version_key = f"{safe_category}/{stamp}.pkl"
    latest_key = f"{safe_category}/latest.pkl"

    buf = io.BytesIO()
    joblib.dump(model_object, buf, compress=("zlib", 3))
    payload = buf.getvalue()
    algo, digest = _signature_for_payload(payload, settings.model_signing_key)
    signature_blob = json.dumps({"algo": algo, "digest": digest}).encode("utf-8")

    client = _s3_client()
    client.put_object(
        Bucket=bucket,
        Key=version_key,
        Body=io.BytesIO(payload).getvalue(),
        ContentType="application/octet-stream",
        ServerSideEncryption="AES256",
    )
    client.put_object(
        Bucket=bucket,
        Key=latest_key,
        Body=io.BytesIO(payload).getvalue(),
        ContentType="application/octet-stream",
        ServerSideEncryption="AES256",
    )
    client.put_object(
        Bucket=bucket,
        Key=f"{version_key}.sig.json",
        Body=signature_blob,
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )
    client.put_object(
        Bucket=bucket,
        Key=f"{latest_key}.sig.json",
        Body=signature_blob,
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )
    return f"s3://{bucket}/{latest_key}"


def load_model(category: str) -> Any | None:
    """Load category model object from s3://<model-bucket>/<category>/latest.pkl."""
    settings = get_settings()
    bucket = settings.s3_model_bucket
    safe_category = _slugify(category)
    latest_key = f"{safe_category}/latest.pkl"
    signature_key = f"{latest_key}.sig.json"

    # In production, do not deserialize untrusted pickle unless explicitly allowed.
    if (
        settings.environment.lower() in {"production", "prod"}
        and not settings.model_signing_key.strip()
        and not settings.allow_unsafe_model_pickle
    ):
        logger.warning("Skipping model load for %s: MODEL_SIGNING_KEY is required in production.", category)
        return None

    try:
        payload_response = _s3_client().get_object(Bucket=bucket, Key=latest_key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
            return None
        raise

    payload = payload_response["Body"].read()

    signing_key = settings.model_signing_key.strip()
    if signing_key:
        try:
            signature_response = _s3_client().get_object(Bucket=bucket, Key=signature_key)
            signature_payload = json.loads(signature_response["Body"].read())
            expected_algo = str(signature_payload.get("algo", ""))
            expected_digest = str(signature_payload.get("digest", ""))
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                logger.warning("Model signature missing for %s; skipping load.", category)
                return None
            raise
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Invalid model signature payload for %s; skipping load.", category)
            return None

        algo, digest = _signature_for_payload(payload, signing_key)
        if expected_algo != algo or not hmac.compare_digest(expected_digest, digest):
            logger.warning("Model signature verification failed for %s; skipping load.", category)
            return None
    elif not settings.allow_unsafe_model_pickle:
        logger.warning("Unsafe pickle loading disabled for %s; skipping cached model load.", category)
        return None

    return joblib.load(io.BytesIO(payload))


def list_model_versions(category: str) -> list[dict[str, Any]]:
    """List model keys for a category with last-modified timestamps."""
    settings = get_settings()
    bucket = settings.s3_model_bucket
    safe_category = _slugify(category)
    prefix = f"{safe_category}/"
    client = _s3_client()

    paginator = client.get_paginator("list_objects_v2")
    versions: list[dict[str, Any]] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = str(obj["Key"])
            if not key.endswith(".pkl"):
                continue
            versions.append(
                {
                    "key": key,
                    "timestamp": obj["LastModified"].astimezone(timezone.utc).isoformat(),
                    "size_bytes": int(obj["Size"]),
                }
            )

    versions.sort(key=lambda item: item["timestamp"], reverse=True)
    return versions

