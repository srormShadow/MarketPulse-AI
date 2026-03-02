"""Debug routes for internal data sanity checks."""

from datetime import date as date_type
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query

from marketpulse.db.get_repo import get_repo

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository
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


@router.get("/festivals", response_model=FestivalListResponse)
def list_festivals(
    repo: "DataRepository" = Depends(get_repo),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2024, le=2100),
) -> FestivalListResponse:
    """Return festival records, optionally filtered by month/year."""
    today = date_type.today()
    rows = repo.list_all_festivals()

    items: list[FestivalItemResponse] = []
    for row in rows:
        d = row["date"]
        if isinstance(d, str):
            d = date_type.fromisoformat(d)

        if month is not None and d.month != month:
            continue
        if year is not None and d.year != year:
            continue

        cat_str = row.get("category", "")
        categories = [c.strip() for c in cat_str.split(",") if c.strip()]
        days_until = (d - today).days
        uplift = float(row.get("historical_uplift", 0.0))

        items.append(
            FestivalItemResponse(
                festival_name=row["festival_name"],
                date=d,
                category=cat_str,
                categories=categories,
                historical_uplift=uplift,
                demand_multiplier=1.0 + uplift,
                days_until=days_until,
            )
        )

    items.sort(key=lambda x: x.date)
    return FestivalListResponse(total=len(items), items=items)


def _find_festival_for_date(rows: list[dict[str, Any]], target_date: date_type) -> dict[str, Any] | None:
    for row in rows:
        raw_date = row.get("date")
        row_date = date_type.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date
        if row_date == target_date:
            return row
    return None


@router.get("/predictions")
def get_prediction(
    date: date_type = Query(..., description="Target date in YYYY-MM-DD"),
    stock: str = Query(..., min_length=1, description="Stock/category name"),
    repo: "DataRepository" = Depends(get_repo),
) -> dict[str, Any]:
    """Return lightweight prediction payload for calendar date click sidebar."""
    series = repo.get_category_daily_sales(stock)
    festivals = repo.list_all_festivals()
    festival_row = _find_festival_for_date(festivals, date)

    if series.empty:
        return {
            "date": date.isoformat(),
            "stock": stock,
            "predicted_demand": None,
            "risk_score": None,
            "confidence_level": "low",
            "suggested_action": "No data available for this stock/category.",
        }

    recent = series.tail(30)["units_sold"]
    baseline = float(recent.mean())
    uplift = float(festival_row.get("historical_uplift", 0.0)) if festival_row else 0.0
    predicted_demand = round(max(0.0, baseline * (1.0 + uplift)), 2)
    variance = float(recent.std()) if len(recent) > 1 else 0.0
    risk_score = min(1.0, round((variance / baseline) if baseline > 0 else 0.0, 3))

    if risk_score >= 0.8:
        confidence = "low"
    elif risk_score >= 0.4:
        confidence = "medium"
    else:
        confidence = "high"

    if festival_row and uplift >= 0.3:
        action = "Increase inventory before festival demand spike."
    elif risk_score >= 0.6:
        action = "Monitor inventory closely and plan a buffer restock."
    else:
        action = "Maintain regular replenishment plan."

    return {
        "date": date.isoformat(),
        "stock": stock,
        "predicted_demand": predicted_demand,
        "risk_score": risk_score,
        "confidence_level": confidence,
        "suggested_action": action,
    }


@router.get("/historical")
def get_historical(
    date: date_type = Query(..., description="Target date in YYYY-MM-DD"),
    stock: str = Query(..., min_length=1, description="Stock/category name"),
    repo: "DataRepository" = Depends(get_repo),
) -> dict[str, Any]:
    """Return same-day historical comparison for last two years."""
    series = repo.get_category_daily_sales(stock)
    if series.empty:
        return {
            str(date.year - 1): None,
            str(date.year - 2): None,
        }

    records = series.copy()
    records["date"] = records["date"].dt.date
    yearly_mean = records.groupby(records["date"].map(lambda d: d.year))["units_sold"].mean().to_dict()

    out: dict[str, Any] = {}
    for year in [date.year - 1, date.year - 2]:
        target = date.replace(year=year)
        match = records.loc[records["date"] == target, "units_sold"]
        if match.empty:
            out[str(year)] = None
            continue

        volume = float(match.iloc[0])
        avg = float(yearly_mean.get(year, volume))
        change_pct = ((volume - avg) / avg * 100.0) if avg else 0.0
        trend = "up" if change_pct > 3 else ("down" if change_pct < -3 else "flat")
        out[str(year)] = {
            "sales_volume": round(volume, 2),
            "demand_trend": trend,
            "percent_change": f"{change_pct:+.1f}%",
        }

    return out
