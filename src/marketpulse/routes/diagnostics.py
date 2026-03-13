"""Model diagnostics API routes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from marketpulse.core.auth import get_current_user
from marketpulse.core.security import verify_api_key
from marketpulse.db.get_repo import get_repo
from marketpulse.services.model_diagnostics import analyze_category_model

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["diagnostics"])


def _discover_categories(repo: "DataRepository") -> list[str]:
    # Read a sufficiently large page from SKU table and infer categories.
    _, rows = repo.list_skus(limit=1000, offset=0)
    categories = sorted(
        {
            str(r.get("category", "")).strip()
            for r in rows
            if str(r.get("category", "")).strip()
        }
    )
    return categories


@router.get("/diagnostics/all")
def all_diagnostics(
    categories: str | None = Query(default=None, description="Comma-separated categories", max_length=500),
    repo: "DataRepository" = Depends(get_repo),
    current_user: dict = Depends(get_current_user),
    _api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Return diagnostics for all discovered categories."""
    scoped_repo = repo.with_organization(current_user.get("organization_id")) if hasattr(repo, "with_organization") else repo
    target_categories = (
        [c.strip() for c in categories.split(",") if c.strip()]
        if categories
        else _discover_categories(scoped_repo)
    )
    out: dict[str, Any] = {}
    items: list[dict[str, Any]] = []

    for category in target_categories:
        try:
            result = analyze_category_model(scoped_repo, category)
            payload = {
                "coefficients": result.get("coefficients", {}),
                "feature_influence": result.get("feature_importance", {}),
                "intercept": result.get("intercept"),
                "n_samples": result.get("n_samples"),
            }
            out[category] = payload
            items.append({"category": category, **payload})
        except Exception:
            logger.exception("Skipping diagnostics for category=%s", category)
            continue

    return {
        "categories": out,
        "items": items,
        "total": len(items),
    }


@router.get("/diagnostics/{category}")
def category_diagnostics(
    category: str,
    repo: "DataRepository" = Depends(get_repo),
    current_user: dict = Depends(get_current_user),
    _api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Return model coefficients and feature influence for one category."""
    try:
        scoped_repo = repo.with_organization(current_user.get("organization_id")) if hasattr(repo, "with_organization") else repo
        result = analyze_category_model(scoped_repo, category)
    except ValueError as exc:
        logger.warning("Diagnostics not found for category=%s: %s", category, str(exc))
        raise HTTPException(status_code=404, detail="Category not found or insufficient data for diagnostics.") from exc
    except Exception as exc:
        logger.exception("Diagnostics failed for category=%s", category)
        raise HTTPException(status_code=500, detail="Diagnostics failed") from exc

    coefficients = result.get("coefficients", {})
    feature_influence = result.get("feature_importance", {})
    return {
        "category": category,
        "coefficients": coefficients,
        "feature_influence": feature_influence,
        "intercept": result.get("intercept"),
        "n_samples": result.get("n_samples"),
    }
