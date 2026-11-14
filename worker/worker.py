import logging, os, socket, sys, time, json
import psycopg
from prometheus_client import CollectorRegistry, Counter, start_http_server

DATABASE_URL = os.environ["DATABASE_URL"]
WORKER_ID = os.getenv("WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")
LEASE_SECONDS = int(os.getenv("LEASE_SECONDS", "30"))
BACKOFF_BASE = float(os.getenv("BACKOFF_BASE_SECONDS", "2"))   # delay = base * 2^(attempts-1)
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "0.5"))
WORK_SECONDS = float(os.getenv("WORK_SECONDS", "1"))
TEST_MODE = os.getenv("TEST_MODE") == "1"
POISON_CUSTOMER_ID = os.getenv("POISON_CUSTOMER_ID", "CUST-POISON")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9100"))

WORKER_REGISTRY = CollectorRegistry()

worker_retries = Counter(
    "fulfillops_worker_retries_total",
    "Worker retries",
    registry=WORKER_REGISTRY,
)
jobs_processed = Counter(
    "fulfillops_worker_jobs_processed_total",
    "Jobs processed",
    ["result"],
    registry=WORKER_REGISTRY,
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger("worker")
def jlog(**kw): log.info(json.dumps({"ts": time.time(), "worker": WORKER_ID, **kw}))

CLAIM_SQL = """
UPDATE jobs SET state='processing', locked_by=%s,
       locked_until = now() + make_interval(secs => %s), attempts = attempts + 1
WHERE order_id = (
    SELECT order_id FROM jobs
    WHERE (state='queued' AND next_run_at <= now())
       OR (state='processing' AND locked_until < now() AND attempts < max_attempts)
    ORDER BY next_run_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1)
RETURNING order_id, attempts, max_attempts
"""

# expired lease with no attempts left -> dead letter
REAP_SQL = """
WITH dead AS (
    UPDATE jobs SET state='dead', locked_by=NULL, locked_until=NULL,
           last_error='lease expired, max attempts reached'
    WHERE state='processing' AND locked_until < now() AND attempts >= max_attempts
    RETURNING order_id)
UPDATE orders SET status='failed' WHERE id IN (SELECT order_id FROM dead) AND status <> 'completed'
"""

def process(conn, order_id):
    cid = conn.execute("SELECT customer_id FROM orders WHERE id=%s", (order_id,)).fetchone()[0]
    time.sleep(WORK_SECONDS)                         # simulated fulfilment work
    if TEST_MODE and cid == POISON_CUSTOMER_ID:      # deterministic poison job
        raise RuntimeError("poison job (test mode)")

OWNED_CLAIM = """
WHERE order_id=%s AND state='processing' AND locked_by=%s AND attempts=%s
  AND locked_until > clock_timestamp()
"""


def complete(conn, order_id, attempts):
    with conn.transaction():                         # order + job in ONE transaction
        job = conn.execute(
            "UPDATE jobs SET state='completed', locked_by=NULL, locked_until=NULL, last_error=NULL "
            + OWNED_CLAIM, (order_id, WORKER_ID, attempts),
        )
        if job.rowcount == 0:
            return False
        conn.execute("UPDATE orders SET status='completed' WHERE id=%s AND status <> 'completed'", (order_id,))
    return True

def fail(conn, order_id, attempts, max_attempts, err):
    msg = str(err)[:500]
    claim = (order_id, WORKER_ID, attempts)
    exhausted = attempts >= max_attempts
    with conn.transaction():
        if exhausted:
            job = conn.execute(
                "UPDATE jobs SET state='dead', locked_by=NULL, locked_until=NULL, last_error=%s "
                + OWNED_CLAIM, (msg, *claim),
            )
        else:                                        # NO restock on failure
            delay = BACKOFF_BASE * (2 ** (attempts - 1))
            job = conn.execute(
                "UPDATE jobs SET state='queued', locked_by=NULL, locked_until=NULL, last_error=%s, "
                "next_run_at = now() + make_interval(secs => %s) "
                + OWNED_CLAIM, (msg, delay, *claim),
            )
        if job.rowcount == 0:
            return False
        if exhausted:
            conn.execute("UPDATE orders SET status='failed' WHERE id=%s AND status <> 'completed'", (order_id,))
    if exhausted:
        jobs_processed.labels("dead").inc()
    else:
        worker_retries.inc()
        jobs_processed.labels("retry").inc()
    return True

def main():
    start_http_server(METRICS_PORT, registry=WORKER_REGISTRY)
    jlog(event="started", lease=LEASE_SECONDS, test_mode=TEST_MODE)
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        while True:
            conn.execute(REAP_SQL)
            row = conn.execute(CLAIM_SQL, (WORKER_ID, LEASE_SECONDS)).fetchone()
            if row is None:
                time.sleep(POLL_SECONDS); continue
            order_id, attempts, max_attempts = row
            jlog(event="claimed", order_id=str(order_id), attempt=attempts)
            try:
                process(conn, order_id)
            except Exception as e:
                if fail(conn, order_id, attempts, max_attempts, e):
                    jlog(event="failed", order_id=str(order_id), attempt=attempts, error=str(e))
                    continue
            else:
                if complete(conn, order_id, attempts):
                    jobs_processed.labels("completed").inc()
                    jlog(event="completed", order_id=str(order_id))
                    continue
            jlog(event="lease_lost", order_id=str(order_id), attempt=attempts)

if __name__ == "__main__":
    main()
