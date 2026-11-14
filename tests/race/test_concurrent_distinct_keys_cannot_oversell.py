import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg


def test_concurrent_distinct_keys_cannot_oversell(client, reset_test_db):
    request_count = 12
    stock = client.get("/api/v1/inventory/KIT-100").json()["available"]
    assert stock == 7
    barrier = Barrier(request_count, timeout=10)

    def submit(key, customer_id):
        barrier.wait()
        return client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": key},
            json={
                "customer_id": customer_id,
                "items": [{"sku": "KIT-100", "quantity": 1}],
            },
        )

    with ThreadPoolExecutor(max_workers=request_count) as executor:
        futures = [
            executor.submit(submit, f"race-distinct-{i:03}", f"CUST-{i}")
            for i in range(request_count)
        ]
        responses = [future.result(timeout=15) for future in futures]

    assert sorted(r.status_code for r in responses) == [202] * stock + [409] * (
        request_count - stock
    )
    accepted_ids = {r.json()["order_id"] for r in responses if r.status_code == 202}
    assert len(accepted_ids) == stock
    assert all(
        r.json()["error"]["code"] == "OUT_OF_STOCK" for r in responses if r.status_code == 409
    )

    assert client.get("/api/v1/inventory/KIT-100").json()["available"] == 0

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        assert {str(row[0]) for row in conn.execute("SELECT id FROM orders")} == accepted_ids
        assert {str(row[0]) for row in conn.execute("SELECT order_id FROM jobs")} == accepted_ids
