import argparse
import csv
import math
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

PATHS = (
    "/api/v1/catalog",
    "/api/v1/inventory/KIT-100",
    "/api/v1/inventory/PART-200",
    "/health/ready",
)


def main():
    parser = argparse.ArgumentParser(description="Measure API latency on a local lab stack")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", default="local-p95.csv")
    parser.add_argument("--samples", type=int, default=250)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    base = args.base_url.rstrip("/")
    rows = []
    for i in range(args.samples):
        path = PATHS[i % len(PATHS)]
        start = time.perf_counter()
        try:
            with urlopen(base + path, timeout=5) as response:
                status = response.status
                response.read()
        except HTTPError as exc:
            status = exc.code
        except (URLError, ConnectionError, TimeoutError):
            status = 0
        rows.append((path, status, (time.perf_counter() - start) * 1000))

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "status", "latency_ms"])
        writer.writerows(rows)
    latencies = sorted(ms for _, _, ms in rows)
    p95 = latencies[math.ceil(0.95 * len(latencies)) - 1]
    errors = sum(not 200 <= status < 300 for _, status, _ in rows)
    print(f"samples={len(rows)} errors={errors} p95={p95:.1f}ms output={args.output}")
    return int(errors != 0)


if __name__ == "__main__":
    raise SystemExit(main())
