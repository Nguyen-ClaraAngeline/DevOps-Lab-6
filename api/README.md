# FulfillOps API

The API serves the catalog and inventory, accepts orders, and reserves stock in PostgreSQL. It stores the order and its job in the same transaction. This milestone covers order acceptance; a separate worker will complete queued orders.

## Run the API locally

Use a disposable PostgreSQL 16 database. Follow the schema verification and seed steps in the [project README](../README.md). To let the API reach the review container from your machine, add `-p 127.0.0.1:15432:5432` to its `docker run` command before starting it. Keep the container running during the API checks.

Run the following from the repository root with Python 3.12.

### Windows Command Prompt (CMD)

```cmd
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r api\requirements.txt
set "DATABASE_URL=postgresql://postgres:review-only@127.0.0.1:15432/fulfillops_review"
.venv\Scripts\python.exe -m uvicorn --app-dir api/app main:app --host 127.0.0.1 --port 8080
```

### Linux and macOS (Bash or Zsh)

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r api/requirements.txt
export DATABASE_URL='postgresql://postgres:review-only@127.0.0.1:15432/fulfillops_review'
.venv/bin/python -m uvicorn --app-dir api/app main:app --host 127.0.0.1 --port 8080
```

## Verify order acceptance

From a second terminal, check the API and note the starting stock. Use `curl.exe` if your Windows shell aliases `curl`.

```text
curl -fsS http://127.0.0.1:8080/health/live
curl -fsS http://127.0.0.1:8080/health/ready
curl -fsS http://127.0.0.1:8080/metrics
curl -fsS http://127.0.0.1:8080/api/v1/inventory/KIT-100
```

All four requests should return HTTP 200. In Windows CMD, submit the same request twice:

```cmd
curl -i -H "Content-Type: application/json" -H "Idempotency-Key: readme-review-001" --data "{\"customer_id\":\"CUST-042\",\"items\":[{\"sku\":\"KIT-100\",\"quantity\":1}]}" http://127.0.0.1:8080/api/v1/orders
```

In Bash or Zsh, use the same request with shell quoting:

```sh
curl -i -H 'Content-Type: application/json' -H 'Idempotency-Key: readme-review-001' --data '{"customer_id":"CUST-042","items":[{"sku":"KIT-100","quantity":1}]}' http://127.0.0.1:8080/api/v1/orders
```

Both submissions should return HTTP 202 with the same `order_id` and `status: queued`. Check inventory again: stock should have decreased by exactly one. On a reused database, choose a fresh key for each new pair of submissions.

Stop Uvicorn with Ctrl+C and remove the disposable database with `docker stop fulfillops-schema-review`. Run the full public checker only after the worker is integrated, against a fresh isolated database.
