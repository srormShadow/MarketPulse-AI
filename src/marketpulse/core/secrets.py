"""AWS Secrets Manager integration.

When USE_SECRETS_MANAGER=true, fetches secrets from AWS Secrets Manager at
startup and injects them into the environment before Settings loads.  When
disabled (default), this module is a no-op.

Usage (in main.py lifespan or settings init):
    from marketpulse.core.secrets import load_secrets
    load_secrets()
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def load_secrets(
    secret_name: str | None = None,
    region: str | None = None,
) -> dict[str, str]:
    """Fetch secrets from AWS Secrets Manager and export them as env vars.

    Returns the raw key/value dict on success, empty dict otherwise.
    Only runs when ``USE_SECRETS_MANAGER`` env var is truthy.
    """
    if not os.getenv("USE_SECRETS_MANAGER", "").strip().lower() in {"1", "true", "yes"}:
        return {}

    secret_name = secret_name or os.getenv("SECRETS_MANAGER_NAME", "marketpulse/prod")
    region = region or os.getenv("AWS_REGION", "ap-south-1")

    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        logger.warning("boto3 not installed; skipping Secrets Manager fetch")
        return {}

    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        secret_string = response.get("SecretString", "{}")
        secrets: dict[str, str] = json.loads(secret_string)

        for key, value in secrets.items():
            env_key = key.upper()
            if env_key not in os.environ:
                os.environ[env_key] = str(value)
                logger.debug("Injected secret %s from Secrets Manager", env_key)
            else:
                logger.debug("Skipping %s — already set in environment", env_key)

        logger.info("Loaded %d secrets from Secrets Manager (%s)", len(secrets), secret_name)
        return secrets
    except ClientError:
        logger.exception("Failed to fetch secrets from Secrets Manager (%s)", secret_name)
        return {}
    except (json.JSONDecodeError, TypeError):
        logger.exception("Invalid JSON in Secrets Manager secret (%s)", secret_name)
        return {}
