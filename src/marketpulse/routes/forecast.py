"""Forecasting and inventory decision routes."""

import json
import logging
from datetime import datetime, timedelta, timezone

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.responses import JSONResponse

from marketpulse.core.auth import get_current_user
from marketpulse.core.rate_limit import limiter
from marketpulse.core.security import verify_api_key
from marketpulse.db.get_repo import get_repo

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository
from marketpulse.schemas.forecast import (
    BatchForecastRequest,
    ForecastDataPoint,
    ForecastErrorResponse,
    ForecastRequest,
    ForecastResponse,
    InventoryDecision,
)
from marketpulse.services.decision_engine import generate_inventory_decision_summary
from marketpulse.services.forecasting import forecast_next_n_days, validate_forecast_output

logger = logging.getLogger(__name__)
router = APIRouter(tags=["forecast"])


def _serialize_forecast_response_payload(
    category: str,
    forecast_df,
    decision_summary: dict,
    n_days: int,
    current_inventory: int,
    lead_time_days: int,
    supplier_pack_size: int,
    last_upload_date: str | None,
) -> dict:
    def _confidence_level(day_index: int) -> str:
        if day_index <= 7:
            return "high"
        if day_index <= 14:
            return "medium"
        return "low"

    forecast_points = [
        {
            "date": row["date"].strftime("%Y-%m-%d"),
            "predicted_mean": float(row["predicted_mean"]),
            "lower_95": float(row["lower_95"]),
            "upper_95": float(row["upper_95"]),
            "festival_score": float(row.get("festival_score", 0.0)),
            "confidence_level": _confidence_level(index + 1),
        }
        for index, (_, row) in enumerate(forecast_df.iterrows())
    ]
    try:
        validation = validate_forecast_output(forecast_df)
        warnings = list(validation.get("warnings", []))
    except Exception:
        logger.exception("Forecast output validation failed for category=%s", category)
        warnings = []
    training_summary = dict(getattr(forecast_df, "attrs", {}).get("training_summary", {}))
    return {
        "category": category,
        "forecast": forecast_points,
        "decision": {
            "recommended_action": decision_summary["recommended_action"],
            "order_quantity": int(decision_summary["order_quantity"]),
            "reorder_point": float(decision_summary["reorder_point"]),
            "safety_stock": float(decision_summary["safety_stock"]),
            "risk_score": float(decision_summary["risk_score"]),
            "festival_buffer_applied": bool(decision_summary.get("festival_buffer_applied", False)),
            "data_stale_warning": bool(decision_summary.get("data_stale_warning", False)),
            "pack_size_applied": bool(decision_summary.get("pack_size_applied", False)),
        },
        "warnings": warnings,
        "n_days": int(n_days),
        "current_inventory": int(current_inventory),
        "lead_time_days": int(lead_time_days),
        "supplier_pack_size": int(max(1, supplier_pack_size)),
        "last_upload_date": last_upload_date,
        "training_summary": training_summary,
    }


def _data_stale_flag(last_upload_ts: datetime | None) -> bool:
    if last_upload_ts is None:
        return False
    return last_upload_ts < (datetime.now(timezone.utc) - timedelta(days=7))


def _build_forecast_response_from_payload(
    payload: dict,
    cache_hit: bool,
    data_stale: bool,
) -> ForecastResponse:
    raw_forecast = payload.get("forecast", [])
    fixed_forecast = []
    for idx, point in enumerate(raw_forecast):
        cloned = dict(point)
        if "confidence_level" not in cloned:
            if idx + 1 <= 7:
                cloned["confidence_level"] = "high"
            elif idx + 1 <= 14:
                cloned["confidence_level"] = "medium"
            else:
                cloned["confidence_level"] = "low"
        fixed_forecast.append(cloned)
    forecast_points = [ForecastDataPoint(**point) for point in fixed_forecast]

    decision_payload = dict(payload.get("decision", {}))
    decision_payload.setdefault("festival_buffer_applied", False)
    decision_payload.setdefault("data_stale_warning", False)
    decision_payload.setdefault("pack_size_applied", False)
    decision = InventoryDecision(**decision_payload)
    return ForecastResponse(
        category=str(payload.get("category", "")),
        forecast=forecast_points,
        decision=decision,
        cache_hit=cache_hit,
        data_stale=data_stale,
        warnings=list(payload.get("warnings", [])),
    )


def _compute_or_fetch_forecast_payload(
    repo: "DataRepository",
    category: str,
    n_days: int,
    current_inventory: int,
    lead_time_days: int,
    supplier_pack_size: int = 1,
    last_upload_date: str | None = None,
) -> tuple[dict, bool, bool]:
    last_upload_ts = repo.get_category_last_upload_timestamp(category)
    data_stale = _data_stale_flag(last_upload_ts)

    cached = repo.get_cached_forecast(
        category=category,
        n_days=n_days,
        current_inventory=current_inventory,
        lead_time_days=lead_time_days,
        supplier_pack_size=supplier_pack_size,
        max_age_seconds=3600,
    )
    if cached:
        generated_at_raw = cached.get("generated_at")
        generated_at: datetime | None = None
        if isinstance(generated_at_raw, str):
            try:
                generated_at = datetime.fromisoformat(generated_at_raw.replace("Z", "+00:00"))
            except ValueError:
                generated_at = None
        is_fresh_vs_upload = (
            (last_upload_ts is None)
            or (generated_at is not None and generated_at >= last_upload_ts)
        )
        if is_fresh_vs_upload:
            cached["warnings"] = list(cached.get("warnings", []))
            return cached, True, data_stale

    forecast_df = forecast_next_n_days(
        repo=repo,
        category=category,
        n_days=n_days,
    )
    decision_summary = generate_inventory_decision_summary(
        forecast_df=forecast_df,
        current_inventory=current_inventory,
        lead_time_days=lead_time_days,
        supplier_pack_size=supplier_pack_size,
        last_upload_date=last_upload_date or (last_upload_ts.isoformat() if last_upload_ts else None),
    )
    payload = _serialize_forecast_response_payload(
        category=category,
        forecast_df=forecast_df,
        decision_summary=decision_summary,
        n_days=n_days,
        current_inventory=current_inventory,
        lead_time_days=lead_time_days,
        supplier_pack_size=supplier_pack_size,
        last_upload_date=last_upload_date,
    )
    repo.save_forecast_cache(
        category=category,
        payload=payload,
        generated_at=datetime.now(timezone.utc),
    )
    return payload, False, data_stale


