"""Service layer for CSV ingestion into retail data models."""

from __future__ import annotations

import io
import logging
import re
from dataclasses import asdict, dataclass

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.sales import Sales
from app.models.sku import SKU

logger = logging.getLogger(__name__)

EXPECTED_SCHEMA_VERSION = "1.0"
SALES_REQUIRED_COLUMNS = {"date", "sku_id", "units_sold"}
SKU_REQUIRED_COLUMNS = {
    "sku_id",
    "product_name",
    "category",
    "mrp",
    "cost",
    "current_inventory",
}
HIDDEN_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f\u200b-\u200f\ufeff]")


@dataclass
class IngestionMetrics:
    """Structured metadata for ingestion cleanup and quality signals."""

    rows_received: int = 0
    rows_cleaned: int = 0
    duplicates_removed: int = 0
    invalid_rows_dropped: int = 0
    outliers_detected: int = 0


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


async def ingest_csv(file: UploadFile, db: Session) -> tuple[str, int, dict[str, int]]:
    """Ingest a CSV upload as SKU master or Sales data."""

    csv_bytes = await file.read()
    if not csv_bytes:
        raise CsvIngestionError(
            "Uploaded file is empty",
            validation_errors=[{"field": "file", "issue": "Uploaded file is empty"}],
        )

    try:
        dataframe = pd.read_csv(io.BytesIO(csv_bytes))
    except pd.errors.EmptyDataError as exc:
        raise CsvIngestionError(
            "Uploaded file is empty",
            validation_errors=[{"field": "file", "issue": "Uploaded file is empty"}],
        ) from exc
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise CsvIngestionError(
            "Unable to parse CSV. File may be corrupted",
            validation_errors=[{"field": "file", "issue": "Unable to parse CSV. File may be corrupted"}],
        ) from exc

    if dataframe.empty:
        raise CsvIngestionError(
            "CSV contains no data rows",
            validation_errors=[{"field": "rows", "issue": "CSV contains no data rows"}],
        )

    dataframe.columns = [str(column).strip().lower() for column in dataframe.columns]
    file_type = _detect_file_type(set(dataframe.columns))
    _validate_schema_version(dataframe)

    metrics = IngestionMetrics(rows_received=len(dataframe))

    try:
        if file_type == "sales":
            inserted = _upsert_sales(dataframe, db, metrics)
        else:
            inserted = _upsert_skus(dataframe, db, metrics)
        db.commit()
    except CsvIngestionError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Unhandled ingestion failure")
        raise

    metadata = asdict(metrics)
    logger.info(
        "CSV ingestion complete | file_type=%s | records_inserted=%s | metadata=%s",
        file_type,
        inserted,
        metadata,
    )
    return file_type, inserted, metadata


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


def _validate_schema_version(dataframe: pd.DataFrame) -> None:
    if "schema_version" not in dataframe.columns:
        return

    normalized = (
        dataframe["schema_version"]
        .dropna()
        .astype(str)
        .str.strip()
    )
    normalized = normalized[normalized.ne("")]
    if normalized.empty:
        return

    invalid = normalized[normalized.ne(EXPECTED_SCHEMA_VERSION)]
    if not invalid.empty:
        raise CsvIngestionError(
            "Invalid schema version",
            validation_errors=[
                {
                    "field": "schema_version",
                    "issue": f"Expected schema_version '{EXPECTED_SCHEMA_VERSION}'",
                }
            ],
        )


def _clean_hidden_chars(value: str) -> str:
    return HIDDEN_CHAR_PATTERN.sub("", value)


def _normalize_sku_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .map(_clean_hidden_chars)
        .str.strip()
        .str.upper()
    )


def _normalize_text_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .map(_clean_hidden_chars)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def _drop_exact_duplicates(frame: pd.DataFrame, metrics: IngestionMetrics) -> pd.DataFrame:
    before = len(frame)
    deduped = frame.drop_duplicates(keep="last")
    removed = before - len(deduped)
    metrics.duplicates_removed += removed
    if removed > 0:
        logger.info("Exact duplicate rows removed | count=%s", removed)
    return deduped


