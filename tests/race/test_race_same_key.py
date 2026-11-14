from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg


def test_concurrent_requests_with_same_key_create_one_order(client, reset_test_db):
    payload = {
        "customer_id": "CUST-RACE",
        "items": [{"sku": "KIT-100", "quantity": 2}],
    }

    barrier = Barrier(2)

    def submit():
        barrier.wait()
        return client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": "race-same-key-001"},
            json=payload,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit) for _ in range(2)]
        responses = [future.result(timeout=15) for future in futures]

    assert all(response.status_code == 202 for response in responses)

    order_ids = {response.json()["order_id"] for response in responses}
    assert len(order_ids) == 1

    assert client.get("/api/v1/inventory/KIT-100").json()["available"] == 5

    with psycopg.connect(__import__("os").environ["DATABASE_URL"]) as conn:
        order_count = conn.execute("SELECT count(*) FROM orders").fetchone()[0]
        job_count = conn.execute("SELECT count(*) FROM jobs").fetchone()[0]

    assert order_count == 1
    assert job_count == 1
