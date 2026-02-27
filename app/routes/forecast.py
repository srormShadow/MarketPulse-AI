"""Forecasting and inventory decision routes."""

import logging

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.sku import SKU
from app.schemas.forecast import (
    ForecastDataPoint,
    ForecastErrorResponse,
    ForecastRequest,
    ForecastResponse,
    InventoryDecision,
)
from app.services.decision_engine import generate_inventory_decision_summary
from app.services.forecasting import forecast_next_n_days

logger = logging.getLogger(__name__)
router = APIRouter(tags=["forecast"])


@router.post(
    "/forecast/{category}",
    response_model=ForecastResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ForecastErrorResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ForecastErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ForecastErrorResponse},
    },
)
async def create_forecast(
    category: str = Path(..., description="Product category to forecast"),
    request: ForecastRequest = ...,
    db: Session = Depends(get_db),
) -> ForecastResponse | JSONResponse:
    """Generate demand forecast and inventory decision for a product category.

    This endpoint:
    1. Validates that the category exists in the database
    2. Generates a probabilistic demand forecast with uncertainty bounds
    3. Calculates inventory optimization metrics (safety stock, reorder point)
    4. Provides actionable inventory recommendations

    Args:
        category: Product category name (e.g., "Snacks", "Beverages")
        request: Forecast parameters including forecast horizon and inventory levels
        db: Database session dependency

    Returns:
        ForecastResponse with forecast time series and inventory decision summary
    """
    # Validate category exists
    stmt = select(SKU).where(SKU.category == category).limit(1)
    result = db.execute(stmt)
    sku_exists = result.scalar_one_or_none()

    if not sku_exists:
        logger.warning("Forecast requested for non-existent category: %s", category)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "status": "error",
                "message": f"Category '{category}' not found in database",
            },
        )

    # Generate forecast
    try:
        forecast_df = forecast_next_n_days(
            session=db,
            category=category,
            n_days=request.n_days,
        )
    except ValueError as exc:
        logger.warning("Forecast validation error for category %s: %s", category, str(exc))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": str(exc),
            },
        )
    except Exception:
        logger.exception("Unexpected error during forecast generation for category: %s", category)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error during forecast generation",
            },
        )

    # Generate inventory decision
    try:
        decision_summary = generate_inventory_decision_summary(
            forecast_df=forecast_df,
            current_inventory=request.current_inventory,
            lead_time_days=request.lead_time_days,
        )
    except Exception:
        logger.exception("Unexpected error during decision generation for category: %s", category)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error during decision generation",
            },
        )

    # Build response
    forecast_points = [
        ForecastDataPoint(
            date=row["date"].strftime("%Y-%m-%d"),
            predicted_mean=float(row["predicted_mean"]),
            lower_95=float(row["lower_95"]),
            upper_95=float(row["upper_95"]),
        )
        for _, row in forecast_df.iterrows()
    ]

    decision = InventoryDecision(
        recommended_action=decision_summary["recommended_action"],
        order_quantity=int(decision_summary["order_quantity"]),
        reorder_point=float(decision_summary["reorder_point"]),
        safety_stock=float(decision_summary["safety_stock"]),
        risk_score=float(decision_summary["risk_score"]),
    )

    logger.info(
        "Forecast generated | category=%s | n_days=%d | action=%s",
        category,
        request.n_days,
        decision.recommended_action,
    )

    return ForecastResponse(
        category=category,
        forecast=forecast_points,
        decision=decision,
    )
