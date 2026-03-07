"""Routes for on-demand discount simulation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pandas as pd
from fastapi import APIRouter, Body, Depends, Path, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from marketpulse.core.rate_limit import limiter
from marketpulse.core.security import verify_api_key
from marketpulse.db.get_repo import get_repo
from marketpulse.schemas.forecast import ForecastDataPoint, InventoryDecision
from marketpulse.schemas.simulation import (
    DiscountSimulationInputs,
    DiscountSimulationRequest,
    DiscountSimulationResponse,
    SimulationBlock,
    SimulationDelta,
)
from marketpulse.services.decision_engine import generate_inventory_decision_summary
from marketpulse.services.discount_simulation import (
    compute_simulation_deltas,
    compute_supply_stability_index,
    simulate_discounted_forecast,
)
from marketpulse.services.forecasting import forecast_next_n_days, validate_forecast_output
from marketpulse.services.insights.bedrock_insights import generate_discount_simulation_explanation

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["simulation"])


def _confidence_level(day_index: int) -> str:
    if day_index <= 7:
        return "high"
    if day_index <= 14:
        return "medium"
    return "low"


def _serialize_forecast_points(df) -> list[ForecastDataPoint]:
    points: list[ForecastDataPoint] = []
    for idx, (_, row) in enumerate(df.iterrows()):
        points.append(
            ForecastDataPoint(
                date=row["date"].strftime("%Y-%m-%d"),
                predicted_mean=float(row["predicted_mean"]),
                lower_95=float(row["lower_95"]),
                upper_95=float(row["upper_95"]),
                confidence_level=_confidence_level(idx + 1),
            )
        )
    return points


def _forecast_df_from_payload(payload: dict) -> pd.DataFrame:
    raw_points = payload.get("forecast", [])
    rows: list[dict[str, object]] = []
    for point in raw_points:
        try:
            rows.append(
                {
                    "date": pd.to_datetime(str(point["date"])),
                    "predicted_mean": float(point["predicted_mean"]),
                    "lower_95": float(point["lower_95"]),
                    "upper_95": float(point["upper_95"]),
                    "festival_score": float(point.get("festival_score", 0.0)),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return pd.DataFrame(rows)


def _load_or_compute_baseline(
    repo: "DataRepository",
    category: str,
    body: DiscountSimulationRequest,
) -> tuple[pd.DataFrame, dict]:
    last_upload_ts = repo.get_category_last_upload_timestamp(category)
    cached = repo.get_cached_forecast(
        category=category,
        n_days=body.n_days,
        current_inventory=body.current_inventory,
        lead_time_days=body.lead_time_days,
        supplier_pack_size=body.supplier_pack_size,
        max_age_seconds=3600,
    )
    if cached:
        generated_at: datetime | None = None
        raw_generated_at = cached.get("generated_at")
        if isinstance(raw_generated_at, str):
            try:
                generated_at = datetime.fromisoformat(raw_generated_at.replace("Z", "+00:00"))
            except ValueError:
                generated_at = None
        fresh_vs_upload = last_upload_ts is None or (
            generated_at is not None and generated_at >= last_upload_ts
        )
        if fresh_vs_upload and cached.get("forecast") and cached.get("decision"):
            cached_df = _forecast_df_from_payload(cached)
            if not cached_df.empty:
                return cached_df, dict(cached["decision"])

    baseline_df = forecast_next_n_days(repo=repo, category=category, n_days=body.n_days)
    baseline_decision = generate_inventory_decision_summary(
        forecast_df=baseline_df,
        current_inventory=body.current_inventory,
        lead_time_days=body.lead_time_days,
        supplier_pack_size=body.supplier_pack_size,
        last_upload_date=last_upload_ts.isoformat() if last_upload_ts else None,
    )
    cache_payload = {
        "category": category,
        "forecast": [
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "predicted_mean": float(row["predicted_mean"]),
                "lower_95": float(row["lower_95"]),
                "upper_95": float(row["upper_95"]),
                "festival_score": float(row.get("festival_score", 0.0)),
                "confidence_level": _confidence_level(idx + 1),
            }
            for idx, (_, row) in enumerate(baseline_df.iterrows())
        ],
        "decision": baseline_decision,
        "warnings": list(validate_forecast_output(baseline_df).get("warnings", [])),
        "n_days": int(body.n_days),
        "current_inventory": int(body.current_inventory),
        "lead_time_days": int(body.lead_time_days),
        "supplier_pack_size": int(max(1, body.supplier_pack_size)),
        "last_upload_date": last_upload_ts.isoformat() if last_upload_ts else None,
    }
    repo.save_forecast_cache(
        category=category,
        payload=cache_payload,
        generated_at=datetime.now(timezone.utc),
    )
    return baseline_df, baseline_decision


@router.post(
    "/simulate/discount/{category}",
    response_model=DiscountSimulationResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Category not found"},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid request"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)
@limiter.limit("15/minute")
async def simulate_discount(
    request: Request,
    category: str = Path(..., description="Product category for simulation", max_length=100),
    raw_body: dict | None = Body(default=None),
    repo: "DataRepository" = Depends(get_repo),
    _api_key: str = Depends(verify_api_key),
) -> DiscountSimulationResponse | JSONResponse:
    try:
        body = DiscountSimulationRequest.model_validate(raw_body or {})
    except ValidationError as exc:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()})
    skus = repo.get_skus_for_category(category)
    if not skus:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": "error", "message": f"Category '{category}' not found in database"},
        )

    try:
        baseline_df, baseline_decision = _load_or_compute_baseline(
            repo=repo,
            category=category,
            body=body,
        )

        simulated_df, simulation_meta = simulate_discounted_forecast(
            baseline_df=baseline_df,
            category=category,
            discount_percent=body.discount_percent,
            elasticity_mode=body.elasticity_mode,
        )
        simulated_decision = generate_inventory_decision_summary(
            forecast_df=simulated_df,
            current_inventory=body.current_inventory,
            lead_time_days=body.lead_time_days,
            supplier_pack_size=body.supplier_pack_size,
        )
        deltas = compute_simulation_deltas(
            baseline_df=baseline_df,
            baseline_decision=baseline_decision,
            simulated_df=simulated_df,
            simulated_decision=simulated_decision,
        )
        stability = compute_supply_stability_index(
            simulated_df=simulated_df,
            simulated_decision=simulated_decision,
            current_inventory=body.current_inventory,
            interval_scale=float(simulation_meta.get("interval_scale", 1.0)),
        )

        warnings = []
        warnings.extend(list(validate_forecast_output(baseline_df).get("warnings", [])))
        warnings.extend(list(validate_forecast_output(simulated_df).get("warnings", [])))
        warnings = sorted(set(warnings))

        explanation: str | None = None
        if body.include_explanation:
            explanation = generate_discount_simulation_explanation(
                category=category,
                discount_percent=body.discount_percent,
                elasticity_mode=body.elasticity_mode,
                baseline_decision=baseline_decision,
                simulated_decision=simulated_decision,
                delta=deltas,
                simulation_meta=simulation_meta,
            )

        return DiscountSimulationResponse(
            category=category,
            inputs=DiscountSimulationInputs(
                n_days=body.n_days,
                current_inventory=body.current_inventory,
                lead_time_days=body.lead_time_days,
                supplier_pack_size=body.supplier_pack_size,
                discount_percent=body.discount_percent,
                elasticity_mode=body.elasticity_mode,
            ),
            baseline=SimulationBlock(
                forecast=_serialize_forecast_points(baseline_df),
                decision=InventoryDecision(**baseline_decision),
            ),
            simulated=SimulationBlock(
                forecast=_serialize_forecast_points(simulated_df),
                decision=InventoryDecision(**simulated_decision),
            ),
            delta=SimulationDelta(**deltas),
            supply_stability_index=stability,
            explanation=explanation,
            warnings=warnings,
        )
    except ValueError:
        logger.exception("Simulation validation error for category=%s", category)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "Invalid simulation parameters."},
        )
    except Exception:
        logger.exception("Simulation failed for category=%s", category)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Simulation failed due to internal error."},
        )
