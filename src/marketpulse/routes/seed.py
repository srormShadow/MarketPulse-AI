"""Seed demo data endpoint for quick local testing."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from marketpulse.core.auth import require_admin
from marketpulse.core.config import get_settings
from marketpulse.db.get_repo import get_repo

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["seed"])

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
SKU_CSV = DATA_DIR / "demo_sku_master.csv"
SALES_CSV = DATA_DIR / "demo_sales_365.csv"


@router.post("/seed_demo")
def seed_demo(
    repo: "DataRepository" = Depends(get_repo),
    _admin: dict = Depends(require_admin),
) -> JSONResponse:
    """Load demo SKU + Sales CSVs into the database for quick testing."""
    if get_settings().environment.lower() in {"production", "prod"}:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"status": "error", "message": "Demo data seeding is disabled in production."},
        )

    if not SKU_CSV.exists() or not SALES_CSV.exists():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "status": "error",
                "message": (
                    "Demo CSV files not found. Please generate demo data first."
                ),
            },
        )

    try:
        # --- SKUs ---
        sku_df = pd.read_csv(SKU_CSV)
        sku_df.columns = [c.strip().lower() for c in sku_df.columns]
        sku_records = sku_df[
            ["sku_id", "product_name", "category", "mrp", "cost", "current_inventory"]
        ].to_dict(orient="records")
        repo.upsert_skus(sku_records)
        repo.commit()
        sku_count = len(sku_records)

        # --- Sales ---
        sales_df = pd.read_csv(SALES_CSV)
        sales_df.columns = [c.strip().lower() for c in sales_df.columns]
        sales_df["date"] = pd.to_datetime(sales_df["date"]).dt.date
        sales_records = sales_df[["date", "sku_id", "units_sold"]].to_dict(orient="records")
        repo.upsert_sales(sales_records)
        repo.commit()
        sales_count = len(sales_records)

        logger.info("Demo seed complete | skus=%s | sales=%s", sku_count, sales_count)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "skus_inserted": sku_count,
                "sales_inserted": sales_count,
            },
        )

    except Exception:
        repo.rollback()
        logger.exception("Demo seed failed")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Demo seed failed"},
        )


@router.post("/reseed_festivals")
def reseed_festivals_endpoint(
    repo: "DataRepository" = Depends(get_repo),
    _admin: dict = Depends(require_admin),
) -> JSONResponse:
    """Clear and reseed festival data with per-category uplift values."""
    from marketpulse.services.festival_seed import reseed_festivals

    if get_settings().environment.lower() in {"production", "prod"}:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"status": "error", "message": "Festival reseeding is disabled in production."},
        )

    try:
        count = reseed_festivals(repo)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "success", "festivals_inserted": count},
        )
    except Exception:
        logger.exception("Festival reseed failed")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Festival reseed failed"},
        )
