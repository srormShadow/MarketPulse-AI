"""Audit logging service.

Provides a simple ``emit()`` call that writes structured audit records to the
database.  All auth events, data mutations, and admin actions should flow
through this module.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def emit(
    *,
    action: str,
    request: Request | None = None,
    user: dict[str, Any] | None = None,
    resource: str | None = None,
    detail: str | None = None,
    repo: Any | None = None,
) -> None:
    """Write an audit record to the database (best-effort, never raises)."""
    try:
        from marketpulse.models.audit_log import AuditLog

        record = AuditLog(
            timestamp=datetime.now(timezone.utc),
            user_id=int(user.get("id") or user.get("sub") or 0) if user else None,
            email=str(user.get("email", "")) if user else None,
            ip_address=_client_ip(request),
            action=action,
            resource=resource,
            detail=detail[:1000] if detail else None,
            organization_id=int(user.get("organization_id") or 0) if user and user.get("organization_id") else None,
        )

        if repo and hasattr(repo, "_db"):
            repo._db.add(record)
            repo._db.commit()
        else:
            from marketpulse.db.session import SessionLocal

            db = SessionLocal()
            try:
                db.add(record)
                db.commit()
            finally:
                db.close()

        logger.debug("audit: %s user=%s resource=%s", action, record.email, resource)
    except Exception:
        logger.warning("Failed to write audit log for action=%s", action, exc_info=True)