def _log_decision_event(repo: "DataRepository", payload: dict, *, cache_hit: bool = False) -> None:
    if cache_hit:
        return
    decision = payload.get("decision", {})
    risk_score = float(decision.get("risk_score", 0.0))
    insight = json.dumps(
        {
            "type": "forecast_decision",
            "category": payload.get("category"),
            "decision": decision,
            "n_days": payload.get("n_days"),
            "warnings": payload.get("warnings", []),
        },
        default=str,
    )
    repo.log_recommendation(
        category=str(payload.get("category", "unknown")),
        risk_score=risk_score,
        insight=insight,
        generated_at=datetime.now(timezone.utc),
    )


@router.post(
    "/forecast/batch",
    response_model=list[ForecastResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ForecastErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ForecastErrorResponse},
    },
)
@limiter.limit("10/minute")
async def create_batch_forecast(
    request: Request,
    body: BatchForecastRequest,
    repo: "DataRepository" = Depends(get_repo),
    current_user: dict = Depends(get_current_user),
    _api_key: str = Depends(verify_api_key),
) -> list[ForecastResponse] | JSONResponse:
    """Generate demand forecasts for multiple categories in one request."""
    org_id = current_user.get("organization_id")
    scoped_repo = repo.with_organization(org_id) if hasattr(repo, "with_organization") else repo
    responses: list[ForecastResponse] = []

    for category in body.categories:
        skus = scoped_repo.get_skus_for_category(category, organization_id=org_id)
        if not skus:
            logger.warning("Batch forecast skipped unknown category=%s", category)
            continue

        current_inventory = int(body.inventory.get(category, 0))
        lead_time_days = int(body.lead_times.get(category, 7))
        supplier_pack_size = int(body.supplier_pack_sizes.get(category, 1))
        last_upload_date = body.last_upload_dates.get(category)

        try:
            payload, cache_hit, data_stale = _compute_or_fetch_forecast_payload(
                repo=scoped_repo,
                category=category,
                n_days=body.n_days,
                current_inventory=current_inventory,
                lead_time_days=lead_time_days,
                supplier_pack_size=supplier_pack_size,
                last_upload_date=last_upload_date,
            )
        except ValueError as exc:
            logger.warning("Batch forecast validation error for category=%s: %s", category, str(exc))
            continue
        except Exception:
            logger.exception("Unexpected batch forecast error for category=%s", category)
            continue

        responses.append(
            _build_forecast_response_from_payload(
                payload=payload,
                cache_hit=cache_hit,
                data_stale=data_stale,
            )
        )
        try:
            _log_decision_event(scoped_repo, payload, cache_hit=cache_hit)
        except Exception:
            logger.exception("Failed to log decision event for category=%s", category)

    return responses


@router.post(
    "/forecast/{category}",
    response_model=ForecastResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ForecastErrorResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ForecastErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ForecastErrorResponse},
    },
)
@limiter.limit("20/minute")
async def create_forecast(
    request: Request,
    category: str = Path(..., description="Product category to forecast", max_length=100),
    body: ForecastRequest = ...,
    repo: "DataRepository" = Depends(get_repo),
    current_user: dict = Depends(get_current_user),
    _api_key: str = Depends(verify_api_key),
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
        repo: DataRepository backend dependency

    Returns:
        ForecastResponse with forecast time series and inventory decision summary
    """
    # Validate category exists
    org_id = current_user.get("organization_id")
    scoped_repo = repo.with_organization(org_id) if hasattr(repo, "with_organization") else repo
    skus = scoped_repo.get_skus_for_category(category, organization_id=org_id)

    if not skus:
        logger.warning("Forecast requested for non-existent category: %s", category)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "status": "error",
                "message": f"Category '{category}' not found in database",
            },
        )

    try:
        payload, cache_hit, data_stale = _compute_or_fetch_forecast_payload(
            repo=scoped_repo,
            category=category,
            n_days=body.n_days,
            current_inventory=body.current_inventory,
            lead_time_days=body.lead_time_days,
            supplier_pack_size=body.supplier_pack_size,
            last_upload_date=body.last_upload_date,
        )
    except ValueError as exc:
        logger.warning("Forecast validation error for category %s: %s", category, str(exc))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Invalid forecast parameters. Please check your inputs.",
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

    logger.info(
        "Forecast served | category=%s | n_days=%d | cache_hit=%s",
        category,
        body.n_days,
        cache_hit,
    )
    try:
        _log_decision_event(scoped_repo, payload, cache_hit=cache_hit)
    except Exception:
        logger.exception("Failed to log decision event for category=%s", category)

    return _build_forecast_response_from_payload(
        payload=payload,
        cache_hit=cache_hit,
        data_stale=data_stale,
    )
