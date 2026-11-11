from prometheus_client import Counter, Histogram

http_requests = Counter(
    "fulfillops_http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status"],
)

http_duration = Histogram(
    "fulfillops_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
)

orders_created = Counter(
    "fulfillops_orders_created_total",
    "Total orders successfully created",
)

orders_failed = Counter(
    "fulfillops_orders_failed_total",
    "Total orders rejected",
    ["error_code"],
)