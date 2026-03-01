"""CSV archival helper for ingestion workflows."""

from __future__ import annotations

from marketpulse.infrastructure.s3 import upload_csv


def archive_csv_upload(file_bytes: bytes, category: str, filename: str | None = None) -> str:
    """Persist uploaded CSV bytes to S3 and return the S3 URI."""
    return upload_csv(file=file_bytes, category=category, filename=filename)

