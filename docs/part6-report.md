# Part 6 Containers and Compose

The API and worker use multi-stage Dockerfiles pinned to the same Python 3.12.16 base image digest. Both run as UID `10001`. Compose starts PostgreSQL with a named volume, runs migrations once per database version, and waits for API and worker health checks. The service build contexts have their own `.dockerignore` files.

In the [isolated verification run](evidence/part6-compose.txt), both images built without cache. PostgreSQL, the API, and the worker became healthy, and the migration service exited with code 0. We applied `db/seed.sql` manually because the automatic catalog seed migration was not on this branch. We created a one-unit order and waited for it to complete. After `docker compose down` without `-v` and `docker compose up -d --wait`, the same order ID was still `completed` with the same total and items. We removed the disposable test volume after verification.

| Image | Naive single stage (bytes) | Multi-stage (bytes) | Difference |
| --- | ---: | ---: | ---: |
| API | 274,712,566 | 279,095,992 | +1.6% |
| Worker | 217,386,396 | 221,771,788 | +2.0% |

Both variants used the same pinned slim Python base and dependency lists. The naive baseline installed dependencies directly and copied its full service build context. The multi-stage build copied its virtual environment into the runtime image. Docker's `image inspect .Size` measurement showed no size reduction with this baseline; the runtime separation and non-root user are the practical benefits.
