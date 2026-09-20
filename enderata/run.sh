#!/usr/bin/env bash
set -euo pipefail

# NOT run-tested in this session (no Docker runtime available here) --
# verify the PostgreSQL init/start sequence on the target arch before
# relying on it. See DOCS.md "next steps".

PGDATA=/data/postgres
export PGDATA

if [ ! -s "${PGDATA}/PG_VERSION" ]; then
  echo "[enderata] Initialising PostgreSQL data directory..."
  mkdir -p "${PGDATA}"
  chown -R postgres:postgres "${PGDATA}"
  su postgres -c "/usr/lib/postgresql/*/bin/initdb -D ${PGDATA}"
fi

chown -R postgres:postgres "${PGDATA}"
su postgres -c "/usr/lib/postgresql/*/bin/pg_ctl -D ${PGDATA} -l /data/postgres.log -w start"

su postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname = 'enderata'\" | grep -q 1 || createdb enderata"
su postgres -c "psql -d enderata -c 'CREATE EXTENSION IF NOT EXISTS postgis;'"

export DATABASE_URL="postgresql://postgres@localhost:5432/enderata"
export ENDERATA_VIEWER_DIR=/app/viewer
export ENDERATA_DATA_DIR=/data/export
export PORT=8000

mkdir -p "${ENDERATA_DATA_DIR}"

echo "[enderata] Starting viewer server on :${PORT}..."
exec python3 -m enderata.viz.server
