"""Dashboard bootstrap endpoints for tenant-scoped UI state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from marketpulse.core.auth import get_current_user
from marketpulse.db.get_repo import get_repo

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/bootstrap", response_model=None)
async def dashboard_bootstrap(
    current_user: dict = Depends(get_current_user),
    repo: "DataRepository" = Depends(get_repo),
) -> JSONResponse:
    org_id = current_user.get("organization_id")
    scoped_repo = repo.with_organization(org_id) if hasattr(repo, "with_organization") else repo
    if org_id is None:
        summary = {"categories": [], "inventory": {}, "lead_times": {}}
    else:
        summary = scoped_repo.get_inventory_summary(org_id)
    connected_stores = scoped_repo.list_shopify_stores(organization_id=org_id)
    sales_count = scoped_repo.count_sales() if hasattr(scoped_repo, "count_sales") else repo.count_sales()

    categories = summary.get("categories", [])
    has_catalog = bool(categories)
    has_sales = int(sales_count or 0) > 0
    has_shopify = bool(connected_stores)

    return JSONResponse(
        content={
            "categories": categories,
            "inventory": summary.get("inventory", {}),
            "lead_times": summary.get("lead_times", {}),
            "connected_store_count": len(connected_stores),
            "has_catalog": has_catalog,
            "has_sales": has_sales,
            "has_shopify": has_shopify,
            "is_empty": not has_catalog and not has_sales and not has_shopify,
            "onboarding_steps": [
                {
                    "id": "connect_shopify",
                    "label": "Connect Shopify",
                    "completed": has_shopify,
                },
                {
                    "id": "upload_catalog",
                    "label": "Upload product catalog CSV",
                    "completed": has_catalog,
                },
                {
                    "id": "upload_sales",
                    "label": "Upload sales history CSV",
                    "completed": has_sales,
                },
            ],
        }
    )
