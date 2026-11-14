import uuid

import metrics
from errors import ApiError
from services.totals import calculate_total_cents

from db import pool


def lookup_prices(conn, skus):
    rows = conn.execute(
        "SELECT sku, unit_price_cents FROM products WHERE sku = ANY(%s)", (list(skus),)
    ).fetchall()
    prices = dict(rows)
    if len(prices) != len(set(skus)):
        raise ApiError(422, "INVALID_SKU", "Unknown SKU")
    return prices


def create_order(key, cid, agg, payload_hash):
    new_id = uuid.uuid4()
    with pool.connection() as conn:
        prices = lookup_prices(conn, agg)
        with conn.transaction():
            row = conn.execute(
                "INSERT INTO idempotency_keys(key, payload_hash, order_id) VALUES (%s,%s,%s) "
                "ON CONFLICT (key) DO NOTHING RETURNING key",
                (key, payload_hash, new_id),
            ).fetchone()
            if row is None:
                h, oid = conn.execute(
                    "SELECT payload_hash, order_id FROM idempotency_keys WHERE key=%s", (key,)
                ).fetchone()
                if h != payload_hash:
                    raise ApiError(
                        409,
                        "IDEMPOTENCY_CONFLICT",
                        "Idempotency key reused with a different payload",
                    )
                return oid
            for sku in sorted(agg):
                q = agg[sku]
                cur = conn.execute(
                    "UPDATE products SET available = available - %s WHERE sku = %s AND available >= %s",
                    (q, sku, q),
                )
                if cur.rowcount == 0:
                    raise ApiError(409, "OUT_OF_STOCK", "Not enough stock")

            total = calculate_total_cents(agg, prices)
            conn.execute(
                "INSERT INTO orders(id, customer_id, total_cents, status) VALUES (%s,%s,%s,'queued')",
                (new_id, cid, total),
            )
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO order_items(order_id, sku, quantity) VALUES (%s,%s,%s)",
                    [(new_id, s, q) for s, q in sorted(agg.items())],
                )
            conn.execute(
                "INSERT INTO jobs(order_id, state, attempts, max_attempts, next_run_at) VALUES (%s,'queued',0,5,now())",
                (new_id,),
            )
    metrics.orders_created.inc()
    return new_id
