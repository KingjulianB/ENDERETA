#!/usr/bin/env bash
set -euo pipefail

# NOT run-tested on real HA hardware yet beyond the Postgres init below --
# verify the rest of this sequence before relying on it. See DOCS.md.

OPTIONS_FILE=/data/options.json
if [ -f "${OPTIONS_FILE}" ]; then
  export COUNTRY_CODE="$(jq -r '.country_code // "AO"' "${OPTIONS_FILE}")"
  export DISTRICT_CODE="$(jq -r '.district_code // "HUA"' "${OPTIONS_FILE}")"
  export AOI_DISTRICT="$(jq -r '.aoi_district // "huambo"' "${OPTIONS_FILE}")"
fi

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
