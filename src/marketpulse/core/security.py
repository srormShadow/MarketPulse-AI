"""API key authentication and security dependencies."""

import logging
import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from marketpulse.core.config import get_settings

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str:
    """Validate the X-API-Key header against the configured API_KEY.

    If no API_KEY is configured (empty string), authentication is skipped
    to allow development without credentials.
    """
    settings = get_settings()
    configured_key = settings.api_key

    if not configured_key:
        return "anonymous"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )

    if not secrets.compare_digest(api_key, configured_key):
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key
