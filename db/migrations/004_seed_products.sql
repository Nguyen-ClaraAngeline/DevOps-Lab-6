-- Migration 002 was empty and may already be recorded as applied.
INSERT INTO products (sku, unit_price_cents, available) VALUES
    ('KIT-100',  1299,  7),
    ('PART-200',  599, 12),
    ('PACK-300',  249,  5)
ON CONFLICT (sku) DO NOTHING;
