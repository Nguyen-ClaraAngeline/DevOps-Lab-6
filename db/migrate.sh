#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 -c "CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());"
for f in /migrations/*.sql; do
  v=$(basename "$f" | cut -d_ -f1 | cut -d. -f1)
  if [ "$(psql -tAc "SELECT 1 FROM schema_migrations WHERE version='$v'")" = "1" ]; then
    echo "skip $v"
  else
    echo "apply $v"
    psql -v ON_ERROR_STOP=1 --single-transaction -f "$f" -c "INSERT INTO schema_migrations(version) VALUES ('$v')"
  fi
done