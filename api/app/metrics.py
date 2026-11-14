from prometheus_client import Counter, Histogram
orders_created = Counter("fulfillops_orders_created_total", "Orders created")
orders_failed  = Counter("fulfillops_orders_failed_total", "Order attempts failed", ["reason"])
worker_retries = Counter("fulfillops_worker_retries_total", "Worker retries")
http_requests  = Counter("fulfillops_http_requests_total", "HTTP requests", ["method", "route", "status"])
http_duration  = Histogram("fulfillops_http_request_duration_seconds", "Request duration", ["method", "route"])
