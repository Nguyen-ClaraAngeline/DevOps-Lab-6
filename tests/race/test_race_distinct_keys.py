from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg
import os


def test_concurrent_requests_with_distinct_keys_create_both_orders(
    client, reset_test_db
):
    barrier = Barrier(2)

    def submit(key, customer_id):
        barrier.wait()
        return client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": key},
            json={
                "customer_id": customer_id,
                "items": [{"sku": "KIT-100", "quantity": 3}],
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(submit, "race-distinct-001", "CUST-A"),
            executor.submit(submit, "race-distinct-002", "CUST-B"),
        ]
        responses = [future.result(timeout=15) for future in futures]

    assert all(response.status_code == 202 for response in responses)

    order_ids = {
        response.json()["order_id"] for response in responses
    }
    assert len(order_ids) == 2

    assert client.get("/api/v1/inventory/KIT-100").json()["available"] == 1

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        order_count = conn.execute(
            "SELECT count(*) FROM orders"
        ).fetchone()[0]
        job_count = conn.execute(
            "SELECT count(*) FROM jobs"
        ).fetchone()[0]

    assert order_count == 2
    assert job_count == 2