"""CSV ingestion routes."""

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

router = APIRouter(tags=["ingestion"])


@router.post(
    "/upload_csv",
    response_model=CsvUploadResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ValidationErrorResponse},
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
            content={"status": "error", "message": "Only .csv files are supported"},
        )

    try:
        file_type, inserted = await ingest_csv(file, db)
    except CsvIngestionError as exc:
        if exc.validation_errors:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "status": "error",
                    "message": "Validation failed",
                    "errors": exc.validation_errors,
                },
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": exc.message},
        )

    return CsvUploadResponse(
        status="success",
        records_inserted=inserted,
        file_type=file_type,
    )
