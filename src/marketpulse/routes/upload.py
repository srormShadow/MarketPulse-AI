"""CSV ingestion routes."""

import logging

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import JSONResponse

from marketpulse.core.config import get_settings
from marketpulse.core.rate_limit import limiter
from marketpulse.core.security import verify_api_key
from marketpulse.db.get_repo import get_repo

if TYPE_CHECKING:
    from marketpulse.db.repository import DataRepository
from marketpulse.schemas.upload import (
    CsvUploadResponse,
    ErrorResponse,
    ValidationErrorResponse,
)
from marketpulse.services.csv_ingestion import CsvIngestionError, ingest_csv

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
@limiter.limit("5/minute")
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    repo: "DataRepository" = Depends(get_repo),
    _api_key: str = Depends(verify_api_key),
) -> CsvUploadResponse | JSONResponse:
    """Upload SKU or Sales CSV and store it in the database."""

    if not file.filename or not file.filename.lower().endswith(".csv"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Validation failed",
                "errors": [{"field": "file", "issue": "Only .csv files are supported"}],
            },
        )

    # Validate MIME type
    if file.content_type and file.content_type not in (
        "text/csv",
        "application/octet-stream",
        "application/vnd.ms-excel",
    ):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "Validation failed",
                "errors": [{"field": "file", "issue": "Invalid file type. Only CSV files are supported."}],
            },
        )

    # Enforce file size limit
    settings = get_settings()
    max_bytes = settings.upload_max_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "status": "error",
                "message": f"File too large. Maximum size is {settings.upload_max_size_mb}MB.",
            },
        )

    try:
        file_type, inserted, metadata = await ingest_csv(file, repo, max_bytes=max_bytes)
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
