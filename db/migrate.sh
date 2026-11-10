#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/migrations"
PSQL=(psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -X -q -t -A)

"${PSQL[@]}" -c "CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);"

applied=0
for f in "$DIR"/*.sql; do
    version="$(basename "$f" .sql)"
    out="$({
        echo "BEGIN;"
        echo "SELECT pg_advisory_xact_lock(727001);"
        echo "SELECT 'APPLIED' WHERE EXISTS (SELECT 1 FROM schema_migrations WHERE version = '$version');"
        echo "COMMIT;"
    } | "${PSQL[@]}")"
    if [[ "$out" == *APPLIED* ]]; then
        echo "skip   $version (already applied)"
        continue
    fi
    {
        echo "BEGIN;"
        echo "SELECT pg_advisory_xact_lock(727001);"
        cat "$f"
        echo "INSERT INTO schema_migrations (version) VALUES ('$version') ON CONFLICT DO NOTHING;"
        echo "COMMIT;"
    } | "${PSQL[@]}" >/dev/null
    echo "apply  $version"
    applied=$((applied + 1))
done
echo "migrations done ($applied applied)"