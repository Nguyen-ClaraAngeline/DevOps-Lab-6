"""Run one Part 5 worker drill against a fresh disposable PostgreSQL container."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import psycopg

ROOT = Path(__file__).resolve().parents[1]
ORDER_SQL = """
SELECT o.status, j.state, j.attempts, j.max_attempts, j.locked_by, j.last_error
FROM orders o JOIN jobs j ON o.id = j.order_id WHERE o.id = %s
"""


def log(message):
    print(f"{datetime.now(UTC).isoformat()} {message}", flush=True)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def docker(*args):
    return subprocess.check_output(["docker", *args], cwd=ROOT, text=True, timeout=180).strip()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(label, check, timeout=35, processes=()):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for proc in processes:
            require(proc.poll() is None, f"Process {proc.pid} exited: {proc.returncode}")
        result = check()
        if result:
            return result
        time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for {label}")


def ready(url):
    try:
        with urlopen(url, timeout=1) as response:
            return response.status == 200
    except (URLError, TimeoutError):
        return False


def stop(proc):
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)


def start(stack, folder, name, args, env):
    path = folder / f"{name}.log"
    handle = stack.enter_context(path.open("wb"))
    proc = subprocess.Popen(
        [sys.executable, "-u", *args], cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT
    )
    stack.callback(stop, proc)
    log(f"Started {name} PID={proc.pid}")
    return proc, path


def events(path, order_id):
    result = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("order_id") == order_id:
            result.append(entry)
    return result


def metric_text(url):
    with urlopen(url, timeout=2) as response:
        return response.read().decode()


def submit(api, mode):
    body = json.dumps(
        {
            "customer_id": "CUST-POISON" if mode == "poison" else "CUST-CRASH",
            "items": [{"sku": "PACK-300", "quantity": 1}],
        }
    ).encode()
    request = Request(
        f"{api}/api/v1/orders",
        data=body,
        headers={"Content-Type": "application/json", "Idempotency-Key": f"part5-{uuid4()}"},
    )
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)
        require(response.status == 202 and payload["status"] == "queued", str(payload))
    log(f"Accepted order {payload['order_id']}")
    return payload["order_id"]


def run_workers(mode, stack, folder, conn, env, api):
    def worker(name, seconds, test_mode="0"):
        port = free_port()
        proc, path = start(
            stack,
            folder,
            name,
            ["worker/worker.py"],
            {
                **env,
                "WORKER_ID": name,
                "METRICS_PORT": str(port),
                "WORK_SECONDS": str(seconds),
                "TEST_MODE": test_mode,
                "POISON_CUSTOMER_ID": "CUST-POISON",
                "LEASE_SECONDS": "20",
                "POLL_SECONDS": "0.1",
                "BACKOFF_BASE_SECONDS": "0.25",
            },
        )
        url = f"http://127.0.0.1:{port}/metrics"
        wait_for(f"{name} metrics", lambda: ready(url), processes=(proc,))
        return proc, path, url

    def stock():
        return conn.execute("SELECT available FROM products WHERE sku='PACK-300'").fetchone()[0]

    initial_stock = stock()
    require(initial_stock == 5, f"Expected fresh PACK-300 stock of 5, found {initial_stock}")
    log(f"PACK-300 before submission: {initial_stock}")
    if mode == "crash":
        first, first_log, _ = worker("part5-slow", 15)
        order_id = submit(api, mode)
        wait_for(
            "first worker claim", lambda: events(first_log, order_id), timeout=5, processes=(first,)
        )
        recovery, recovery_log, metrics_url = worker("part5-recovery", 0.25)
        row = conn.execute(ORDER_SQL, (order_id,)).fetchone()
        require(
            row is not None and row[1:3] == ("processing", 1) and row[4] == "part5-slow",
            f"Expected slow worker to own attempt 1 before kill: {row}",
        )
        log(f"Before kill: {row}")
        log(f"Killing part5-slow PID={first.pid}; recovery worker already serving metrics")
        stop(first)
        log(f"Killed part5-slow; exit code={first.returncode}")
        paths = (first_log, recovery_log)
        expected = ("completed", "completed", 2, 5, None, None)
        expected_events = [
            ("part5-slow", "claimed", 1),
            ("part5-recovery", "claimed", 2),
            ("part5-recovery", "completed", None),
        ]
    else:
        recovery, path, metrics_url = worker("part5-poison", 0.1, "1")
        order_id = submit(api, mode)
        paths = (path,)
        expected = ("failed", "dead", 5, 5, None, "poison job (test mode)")
        expected_events = [
            ("part5-poison", event, attempt)
            for attempt in range(1, 6)
            for event in ("claimed", "failed")
        ]

    def observed_events():
        return [entry for path in paths for entry in events(path, order_id)]

    def event_keys():
        return [(e["worker"], e["event"], e.get("attempt")) for e in observed_events()]

    wait_for(
        "worker event sequence", lambda: event_keys() == expected_events, processes=(recovery,)
    )
    final = conn.execute(ORDER_SQL, (order_id,)).fetchone()
    require(final == expected, f"Unexpected final SQL row: {final}")
    require(stock() == initial_stock - 1, "Stock changed by more than one reservation")
    for entry in observed_events():
        log(json.dumps({**entry, "utc": datetime.fromtimestamp(entry["ts"], UTC).isoformat()}))
    log(f"Final SQL ({order_id}): {final}; PACK-300 available={stock()}")
    if mode == "poison":
        time.sleep(5)  # Longer than the next backoff would be with this drill's settings.
        require(conn.execute(ORDER_SQL, (order_id,)).fetchone() == final, "Final row changed")
        require(
            stock() == initial_stock - 1 and event_keys() == expected_events,
            "Job retried or stock changed",
        )
        log("Second SQL check: unchanged at 5/5 attempts; PACK-300 available=4")
    metrics = metric_text(metrics_url)
    expected_metric = (
        'fulfillops_worker_jobs_processed_total{result="completed"} 1.0'
        if mode == "crash"
        else "fulfillops_worker_retries_total 4.0"
    )
    require(expected_metric in metrics.splitlines(), f"Missing metric: {expected_metric}")
    log(expected_metric)
    log(f"PASS: {mode} drill")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("crash", "poison"))
    mode = parser.parse_args().mode
    name = f"fulfillops-drill-{uuid4().hex[:10]}"
    with tempfile.TemporaryDirectory(prefix="fulfillops-drill-") as directory, ExitStack() as stack:
        folder = Path(directory)
        docker(
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-p",
            "127.0.0.1::5432",
            "-e",
            "POSTGRES_USER=ci",
            "-e",
            "POSTGRES_PASSWORD=ci-throwaway",
            "-e",
            "POSTGRES_DB=fulfillops_test",
            "-v",
            f"{ROOT / 'db'}:/drill-db:ro",
            "postgres:16",
        )
        stack.callback(docker, "stop", name)
        port = docker("port", name, "5432/tcp").rsplit(":", 1)[1]
        url = f"postgresql://ci:ci-throwaway@127.0.0.1:{port}/fulfillops_test?connect_timeout=2"

        def connect():
            try:
                return psycopg.connect(url, autocommit=True)
            except psycopg.OperationalError:
                return None

        conn = stack.enter_context(wait_for("PostgreSQL", connect))
        docker(
            "exec",
            "-e",
            "PGHOST=127.0.0.1",
            "-e",
            "PGUSER=ci",
            "-e",
            "PGPASSWORD=ci-throwaway",
            "-e",
            "PGDATABASE=fulfillops_test",
            name,
            "sh",
            "-c",
            "ln -s /drill-db/migrations /migrations && sh /drill-db/migrate.sh && "
            "psql -v ON_ERROR_STOP=1 -f /drill-db/seed.sql",
        )
        env = {**os.environ, "DATABASE_URL": url}
        api_port = free_port()
        api = f"http://127.0.0.1:{api_port}"
        proc, _ = start(
            stack,
            folder,
            "api",
            [
                "-m",
                "uvicorn",
                "--app-dir",
                "api/app",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            env,
        )
        try:
            wait_for("API readiness", lambda: ready(f"{api}/health/ready"), processes=(proc,))
            run_workers(mode, stack, folder, conn, env, api)
        except (RuntimeError, OSError, psycopg.Error, ValueError):
            for path in sorted(folder.glob("*.log")):
                log(f"{path.name}:\n{path.read_text(encoding='utf-8', errors='replace')}")
            raise


if __name__ == "__main__":
    main()
