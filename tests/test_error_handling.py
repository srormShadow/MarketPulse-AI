"""Error-path tests ensuring upload endpoint handles server failures cleanly."""

import logging

import app.routes.upload as upload_route


async def _raise_runtime_error(file, db):  # noqa: ARG001
    raise RuntimeError("simulated database failure")


def test_upload_returns_500_and_logs_when_ingestion_fails(client, caplog, monkeypatch, csv_bytes):
    monkeypatch.setattr(upload_route, "ingest_csv", _raise_runtime_error)
    caplog.set_level(logging.ERROR)

    response = client.post(
        "/upload_csv",
        files={"file": ("sku_valid.csv", csv_bytes("sku_valid.csv"), "text/csv")},
    )

    assert response.status_code == 500
    assert response.json() == {"status": "error", "message": "Internal server error"}
    assert "Unhandled server error in /upload_csv" in caplog.text
