"""Shared rate-limiter instance for all API routes."""

import os
import sys

from slowapi import Limiter
from slowapi.util import get_remote_address

from marketpulse.core.config import get_settings

_settings = get_settings()
_is_test_runtime = (
    _settings.environment.lower() in {"test", "testing"}
    or _settings.app_env.lower() in {"test", "testing"}
    or "PYTEST_CURRENT_TEST" in os.environ
    or "pytest" in sys.modules
)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    enabled=not _is_test_runtime,
)
