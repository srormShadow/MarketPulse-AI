"""End-to-end integration test for MarketPulse AI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from boto3.dynamodb.conditions import Key
from fastapi.testclient import TestClient

from marketpulse.core.config import get_settings
from marketpulse.db.dynamo import get_dynamo_client, get_dynamo_resource
from marketpulse.db.dynamo_repository import DynamoRepository
from marketpulse.main import app
from marketpulse.services.forecasting import validate_forecast_output


REQUIRED_DECISION_FIELDS = {
    "recommended_action",
    "order_quantity",
    "reorder_point",
    "safety_stock",
    "risk_score",
    "festival_buffer_applied",
    "data_stale_warning",
    "pack_size_applied",
}
CATEGORIES = ["Snacks", "Staples", "Edible Oil"]


@dataclass
class StepResult:
    name: str
    passed: bool
    detail: str


def _assert_dynamo_available() -> None:
    settings = get_settings()
    if not settings.use_dynamo:
        pytest.skip("E2E test requires USE_DYNAMO=true")
    try:
        get_dynamo_client().list_tables()
    except Exception as exc:  # pragma: no cover - runtime infra check
        pytest.skip(f"DynamoDB is not reachable for E2E test: {exc}")


def _set_last_upload_days_ago(category: str, days_ago: int) -> None:
    resource = get_dynamo_resource()
    table = resource.Table("marketpulse_inventory")
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    response = table.query(KeyConditionExpression=Key("category").eq(category))
    for item in response.get("Items", []):
        table.update_item(
            Key={"category": item["category"], "sku_id": item["sku_id"]},
            UpdateExpression="SET last_upload_timestamp = :ts",
            ExpressionAttributeValues={":ts": ts},
        )


@pytest.mark.e2e
def test_marketpulse_end_to_end() -> None:
    os.environ.setdefault("MOCK_BEDROCK", "true")
    get_settings.cache_clear()
    _assert_dynamo_available()

    results: list[StepResult] = []
    repo = DynamoRepository()

    demo_sales_path = Path("data/demo_sales_365.csv")
    demo_sku_path = Path("data/demo_sku_master.csv")
    if not demo_sales_path.exists():
        pytest.fail("Missing fixture file: data/demo_sales_365.csv")
    if not demo_sku_path.exists():
        pytest.fail("Missing fixture file: data/demo_sku_master.csv")

    with TestClient(app) as client:
        # 1) Upload demo CSV(s) (SKU first so sales references exist)
        try:
            with demo_sku_path.open("rb") as f:
                sku_resp = client.post("/upload_csv", files={"file": ("demo_sku_master.csv", f, "text/csv")})
            with demo_sales_path.open("rb") as f:
                sales_resp = client.post("/upload_csv", files={"file": ("demo_sales_365.csv", f, "text/csv")})
            assert sku_resp.status_code == 200, sku_resp.text
            assert sales_resp.status_code == 200, sales_resp.text
            assert int(sales_resp.json().get("records_inserted", 0)) > 0
            results.append(StepResult("1. Upload demo CSV", True, "SKU and sales uploads succeeded"))
        except Exception as exc:
            results.append(StepResult("1. Upload demo CSV", False, str(exc)))

        # 2) Verify DynamoDB ingestion
        try:
            assert repo.count_sales() > 0
            for cat in CATEGORIES:
                assert len(repo.get_skus_for_category(cat)) > 0
            results.append(StepResult("2. Verify Dynamo ingestion", True, "Sales and SKU records found"))
        except Exception as exc:
            results.append(StepResult("2. Verify Dynamo ingestion", False, str(exc)))

        # 3 + 4) Trigger individual forecasts and validate structure/sanity
        individual: dict[str, dict] = {}
        try:
            for cat in CATEGORIES:
                payload = {
                    "n_days": 30,
                    "current_inventory": {"Snacks": 2800, "Staples": 5100, "Edible Oil": 1900}[cat],
                    "lead_time_days": {"Snacks": 5, "Staples": 7, "Edible Oil": 10}[cat],
                }
                resp = client.post(f"/forecast/{cat}", json=payload)
                assert resp.status_code == 200, resp.text
                body = resp.json()
                individual[cat] = body

                forecast = body["forecast"]
                decision = body["decision"]
                assert len(forecast) == 30
                assert REQUIRED_DECISION_FIELDS.issubset(set(decision.keys()))
                for row in forecast:
                    assert row.get("date")
                    mean = float(row["predicted_mean"])
                    lo = float(row["lower_95"])
                    hi = float(row["upper_95"])
                    assert mean >= 0 and lo >= 0 and hi >= 0
                    assert lo < mean < hi
            results.append(StepResult("3/4. Forecast + output validation", True, "All categories passed schema and sanity checks"))
        except Exception as exc:
            results.append(StepResult("3/4. Forecast + output validation", False, str(exc)))

        # 5) Batch forecast matches individual
        try:
            batch_resp = client.post(
                "/forecast/batch",
                json={
                    "categories": CATEGORIES,
                    "n_days": 30,
                    "inventory": {"Snacks": 2800, "Staples": 5100, "Edible Oil": 1900},
                    "lead_times": {"Snacks": 5, "Staples": 7, "Edible Oil": 10},
                },
            )
            assert batch_resp.status_code == 200, batch_resp.text
            batch_rows = {row["category"]: row for row in batch_resp.json()}
            assert set(batch_rows.keys()) == set(CATEGORIES)
            for cat in CATEGORIES:
                assert len(batch_rows[cat]["forecast"]) == len(individual[cat]["forecast"])
                assert batch_rows[cat]["decision"]["recommended_action"] == individual[cat]["decision"]["recommended_action"]
            results.append(StepResult("5. Batch forecast parity", True, "Batch and individual responses are consistent"))
        except Exception as exc:
            results.append(StepResult("5. Batch forecast parity", False, str(exc)))

        # 6) Bedrock insights endpoint
        try:
            for cat in CATEGORIES:
                insight_resp = client.post(
                    f"/insights/{cat}",
                    json={
                        "forecast_data": individual[cat]["forecast"],
                        "decision_data": individual[cat]["decision"],
                    },
                )
                assert insight_resp.status_code == 200, insight_resp.text
                insight = insight_resp.json().get("insight", "")
                assert isinstance(insight, str) and insight.strip()
                assert 100 <= len(insight) <= 500
            results.append(StepResult("6. Bedrock insights", True, "Insights returned with expected length"))
        except Exception as exc:
            results.append(StepResult("6. Bedrock insights", False, str(exc)))

        # 7) Verify DynamoDB forecast cache + recommendation logs
        try:
            for cat in CATEGORIES:
                decision = individual[cat]["decision"]
                cached = repo.get_cached_forecast(
                    category=cat,
                    n_days=30,
                    current_inventory={"Snacks": 2800, "Staples": 5100, "Edible Oil": 1900}[cat],
                    lead_time_days={"Snacks": 5, "Staples": 7, "Edible Oil": 10}[cat],
                    max_age_seconds=3600,
                )
                assert cached is not None
                rec = repo.get_cached_recommendation(
                    category=cat,
                    risk_score=float(decision["risk_score"]),
                    max_age_seconds=3600,
                )
                assert rec is not None
            results.append(StepResult("7. Dynamo logging/cache", True, "Forecast cache and recommendation logs found"))
        except Exception as exc:
            results.append(StepResult("7. Dynamo logging/cache", False, str(exc)))

        # 8) Data staleness flag
        try:
            _set_last_upload_days_ago("Snacks", days_ago=8)
            stale_resp = client.post(
                "/forecast/Snacks",
                json={"n_days": 30, "current_inventory": 2800, "lead_time_days": 5},
            )
            assert stale_resp.status_code == 200, stale_resp.text
            assert stale_resp.json().get("data_stale") is True
            results.append(StepResult("8. Data staleness", True, "data_stale=true returned for stale upload"))
        except Exception as exc:
            results.append(StepResult("8. Data staleness", False, str(exc)))

        # 9) Forecast sanity validator with all-zeros mock
        try:
            mock = pd.DataFrame(
                {
                    "predicted_mean": [0.0] * 30,
                    "lower_95": [0.0] * 30,
                    "upper_95": [0.0] * 30,
                }
            )
            validation = validate_forecast_output(mock)
            assert "model_collapse" in list(validation.get("warnings", []))
            results.append(StepResult("9. Forecast sanity validation", True, "model_collapse warning emitted"))
        except Exception as exc:
            results.append(StepResult("9. Forecast sanity validation", False, str(exc)))

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    print("\n=== MarketPulse E2E Summary ===")
    for r in results:
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name}: {r.detail}")
    print(f"Total: {passed} passed / {failed} failed")

    assert failed == 0, "One or more E2E validation steps failed"
