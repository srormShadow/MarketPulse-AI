"""Pydantic schemas for CSV upload and API error responses."""

from typing import Literal

from pydantic import BaseModel, Field


class CsvUploadResponse(BaseModel):
    """Response schema for successful CSV ingestion."""

    status: Literal["success"] = "success"
    records_inserted: int = Field(ge=0)
    file_type: Literal["sales", "sku"]


class CsvUploadRequest(BaseModel):
    """Request metadata schema for CSV upload operations."""

    filename: str


class ErrorResponse(BaseModel):
    """Response schema for non-validation ingestion errors."""

    status: Literal["error"] = "error"
    message: str


class ValidationErrorItem(BaseModel):
    """Row or field-level validation error details."""

    field: str
    issue: str


class ValidationErrorResponse(BaseModel):
    """Response schema for validation-specific ingestion failures."""

    status: Literal["error"] = "error"
    message: str = "Validation failed"
    errors: list[ValidationErrorItem]
