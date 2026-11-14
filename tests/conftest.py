import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest

API_APP = Path(__file__).resolve().parents[1] / "api" / "app"
sys.path.insert(0, str(API_APP))

TEST_DATABASE_URL = (
    os.environ.get("TEST_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or "postgresql://ci:ci-throwaway@localhost:5432/fulfillops_test"
)

if urlparse(TEST_DATABASE_URL).path != "/fulfillops_test":
    raise RuntimeError("Tests must use the dedicated fulfillops_test database.")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL


@pytest.fixture
def reset_test_db():
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        conn.execute("""
            TRUNCATE TABLE
                jobs,
                order_items,
                orders,
                idempotency_keys
            CASCADE
        """)

        conn.execute("""
            INSERT INTO products (sku, unit_price_cents, available)
            VALUES
                ('KIT-100', 1299, 7),
                ('PART-200', 599, 12),
                ('PACK-300', 249, 5)
            ON CONFLICT (sku) DO UPDATE SET
                unit_price_cents = EXCLUDED.unit_price_cents,
                available = EXCLUDED.available
        """)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as test_client:
        yield test_client