def _upsert_skus(dataframe: pd.DataFrame, db: Session, metrics: IngestionMetrics) -> int:
    frame = _drop_exact_duplicates(dataframe.copy(), metrics)

    frame["sku_id"] = _normalize_sku_series(frame["sku_id"])
    frame["product_name"] = _normalize_text_series(frame["product_name"])
    frame["category"] = _normalize_text_series(frame["category"]).str.title()

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
        | frame["current_inventory"].lt(0)
        | frame["cost"].ge(frame["mrp"])
    )

    dropped_invalid = int(invalid_mask.sum())
    metrics.invalid_rows_dropped += dropped_invalid
    if dropped_invalid > 0:
        logger.warning(
            "Invalid SKU rows dropped | count=%s | rules=[current_inventory>=0,cost<mrp,types]",
            dropped_invalid,
        )

    valid_frame = frame.loc[~invalid_mask].copy()
    if valid_frame.empty:
        raise CsvIngestionError(
            "No valid SKU rows found after validation",
            validation_errors=[
                {"field": "rows", "issue": "All rows failed required field, value, or data type checks"}
            ],
        )

    valid_frame["current_inventory"] = valid_frame["current_inventory"].astype(int)

    before_logical = len(valid_frame)
    valid_frame = valid_frame.drop_duplicates(subset=["sku_id"], keep="last")
    removed_logical = before_logical - len(valid_frame)
    metrics.duplicates_removed += removed_logical
    if removed_logical > 0:
        logger.info("Logical SKU duplicates removed | count=%s", removed_logical)

    metrics.rows_cleaned = len(valid_frame)

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


def _upsert_sales(dataframe: pd.DataFrame, db: Session, metrics: IngestionMetrics) -> int:
    frame = _drop_exact_duplicates(dataframe.copy(), metrics)

    frame["sku_id"] = _normalize_sku_series(frame["sku_id"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    frame["units_sold"] = pd.to_numeric(frame["units_sold"], errors="coerce")

    units_non_integer = frame["units_sold"].notna() & (frame["units_sold"] % 1 != 0)
    invalid_mask = (
        frame["sku_id"].eq("")
        | frame["date"].isna()
        | frame["units_sold"].isna()
        | units_non_integer
        | frame["units_sold"].lt(0)
    )

    dropped_invalid = int(invalid_mask.sum())
    metrics.invalid_rows_dropped += dropped_invalid
    if dropped_invalid > 0:
        logger.warning("Invalid Sales rows dropped | count=%s | rules=[units_sold>=0,types]", dropped_invalid)

    valid_frame = frame.loc[~invalid_mask].copy()
    if valid_frame.empty:
        raise CsvIngestionError(
            "No valid Sales rows found after validation",
            validation_errors=[
                {"field": "rows", "issue": "All rows failed required field, value, or data type checks"}
            ],
        )

    valid_frame["units_sold"] = valid_frame["units_sold"].astype(int)

    before_logical = len(valid_frame)
    valid_frame = valid_frame.drop_duplicates(subset=["date", "sku_id"], keep="last")
    removed_logical = before_logical - len(valid_frame)
    metrics.duplicates_removed += removed_logical
    if removed_logical > 0:
        logger.info("Logical Sales duplicates removed | count=%s", removed_logical)

    existing_skus = {
        row[0]
        for row in db.execute(select(SKU.sku_id).where(SKU.sku_id.in_(valid_frame["sku_id"].unique().tolist())))
    }
    unknown_sku_mask = ~valid_frame["sku_id"].isin(existing_skus)
    unknown_dropped = int(unknown_sku_mask.sum())
    if unknown_dropped > 0:
        metrics.invalid_rows_dropped += unknown_dropped
        logger.warning("Sales rows dropped due to unknown SKU IDs | count=%s", unknown_dropped)

    valid_frame = valid_frame.loc[~unknown_sku_mask].copy()
    if valid_frame.empty:
        raise CsvIngestionError(
            "No valid Sales rows reference known SKU IDs",
            validation_errors=[
                {"field": "sku_id", "issue": "Sales rows contain unknown SKU IDs"}
            ],
        )

    outlier_count = _log_sales_outliers(valid_frame)
    metrics.outliers_detected += outlier_count
    metrics.rows_cleaned = len(valid_frame)

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


def _log_sales_outliers(frame: pd.DataFrame) -> int:
    """Log IQR-based extreme outliers without dropping records."""

    if len(frame) < 4:
        return 0

    q1 = float(frame["units_sold"].quantile(0.25))
    q3 = float(frame["units_sold"].quantile(0.75))
    iqr = q3 - q1
    upper_bound = q3 + (3.0 * iqr)

    outliers = frame.loc[frame["units_sold"] > upper_bound]
    if outliers.empty:
        return 0

    logger.warning(
        "Sales outliers detected via IQR | count=%s | threshold=%.2f",
        len(outliers),
        upper_bound,
    )
    for _, row in outliers.iterrows():
        logger.warning(
            "Outlier row | sku_id=%s | date=%s | units_sold=%s",
            row["sku_id"],
            row["date"],
            row["units_sold"],
        )
    return int(len(outliers))


def _sales_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Build normalized sales record dictionaries for bulk upsert."""

    return frame[["date", "sku_id", "units_sold"]].to_dict(orient="records")
