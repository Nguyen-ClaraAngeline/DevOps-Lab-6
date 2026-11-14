import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg


def test_concurrent_requests_with_same_key_create_one_order(client, reset_test_db):
    request_count = 8
    payload = {
        "customer_id": "CUST-RACE",
        "items": [{"sku": "KIT-100", "quantity": 1}],
    }

    barrier = Barrier(request_count, timeout=10)

    def submit():
        barrier.wait()
        return client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": "race-same-key-001"},
            json=payload,
        )

    with ThreadPoolExecutor(max_workers=request_count) as executor:
        futures = [executor.submit(submit) for _ in range(request_count)]
        responses = [future.result(timeout=15) for future in futures]

    assert all(response.status_code == 202 for response in responses)
    assert all(response.json()["status"] == "queued" for response in responses)

    order_ids = {response.json()["order_id"] for response in responses}
    assert len(order_ids) == 1

    assert client.get("/api/v1/inventory/KIT-100").json()["available"] == 6

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        assert [str(row[0]) for row in conn.execute("SELECT id FROM orders")] == list(order_ids)
        assert [str(row[0]) for row in conn.execute("SELECT order_id FROM jobs")] == list(order_ids)
