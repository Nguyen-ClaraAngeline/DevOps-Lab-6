# FulfillOps test evidence

Part 4 verifies input validation, order acceptance, stock reservation under concurrent requests, and worker job claiming. The local PostgreSQL run passed **53 tests** after switching the FastAPI test client dependency to `httpx2`.

| Test layer | What it checks |
| --- | --- |
| [Unit](unit/) | Request validation, duplicate SKU normalization, and order totals. |
| [Integration](integration/) | API health and readiness, transactional reservation and rollback, and concurrent worker claims. |
| [Race](race/) | Two requests sharing an idempotency key create one order. Two distinct keys competing for seven units (four per request) produce one accepted order, one `OUT_OF_STOCK` response, and three units left. These tests use one API instance. |
| [Regression](regression/test_red_to_green.py) | Duplicate lines for the same SKU are combined before reserving stock and calculating the total. |

## Reproduce the local run

Use a fresh, isolated database named `fulfillops_test`. The fixtures reset order data and seed stock, so never give them access to a shared or production database. Run the commands from the repository root with Docker Desktop running.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r api/requirements.txt -r worker/requirements.txt

docker run -d --rm --name fulfillops-pytest `
  -p 127.0.0.1:15432:5432 `
  -e POSTGRES_USER=ci -e POSTGRES_PASSWORD=ci-throwaway -e POSTGRES_DB=fulfillops_test `
  -v "${PWD}/db/migrations:/migrations:ro" `
  -v "${PWD}/db/migrate.sh:/migrate.sh:ro" `
  postgres:16

docker exec fulfillops-pytest pg_isready -h 127.0.0.1 -U ci -d fulfillops_test
```

Wait until `pg_isready` reports `accepting connections`, then migrate and run the suite:

```powershell
docker exec -e PGHOST=127.0.0.1 -e PGUSER=ci -e PGPASSWORD=ci-throwaway -e PGDATABASE=fulfillops_test fulfillops-pytest sh /migrate.sh
$env:TEST_DATABASE_URL = 'postgresql://ci:ci-throwaway@127.0.0.1:15432/fulfillops_test'
.venv\Scripts\python.exe -m pytest tests -q
```

Keep the container running for the regression exercise below. When finished, stop it with `docker stop fulfillops-pytest` and clear the shell variable with `Remove-Item Env:TEST_DATABASE_URL`.

## Red to green regression evidence

Run the regression test once to establish the passing baseline. In [validation.py](../api/app/validation.py), temporarily replace `agg[it["sku"]] = agg.get(it["sku"], 0) + it["quantity"]` with `agg[it["sku"]] = it["quantity"]`. Rerun the test and capture the assertion failure: the buggy code keeps only the last quantity instead of adding `2 + 3`. Restore the original line and rerun the same command to capture the pass.

```powershell
.venv\Scripts\python.exe -m pytest tests/regression/test_red_to_green.py -v
```

- **Failing run:** Evidence pending.
- **Passing run after restoring the fix:** Evidence pending.
- **GitHub Actions:** Add the run link when CI passes.
