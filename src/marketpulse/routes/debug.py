"""Debug routes for internal data sanity checks."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from marketpulse.db.session import get_db
from marketpulse.models.festival import Festival
from marketpulse.models.sales import Sales
from marketpulse.models.sku import SKU
from marketpulse.schemas.debug import (
    FestivalItemResponse,
    FestivalListResponse,
    SalesCountResponse,
    SKUItemResponse,
    SKUListResponse,
)

router = APIRouter(tags=["debug"])


@router.get("/skus", response_model=SKUListResponse)
def list_skus(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> SKUListResponse:
    """Return paginated SKU records for internal debugging."""

    total = db.scalar(select(func.count()).select_from(SKU)) or 0
    rows = db.scalars(
        select(SKU)
        .order_by(SKU.sku_id.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    items = [
        SKUItemResponse(
            sku_id=row.sku_id,
            product_name=row.product_name,
            category=row.category,
            mrp=row.mrp,
            cost=row.cost,
            current_inventory=row.current_inventory,
        )
        for row in rows
    ]

    return SKUListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/sales/count", response_model=SalesCountResponse)
def sales_count(db: Session = Depends(get_db)) -> SalesCountResponse:
    """Return total row count for sales records."""

    total_rows = db.scalar(select(func.count()).select_from(Sales)) or 0
    return SalesCountResponse(total_sales_rows=total_rows)


@router.get("/festivals", response_model=FestivalListResponse)
def list_festivals(db: Session = Depends(get_db)) -> FestivalListResponse:
    """Return seeded festival records."""

    rows = db.scalars(select(Festival).order_by(Festival.date.asc())).all()
    items = [
        FestivalItemResponse(
            festival_name=row.festival_name,
            date=row.date,
            category=row.category,
            historical_uplift=row.historical_uplift,
        )
        for row in rows
    ]
    return FestivalListResponse(total=len(items), items=items)
