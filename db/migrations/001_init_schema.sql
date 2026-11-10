CREATE TABLE IF NOT EXISTS products (
    sku               TEXT PRIMARY KEY,
    unit_price_cents  INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    available         INTEGER NOT NULL CHECK (available >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    id           UUID PRIMARY KEY,
    customer_id  TEXT NOT NULL CHECK (char_length(customer_id) BETWEEN 1 AND 64),
    total_cents  BIGINT NOT NULL CHECK (total_cents >= 0),
    status       TEXT NOT NULL DEFAULT 'queued'
                 CHECK (status IN ('queued','processing','completed','failed')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id  UUID    NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sku       TEXT    NOT NULL REFERENCES products(sku),
    quantity  INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 20),
    PRIMARY KEY (order_id, sku)
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key           TEXT PRIMARY KEY CHECK (char_length(key) BETWEEN 8 AND 128),
    payload_hash  TEXT NOT NULL,
    order_id      UUID REFERENCES orders(id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS jobs (
    order_id      UUID PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
    state         TEXT NOT NULL DEFAULT 'queued'
                  CHECK (state IN ('queued','processing','completed','dead')),
    attempts      INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts  INTEGER NOT NULL DEFAULT 5 CHECK (max_attempts >= 1),
    locked_by     TEXT,
    locked_until  TIMESTAMPTZ,
    next_run_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error    TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_claim ON jobs (state, next_run_at);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders (customer_id);