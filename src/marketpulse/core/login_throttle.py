"""Per-account login throttling with exponential backoff.

Tracks failed login attempts in-memory (or Redis when available) and
enforces progressive lockout:
  - After 5 failures: 30-second lockout
  - After 10 failures: 5-minute lockout
  - After 15 failures: 30-minute lockout
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS_BEFORE_LOCK = 5
_LOCKOUT_TIERS = [
    (5, 30),      # 5 failures → 30s
    (10, 300),    # 10 failures → 5 min
    (15, 1800),   # 15 failures → 30 min
]
_ATTEMPT_WINDOW = 3600  # reset counter after 1 hour of no failures


@dataclass
class _AccountState:
    failures: int = 0
    last_failure: float = 0.0
    locked_until: float = 0.0


_store: dict[str, _AccountState] = defaultdict(_AccountState)


def check_lockout(email: str) -> tuple[bool, int]:
    """Return (is_locked, seconds_remaining). Thread-safe enough for single-process."""
    state = _store.get(email)
    if state is None:
        return False, 0
    now = time.monotonic()
    if now - state.last_failure > _ATTEMPT_WINDOW:
        # Window expired — reset
        _store.pop(email, None)
        return False, 0
    if state.locked_until > now:
        return True, int(state.locked_until - now) + 1
    return False, 0


def record_failure(email: str) -> int:
    """Record a failed login attempt. Returns the new failure count."""
    state = _store[email]
    now = time.monotonic()
    if now - state.last_failure > _ATTEMPT_WINDOW:
        state.failures = 0
    state.failures += 1
    state.last_failure = now
    # Apply lockout tier
    for threshold, duration in reversed(_LOCKOUT_TIERS):
        if state.failures >= threshold:
            state.locked_until = now + duration
            logger.warning("Account %s locked for %ds after %d failures", email, duration, state.failures)
            break
    return state.failures


def record_success(email: str) -> None:
    """Clear failure state on successful login."""
    _store.pop(email, None)
