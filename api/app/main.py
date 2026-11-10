import json, logging, sys, time, uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.exceptions import HTTPException as StarletteHTTPException
from psycopg_pool import PoolTimeout
import psycopg

from db import pool
from errors import ApiError
from validation import parse_order
import orders, metrics

REQUIRED_MIGRATION = "001"   # must match your migration tracking table

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger("fulfillops")

@asynccontextmanager
async def lifespan(app):
    pool.open(wait=False); yield; pool.close()

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

def err(status, code, msg):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": msg}})

@app.exception_handler(ApiError)
async def _api(request, exc): return err(exc.status, exc.code, exc.message)

@app.exception_handler(StarletteHTTPException)
async def _http(request, exc):
    return err(exc.status_code, "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR", "Request could not be served")

@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except (PoolTimeout, psycopg.OperationalError):
        response = err(503, "SERVICE_UNAVAILABLE", "Service temporarily unavailable")
    except Exception:
        log.exception("unhandled")
        response = err(500, "INTERNAL_ERROR", "Internal error")
    route = getattr(request.scope.get("route"), "path", "unmatched")
    dur = time.perf_counter() - start
    metrics.http_requests.labels(request.method, route, str(response.status_code)).inc()
    metrics.http_duration.labels(request.method, route).observe(dur)
    log.info(json.dumps({"ts": time.time(), "level": "info", "method": request.method, "route": route,
                         "status": response.status_code, "duration_ms": round(dur * 1000, 1)}))
    return response

@app.get("/health/live")
def live(): return {"status": "ok"}

@app.get("/health/ready")
def ready():
    try:
        with pool.connection() as c:
            c.execute("SELECT 1")
            ok = c.execute("SELECT 1 FROM schema_migrations WHERE version=%s", (REQUIRED_MIGRATION,)).fetchone()
        if not ok: raise RuntimeError
    except Exception:
        return err(503, "NOT_READY", "Service not ready")
    return {"status": "ready"}

@app.get("/api/v1/catalog")
def catalog():
    with pool.connection() as c:
        rows = c.execute("SELECT sku, unit_price_cents, available FROM products ORDER BY sku").fetchall()
    return {"products": [{"sku": s, "unit_price_cents": p, "available": a} for s, p, a in rows]}

@app.get("/api/v1/inventory/{sku}")
def inventory(sku: str):
    with pool.connection() as c:
        r = c.execute("SELECT sku, available FROM products WHERE sku=%s", (sku,)).fetchone()
    if not r: raise ApiError(404, "SKU_NOT_FOUND", "SKU not found")
    return {"sku": r[0], "available": r[1]}

@app.get("/api/v1/orders/{order_id}")
def get_order(order_id: str):
    try: oid = uuid.UUID(order_id)
    except ValueError: raise ApiError(404, "ORDER_NOT_FOUND", "Order not found")
    with pool.connection() as c:
        o = c.execute("SELECT id, customer_id, total_cents, status, created_at FROM orders WHERE id=%s", (oid,)).fetchone()
        if not o: raise ApiError(404, "ORDER_NOT_FOUND", "Order not found")
        items = c.execute("SELECT sku, quantity FROM order_items WHERE order_id=%s ORDER BY sku", (oid,)).fetchall()
    return {"order_id": str(o[0]), "customer_id": o[1], "total_cents": o[2], "status": o[3],
            "created_at": o[4].isoformat(), "items": [{"sku": s, "quantity": q} for s, q in items]}

def _handle_order(key, raw):
    try:
        cid, agg, h = parse_order(key, raw)
        oid = orders.create_order(key, cid, agg, h)
    except ApiError as e:
        metrics.orders_failed.labels(e.code).inc()
        raise
    return {"order_id": str(oid), "status": "queued"}

@app.post("/api/v1/orders", status_code=202)
async def post_order(request: Request):
    raw = await request.body()
    return await run_in_threadpool(_handle_order, request.headers.get("Idempotency-Key"), raw)

@app.get("/metrics")
def prom(): return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)