#!/bin/sh
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is required. Add a Railway PostgreSQL service and reference its DATABASE_URL variable." >&2
  exit 1
fi

# Apply committed Drizzle migrations before the API accepts requests. This
# is idempotent on every restart and creates the tables in a fresh Railway DB.
pnpm --filter @workspace/db exec drizzle-kit migrate --config ./drizzle.config.ts

exec node artifacts/api-server/dist/index.mjs