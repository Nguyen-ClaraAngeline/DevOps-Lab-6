# FulfillOps test evidence

Part 4 verifies input validation, order acceptance, stock reservation under concurrent requests, and worker job claiming. On 14 November 2026, the full local suite passed **53 tests** against isolated PostgreSQL 16 with `httpx2`. Ruff and the formatting check also passed.

| Test layer | What it checks | Command (activated venv) | Result in full suite |
| --- | --- | --- | --- |
| [Unit](unit/) | Request validation, duplicate SKU normalization, and order totals. | `python -m pytest tests/unit -q` | 41 passed |
| [Integration](integration/) | API health and readiness, transactional reservation and rollback, and concurrent worker claims. | `python -m pytest tests/integration -q` | 9 passed |
| [Distinct-key race](race/test_concurrent_distinct_keys_cannot_oversell.py) | Twelve requests compete for seven units. Seven succeed, five return `OUT_OF_STOCK`, and stock reaches zero. Only accepted order IDs have order and job rows. | `python -m pytest tests/race/test_concurrent_distinct_keys_cannot_oversell.py -q` | 1 passed |
| [Same-key race](race/test_race_same_key.py) | Eight identical requests return one order ID, reserve one unit, and create one order and one job. | `python -m pytest tests/race/test_race_same_key.py -q` | 1 passed |
| [Regression](regression/test_red_to_green.py) | Duplicate SKU lines are combined before reserving stock and calculating the total. | `python -m pytest tests/regression/test_red_to_green.py -q` | 1 passed |

Both race tests use one API instance. Part 5 covers cross-replica behavior.

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

- **Failing local run:** `1 failed`. The test expected `6495` cents for five units and got `3897` cents for three units (`assert 3897 == 6495`).
- **Passing local run after restoring the fix:** `1 passed`. The deliberate bug was run in a temporary copy and was not committed.
- **GitHub Actions:** These results are local. The task breakdown also calls for failing and passing CI run links; add them once those runs are captured.
