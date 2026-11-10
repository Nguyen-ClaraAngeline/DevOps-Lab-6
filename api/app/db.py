import os
from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    os.environ["DATABASE_URL"],
    min_size=2, max_size=20, timeout=5,
    kwargs={"autocommit": True},
    open=False,
)