"""Optional Redis caching layer.

When REDIS_URL is configured, provides a thin wrapper around Redis for
caching frequently-queried data (festival calendars, category stats, SKU
aggregations).  When Redis is unavailable, all operations silently no-op so
the application degrades gracefully.

Usage:
    from marketpulse.core.cache import cache

    # Read-through pattern
    data = cache.get("festivals:all")
    if data is None:
        data = expensive_query()
        cache.set("festivals:all", data, ttl=300)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from marketpulse.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client = None
_initialized = False


def _get_redis():
    global _redis_client, _initialized
    if _initialized:
        return _redis_client
    _initialized = True
    settings = get_settings()
    redis_url = getattr(settings, "redis_url", None)
    if not redis_url:
        logger.debug("REDIS_URL not configured; caching disabled")
        return None
    try:
        import redis

        _redis_client = redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
        _redis_client.ping()
        logger.info("Redis cache connected at %s", redis_url)
    except Exception:
        logger.warning("Redis connection failed; caching disabled", exc_info=True)
        _redis_client = None
    return _redis_client


class _Cache:
    """Thin cache facade. All methods are safe to call even without Redis."""

    def get(self, key: str) -> Any | None:
        r = _get_redis()
        if r is None:
            return None
        try:
            raw = r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        r = _get_redis()
        if r is None:
            return
        try:
            r.setex(key, ttl, json.dumps(value, default=str))
        except Exception:
            pass

    def delete(self, key: str) -> None:
        r = _get_redis()
        if r is None:
            return
        try:
            r.delete(key)
        except Exception:
            pass

    def invalidate_prefix(self, prefix: str) -> None:
        r = _get_redis()
        if r is None:
            return
        try:
            cursor = 0
            while True:
                cursor, keys = r.scan(cursor, match=f"{prefix}*", count=100)
                if keys:
                    r.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            pass


cache = _Cache()
