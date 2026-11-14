import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg


def test_concurrent_distinct_keys_cannot_oversell(client, reset_test_db):
    barrier = Barrier(2)

    def submit(key, customer_id):
        barrier.wait()
        return client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": key},
            json={
                "customer_id": customer_id,
                "items": [{"sku": "KIT-100", "quantity": 4}],
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(submit, "race-distinct-001", "CUST-A"),
            executor.submit(submit, "race-distinct-002", "CUST-B"),
        ]
        responses = [future.result(timeout=15) for future in futures]

    assert sorted(r.status_code for r in responses) == [202, 409]

    rejected = next(r for r in responses if r.status_code == 409)
    assert rejected.json()["error"]["code"] == "OUT_OF_STOCK"

    assert client.get("/api/v1/inventory/KIT-100").json()["available"] == 3

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        assert conn.execute("SELECT count(*) FROM orders").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
