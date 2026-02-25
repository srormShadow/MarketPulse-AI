"""Service layer for CSV ingestion into retail data models."""

from __future__ import annotations

import io
import logging

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.sales import Sales
from app.models.sku import SKU

logger = logging.getLogger(__name__)

SALES_REQUIRED_COLUMNS = {"date", "sku_id", "units_sold"}
SKU_REQUIRED_COLUMNS = {
    "sku_id",
    "product_name",
    "category",
    "mrp",
    "cost",
    "current_inventory",
}


class CsvIngestionError(Exception):
    """Raised when CSV ingestion fails due to file or semantic issues."""

    def __init__(
        self,
        message: str,
        *,
        validation_errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.validation_errors = validation_errors or []


async def ingest_csv(file: UploadFile, db: Session) -> tuple[str, int]:
    """Ingest a CSV upload as SKU master or Sales data."""

    csv_bytes = await file.read()
    if not csv_bytes:
        raise CsvIngestionError("Uploaded file is empty")

    try:
        dataframe = pd.read_csv(io.BytesIO(csv_bytes))
    except pd.errors.EmptyDataError as exc:
        raise CsvIngestionError("Uploaded file is empty") from exc
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise CsvIngestionError("Unable to parse CSV. File may be corrupted") from exc

    if dataframe.empty:
        raise CsvIngestionError("CSV contains no data rows")

    dataframe.columns = [str(column).strip().lower() for column in dataframe.columns]
    file_type = _detect_file_type(set(dataframe.columns))

    try:
        if file_type == "sales":
            inserted = _upsert_sales(dataframe, db)
        else:
            inserted = _upsert_skus(dataframe, db)
        db.commit()
    except CsvIngestionError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Unhandled ingestion failure")
        raise CsvIngestionError("Failed to ingest CSV data") from exc

    logger.info("CSV ingestion complete | file_type=%s | records_inserted=%s", file_type, inserted)
    return file_type, inserted


def _detect_file_type(columns: set[str]) -> str:
    missing_for_sales = SALES_REQUIRED_COLUMNS - columns
    missing_for_sku = SKU_REQUIRED_COLUMNS - columns

    if not missing_for_sku:
        return "sku"
    if not missing_for_sales:
        return "sales"

    messages = [
        {
            "field": "columns",
            "issue": (
                "Missing required columns for sales: "
                f"{sorted(missing_for_sales)}; for sku: {sorted(missing_for_sku)}"
            ),
        }
    ]
    raise CsvIngestionError("CSV does not match supported file schemas", validation_errors=messages)


def _upsert_skus(dataframe: pd.DataFrame, db: Session) -> int:
    frame = dataframe.copy()

    for column in ("sku_id", "product_name", "category"):
        frame[column] = frame[column].astype(str).str.strip()

    frame["mrp"] = pd.to_numeric(frame["mrp"], errors="coerce")
    frame["cost"] = pd.to_numeric(frame["cost"], errors="coerce")
    frame["current_inventory"] = pd.to_numeric(frame["current_inventory"], errors="coerce")
    inventory_non_integer = frame["current_inventory"].notna() & (frame["current_inventory"] % 1 != 0)

    invalid_mask = (
        frame["sku_id"].eq("")
        | frame["product_name"].eq("")
        | frame["category"].eq("")
        | frame["mrp"].isna()
        | frame["cost"].isna()
        | frame["current_inventory"].isna()
        | inventory_non_integer
    )
    valid_frame = frame.loc[~invalid_mask].copy()

    if valid_frame.empty:
        raise CsvIngestionError(
            "No valid SKU rows found after validation",
            validation_errors=[
                {"field": "rows", "issue": "All rows failed required field or data type checks"}
            ],
        )

    valid_frame["current_inventory"] = valid_frame["current_inventory"].astype(int)

    records = valid_frame[
        ["sku_id", "product_name", "category", "mrp", "cost", "current_inventory"]
    ].to_dict(orient="records")

    statement = sqlite_insert(SKU).values(records)
    upsert = statement.on_conflict_do_update(
        index_elements=[SKU.sku_id],
        set_={
            "product_name": statement.excluded.product_name,
            "category": statement.excluded.category,
            "mrp": statement.excluded.mrp,
            "cost": statement.excluded.cost,
            "current_inventory": statement.excluded.current_inventory,
        },
    )
    db.execute(upsert)
    return len(records)


def _upsert_sales(dataframe: pd.DataFrame, db: Session) -> int:
    frame = dataframe.copy()

    frame["sku_id"] = frame["sku_id"].astype(str).str.strip()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    frame["units_sold"] = pd.to_numeric(frame["units_sold"], errors="coerce")
    units_non_integer = frame["units_sold"].notna() & (frame["units_sold"] % 1 != 0)

    invalid_mask = (
        frame["sku_id"].eq("")
        | frame["date"].isna()
        | frame["units_sold"].isna()
        | units_non_integer
    )
    valid_frame = frame.loc[~invalid_mask].copy()

    if valid_frame.empty:
        raise CsvIngestionError(
            "No valid Sales rows found after validation",
            validation_errors=[
                {"field": "rows", "issue": "All rows failed required field or data type checks"}
            ],
        )

    valid_frame["units_sold"] = valid_frame["units_sold"].astype(int)

    existing_skus = {
        row[0]
        for row in db.execute(select(SKU.sku_id).where(SKU.sku_id.in_(valid_frame["sku_id"].unique().tolist())))
    }
    valid_frame = valid_frame.loc[valid_frame["sku_id"].isin(existing_skus)]

    if valid_frame.empty:
        raise CsvIngestionError(
            "No valid Sales rows reference known SKU IDs",
            validation_errors=[
                {"field": "sku_id", "issue": "Sales rows contain unknown SKU IDs"}
            ],
        )

    records = _sales_records(valid_frame)

    statement = sqlite_insert(Sales).values(records)
    upsert = statement.on_conflict_do_update(
        index_elements=[Sales.date, Sales.sku_id],
        set_={
            "units_sold": statement.excluded.units_sold,
        },
    )
    db.execute(upsert)
    return len(records)


def _sales_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Build normalized sales record dictionaries for bulk upsert."""

    return frame[["date", "sku_id", "units_sold"]].to_dict(orient="records")
