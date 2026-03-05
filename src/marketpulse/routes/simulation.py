"""Routes for on-demand discount simulation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Body, Depends, Path, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address

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
limiter = Limiter(key_func=get_remote_address)


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
        baseline_df = forecast_next_n_days(repo=repo, category=category, n_days=body.n_days)
        baseline_decision = generate_inventory_decision_summary(
            forecast_df=baseline_df,
            current_inventory=body.current_inventory,
            lead_time_days=body.lead_time_days,
            supplier_pack_size=body.supplier_pack_size,
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
