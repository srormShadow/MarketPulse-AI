"""Routes for Bedrock-generated category insights."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

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


@router.post("/insights/batch", response_model=BatchInsightResponse)
async def generate_batch_insights(
    request: BatchInsightRequest,
    repo: "DataRepository" = Depends(get_repo),
) -> BatchInsightResponse:
    """Generate Bedrock insights for multiple categories in one request."""
    now = datetime.now(timezone.utc)
    results: list[InsightResponse] = []

    for item in request.items:
        risk = _risk_score(item.decision_data)
        try:
            cached = repo.get_cached_recommendation(
                category=item.category,
                risk_score=risk,
                max_age_seconds=3600,
            )
        except Exception:
            logger.exception("Failed cache lookup for category=%s", item.category)
            cached = None
        if cached and cached.get("insight"):
            results.append(
                InsightResponse(
                    category=item.category,
                    insight=str(cached["insight"]),
                    generated_at=str(cached.get("generated_at", now.isoformat())),
                )
            )
            continue

        festival_context = _resolve_festival_context(repo, item.festival_context)
        insight = generate_category_insight(
            category=item.category,
            forecast_data=item.forecast_data,
            decision_data=item.decision_data,
            festival_context=festival_context,
        )
        generated_at = datetime.now(timezone.utc)
        try:
            repo.log_recommendation(
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
async def generate_insight_for_category(
    category: str,
    request: InsightRequest,
    repo: "DataRepository" = Depends(get_repo),
) -> InsightResponse:
    """Generate one Bedrock insight for a category with cache-aware behavior."""
    risk = _risk_score(request.decision_data)
    try:
        cached = repo.get_cached_recommendation(
            category=category,
            risk_score=risk,
            max_age_seconds=3600,
        )
    except Exception:
        logger.exception("Failed cache lookup for category=%s", category)
        cached = None
    if cached and cached.get("insight"):
        return InsightResponse(
            category=category,
            insight=str(cached["insight"]),
            generated_at=str(cached.get("generated_at", datetime.now(timezone.utc).isoformat())),
        )

    festival_context = _resolve_festival_context(repo, request.festival_context)
    insight = generate_category_insight(
        category=category,
        forecast_data=request.forecast_data,
        decision_data=request.decision_data,
        festival_context=festival_context,
    )
    generated_at = datetime.now(timezone.utc)
    try:
        repo.log_recommendation(
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
