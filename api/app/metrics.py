from prometheus_client import Counter, Histogram

http_requests = Counter(
    "fulfillops_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
http_duration = Histogram(
    "fulfillops_http_request_duration_seconds", "HTTP request latency (s)", ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
orders_created = Counter("fulfillops_orders_created_total", "Orders accepted")
orders_failed = Counter("fulfillops_orders_failed_total", "Orders rejected or failed", ["code"])
worker_retries = Counter("fulfillops_worker_retries_total", "Worker retries")