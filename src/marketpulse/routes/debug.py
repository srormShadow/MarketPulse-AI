"""Debug routes for internal data sanity checks."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from marketpulse.db.get_repo import get_repo

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository
from marketpulse.schemas.debug import (
    SalesCountResponse,
    SKUItemResponse,
    SKUListResponse,
)

router = APIRouter(tags=["debug"])


@router.get("/skus", response_model=SKUListResponse)
def list_skus(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: "DataRepository" = Depends(get_repo),
) -> SKUListResponse:
    """Return paginated SKU records for internal debugging."""

    total, rows = repo.list_skus(limit=limit, offset=offset)

    items = [
        SKUItemResponse(
            sku_id=row["sku_id"],
            product_name=row["product_name"],
            category=row["category"],
            mrp=row["mrp"],
            cost=row["cost"],
            current_inventory=row["current_inventory"],
        )
        for row in rows
    ]

    return SKUListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/sales/count", response_model=SalesCountResponse)
def sales_count(repo: "DataRepository" = Depends(get_repo)) -> SalesCountResponse:
    """Return total row count for sales records."""

    total_rows = repo.count_sales()
    return SalesCountResponse(total_sales_rows=total_rows)
