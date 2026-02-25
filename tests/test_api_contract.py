"""API contract tests for stable response shape and status codes."""


def test_health_endpoint_contract(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["timestamp"], str)


def test_upload_success_response_contract(client, csv_bytes):
    response = client.post(
        "/upload_csv",
        files={"file": ("sku_valid.csv", csv_bytes("sku_valid.csv"), "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"status", "records_inserted", "file_type"}
    assert payload["status"] == "success"


def test_upload_error_response_contract(client, csv_bytes):
    response = client.post(
        "/upload_csv",
        files={"file": ("sku_missing_column.csv", csv_bytes("sku_missing_column.csv"), "text/csv")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["message"] == "Validation failed"
    assert isinstance(payload["errors"], list)
    assert payload["errors"]
