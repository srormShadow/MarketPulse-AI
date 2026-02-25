"""CSV ingestion routes."""

import logging

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.upload import (
    CsvUploadResponse,
    ErrorResponse,
    ValidationErrorResponse,
)
from app.services.csv_ingestion import CsvIngestionError, ingest_csv

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingestion"])


@router.post(
    "/upload_csv",
    response_model=CsvUploadResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ValidationErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> CsvUploadResponse | JSONResponse:
    """Upload SKU or Sales CSV and store it in SQLite."""

    if not file.filename or not file.filename.lower().endswith(".csv"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Validation failed",
                "errors": [{"field": "file", "issue": "Only .csv files are supported"}],
            },
        )

    try:
        file_type, inserted, metadata = await ingest_csv(file, db)
    except CsvIngestionError as exc:
        errors = exc.validation_errors or [{"field": "file", "issue": exc.message}]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Validation failed",
                "errors": errors,
            },
        )
    except Exception:
        logger.exception("Unhandled server error in /upload_csv")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "Internal server error"},
        )
    logger.info("Upload metadata | file_type=%s | details=%s", file_type, metadata)

    return CsvUploadResponse(
        status="success",
        records_inserted=inserted,
        file_type=file_type,
    )
