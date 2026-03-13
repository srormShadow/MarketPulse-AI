"""Prometheus metrics instrumentation.

Exposes application-level counters and histograms. The ``/metrics`` endpoint
is mounted in ``main.py`` and returns Prometheus text exposition format.

When ``prometheus-client`` is not installed, all metric operations are no-ops.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram, generate_latest

    REQUEST_COUNT = Counter(
        "marketpulse_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "marketpulse_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "endpoint"],
    )
    CSV_UPLOADS = Counter(
        "marketpulse_csv_uploads_total",
        "Total CSV file uploads",
        ["file_type", "status"],
    )
    LOGIN_ATTEMPTS = Counter(
        "marketpulse_login_attempts_total",
        "Login attempts",
        ["status"],
    )
    SHOPIFY_SYNCS = Counter(
        "marketpulse_shopify_syncs_total",
        "Shopify sync operations",
        ["status"],
    )

    _ENABLED = True

except ImportError:
    _ENABLED = False

    def generate_latest() -> bytes:  # type: ignore[misc]
        return b""

    class _NoOp:
        def labels(self, *args: Any, **kwargs: Any) -> "_NoOp":
            return self

        def inc(self, *args: Any, **kwargs: Any) -> None:
            pass

        def observe(self, *args: Any, **kwargs: Any) -> None:
            pass

    REQUEST_COUNT = _NoOp()  # type: ignore[assignment]
    REQUEST_LATENCY = _NoOp()  # type: ignore[assignment]
    CSV_UPLOADS = _NoOp()  # type: ignore[assignment]
    LOGIN_ATTEMPTS = _NoOp()  # type: ignore[assignment]
    SHOPIFY_SYNCS = _NoOp()  # type: ignore[assignment]


def is_enabled() -> bool:
    return _ENABLED


def metrics_response() -> bytes:
    """Return Prometheus text exposition format bytes."""
    return generate_latest()
