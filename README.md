# FulfillOps

FulfillOps is a DevOps capstone about reliably processing orders for a fictional electronics fulfilment business. The API is designed to accept an order, reserve inventory, and enqueue work in one PostgreSQL transaction. A separate worker processes the order. Repeating a request with the same idempotency key must return the original order ID without reserving stock again.

**Current status:** The initial PostgreSQL schema, seed data, and architecture documents are in place. The API, worker, automated tests, Compose stack, CI, and deployment files are still being developed. The database checks below can be run independently of those components.

## Project structure

| Path | Purpose |
| --- | --- |
| [`docs/`](docs/) | [API contract](docs/API_CONTRACT_EN.md), [architecture](docs/architecture.md), [design decisions](docs/ADR-001.md), and [threat model](docs/threat-model.md). |
| [`db/`](db/) | SQL migrations, Bash migration runner, and a separate catalog seed script. |
| [`api/`](api/) and [`worker/`](worker/) | HTTP service and background processor. |
| [`tests/`](tests/) | Team-owned unit, integration, race, and regression tests. |
| [`assessment/`](assessment/) | Supplied public API checker and rollout probe. |
| [`scripts/`](scripts/) | Local verification and failure drills. |
| [`compose.yaml`](compose.yaml) and [`.github/workflows/`](.github/workflows/) | Local container stack and CI workflows. |
| [`infra/`](infra/) | kind, Kubernetes, and Argo CD configuration. |

## How to verify the database setup

Start Docker and open a terminal in the repository root. Use the command for your platform to start a disposable PostgreSQL database with no published port, then follow the shared verification steps below.

### Windows Command Prompt (CMD)

Use `cmd.exe` and make sure Docker Desktop is in Linux container mode.

```cmd
docker run -d --rm --name fulfillops-schema-review -e POSTGRES_PASSWORD=review-only -e POSTGRES_DB=fulfillops_review -v "%CD%\db:/review/db:ro" postgres:16
```

### Linux and macOS (Bash or Zsh)

```sh
docker run -d --rm --name fulfillops-schema-review -e POSTGRES_PASSWORD=review-only -e POSTGRES_DB=fulfillops_review -v "$PWD/db:/review/db:ro" postgres:16
```

### Verify the schema and seed data (all platforms)

```text
docker exec fulfillops-schema-review pg_isready -h 127.0.0.1 -U postgres -d fulfillops_review
```

If `pg_isready` reports `no response`, retry until it reports `accepting connections`. Run migrations once, then seed the catalog separately:

```text
docker exec -e DATABASE_URL=postgresql://postgres:review-only@127.0.0.1:5432/fulfillops_review fulfillops-schema-review bash /review/db/migrate.sh
docker exec fulfillops-schema-review psql -U postgres -d fulfillops_review -v ON_ERROR_STOP=1 -f /review/db/seed.sql
docker exec fulfillops-schema-review psql -U postgres -d fulfillops_review -v ON_ERROR_STOP=1 -c "\dt" -c "SELECT sku, unit_price_cents, available FROM products ORDER BY sku;"
```

Expect the `products`, `orders`, `order_items`, `idempotency_keys`, `jobs`, and `schema_migrations` tables. The initial catalog should match the contract:

| SKU | Price (cents) | Available |
| --- | ---: | ---: |
| `KIT-100` | 1299 | 7 |
| `PACK-300` | 249 | 5 |
| `PART-200` | 599 | 12 |

Check that rerunning the seed preserves inventory changes. In this disposable database, set `KIT-100` stock to `6`, run the seed again, and verify that it stays at `6`:

```text
docker exec fulfillops-schema-review psql -U postgres -d fulfillops_review -v ON_ERROR_STOP=1 -c "UPDATE products SET available = 6 WHERE sku = 'KIT-100';" -f /review/db/seed.sql -c "SELECT sku, available FROM products WHERE sku = 'KIT-100';"
```

Remove the review container and its disposable data when finished:

```text
docker stop fulfillops-schema-review
```

## Planned application checks

Once Compose and the application are implemented, start the stack, check readiness, and run the supplied checker from Windows CMD:

```cmd
docker compose up -d --build
curl.exe -fsS http://localhost:8080/health/ready
py -3 assessment\fulfillops_public_checker.py --base-url http://localhost:8080 --concurrency --stress
docker compose down
```

Run the checker only against a **fresh, isolated test database**: it creates orders and consumes inventory. The final target is **15 passed, 0 failed, 0 skipped**. The checker supplements the team's own tests; it does not verify worker crash recovery or GitOps rollouts.
