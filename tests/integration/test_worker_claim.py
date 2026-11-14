import importlib.util
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg

WORKER_PATH = Path(__file__).resolve().parents[2] / "worker" / "worker.py"

spec = importlib.util.spec_from_file_location("fulfillops_worker", WORKER_PATH)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

DATABASE_URL = os.environ["DATABASE_URL"]


def create_jobs(count):
    order_ids = [uuid.uuid4() for _ in range(count)]

    with psycopg.connect(DATABASE_URL) as conn:
        for order_id in order_ids:
            conn.execute(
                """
                INSERT INTO orders (id, customer_id, total_cents, status)
                VALUES (%s, %s, 1000, 'queued')
                """,
                (order_id, "CUST-TEST"),
            )
            conn.execute(
                """
                INSERT INTO jobs (order_id, state, attempts, max_attempts)
                VALUES (%s, 'queued', 0, 5)
                """,
                (order_id,),
            )

    return order_ids


def claim_job(worker_id):
    with psycopg.connect(DATABASE_URL) as conn:
        return conn.execute(
            worker.CLAIM_SQL,
            (worker_id, 30),
        ).fetchone()


def test_worker_claims_queued_job(client, reset_test_db):
    order_ids = create_jobs(1)

    result = claim_job("worker-test-1")

    assert result is not None
    assert result[0] == order_ids[0]
    assert result[1] == 1

    with psycopg.connect(DATABASE_URL) as conn:
        job = conn.execute(
            """
            SELECT state, locked_by, attempts
            FROM jobs WHERE order_id = %s
            """,
            (order_ids[0],),
        ).fetchone()

    assert job == ("processing", "worker-test-1", 1)


def test_two_workers_claim_different_jobs_concurrently(client, reset_test_db):
    order_ids = create_jobs(2)
    barrier = threading.Barrier(2)

    def concurrent_claim(worker_id):
        barrier.wait()
        return claim_job(worker_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(concurrent_claim, "worker-A"),
            executor.submit(concurrent_claim, "worker-B"),
        ]
        results = [future.result(timeout=10) for future in futures]

    claimed_ids = [result[0] for result in results if result is not None]

    assert len(claimed_ids) == 2
    assert len(set(claimed_ids)) == 2
    assert set(claimed_ids) == set(order_ids)

    with psycopg.connect(DATABASE_URL) as conn:
        jobs = conn.execute(
            """
            SELECT state, locked_by, attempts
            FROM jobs ORDER BY locked_by
            """
        ).fetchall()

    assert len(jobs) == 2
    assert all(job[0] == "processing" for job in jobs)
    assert all(job[2] == 1 for job in jobs)
    assert {job[1] for job in jobs} == {"worker-A", "worker-B"}
