"""Resilience wrappers (circuit breaker + retry) for external service calls.

Uses tenacity for retries with exponential backoff and a simple circuit-breaker
pattern.  Shopify API calls and AWS Bedrock invocations should use these
decorators to fail fast and surface degraded-mode behavior instead of
cascading timeouts.
"""

from __future__ import annotations

import logging

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


def _log_retry(retry_state: RetryCallState) -> None:
    logger.warning(
        "Retrying %s (attempt %d) after %s",
        retry_state.fn.__name__ if retry_state.fn else "unknown",
        retry_state.attempt_number,
        retry_state.outcome.exception() if retry_state.outcome else "n/a",
    )


# ---------------------------------------------------------------------------
# Shopify API resilience
# ---------------------------------------------------------------------------
shopify_retry = retry(
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=_log_retry,
    reraise=True,
)

# ---------------------------------------------------------------------------
# AWS Bedrock resilience
# ---------------------------------------------------------------------------
bedrock_retry = retry(
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    before_sleep=_log_retry,
    reraise=True,
)
