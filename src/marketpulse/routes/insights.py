"""Routes for Bedrock-generated category insights."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import APIRouter, Body, Depends, Request

from marketpulse.core.auth import get_current_user
from marketpulse.core.rate_limit import limiter
from marketpulse.core.security import verify_api_key
from marketpulse.db.get_repo import get_repo
from marketpulse.schemas.insights import (
    BatchInsightRequest,
    BatchInsightResponse,
    InsightRequest,
    InsightResponse,
)
from marketpulse.services.insights import generate_category_insight

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["insights"])


def _risk_score(decision_data: dict) -> float:
    try:
        return round(float(decision_data.get("risk_score", 0.0)), 3)
    except (TypeError, ValueError):
        return 0.0


def _resolve_festival_context(repo: "DataRepository", supplied_context):
    if supplied_context is not None:
        return supplied_context
    try:
        return repo.list_all_festivals()
    except Exception:
        logger.exception("Failed to load festival context from repository")
        return []


def _is_bedrock_cacheable_insight(insight: str) -> bool:
    """Reject forecast-decision JSON blobs when serving AI insight cache."""
    text = (insight or "").strip()
    if not text:
        return False
    if not text.startswith("{"):
        return True
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return True
    if not isinstance(payload, dict):
        return True
    if payload.get("type") == "forecast_decision":
        return False
    if "decision" in payload and "recommended_action" in str(payload.get("decision", {})):
        return False
    return True


@router.post("/insights/batch", response_model=BatchInsightResponse)
@limiter.limit("5/minute")
async def generate_batch_insights(
    request: Request,
    raw_body: dict | None = Body(default=None),
    repo: "DataRepository" = Depends(get_repo),
    current_user: dict = Depends(get_current_user),
    _api_key: str = Depends(verify_api_key),
) -> BatchInsightResponse:
    """Generate Bedrock insights for multiple categories in one request."""
    body = BatchInsightRequest.model_validate(raw_body or {})
    scoped_repo = repo.with_organization(current_user.get("organization_id")) if hasattr(repo, "with_organization") else repo
    now = datetime.now(timezone.utc)
    results: list[InsightResponse] = []

    for item in body.items:
        risk = _risk_score(item.decision_data)
        try:
            cached = scoped_repo.get_cached_recommendation(
                category=item.category,
                risk_score=risk,
                max_age_seconds=3600,
            )
        except Exception:
            logger.exception("Failed cache lookup for category=%s", item.category)
            cached = None
        if cached and cached.get("insight") and _is_bedrock_cacheable_insight(str(cached["insight"])):
            results.append(
                InsightResponse(
                    category=item.category,
                    insight=str(cached["insight"]),
                    generated_at=str(cached.get("generated_at", now.isoformat())),
                )
            )
            continue

        festival_context = _resolve_festival_context(scoped_repo, item.festival_context)
        insight = generate_category_insight(
            category=item.category,
            forecast_data=item.forecast_data,
            decision_data=item.decision_data,
            festival_context=festival_context,
        )
        generated_at = datetime.now(timezone.utc)
        try:
            scoped_repo.log_recommendation(
                category=item.category,
                risk_score=risk,
                insight=insight,
                generated_at=generated_at,
            )
        except Exception:
            logger.exception("Failed to log recommendation for category=%s", item.category)
        results.append(
            InsightResponse(
                category=item.category,
                insight=insight,
                generated_at=generated_at.isoformat(),
            )
        )

    return BatchInsightResponse(
        insights=results,
        generated_at=now.isoformat(),
    )


@router.post("/insights/{category}", response_model=InsightResponse)
@limiter.limit("10/minute")
async def generate_insight_for_category(
    request: Request,
    category: str,
    raw_body: dict | None = Body(default=None),
    repo: "DataRepository" = Depends(get_repo),
    current_user: dict = Depends(get_current_user),
    _api_key: str = Depends(verify_api_key),
) -> InsightResponse:
    """Generate one Bedrock insight for a category with cache-aware behavior."""
    body = InsightRequest.model_validate(raw_body or {})
    scoped_repo = repo.with_organization(current_user.get("organization_id")) if hasattr(repo, "with_organization") else repo
    risk = _risk_score(body.decision_data)
    try:
        cached = scoped_repo.get_cached_recommendation(
            category=category,
            risk_score=risk,
            max_age_seconds=3600,
        )
    except Exception:
        logger.exception("Failed cache lookup for category=%s", category)
        cached = None
    if cached and cached.get("insight") and _is_bedrock_cacheable_insight(str(cached["insight"])):
        return InsightResponse(
            category=category,
            insight=str(cached["insight"]),
            generated_at=str(cached.get("generated_at", datetime.now(timezone.utc).isoformat())),
        )

    festival_context = _resolve_festival_context(scoped_repo, body.festival_context)
    insight = generate_category_insight(
        category=category,
        forecast_data=body.forecast_data,
        decision_data=body.decision_data,
        festival_context=festival_context,
    )
    generated_at = datetime.now(timezone.utc)
    try:
        scoped_repo.log_recommendation(
            category=category,
            risk_score=risk,
            insight=insight,
            generated_at=generated_at,
        )
    except Exception:
        logger.exception("Failed to log recommendation for category=%s", category)

    return InsightResponse(
        category=category,
        insight=insight,
        generated_at=generated_at.isoformat(),
    )
