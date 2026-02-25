"""Performance-like ingestion tests for non-functional stability checks."""

from time import perf_counter


def test_ingestion_time_for_1000_rows_under_threshold(client):
    rows = [
        "sku_id,product_name,category,mrp,cost,current_inventory",
    ]
    for idx in range(1000):
        rows.append(f"SKU_PERF_{idx},Perf {idx},Perf,100,70,{idx}")

    payload = ("\n".join(rows) + "\n").encode("utf-8")

    start = perf_counter()
    response = client.post("/upload_csv", files={"file": ("sku_perf.csv", payload, "text/csv")})
    elapsed = perf_counter() - start

    assert response.status_code == 200
    assert response.json()["records_inserted"] == 1000
    assert elapsed < 5.0
