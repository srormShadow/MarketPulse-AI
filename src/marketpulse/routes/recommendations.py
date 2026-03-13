"""Routes for recommendation logs and audit trail."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query

from marketpulse.core.auth import get_current_user
from marketpulse.core.security import verify_api_key
from marketpulse.db.get_repo import get_repo

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

router = APIRouter(tags=["recommendations"])


def _extract_action_and_order(insight: str) -> tuple[str, int]:
    action = "n/a"
    order_qty = 0
    try:
        parsed = json.loads(insight)
        decision = parsed.get("decision", {}) if isinstance(parsed, dict) else {}
        action = str(decision.get("recommended_action", action))
        order_qty = int(decision.get("order_quantity", order_qty))
    except Exception:
        # Insight may be plain text (e.g., Bedrock response). Keep defaults.
        pass
    return action, order_qty


@router.get("/recommendations/recent")
def recent_recommendations(
    limit: int = Query(default=10, ge=1, le=100),
    repo: "DataRepository" = Depends(get_repo),
    current_user: dict = Depends(get_current_user),
    _api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    scoped_repo = repo.with_organization(current_user.get("organization_id")) if hasattr(repo, "with_organization") else repo
    rows = scoped_repo.list_recent_recommendations(limit=limit)
    items: list[dict[str, Any]] = []

    for row in rows:
        action, order_qty = _extract_action_and_order(str(row.get("insight", "")))
        ts = str(row.get("timestamp", ""))
        # Normalize timestamp if possible.
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).isoformat()
        except Exception:
            pass

        items.append(
            {
                "date": ts,
                "category": str(row.get("category", "unknown")),
                "action": action,
                "order_quantity": int(order_qty),
                "risk_score": float(row.get("risk_score", 0.0)),
            }
        )

    return {
        "items": items,
        "total": len(items),
    }

