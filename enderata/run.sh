#!/usr/bin/env bash
set -euo pipefail

# NOT run-tested on real HA hardware yet beyond the Postgres init below --
# verify the rest of this sequence before relying on it. See DOCS.md.

OPTIONS_FILE=/data/options.json
if [ -f "${OPTIONS_FILE}" ]; then
  export COUNTRY_CODE="$(jq -r '.country_code // "AO"' "${OPTIONS_FILE}")"
  export DISTRICT_CODE="$(jq -r '.district_code // "LUA"' "${OPTIONS_FILE}")"
  export AOI_DISTRICT="$(jq -r '.aoi_district // "luanda"' "${OPTIONS_FILE}")"
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

# Debian's postgres binaries default to /var/run/postgresql for the
# unix socket (baked in at compile time); we're running initdb/pg_ctl
# by hand instead of through Debian's pg_createcluster wrapper, so
# nothing else creates that directory for us.
mkdir -p /var/run/postgresql
chown postgres:postgres /var/run/postgresql

# Log file must live under PGDATA -- that's the only path chowned to
# postgres; /data itself is root-owned (permission denied writing
# /data/postgres.log directly, seen on a real HA run).
su postgres -c "/usr/lib/postgresql/*/bin/pg_ctl -D ${PGDATA} -l ${PGDATA}/postgres.log -w start"

su postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname = 'enderata'\" | grep -q 1 || createdb enderata"
su postgres -c "psql -d enderata -c 'CREATE EXTENSION IF NOT EXISTS postgis;'"

export DATABASE_URL="postgresql://postgres@localhost:5432/enderata"
export ENDERATA_VIEWER_DIR=/app/viewer
export ENDERATA_DATA_DIR=/data/export
export PORT=8000

# The nationwide basemap (tiles/angola.mbtiles, 154MB) exceeds GitHub's
# 100MB file size limit, so it isn't baked into the Docker image via
# the Dockerfile's `COPY tiles ./tiles` -- it's deployed straight into
# this add-on's persistent /data (host-writable, survives restarts and
# add-on updates) instead. See tiles/README.md "Deployment" section.
if [ -f /data/tiles/angola.mbtiles ]; then
  export ENDERATA_MBTILES_PATH=/data/tiles/angola.mbtiles
fi

mkdir -p "${ENDERATA_DATA_DIR}"

echo "[enderata] Starting viewer server on :${PORT}..."
exec python3 -m enderata.viz.server
