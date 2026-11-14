# FulfillOps live demo (Windows CMD)

Stay on **main**. The live demo shows the working application: the API accepts an order and reserves stock, and a separate worker completes it. Use Docker Compose for this demo. No branch changes, Kubernetes setup, or deliberate failures are needed.

## 1. Start the stack before presenting

Start Docker Desktop in Linux container mode. Open **Command Prompt** in the repository root. Run the first two setup commands once. If a local .env already exists, keep it and make sure it is configured for this demo stack.

~~~cmd
if not exist .env copy .env.example .env
notepad .env
~~~

For a new .env, replace CHANGE_ME with a throwaway alphanumeric password and save. Leave POSTGRES_USER and POSTGRES_DB at their defaults unless you already use different values for this stack. Use the same password on subsequent runs with the same volume.

~~~cmd
set "TEST_MODE=0"
docker compose -p fulfillops-demo up -d --build --wait
docker compose -p fulfillops-demo ps
~~~

The API, worker, and database should be healthy. The migration container finishing with exit code 0 is expected; use docker compose -p fulfillops-demo ps -a if you want to show it. If a different stack already occupies port 8080 or 5432, stop that stack before starting the demo. The demo has a separate database volume; a fresh one is seeded automatically.

## 2. Show that the API works

Use the same CMD window throughout so the variables stay available.

~~~cmd
curl -i "http://localhost:8080/health/ready"
curl -i "http://localhost:8080/api/v1/catalog"
~~~

Read the starting stock aloud. On a fresh demo database, KIT-100 starts at 7. If you rehearsed on the same volume, it may be lower; make sure at least one is available.

## 3. Place an order and show the worker complete it

~~~cmd
set "ORDER_KEY=demo-%RANDOM%-%RANDOM%"
curl -i -H "Content-Type: application/json" -H "Idempotency-Key: %ORDER_KEY%" --data "{\"customer_id\":\"DEMO-001\",\"items\":[{\"sku\":\"KIT-100\",\"quantity\":1}]}" "http://localhost:8080/api/v1/orders"
~~~

Expect HTTP **202 Accepted** and an order ID. Copy that ID into the command below. If the status is still queued or processing, repeat the lookup after a moment. Once it is completed, show the stock again: it should be down by one.

~~~cmd
set "ORDER_ID=PASTE_ORDER_ID_HERE"
curl -i "http://localhost:8080/api/v1/orders/%ORDER_ID%"
curl -i "http://localhost:8080/api/v1/inventory/KIT-100"
~~~

**What to say:** “The API reserves stock and queues the job in PostgreSQL in one transaction. It returns an order ID immediately after accepting it. The worker picks up the job separately; this status lookup shows it reached completed.”

## Optional: replay the same request

If you have time, run the POST again with the **same key and body**. Do not rerun the line that generates ORDER_KEY.

~~~cmd
curl -i -H "Content-Type: application/json" -H "Idempotency-Key: %ORDER_KEY%" --data "{\"customer_id\":\"DEMO-001\",\"items\":[{\"sku\":\"KIT-100\",\"quantity\":1}]}" "http://localhost:8080/api/v1/orders"
curl -i "http://localhost:8080/api/v1/inventory/KIT-100"
~~~

Expect the same order ID and no further stock decrease. The POST can still say queued because it replays the acceptance receipt; the GET order endpoint shows the current status.

## Run the tests

### Public checker (end-to-end)

Run this from the repository root in CMD. It creates orders and consumes inventory, so use a **fresh checker stack** separate from the demo stack. Run one block at a time and check that startup succeeds before launching the checker. No Python venv is needed.

~~~cmd
docker compose -p fulfillops-demo down
docker compose -p fulfillops-check up -d --build --wait
docker compose -p fulfillops-check exec -T api python - --base-url http://localhost:8080 --concurrency --stress < assessment\fulfillops_public_checker.py
~~~

Expected: **15 passed / 0 failed / 0 skipped**. Afterward, remove the checker stack and its disposable volume so the next checker run starts fresh. Then restart the demo stack with its own data.

~~~cmd
docker compose -p fulfillops-check down --volumes
docker compose -p fulfillops-demo up -d --wait
~~~

### Team pytest suite (53 tests)

Use your existing .venv. If it is missing, create it with py -3.12 -m venv .venv. The commands below activate it in CMD. The suite uses a separate PostgreSQL container on port 15432 and resets its test data.

~~~cmd
pip install -r requirements-dev.txt
docker run -d --rm --name fulfillops-pytest -p 127.0.0.1:15432:5432 -e POSTGRES_USER=ci -e POSTGRES_PASSWORD=ci-throwaway -e POSTGRES_DB=fulfillops_test -v "%CD%\db\migrations:/migrations:ro" -v "%CD%\db\migrate.sh:/migrate.sh:ro" postgres:16
docker exec fulfillops-pytest pg_isready -h 127.0.0.1 -U ci -d fulfillops_test
~~~

Wait for accepting connections (repeat pg_isready if needed), then run:

~~~cmd
docker exec -e PGHOST=127.0.0.1 -e PGUSER=ci -e PGPASSWORD=ci-throwaway -e PGDATABASE=fulfillops_test fulfillops-pytest sh /migrate.sh
set "TEST_DATABASE_URL=postgresql://ci:ci-throwaway@127.0.0.1:15432/fulfillops_test"
python -m pytest tests


python -m pytest tests/regression
python -m pytest tests/unit
python -m pytest tests/integration
python -m pytest tests/race
~~~

## If something does not work

~~~cmd
docker compose -p fulfillops-demo ps -a
docker compose -p fulfillops-demo logs --tail=50 db migrate api worker
~~~

If asked about failures, explain the design and show the recorded [worker recovery evidence](part5-report.md) or [rollout and rollback evidence](part9-report.md). Those are backup material, not live demo steps.

After the presentation, stop the stack while keeping its data:

~~~cmd
docker compose -p fulfillops-demo down
~~~
